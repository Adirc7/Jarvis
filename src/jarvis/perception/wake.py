""""Hey Jarvis" without the key (4 Nov, Adhi): openWakeWord on the laptop's CPU.

    wake = WakeWord(Path("models/openwakeword"), on_wake=..., muted=...)
    recorder.listeners.append(wake.feed)        # every microphone block, between key presses too

openWakeWord (Apache-2.0 code) turns each 80 ms of sound into speech features and its small "hey jarvis"
model scores them, about 2.5 ms of CPU each. Its pre-trained model is CC BY-NC-SA 4.0: fine for this
non-commercial project. Nothing is recorded or sent: each block is scored and dropped, like the double
clap's measuring (perception/clap.py). The model files (about 7 MB) download once, to models/openwakeword.

Checked on made-up speech (Kokoro voices, 4 Nov): "Hey Jarvis" 0.99 in three voices, "Jarvis" alone and
"Hey Travis" 0.90, an ordinary question 0.00, room noise at most 0.10. So it is deaf while Jarvis speaks
(his own "Jarvis here, sir" would wake it) and for a second after, and rests 2 s after waking.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

FILES = ("hey_jarvis_v0.1.onnx", "melspectrogram.onnx", "embedding_model.onnx")
CHUNK = 1280                                   # 80 ms at 16 kHz: what the model scores at a time


def ensure_models(folder: Path) -> Path:
    """The model files, downloaded from openWakeWord's GitHub releases the first time (about 7 MB)."""
    if not all((folder / name).is_file() for name in FILES):
        folder.mkdir(parents=True, exist_ok=True)
        from openwakeword.utils import download_models
        download_models(model_names=["hey_jarvis"], target_directory=str(folder))
    return folder


def load_model(folder: Path) -> Any:
    from openwakeword.model import Model
    folder = ensure_models(folder)
    return Model(wakeword_models=[str(folder / FILES[0])], inference_framework="onnx",
                 melspec_model_path=str(folder / FILES[1]), embedding_model_path=str(folder / FILES[2]))


class WakeWord:
    """Microphone blocks in (from PortAudio's thread, quickly queued), on_wake() out (from its own thread)."""

    def __init__(self, model: Any, on_wake: Callable[[], None], muted: Callable[[], bool] = lambda: False,
                 threshold: float = 0.5, quiet_after_s: float = 1.0, rest_s: float = 2.0,
                 clock: Callable[[], float] = time.monotonic, thread: bool = True):
        self.model, self.on_wake, self.muted = model, on_wake, muted
        self.threshold, self.quiet_after_s, self.rest_s, self.clock = threshold, quiet_after_s, rest_s, clock
        self.on = True
        self.best = 0.0                            # the highest score lately (for /wake)
        self._deaf_until = 0.0
        self._was_muted = False
        self._buf = np.zeros(0, np.int16)
        self._queue: queue.Queue = queue.Queue(maxsize=64)
        if thread:
            threading.Thread(target=self._run, name="wake-word", daemon=True).start()

    def feed(self, samples: np.ndarray) -> None:
        if not self.on:
            return
        pcm = (np.clip(np.asarray(samples, np.float32).reshape(-1), -1, 1) * 32767).astype(np.int16)
        try:
            self._queue.put_nowait(pcm)
        except queue.Full:                         # behind: drop a block rather than hold up the microphone
            pass

    def _run(self) -> None:
        while True:
            self.process(self._queue.get())

    def process(self, pcm: np.ndarray) -> bool:
        """Score what came in; True when it woke (also used directly by the tests)."""
        now = self.clock()
        if self.muted():
            self._deaf_until, self._was_muted = now + self.quiet_after_s, True
            self._buf = np.zeros(0, np.int16)
            return False
        if self._was_muted:                        # forget what was heard while Jarvis spoke
            self.model.reset()
            self._was_muted = False
        self._buf = np.concatenate([self._buf, pcm])
        woke = False
        while len(self._buf) >= CHUNK:
            chunk, self._buf = self._buf[:CHUNK], self._buf[CHUNK:]
            score = float(next(iter(self.model.predict(chunk).values()), 0.0))
            self.best = max(self.best * 0.999, score)
            if score >= self.threshold and now >= self._deaf_until:
                self._deaf_until = now + self.rest_s
                self.model.reset()
                woke = True
        if woke:
            self.on_wake()
        return woke


__all__ = ["WakeWord", "ensure_models", "load_model"]
