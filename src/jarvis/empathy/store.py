"""The empathy learner's memory: good and bad counts per mode, and the log of every feedback.

    state/empathy.json         {"counts": {"all": {"balanced": {"good": 3.0, "bad": 1.5}, ...}}}
    state/empathy-log.jsonl    one line per feedback: when, mode, reward, weight, why, context

Weights make the counts fractional (an interruption adds 0.5 to "bad").
Only labels and counts are kept, never what you said.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .signals import Feedback


class EmpathyStore:
    def __init__(self, path: Path | None, counts: dict[str, dict[str, dict[str, float]]] | None = None):
        self.path = path
        self.counts = counts or {}

    @classmethod
    def load(cls, path: Path | None) -> EmpathyStore:
        if path is None or not path.is_file():
            return cls(path)
        try:
            return cls(path, json.loads(path.read_text(encoding="utf-8")).get("counts", {}))
        except (OSError, ValueError, AttributeError):
            return cls(path)

    def for_context(self, context: str = "all") -> dict[str, tuple[float, float]]:
        """{mode: (good, bad)} for one context."""
        return {m: (c.get("good", 0.0), c.get("bad", 0.0)) for m, c in self.counts.get(context, {}).items()}

    def add(self, fb: Feedback, now: datetime | None = None) -> None:
        cell = self.counts.setdefault(fb.context, {}).setdefault(fb.mode, {"good": 0.0, "bad": 0.0})
        cell["good" if fb.reward >= 0.5 else "bad"] += fb.weight
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        when = (now or datetime.now()).isoformat(timespec="seconds")  # noqa: DTZ005 - local, like the logs
        with self.path.with_name("empathy-log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": when, **asdict(fb)}) + "\n")

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"counts": self.counts}, indent=1), encoding="utf-8")

    def forget(self) -> None:
        self.counts = {}
        self.save()
