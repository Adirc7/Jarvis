"""Your hands as the 3D explorer's controls (knowledge/explore_models.py, ui/explore.js).

    controls = ExploreHands(hand="right")
    msg = controls.update(t, hands)        # hands: HandSeen with their 21 points, from the camera
    # {"hands": [{"side", "gesture", "open", "pinch", "tip", "centre", "roll", "points"}, ...],
    #  "events": ["pinch"] or ["next"] or []}

What each hand does in the window (decided there, from these numbers):

- open: how open the hand is, 0 (a fist) to 1 (fingers spread): the model comes apart as you open it;
- a fist puts it back together; moving or twisting the open hand turns it, raising it tilts it;
- pointing (the index finger out) moves a pointer; a pinch (thumb tip to index tip) picks the part under
  it, and Jarvis explains that part;
- two hands: moving them apart or together zooms;
- the peace sign, held half a second: the next model.

Points are mirrored here (x = 1 - x), so the window draws your hand where you see it, like a mirror.
MediaPipe's gestures (Closed_Fist, Open_Palm, Pointing_Up, Victory, ...) come with each hand; the
openness and the pinch are measured from the 21 points, relative to the hand's own size, so they work
near and far from the camera.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .gestures import HandSeen

TIPS = (4, 8, 12, 16, 20)                   # thumb, index, middle, ring, little fingertips
OPEN_FIST, OPEN_FLAT = 1.15, 1.9            # fingertips' mean distance from the wrist, in hand sizes
PINCH = 0.33                                # thumb tip to index tip, in hand sizes


def pose(hand: HandSeen, open_fist: float = OPEN_FIST, open_flat: float = OPEN_FLAT,
         pinch: float = PINCH) -> dict | None:
    """One hand's controls, or None when it came without its points. The three limits are settings
    ([explore] open_fist, open_flat, pinch): tune them from the side panel's readouts on your camera."""
    pts = hand.points
    if len(pts) < 21 or hand.size <= 0:
        return None
    w, h = hand.frame
    size = hand.size
    wrist = pts[0]
    spread = sum(math.dist(pts[i], wrist) for i in TIPS) / len(TIPS) / size
    openness = min(1.0, max(0.0, (spread - open_fist) / max(0.05, open_flat - open_fist)))
    if hand.gesture == "Closed_Fist":
        openness = min(openness, 0.05)
    pinch_d = math.dist(pts[4], pts[8]) / size
    # In a fist the thumb rests on the index finger too: a pinch needs the index reaching out
    index_out = math.dist(pts[8], wrist) / size > 1.25 and hand.gesture != "Closed_Fist"
    mirror = lambda p: (round(1 - p[0] / w, 4), round(p[1] / h, 4))    # noqa: E731
    knuckle = pts[9]
    # how far the hand leans, as you see it: 0 upright, positive leaning to your right
    roll = math.atan2(-(knuckle[0] - wrist[0]), -(knuckle[1] - wrist[1]))
    return {"side": hand.side, "gesture": hand.gesture, "score": round(hand.score, 2),
            "open": round(openness, 3), "pinch": pinch_d < pinch and index_out, "pinch_d": round(pinch_d, 3),
            "spread": round(spread, 3), "pinch_at_most": pinch,
            "tip": mirror(pts[8]), "pinch_at": mirror(((pts[4][0] + pts[8][0]) / 2, (pts[4][1] + pts[8][1]) / 2)),
            "centre": mirror(hand.centre), "roll": round(roll, 3), "size": round(size / max(w, h), 4),
            "points": [mirror(p) for p in pts[:21]]}


class ExploreHands:
    """The hands, the hand that leads, and the moments that matter (a pinch, a held peace sign)."""

    def __init__(self, hand: str = "right", next_hold_s: float = 0.6, pinch_gap_s: float = 0.4,
                 open_fist: float = OPEN_FIST, open_flat: float = OPEN_FLAT, pinch: float = PINCH):
        self.hand = hand.lower()
        self.limits = (open_fist, open_flat, pinch)
        self.next_hold_s, self.pinch_gap_s = next_hold_s, pinch_gap_s
        self._pinching = False
        self._last_pinch = -1e9
        self._peace_since: float | None = None
        self._peace_done = False

    def update(self, t: float, hands: Sequence[HandSeen]) -> dict:
        poses = [p for p in (pose(h, *self.limits) for h in hands) if p is not None]
        poses.sort(key=lambda p: (p["side"].lower() != self.hand, -p["score"]))   # your hand first
        events: list[str] = []
        lead = poses[0] if poses else None
        pinching = bool(lead and lead["pinch"])
        if pinching and not self._pinching and t - self._last_pinch >= self.pinch_gap_s:
            events.append("pinch")
            self._last_pinch = t
        self._pinching = pinching
        if lead is not None and lead["gesture"] == "Victory":
            if self._peace_since is None:
                self._peace_since = t
            if not self._peace_done and t - self._peace_since >= self.next_hold_s:
                events.append("next")
                self._peace_done = True
        else:
            self._peace_since, self._peace_done = None, False
        return {"hands": poses[:2], "events": events}


__all__ = ["ExploreHands", "OPEN_FIST", "OPEN_FLAT", "PINCH", "pose"]
