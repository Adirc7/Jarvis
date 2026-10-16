"""Global kill switch: one hotkey that stops everything, from any app.

Built in Phase 0 on purpose. Every later module (speech, gestures, tools) checks
a CancelToken, so the kill switch keeps working as features are added.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from .bus import EventBus
from .events import KillSwitchPressed


class HotkeyListener:
    """Runs pynput's global hotkey listener in its own thread.

    pynput is imported lazily so the rest of Jarvis (and the tests) work on
    machines without a display.
    """

    def __init__(self, bindings: dict[str, Callable[[], None]]):
        self._bindings = bindings
        self._listener = None

    def start(self) -> None:
        from pynput import keyboard  # lazy import

        self._listener = keyboard.GlobalHotKeys(self._bindings)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None


def kill_switch_binding(bus: EventBus, source: str = "hotkey") -> Callable[[], None]:
    """Callback for the listener thread: hands the press to the asyncio loop."""
    def _pressed() -> None:
        bus.publish_threadsafe(KillSwitchPressed(source=source))
    return _pressed


class Once:
    """Debounce helper: hotkeys can fire several times while held down."""

    def __init__(self, fn: Callable[[], None], min_interval_s: float = 0.5):
        self._fn = fn
        self._min = min_interval_s
        self._last = -1e9
        self._lock = threading.Lock()

    def __call__(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now - self._last < self._min:
                return
            self._last = now
        self._fn()
