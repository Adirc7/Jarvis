"""Read and write 16-bit mono WAV files with the standard library only."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np


def save_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path}: only 16-bit WAV is supported")
        rate, channels = w.getframerate(), w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


def resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Linear resampling; good enough to feed Whisper 16 kHz from other rates."""
    if src == dst or audio.size == 0:
        return audio
    n = int(round(len(audio) * dst / src))
    x_old = np.linspace(0, 1, num=len(audio), endpoint=False)
    x_new = np.linspace(0, 1, num=n, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)
