"""The "Jarvis feel": a light studio effects chain on every spoken reply.

Not a copy of any real voice. It's ordinary production polish: rumble removed,
a little warmth and presence, even loudness, a faint shimmer and a small clean
room. Every setting lives in [voice_style] in config/settings.toml.

Uses Spotify's free pedalboard library. If it isn't installed, audio passes
through unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from typing import Any

import numpy as np

log = logging.getLogger(__name__)
TAIL_SECONDS = 0.25   # silence appended so the reverb tail isn't cut off


@dataclass
class VoiceStyle:
    enabled: bool = True
    highpass_hz: float = 90
    low_shelf_db: float = 2.0
    presence_db: float = 2.5
    air_db: float = 2.0
    compressor_threshold_db: float = -20
    compressor_ratio: float = 3.0
    chorus_mix: float = 0.08
    reverb_room: float = 0.14
    reverb_wet: float = 0.10
    output_gain_db: float = 0.0
    # Every reply ends up at the same loudness, whichever engine spoke it
    # (Kokoro, Piper and MMS all come out at different levels).
    target_rms_db: float = -20.0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "VoiceStyle":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})

    def board(self):
        import pedalboard as pb

        chain = [
            pb.HighpassFilter(cutoff_frequency_hz=self.highpass_hz),
            pb.LowShelfFilter(cutoff_frequency_hz=250, gain_db=self.low_shelf_db),
            pb.PeakFilter(cutoff_frequency_hz=3000, gain_db=self.presence_db, q=0.9),
            pb.HighShelfFilter(cutoff_frequency_hz=9000, gain_db=self.air_db),
            pb.Compressor(threshold_db=self.compressor_threshold_db, ratio=self.compressor_ratio,
                          attack_ms=5, release_ms=80),
        ]
        if self.chorus_mix > 0:
            chain.append(pb.Chorus(rate_hz=0.6, depth=0.12, centre_delay_ms=7, feedback=0.0, mix=self.chorus_mix))
        if self.reverb_wet > 0:
            chain.append(pb.Reverb(room_size=self.reverb_room, damping=0.6, wet_level=self.reverb_wet,
                                   dry_level=1.0 - self.reverb_wet / 2, width=0.6))
        chain += [pb.Gain(gain_db=self.output_gain_db), pb.Limiter(threshold_db=-1.0)]
        return pb.Pedalboard(chain)

    def process(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply the chain to mono float32 audio. Safe to call when disabled."""
        if not self.enabled or audio.size == 0:
            return audio
        try:
            board = self.board()
        except ImportError:
            log.warning("pedalboard not installed; voice_style skipped")
            return audio
        padded = np.concatenate([audio.astype(np.float32), np.zeros(int(TAIL_SECONDS * sample_rate), np.float32)])
        out = board(padded[np.newaxis, :], sample_rate)[0]
        return match_loudness(out, self.target_rms_db)


PEAK_CEILING = 10 ** (-1 / 20)   # -1 dBFS


def match_loudness(audio: np.ndarray, target_rms_db: float = -20.0) -> np.ndarray:
    """Scale to a target RMS level, then make sure no peak goes above -1 dBFS."""
    audio = audio.astype(np.float32)
    rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0
    if rms < 1e-6:
        return audio
    audio = audio * (10 ** (target_rms_db / 20) / rms)
    peak = float(np.max(np.abs(audio)))
    if peak > PEAK_CEILING:
        audio = audio * (PEAK_CEILING / peak)
    return audio.astype(np.float32)
