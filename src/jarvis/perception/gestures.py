"""Palm to pause: when an open palm counts (decision D29).

Two layers, both pure (no camera, no MediaPipe), so they can be tested with
made-up hands:

    PalmHold      the timing rule: the palm held still for half a second
                  counts once; the hand must drop before the next one counts.
    PalmTrigger   picks the hand Jarvis listens to (the right hand by
                  default) and decides whether it shows an open palm, then
                  asks PalmHold.

The numbers come from the laptop recordings of 24-25 Oct (docs/DEVLOG.md):
an open-palm score of at least 0.6, held 0.5 s, the palm's middle staying
within 0.35 of its size. With those, 15 of 15 palms counted and nothing else
did, apart from a still raised hand during a pause in waving, which is a
palm too. The camera side (camera.py) and what a palm does in the app
(docs/IMPLEMENTATION_PLAN.md, M8, steps 4-5) come next.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class PalmHold:
    """Held long enough and still enough, once; then the hand must drop first.

        waiting --palm--> holding --held hold_s--> fired --no palm--> rearming
           ^                 |                       ^                   |
           |  lost for more  |                       |     palm again    |
           +--than max_missed+                       +-------------------+
           +---------------------- no palm for rearm_s --------------------+
    """

    hold_s: float = 0.5        # how long the palm must be held
    rearm_s: float = 0.5       # how long the hand must be away before the next palm
    max_missed: int = 2        # results the tracker may lose mid-hold (it flickers)
    # How far the middle of the palm may drift during the hold, as a share of
    # the palm's size. A "stop" palm stays put; a wave swings much further.
    # None (or 0) switches the stillness check off.
    max_move: float | None = 0.35
    state: str = "waiting"     # waiting -> holding -> fired -> rearming -> waiting
    since: float = 0.0
    missed: int = 0
    anchor: tuple[float, float] | None = None    # where the palm was when the hold (re)started
    moved_at: float = -10.0                      # last time a move restarted the hold

    def update(self, t: float, palm: bool, centre: tuple[float, float] | None = None,
               size: float | None = None) -> bool:
        """Feed one result. Returns True only on the result where the palm is accepted.

        `centre` and `size` (any unit, e.g. pixels) let the rule check the
        palm stays still; without them only the time counts.
        """
        if self.state == "waiting":
            if palm:
                self.state, self.since, self.missed, self.anchor = "holding", t, 0, centre
        elif self.state == "holding":
            if palm:
                self.missed = 0
                if self._moved(centre, size):
                    # It's moving (a wave, or the hand still rising): the
                    # half second starts again from here.
                    self.since, self.anchor, self.moved_at = t, centre, t
                elif t - self.since >= self.hold_s:
                    self.state = "fired"
                    return True
            else:
                self.missed += 1
                if self.missed > self.max_missed:      # the hand really went: start again
                    self.state = "waiting"
        elif self.state == "fired":
            if not palm:
                self.state, self.since = "rearming", t
        elif self.state == "rearming":
            if palm:
                self.state = "fired"                   # still the same palm: no second event
            elif t - self.since >= self.rearm_s:
                self.state = "waiting"
        return False

    def _moved(self, centre: tuple[float, float] | None, size: float | None) -> bool:
        if not self.max_move or centre is None or self.anchor is None or not size:
            return False
        return math.dist(centre, self.anchor) > self.max_move * size

    def held(self, t: float) -> float:
        """Seconds the current hold has lasted (0 when not holding)."""
        return t - self.since if self.state == "holding" else 0.0


@dataclass(frozen=True)
class HandSeen:
    """One hand in one camera result, reduced to what the palm rule needs."""

    side: str                          # "Right" or "Left", as MediaPipe says (unmirrored picture)
    gesture: str                       # "Open_Palm", "Closed_Fist", ..., or "None"
    score: float                       # how sure MediaPipe is of that gesture, 0-1
    centre: tuple[float, float]        # middle of the palm (wrist and four knuckles)
    size: float                        # wrist to middle knuckle, same unit as centre
    side_score: float = 1.0            # how sure MediaPipe is of the side

    @classmethod
    def from_points(cls, side: str, gesture: str, score: float, points: Sequence[Sequence[float]],
                    width: float = 1.0, height: float = 1.0, side_score: float = 1.0) -> HandSeen:
        """From MediaPipe's 21 landmarks (x and y from 0 to 1), scaled to pixels.

        Scaling by the picture's width and height keeps distances true when
        the picture isn't square.
        """
        ids = (0, 5, 9, 13, 17)                      # wrist and the four knuckles
        cx = sum(points[i][0] for i in ids) / len(ids) * width
        cy = sum(points[i][1] for i in ids) / len(ids) * height
        size = math.dist((points[0][0] * width, points[0][1] * height),
                         (points[9][0] * width, points[9][1] * height))
        return cls(side, gesture, score, (cx, cy), size, side_score)


@dataclass(frozen=True)
class PalmSettings:
    hand: str = "right"        # "right" or "left": which hand counts
    min_score: float = 0.6     # how sure MediaPipe must be that it's an open palm
    hold_s: float = 0.5
    rearm_s: float = 0.5
    max_move: float = 0.35     # 0 switches the stillness check off

    @classmethod
    def from_settings(cls, settings: Any) -> PalmSettings:
        """From [gestures] in config/settings.toml."""
        return cls(hand=str(settings.get("gestures.hand", "right")).lower(),
                   min_score=float(settings.get("gestures.min_score", 0.6)),
                   hold_s=float(settings.get("gestures.hold_ms", 500)) / 1000,
                   rearm_s=float(settings.get("gestures.rearm_ms", 500)) / 1000,
                   max_move=float(settings.get("gestures.max_move", 0.35)))


class PalmTrigger:
    """Feed it every camera result; it says True once per deliberate palm."""

    def __init__(self, config: PalmSettings | None = None):
        self.config = config or PalmSettings()
        self.side = self.config.hand.capitalize()
        self.hold = PalmHold(hold_s=self.config.hold_s, rearm_s=self.config.rearm_s,
                             max_move=self.config.max_move or None)

    def chosen(self, hands: Sequence[HandSeen]) -> HandSeen | None:
        """The hand Jarvis listens to; if two look like it, the one MediaPipe is surer of."""
        return max((h for h in hands if h.side == self.side), key=lambda h: h.side_score, default=None)

    def is_palm(self, hand: HandSeen | None) -> bool:
        return hand is not None and hand.gesture == "Open_Palm" and hand.score >= self.config.min_score

    def update(self, t: float, hands: Sequence[HandSeen]) -> bool:
        """One camera result (all hands seen in it, maybe none). True = palm accepted."""
        hand = self.chosen(hands)
        if hand is None:
            return self.hold.update(t, False)
        return self.hold.update(t, self.is_palm(hand), hand.centre, hand.size)

    @property
    def state(self) -> str:
        return self.hold.state
