"""What a tool is, and the list of tools Jarvis may use (Phase 2, ROADMAP "The pieces").

A tool declares its name, a description and parameters (the JSON schema the
model sees), a risk tier, how to run it, a verify() that checks the real
result afterwards, and an undo() when it can be reversed. Only tools in the
Registry can run, and only through the gate (tools/gate.py).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Tier(Enum):
    """How careful to be (ROADMAP "Risk tiers")."""

    JUST_DO = "just do it"          # open an app, search, read, list, time and battery
    DO_AND_LOG = "do and log"       # create, move, rename, copy: logged, "undo that" reverses it
    ASK_FIRST = "ask first"         # delete, send, install, run code, change a setting: only a click confirms
    NEVER = "never"                 # system folders, administrator rights, a raw shell: not available at all


@dataclass
class Result:
    """What a tool did. `summary` is said to Adhi; `undo_data` is whatever undo() needs."""

    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    undo_data: Any = None


Args = dict[str, Any]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]                       # JSON schema of an object
    tier: Tier
    run: Callable[[Args], Result]
    verify: Callable[[Args, Result], bool] | None = None
    undo: Callable[[Args, Result], Result] | None = None
    path_params: tuple[str, ...] = ()               # arguments that are file paths: must be in allowed folders
    describe: Callable[[Args], str] | None = None   # the confirm box's words, written by code from the arguments

    def spec(self) -> dict[str, Any]:
        """The OpenAI-style function definition the model sees."""
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}

    def what_it_will_do(self, args: Args) -> str:
        """Exactly what will happen, for the confirm box: never words from the model."""
        if self.describe:
            return self.describe(args)
        shown = ", ".join(f"{k} = {v!r}" for k, v in sorted(args.items()))
        return f"{self.name}({shown})"


class Registry:
    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name!r} registered twice")
        if tool.parameters.get("type") != "object":
            raise ValueError(f"tool {tool.name!r}: parameters must be a JSON schema of type object")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[dict[str, Any]]:
        """What the model is offered: every tool except the 'never' ones."""
        return [t.spec() for t in self._tools.values() if t.tier is not Tier.NEVER]

    def names(self) -> list[str]:
        return list(self._tools)
