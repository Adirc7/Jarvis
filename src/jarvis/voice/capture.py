"""Microphone capture with push-to-talk.

The input stream stays open the whole session (opening it on every key press
would clip the first syllable), but frames are only kept while the
push-to-talk key is held. Everything else is discarded immediately: no audio
is stored outside the current utterance (decision D7).
"""

from __future__ import annotations

import re
import threading
from typing import Callable

import numpy as np


class MicRecorder:
    def __init__(self, sample_rate: int = 16000, device: str | int | None = None, max_seconds: float = 30):
        self.sample_rate = sample_rate
        self._device = device or None
        self._max_frames = int(max_seconds * sample_rate)
        self._frames: list[np.ndarray] = []
        self._count = 0
        self._recording = False
        self._lock = threading.Lock()
        self._stream = None

    # The stream callback runs on PortAudio's thread.
    def _callback(self, indata, frames, time_info, status) -> None:
        self.feed(indata[:, 0])

    def feed(self, samples: np.ndarray) -> None:
        with self._lock:
            if not self._recording or self._count >= self._max_frames:
                return
            take = samples[: self._max_frames - self._count].astype(np.float32, copy=True)
            self._frames.append(take)
            self._count += len(take)

    def open(self) -> None:
        import sounddevice as sd

        self._stream = sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="float32",
            device=self._device, callback=self._callback, blocksize=0,
        )
        self._stream.start()

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def begin(self) -> None:
        with self._lock:
            self._frames, self._count, self._recording = [], 0, True

    def end(self) -> np.ndarray:
        with self._lock:
            self._recording = False
            audio = np.concatenate(self._frames) if self._frames else np.zeros(0, np.float32)
            self._frames, self._count = [], 0
        return audio

    @property
    def recording(self) -> bool:
        return self._recording


def parse_key(name: str):
    """'ctrl_r' -> Key.ctrl_r, 'f9' -> Key.f9, '`' -> KeyCode for that character."""
    from pynput import keyboard

    name = name.strip()
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    try:
        return getattr(keyboard.Key, name.lower())
    except AttributeError as exc:
        raise ValueError(f"unknown push-to-talk key '{name}'") from exc


_KEY_LABELS = {
    "ctrl_r": "Right Ctrl", "ctrl_l": "Left Ctrl", "alt_r": "Right Alt", "alt_l": "Left Alt",
    "alt_gr": "AltGr", "shift_r": "Right Shift", "shift_l": "Left Shift", "cmd": "Windows key",
    "cmd_l": "Windows key", "cmd_r": "Windows key", "page_up": "Page Up", "page_down": "Page Down",
    "caps_lock": "Caps Lock", "num_lock": "Num Lock", "scroll_lock": "Scroll Lock",
    "print_screen": "Print Screen", "esc": "Esc",
}
_TYPING_KEYS = {
    "space", "enter", "tab", "backspace", "delete", "shift", "shift_l", "shift_r", "ctrl", "ctrl_l",
    "alt", "alt_l", "caps_lock", "up", "down", "left", "right", "home", "end", "page_up", "page_down",
}


def describe_key(name: str) -> str:
    """'ctrl_r' -> 'Right Ctrl', 'f9' -> 'F9', for messages."""
    name = name.strip()
    if len(name) == 1:
        return f"the {name} key"
    low = name.lower()
    if low in _KEY_LABELS:
        return _KEY_LABELS[low]
    if re.fullmatch(r"f\d{1,2}", low):
        return low.upper()
    return low.replace("_", " ").title()


def check_push_to_talk_key(name: str | None) -> str | None:
    """Why `name` is a bad push-to-talk key, or None if it's fine.

    The key is held while talking and watched from every app, so it must be
    one you don't type with and that Windows doesn't use itself.
    """
    if not name:
        return "Jarvis can't tell which key that is."
    low = name.strip().lower()
    if len(low) == 1 or low in _TYPING_KEYS:
        return "You use that key while typing, so Jarvis would start listening as you type."
    if low.startswith("cmd"):
        return "Windows uses that key itself (the Copilot key sends it too)."
    if low.startswith("media_"):
        return "That's a media key. Hold Fn while pressing it to get the F-key instead."
    if low in ("print_screen", "num_lock"):
        return f"Windows uses {describe_key(low)} for something else."
    if low == "esc":
        return "Esc is used to cancel things."
    return None


class PushToTalk:
    """Calls on_press when the key goes down and on_release when it comes up.

    Windows repeats key-down events while a key is held; only the first one
    counts.
    """

    def __init__(self, key_name: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self._key_name = key_name
        self._on_press = on_press
        self._on_release = on_release
        self._held = False
        self._listener = None
        self._key = None

    def _matches(self, key) -> bool:
        return key == self._key

    def handle_press(self, key) -> None:
        if self._matches(key) and not self._held:
            self._held = True
            self._on_press()

    def handle_release(self, key) -> None:
        if self._matches(key) and self._held:
            self._held = False
            self._on_release()

    def start(self) -> None:
        from pynput import keyboard

        self._key = parse_key(self._key_name)
        self._listener = keyboard.Listener(on_press=self.handle_press, on_release=self.handle_release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
