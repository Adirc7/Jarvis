"""Shared state from the implementation plan (section 4), kept in one place.

Rule: only code running on the asyncio loop thread mutates this object.
Producer threads never touch it; they publish events instead.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    GESTURE = "gesture"       # gesture mode owns the mouse; agent actions pause
    PAUSED = "paused"         # after the kill switch: nothing acts until resumed


@dataclass
class SharedState:
    language: str = "en"
    empathy: str = "balanced"     # emotional style: logical, balanced, supportive
    mode: Mode = Mode.IDLE
    current_task: str | None = None
    active_app: str | None = None
    selected_object: str | None = None
    pending_action: str | None = None
    awaiting_confirmation: bool = False
    last_observation_time: float = field(default_factory=time.monotonic)
    # Bumped by the kill switch (and by barge-in later). Any work started under
    # an older generation must stop as soon as it notices.
    cancel_generation: int = 0

    def token(self) -> "CancelToken":
        return CancelToken(self, self.cancel_generation)

    def cancel_all(self) -> int:
        self.cancel_generation += 1
        return self.cancel_generation


class CancelToken:
    """Captures the generation at the start of a piece of work.

    Long-running work (streaming a reply, speaking, a multi-step tool chain)
    checks `token.cancelled` between steps and stops when it turns True.
    """

    def __init__(self, state: SharedState, generation: int):
        self._state = state
        self.generation = generation

    @property
    def cancelled(self) -> bool:
        return self._state.cancel_generation != self.generation
