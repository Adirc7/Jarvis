"""The double clap (decision D29; docs/IMPLEMENTATION_PLAN.md, "The double clap, step by step").

    detector = ClapDetector(16000)
    for event in detector.feed(block):         # any block size of 16 kHz mono float32
        if event.kind == "double": ...        # two claps 0.2-0.6 s apart, and no third

No model: a clap is a sharp, short, broadband sound, and signal processing finds that.

- 10 ms frames; each frame's energy in dB; the noise floor is the 20th percentile of the last 3 s.
- A peak (one clap) rises at least 15 dB above the floor, at least 10 dB of it within 20 ms (a sharp
  start), and falls back 10 dB within 100 ms (a short sound). Speech, music, a fan or a tone rise slowly
  or last long, so they fail one of the two.
- Broadband: a clap has much of its energy above 2 kHz; a desk tap or a door knock is mostly low.
- A pair: a second peak 0.2-0.6 s after the first, then no third within 0.6 s (applause, knocking);
  then 2 s of rest.
- While Jarvis speaks, and 0.5 s after, nothing counts (the sound could be his own voice).

After a double clap Jarvis listens hands-free (`SpeechEnd`): the recording stops when you pause for
0.8 s after speaking, or after 5 s if you say nothing. Nothing is stored: frames are measured and dropped,
like the push-to-talk microphone outside a key press (D7).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

FRAME_S = 0.01


@dataclass
class ClapSettings:
    rise_db: float = 15.0          # a peak is this far above the noise floor...
    jump_db: float = 10.0          # ...and rose at least this much within 20 ms
    fall_db: float = 10.0          # and fell back this much...
    fall_ms: float = 100.0         # ...within this long
    min_high_share: float = 0.3    # share of its energy above high_hz (calibrate: scripts/clap_test.py)
    high_hz: float = 2000.0
    min_peak_db: float = -50.0     # quieter than this isn't a clap, however quiet the room
    min_gap_s: float = 0.2
    max_gap_s: float = 0.6
    quiet_after_s: float = 0.6     # no third peak this soon after the second
    rest_s: float = 2.0            # after a double clap, before the next can count
    mute_after_s: float = 0.5      # after Jarvis stops speaking
    warmup_s: float = 0.5          # room noise to learn from before anything counts

    @classmethod
    def from_settings(cls, settings) -> ClapSettings:
        values = {}
        for name, default in cls().__dict__.items():
            got = settings.get(f"clap.{name}", default)
            if isinstance(got, (int, float)) and not isinstance(got, bool):
                values[name] = float(got)
        return cls(**values)


@dataclass(frozen=True)
class ClapEvent:
    kind: str                      # "peak" or "double"
    t: float                       # seconds since the detector started
    db: float = 0.0                # a peak's loudness (dBFS) and how far above the floor
    above: float = 0.0
    high_share: float = 0.0
    counted: bool = True           # a peak that failed the broadband check is reported, not counted
    why: str = ""


@dataclass
class _Peak:
    start: float
    top_db: float
    frames: int = 0
    samples: list = field(default_factory=list)


class ClapDetector:
    def __init__(self, rate: int = 16000, settings: ClapSettings | None = None,
                 muted: Callable[[], bool] | None = None):
        self.rate, self.s = rate, settings or ClapSettings()
        self.muted = muted or (lambda: False)
        self.frame = int(round(rate * FRAME_S))
        self._buf = np.zeros(0, np.float32)
        self._t = 0.0
        self._db: deque[float] = deque(maxlen=int(3 / FRAME_S))
        self._recent: deque[np.ndarray] = deque(maxlen=3)
        self._peak: _Peak | None = None
        self._long_sound = False
        self._first: float | None = None          # a single clap waiting for its partner
        self._second: float | None = None         # a pair waiting to see there's no third
        self._rest_until = 0.0
        self._mute_until = 0.0
        freqs = np.fft.rfftfreq(self.frame * 2, 1 / rate)
        self._high = freqs >= self.s.high_hz
        self._band = freqs >= 100

    @property
    def floor_db(self) -> float:
        return float(np.percentile(self._db, 20)) if self._db else -90.0

    def feed(self, samples: np.ndarray) -> list[ClapEvent]:
        if self.muted():
            self._mute_until = self._t + len(samples) / self.rate + self.s.mute_after_s
        self._buf = np.concatenate([self._buf, np.asarray(samples, np.float32).reshape(-1)])
        events: list[ClapEvent] = []
        while len(self._buf) >= self.frame:
            frame, self._buf = self._buf[:self.frame], self._buf[self.frame:]
            events += self._frame(frame)
            self._t += FRAME_S
        return events

    # ---- one 10 ms frame -------------------------------------------------------------------------
    def _frame(self, frame: np.ndarray) -> list[ClapEvent]:
        s, t = self.s, self._t
        db = 10 * np.log10(float(np.mean(frame * frame)) + 1e-12)
        floor = self.floor_db
        before = self._db[-2] if len(self._db) >= 2 else db           # 20 ms ago
        self._db.append(db)
        self._recent.append(frame)
        events: list[ClapEvent] = []
        if self._second is not None and t - self._second >= s.quiet_after_s:
            events.append(ClapEvent("double", t))                     # two, and no third
            self._second, self._first, self._rest_until = None, None, t + s.rest_s
        if t < s.warmup_s:
            return events
        muted = t < self._mute_until
        if muted:
            self._peak, self._first, self._second = None, None, None
        if self._long_sound:                                           # wait for a long sound to end
            if db < floor + s.rise_db / 2:
                self._long_sound = False
            return events
        if self._peak is None:
            if not muted and db >= floor + s.rise_db and db - before >= s.jump_db and db >= s.min_peak_db:
                self._peak = _Peak(t, db, 0, [*list(self._recent)[-2:]])
            return events
        p = self._peak
        p.frames += 1
        if len(p.samples) < 4:
            p.samples.append(frame)
        if db > p.top_db:
            p.top_db = db
        elif p.top_db - db >= s.fall_db:                               # short: it's a peak
            self._peak = None
            share = self._high_share(np.concatenate(p.samples))
            above = p.top_db - floor
            if share < s.min_high_share:
                return [*events, ClapEvent("peak", p.start, p.top_db, above, share, False, "low-pitched")]
            return [*events, ClapEvent("peak", p.start, p.top_db, above, share), *self._counted(p.start)]
        if p.frames * FRAME_S * 1000 > s.fall_ms:                      # too long for a clap
            self._peak, self._long_sound = None, True
        return events

    def _high_share(self, samples: np.ndarray) -> float:
        x = samples[: self.frame * 2]
        if len(x) < self.frame * 2:
            x = np.pad(x, (0, self.frame * 2 - len(x)))
        power = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
        total = float(power[self._band].sum())
        return float(power[self._high].sum()) / total if total > 0 else 0.0

    def _counted(self, t: float) -> list[ClapEvent]:
        s = self.s
        if t < self._rest_until:
            return []
        if self._second is not None:                                   # a third: applause or knocking
            self._first, self._second, self._rest_until = None, None, t + s.quiet_after_s
            return []
        if self._first is not None and s.min_gap_s <= t - self._first <= s.max_gap_s:
            self._second = t
        else:
            self._first = t
        return []


class TripleClap:
    """Three claps, each 0.2-0.6 s after the one before, then quiet: opens Jarvis (clap_launcher.py).

    Fed the detector's counted peaks and its clock. A fourth clap soon after (applause, knocking) makes it
    nothing; after a triple, the next one counts only `rest_s` later.
    """

    def __init__(self, settings: ClapSettings | None = None, claps: int = 3, rest_s: float = 8.0,
                 min_above_db: float = 0.0, max_spread_db: float = 99.0, max_rhythm: float = 99.0):
        self.s, self.claps, self.rest_s = settings or ClapSettings(), claps, rest_s
        # 4 Nov: typing near the laptop's microphone started Jarvis 25 times in 25 minutes. Real claps were
        # 37-50 dB above the room, the rest 15-34; claps come evenly and equally loud, keys don't.
        self.min_above_db, self.max_spread_db, self.max_rhythm = min_above_db, max_spread_db, max_rhythm
        self.times: list[float] = []
        self.loud: list[float] = []
        self._rest_until = 0.0

    def peak(self, t: float, above: float = 99.0) -> bool:
        """A clap; False when it isn't counted (resting, an echo, or too quiet)."""
        if t < self._rest_until or above < self.min_above_db:
            return False
        if self.times and t - self.times[-1] < self.s.min_gap_s:
            return False                                               # the same clap's echo
        if self.times and t - self.times[-1] > self.s.max_gap_s:
            self.times, self.loud = [], []
        self.times.append(t)
        self.loud.append(above)
        if len(self.times) > self.claps:                               # too many: applause
            self.times, self.loud, self._rest_until = [], [], t + self.s.quiet_after_s
        return True

    def even(self) -> bool:
        """The gaps alike and the claps equally loud: a deliberate clap-clap-clap, not typing."""
        gaps = [b - a for a, b in zip(self.times, self.times[1:], strict=False)]
        rhythm_ok = not gaps or max(gaps) / max(min(gaps), 1e-6) <= self.max_rhythm
        return rhythm_ok and (max(self.loud) - min(self.loud) <= self.max_spread_db if self.loud else True)

    def done(self, now: float) -> bool:
        """True once, when the claps are in and nothing followed for quiet_after_s."""
        if len(self.times) == self.claps and now - self.times[-1] >= self.s.quiet_after_s:
            ok = self.even()
            self.times, self.loud = [], []
            if ok:
                self._rest_until = now + self.rest_s
            return ok
        if self.times and now - self.times[-1] > self.s.max_gap_s and len(self.times) < self.claps:
            self.times, self.loud = [], []
        return False


class SpeechEnd:
    """After a double clap: has the user started talking, and then paused? (energy above the room's noise)

    feed() returns "" while it waits, "ended" after speech and then end_s of quiet, or "nothing" when
    nobody spoke within wait_s. max_s caps it, like the push-to-talk limit."""

    def __init__(self, floor_db: float, rate: int = 16000, margin_db: float = 10.0, start_s: float = 0.05,
                 end_s: float = 0.8, wait_s: float = 5.0, max_s: float = 15.0):
        self.threshold = floor_db + margin_db
        self.rate, self.frame = rate, int(round(rate * FRAME_S))
        self.start_n, self.end_n = int(start_s / FRAME_S), int(end_s / FRAME_S)
        self.wait_n, self.max_n = int(wait_s / FRAME_S), int(max_s / FRAME_S)
        self._buf = np.zeros(0, np.float32)
        self.n = self.loud = self.quiet = 0
        self.speaking = False

    def feed(self, samples: np.ndarray) -> str:
        self._buf = np.concatenate([self._buf, np.asarray(samples, np.float32).reshape(-1)])
        while len(self._buf) >= self.frame:
            frame, self._buf = self._buf[:self.frame], self._buf[self.frame:]
            self.n += 1
            loud = 10 * np.log10(float(np.mean(frame * frame)) + 1e-12) >= self.threshold
            if not self.speaking:
                self.loud = self.loud + 1 if loud else 0
                if self.loud >= self.start_n:
                    self.speaking = True
                elif self.n >= self.wait_n:
                    return "nothing"
            else:
                self.quiet = 0 if loud else self.quiet + 1
                if self.quiet >= self.end_n:
                    return "ended"
            if self.n >= self.max_n:
                return "ended" if self.speaking else "nothing"
        return ""


class ClapListener:
    """Between the microphone and Jarvis (on the microphone's thread): claps in, a double clap out; then,
    when Jarvis asks, it records hands-free until you pause."""

    def __init__(self, recorder, settings: ClapSettings | None = None, on_double: Callable[[], None] = lambda: None,
                 on_heard: Callable[[np.ndarray], None] = lambda audio: None,
                 on_nothing: Callable[[], None] = lambda: None, muted: Callable[[], bool] | None = None,
                 rate: int = 16000):
        self.recorder, self.rate = recorder, rate
        self.detector = ClapDetector(rate, settings, muted)
        self.on_double, self.on_heard, self.on_nothing = on_double, on_heard, on_nothing
        self.listening: SpeechEnd | None = None
        self.on = True

    def feed(self, samples: np.ndarray) -> None:
        listening = self.listening
        if listening is not None:
            state = listening.feed(samples)
            if state and self.listening is listening:
                self.listening = None
                audio = self.recorder.end()
                (self.on_heard(audio) if state == "ended" else self.on_nothing())
            return
        events = self.detector.feed(samples)       # always: the room's noise is what "you paused" is measured against
        if not self.on:
            return
        for event in events:
            if event.kind == "double":
                self.on_double()

    def listen(self) -> None:
        """Start recording now, until the user pauses (called by Jarvis after "Yes, sir?")."""
        self.recorder.begin()
        known = len(self.detector._db) >= int(self.detector.s.warmup_s / FRAME_S)
        self.listening = SpeechEnd(self.detector.floor_db if known else -60.0, self.rate)

    def cancel(self) -> None:
        """Push-to-talk took over: its own key press decides when the recording ends."""
        self.listening = None


__all__ = ["ClapDetector", "ClapEvent", "ClapListener", "ClapSettings", "SpeechEnd"]
