"""Plays synthesized audio chunks in order, and stops instantly when asked.

A background thread takes chunks from a queue and plays them one after another,
so sentence 2 can be synthesized while sentence 1 is playing. `stop()` empties
the queue and cuts off the current chunk: that is how the kill switch and
barge-in (pressing push-to-talk while Jarvis talks) silence it.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..state import CancelToken


class SoundDeviceBackend:
    """Real speakers via sounddevice (lazy import so tests don't need PortAudio)."""

    def __init__(self, device: str | int | None = None):
        import sounddevice as sd

        self._sd = sd
        self._device = device or None

    def play(self, audio: np.ndarray, sample_rate: int, stop: threading.Event) -> None:
        self._sd.play(audio, sample_rate, device=self._device)
        duration = len(audio) / sample_rate
        end = time.monotonic() + duration     # then sd.wait() for the last buffer; no extra pause
        while time.monotonic() < end:
            if stop.wait(0.02):
                self._sd.stop()
                return
        self._sd.wait()

    def stop(self) -> None:
        self._sd.stop()


@dataclass
class _Item:
    audio: np.ndarray
    sample_rate: int
    token: CancelToken | None
    on_start: Callable[[], None] | None


class AudioPlayer:
    def __init__(self, backend=None):
        self._backend = backend
        self._queue: queue.Queue[_Item | None] = queue.Queue()
        self._stop = threading.Event()
        self._idle = threading.Event()
        self._idle.set()
        self._pending = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="audio-player", daemon=True)
        self._thread.start()

    @property
    def backend(self):
        if self._backend is None:
            self._backend = SoundDeviceBackend()
        return self._backend

    def play(self, audio: np.ndarray, sample_rate: int, token: CancelToken | None = None,
             on_start: Callable[[], None] | None = None) -> None:
        with self._lock:
            self._pending += 1
            self._idle.clear()
        self._queue.put(_Item(audio, sample_rate, token, on_start))

    def stop(self) -> None:
        """Drop everything queued and cut off what's playing now."""
        self._stop.set()
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is not None:
                self._done_one()
        try:
            self.backend.stop()
        except Exception:
            pass

    @property
    def busy(self) -> bool:
        return not self._idle.is_set()

    def wait_idle(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    def close(self) -> None:
        self.stop()
        self._queue.put(None)

    def _done_one(self) -> None:
        with self._lock:
            self._pending = max(0, self._pending - 1)
            if self._pending == 0:
                self._idle.set()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            try:
                if item.token is not None and item.token.cancelled:
                    continue
                self._stop.clear()
                # Re-check: a stop() between get() and clear() would otherwise be lost.
                if item.token is not None and item.token.cancelled:
                    continue
                if item.on_start:
                    item.on_start()
                self.backend.play(item.audio, item.sample_rate, self._stop)
            except Exception as exc:   # a broken audio device must not kill the thread
                print(f"[audio] playback failed: {exc}")
            finally:
                self._done_one()
