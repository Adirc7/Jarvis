"""Greet like a person: once per session, not every time Jarvis starts.

    first time today                -> a full greeting for the time of day
    back after a break              -> a short pick-up ("Welcome back, sir.")
    back within the same session    -> no greeting, just "I'm here, sir."

"Same session" means you last talked to Jarvis less than
[greeting].same_session_minutes ago (15 by default). When that was, and the
date of the last full greeting, are kept in state/presence.json (not
committed), so the rules hold across restarts. Later the wake word uses the
same rules.

The lines themselves live in config/languages.toml under [<code>.greetings].
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

FULL, PICKUP, SAME_SESSION = "full", "pickup", "same_session"


def part_of_day(hour: int) -> str:
    """morning 5-12, afternoon 12-17, evening 17-21, night otherwise."""
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def greeting_kind(now: datetime, last_active: datetime | None, last_full: date | None,
                  same_session_minutes: float = 15) -> str:
    """Which kind of greeting fits, from when you last talked to Jarvis."""
    if last_active is not None and timedelta(0) <= now - last_active <= timedelta(minutes=same_session_minutes):
        return SAME_SESSION          # carry on; this also holds across midnight
    if last_full != now.date():
        return FULL                  # first time today
    return PICKUP


def fill(template: str, address: str) -> str:
    """Put the form of address in, or remove it cleanly when there is none."""
    if address:
        return template.replace("{address}", address)
    text = re.sub(r",?[ \t]*\{address\}", "", template)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


@dataclass
class Presence:
    """When you last talked to Jarvis, and when it last greeted you fully."""

    path: Path | None = None
    last_active: datetime | None = None
    last_full: date | None = None

    @classmethod
    def load(cls, path: Path | None) -> "Presence":
        if path is None or not path.is_file():
            return cls(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            last_active = datetime.fromisoformat(raw["last_active"]) if raw.get("last_active") else None
            last_full = date.fromisoformat(raw["last_full"]) if raw.get("last_full") else None
            return cls(path, last_active, last_full)
        except (OSError, ValueError, TypeError, KeyError):
            return cls(path)          # a damaged file just means "no history"

    def touch(self, now: datetime | None = None) -> None:
        self.last_active = now or datetime.now()

    def save(self) -> None:
        if self.path is None:
            return
        data = {
            "last_active": self.last_active.isoformat(timespec="seconds") if self.last_active else None,
            "last_full": self.last_full.isoformat() if self.last_full else None,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass                      # remembering is a nicety, never a reason to crash


class Greeter:
    """Picks a line for the kind of greeting, never the same one twice in a row."""

    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._last: str | None = None

    def pick(self, kind: str, now: datetime, greetings: dict[str, tuple[str, ...]], address: str = "") -> str | None:
        key = part_of_day(now.hour) if kind == FULL else kind
        lines = list(greetings.get(key, ()))
        if not lines:
            return None
        choices = [line for line in lines if line != self._last] or lines
        line = self._rng.choice(choices)
        self._last = line
        return fill(line, address)
