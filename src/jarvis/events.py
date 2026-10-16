"""Typed events that travel over the event bus.

Producers (mic, camera, OS watcher) create events; consumers (agent, speech,
telemetry) subscribe to the types they care about. Subscribing to `Event`
receives everything.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    ts: float = field(default_factory=time.monotonic, kw_only=True)

    @property
    def kind(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class UserText(Event):
    """What the user said or typed, after speech-to-text."""
    text: str
    language: str                   # language code Jarvis used to transcribe
    detected_language: str | None = None
    detected_probability: float | None = None
    source: str = "voice"           # "voice" or "keyboard"


@dataclass(frozen=True)
class GestureEvent(Event):
    name: str                       # "point", "pinch_start", "pinch_end", "open_palm", ...
    x: float                        # normalised 0..1 screen coordinates
    y: float
    confidence: float = 1.0


@dataclass(frozen=True)
class OSEvent(Event):
    name: str                       # "window_focus", "file_created", ...
    detail: str = ""


@dataclass(frozen=True)
class SpeakRequest(Event):
    text: str
    language: str
    priority: int = 0               # higher interrupts lower
    generation: int = 0             # cancel generation it belongs to


@dataclass(frozen=True)
class LanguageChanged(Event):
    old: str
    new: str
    source: str                     # "voice_command", "hotkey", "ui", "llm_tool", "auto"


@dataclass(frozen=True)
class KillSwitchPressed(Event):
    source: str = "hotkey"


@dataclass(frozen=True)
class Shutdown(Event):
    reason: str = ""
