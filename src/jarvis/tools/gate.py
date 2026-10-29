"""The gate: every tool call from the model goes through here (Phase 2, ROADMAP "How one action flows").

    1. the model proposes a call (a tool name and JSON arguments)
    2. the gate checks it: a registered tool, not "never", arguments valid
       against the tool's schema, every path inside an allowed folder
    3. if the tier says so (or the turn holds untrusted text, or the request
       came from the phone), Jarvis asks, and only a click confirms
    4. the tool runs, unless the kill switch was pressed
    5. verify(): the tool checks the real result
    6. the action log records it; reversible actions can be undone
    7. Jarvis says what it verified, or plainly that it couldn't confirm it

The model's text never reaches the confirm box: its words come from the
tool's own describe(), built from the checked arguments.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .registry import Args, Registry, Result, Tier, Tool

# confirm(tool, args, what_it_will_do) -> True only when Adhi clicked the action button
Confirm = Callable[[Tool, Args, str], bool]


# ---- arguments -------------------------------------------------------------------
def schema_problems(value: Any, schema: dict[str, Any], where: str = "arguments") -> list[str]:
    """The ways `value` breaks `schema` (a small part of JSON schema: enough for tool parameters).

    Unknown properties are refused unless the schema says additionalProperties: true.
    """
    kind = schema.get("type")
    checks = {"object": dict, "array": list, "string": str, "boolean": bool}
    if kind in checks and not isinstance(value, checks[kind]):
        return [f"{where} should be {kind}"]
    if kind == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
        return [f"{where} should be a whole number"]
    if kind == "number" and (isinstance(value, bool) or not isinstance(value, int | float)):
        return [f"{where} should be a number"]
    problems: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{where} should be one of {schema['enum']}")
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{where} is below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{where} is above {schema['maximum']}")
    if isinstance(value, str):
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problems.append(f"{where} is longer than {schema['maxLength']} characters")
        if "minLength" in schema and len(value) < schema["minLength"]:
            problems.append(f"{where} is shorter than {schema['minLength']} characters")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            problems.append(f"{where} doesn't match {schema['pattern']}")
    if kind == "array":
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            problems.append(f"{where} has more than {schema['maxItems']} items")
        if "minItems" in schema and len(value) < schema["minItems"]:
            problems.append(f"{where} has fewer than {schema['minItems']} items")
        for i, item in enumerate(value):
            problems += schema_problems(item, schema.get("items", {}), f"{where}[{i}]")
    if kind == "object":
        props = schema.get("properties", {})
        problems += [f"{where} is missing {name!r}" for name in schema.get("required", []) if name not in value]
        if not schema.get("additionalProperties", False):
            problems += [f"{where} has an unknown {name!r}" for name in value if name not in props]
        for name, item in value.items():
            if name in props:
                problems += schema_problems(item, props[name], name)
    return problems


def inside(path: Path, folders: list[Path]) -> bool:
    """True when `path`, with `..` and links resolved, is inside one of `folders`."""
    real = path.resolve()
    return any(real == f or real.is_relative_to(f) for f in folders)


# ---- the action log ----------------------------------------------------------------
class ActionLog:
    """logs/actions-YYYYMMDD.jsonl: time, tool, arguments, tier, decision, who confirmed, result, verify."""

    def __init__(self, folder: Path | None):
        self.folder = folder

    def write(self, **entry: Any) -> None:
        if self.folder is None:
            return
        entry = {"time": datetime.now().isoformat(timespec="seconds"), **entry}  # noqa: DTZ005 - local time
        if "args" in entry:
            entry["args"] = {k: (v[:200] + "...") if isinstance(v, str) and len(v) > 200 else v
                             for k, v in entry["args"].items()}
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"actions-{datetime.now():%Y%m%d}.jsonl"  # noqa: DTZ005
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


# ---- the gate ------------------------------------------------------------------------
@dataclass
class Outcome:
    """What happened to one call, and what Jarvis says about it."""

    status: str              # "done", "claimed" (no check exists), "unconfirmed" (check failed),
                             # "failed", "refused", "cancelled"
    text: str
    tool: str = ""
    result: Result | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def acted(self) -> bool:
        return self.status in ("done", "claimed", "unconfirmed")


class Gate:
    def __init__(self, registry: Registry, allowed_folders: list[Path | str], log: ActionLog | None = None,
                 confirm: Confirm | None = None, stopped: Callable[[], bool] = lambda: False):
        self.registry = registry
        self.folders = [Path(f).expanduser().resolve() for f in allowed_folders]
        self.log = log or ActionLog(None)
        self.confirm = confirm          # None: nothing can confirm, so "ask first" never runs
        self.stopped = stopped          # the kill switch
        self.last_undoable: tuple[Tool, Args, Result] | None = None

    def _refuse(self, name: str, reasons: list[str], args: Args | None = None) -> Outcome:
        self.log.write(tool=name, args=args or {}, decision="refused", reasons=reasons)
        return Outcome("refused", "I can't do that one.", name, reasons=reasons)

    def _path_problems(self, tool: Tool, args: Args) -> list[str]:
        problems = []
        for name in tool.path_params:
            if name not in args:
                continue
            raw = Path(str(args[name])).expanduser()
            path = raw if raw.is_absolute() or not self.folders else self.folders[0] / raw
            if not inside(path, self.folders):
                problems.append(f"{name} is outside the folders Jarvis may use")
            else:
                args[name] = str(path.resolve())         # the tool gets the checked, resolved path
        return problems

    def call(self, name: str, arguments: str | Args = "{}", *, untrusted: bool = False,
             remote: bool = False) -> Outcome:
        """Check, maybe ask, run, verify and log one tool call."""
        tool = self.registry.get(name)
        if tool is None:
            return self._refuse(name, ["not a tool Jarvis has"])
        if tool.tier is Tier.NEVER:
            return self._refuse(name, ["never allowed"])
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments or "{}")
            except ValueError:
                return self._refuse(name, ["arguments aren't valid JSON"])
        else:
            args = dict(arguments)
        if not tool.parameters.get("properties") and isinstance(args, dict) and args:
            # A tool that takes nothing (undo, screenshot): models sometimes send
            # filler like {"action": {}}. The tool can't use it, so drop it.
            self.log.write(tool=name, args=args, decision="ignored_arguments")
            args = {}
        problems = schema_problems(args, tool.parameters)
        if problems:
            return self._refuse(name, problems, args if isinstance(args, dict) else {})
        problems = self._path_problems(tool, args)
        if problems:
            return self._refuse(name, problems, args)

        ask = tool.tier is Tier.ASK_FIRST or (tool.tier is Tier.DO_AND_LOG and (untrusted or remote))
        confirmed_by = None
        if ask:
            words = tool.what_it_will_do(args)
            if self.confirm is None or not self.confirm(tool, args, words):
                self.log.write(tool=name, args=args, tier=tool.tier.value, decision="cancelled", asked=words)
                return Outcome("cancelled", "Okay, I didn't do it.", name)
            confirmed_by = "click"
        if self.stopped():
            self.log.write(tool=name, args=args, tier=tool.tier.value, decision="stopped")
            return Outcome("cancelled", "Stopped.", name)

        start = time.perf_counter()
        try:
            result = tool.run(args)
        except Exception as exc:  # noqa: BLE001 - a broken tool must not break Jarvis; the log says why
            self.log.write(tool=name, args=args, tier=tool.tier.value, decision="ran", confirmed_by=confirmed_by,
                           ok=False, error=f"{type(exc).__name__}: {exc}"[:300])
            return Outcome("failed", "Sorry, that didn't work.", name, reasons=[type(exc).__name__])
        verified = None
        if result.ok and tool.verify:
            try:
                checked = tool.verify(args, result)       # None: this time it couldn't be measured
                verified = None if checked is None else bool(checked)
            except Exception:  # noqa: BLE001 - a check that crashes counts as not confirmed
                verified = False
        ms = round((time.perf_counter() - start) * 1000)
        self.log.write(tool=name, args=args, tier=tool.tier.value, decision="ran", confirmed_by=confirmed_by,
                       ok=result.ok, verified=verified, summary=result.summary, ms=ms)
        if not result.ok:
            return Outcome("failed", result.summary or "Sorry, that didn't work.", name, result)
        if tool.undo is not None:
            self.last_undoable = (tool, args, result)
        if verified is False:
            return Outcome("unconfirmed", f"I tried, but I couldn't confirm it: {result.summary}", name, result)
        return Outcome("done" if verified else "claimed", result.summary, name, result)

    def undo_last(self) -> Outcome:
        """"Undo that": reverse the last reversible action."""
        if self.last_undoable is None:
            return Outcome("refused", "There's nothing I can undo.", reasons=["nothing to undo"])
        tool, args, result = self.last_undoable
        self.last_undoable = None
        try:
            undone = tool.undo(args, result) if tool.undo else Result(False, "")
        except Exception as exc:  # noqa: BLE001
            self.log.write(tool=tool.name, args=args, decision="undo", ok=False, error=str(exc)[:300])
            return Outcome("failed", "Sorry, I couldn't undo that.", tool.name)
        self.log.write(tool=tool.name, args=args, decision="undo", ok=undone.ok, summary=undone.summary)
        return Outcome("done" if undone.ok else "failed", undone.summary, tool.name, undone)
