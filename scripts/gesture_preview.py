"""See what Jarvis's camera sees: hands, gestures, and when a palm would count.

    uv run python scripts/gesture_preview.py                  right hand (the default)
    uv run python scripts/gesture_preview.py --camera 1       another camera
    uv run python scripts/gesture_preview.py --swap-hands     if "Right" shows for your left hand

A window shows the camera like a mirror, the 21 points of each hand, which
hand MediaPipe thinks it is, and the gesture it sees. When your right hand
holds an open palm for half a second, the window shows "accepted": that is
the moment Jarvis would stop talking or pause the video (decision D29).
Then the hand has to drop for half a second before the next palm counts.

Nothing is saved, and nothing in Jarvis is controlled: this only shows.
Press q (or close the window) to quit; a summary prints to paste into the
chat. The plan is docs/IMPLEMENTATION_PLAN.md, M8, "Palm to pause".
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import load_settings

WINDOW = "Jarvis gesture preview"

# Which of the 21 points join up, to draw the hand's skeleton. MediaPipe 1.x
# no longer ships drawing helpers (mp.solutions is gone), so it's listed here.
# 0 is the wrist; 4, 8, 12, 16 and 20 are the finger tips.
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),            # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),            # index finger
    (9, 10), (10, 11), (11, 12),               # middle finger
    (13, 14), (14, 15), (15, 16),              # ring finger
    (0, 17), (17, 18), (18, 19), (19, 20),     # little finger
    (5, 9), (9, 13), (13, 17),                 # across the palm
]

# Colours are blue, green, red in OpenCV.
COLOUR_CHOSEN = (80, 200, 60)       # the hand Jarvis listens to: green
COLOUR_OTHER = (150, 150, 150)      # any other hand: grey
COLOUR_ACCEPTED = (60, 220, 255)    # "accepted": yellow
WHITE = (255, 255, 255)


# --------------------------------------------------------------------------
# The palm rule: held long enough, once, then the hand must drop first.
# This is the preview's version; step 2 of the plan turns it into
# PalmTrigger in src/jarvis/sensors/gestures.py, with tests.
# --------------------------------------------------------------------------
@dataclass
class PalmHold:
    hold_s: float = 0.5        # how long the palm must be held
    rearm_s: float = 0.5       # how long the hand must be away before the next palm
    max_missed: int = 2        # frames the tracker may lose mid-hold (it flickers)
    state: str = "waiting"     # waiting -> holding -> fired -> rearming -> waiting
    since: float = 0.0
    missed: int = 0

    def update(self, t: float, palm: bool) -> bool:
        """Feed one result. Returns True only on the frame the palm is accepted."""
        if self.state == "waiting":
            if palm:
                self.state, self.since, self.missed = "holding", t, 0
        elif self.state == "holding":
            if palm:
                self.missed = 0
                if t - self.since >= self.hold_s:
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

    def held(self, t: float) -> float:
        return t - self.since if self.state == "holding" else 0.0


@dataclass
class Hand:
    side: str            # "Right" or "Left", after --swap-hands
    side_score: float
    gesture: str         # "Open_Palm", "Closed_Fist", ..., or "None"
    gesture_score: float
    points: list         # 21 (x, y), each from 0 to 1


def read_hands(result, swap: bool) -> list[Hand]:
    """Turn MediaPipe's result into a plain list of hands."""
    hands = []
    for i, points in enumerate(result.hand_landmarks):
        side = result.handedness[i][0] if result.handedness and result.handedness[i] else None
        best = result.gestures[i][0] if result.gestures and result.gestures[i] else None
        name = side.category_name if side else "?"
        if swap and name in ("Left", "Right"):
            name = "Left" if name == "Right" else "Right"
        hands.append(Hand(
            side=name, side_score=side.score if side else 0.0,
            gesture=best.category_name if best else "None", gesture_score=best.score if best else 0.0,
            points=[(p.x, p.y) for p in points]))
    return hands


def chosen_palm(hands: list[Hand], side: str, min_score: float) -> Hand | None:
    """The hand Jarvis listens to, if it shows an open palm clearly enough."""
    palms = [h for h in hands if h.side == side and h.gesture == "Open_Palm" and h.gesture_score >= min_score]
    return max(palms, key=lambda h: h.gesture_score, default=None)


@dataclass
class Latest:
    """The newest result. MediaPipe calls back on its own thread, so it's locked."""
    lock: threading.Lock = field(default_factory=threading.Lock)
    result: object = None
    timestamp_ms: int = -1
    latency_ms: float = 0.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------
def draw_hand(cv2, frame, hand: Hand, chosen: bool) -> None:
    h, w = frame.shape[:2]
    colour = COLOUR_CHOSEN if chosen else COLOUR_OTHER
    pts = [(int(x * w), int(y * h)) for x, y in hand.points]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], colour, 2)
    for p in pts:
        cv2.circle(frame, p, 4, colour, -1)
    wx, wy = pts[0]                                    # label under the wrist
    label = f"{hand.side} {hand.side_score:.2f} | {hand.gesture} {hand.gesture_score:.2f}"
    cv2.putText(frame, label, (max(5, wx - 120), min(h - 10, wy + 28)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2)


def draw_status(cv2, frame, lines: list[tuple[str, tuple[int, int, int]]]) -> None:
    y = 26
    for text, colour in lines:
        cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)   # outline
        cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 1)
        y += 24


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--camera", type=int, default=None, help="camera number (default: vision.camera_index, 0)")
    ap.add_argument("--hand", choices=["right", "left"], default=None, help="which hand counts (default: right)")
    ap.add_argument("--swap-hands", action="store_true", help="swap Left and Right, if they show the wrong way round")
    ap.add_argument("--min-score", type=float, default=0.7, help="how sure the open palm must be (0-1)")
    ap.add_argument("--hold", type=float, default=0.5, help="seconds the palm must be held")
    args = ap.parse_args()

    settings = load_settings(load_env=False)
    side = (args.hand or settings.get("gestures.hand", "right")).capitalize()
    model = settings.path("vision.gesture_model", "models/gesture_recognizer.task")
    if not model.exists():
        print(f"No gesture model at {model}.\nRun: uv run python scripts/download_models.py")
        return 1

    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
    except ImportError as exc:
        print(f"Missing a library ({exc}).\nRun: scripts\\update.cmd  (it installs the vision extra)")
        return 1

    # 1. The camera. CAP_DSHOW opens it much faster on Windows.
    index = args.camera if args.camera is not None else settings.get("vision.camera_index", 0)
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        print(f"Couldn't open camera {index}. Close other apps that use it (Teams, Zoom, the browser),\n"
              "or try another number: --camera 1")
        return 1
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # 2. The recognizer. LIVE_STREAM: we send frames and it calls back with
    # results on its own thread; while it's busy it skips frames, so it never
    # falls behind the camera.
    latest = Latest()

    def on_result(result, image, timestamp_ms: int) -> None:
        with latest.lock:
            latest.result = result
            latest.timestamp_ms = timestamp_ms
            latest.latency_ms = time.monotonic() * 1000 - timestamp_ms

    options = vision.GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_path=str(model)),
        running_mode=vision.RunningMode.LIVE_STREAM,
        num_hands=2,                          # so the chosen hand can be picked out
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        result_callback=on_result)

    rule = PalmHold(hold_s=args.hold)
    latencies: list[float] = []
    seen = {"Right": 0, "Left": 0}            # results where each hand was seen
    frames = results = accepted = 0
    accepted_at = -10.0
    last_ts = -1
    last_result_ts = -1
    fps = 0.0
    start = prev = time.monotonic()
    print(f"Showing camera {index}. Hold up your {side.lower()} hand. q = quit.")

    try:
        with vision.GestureRecognizer.create_from_options(options) as recognizer:
            failures = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    failures += 1
                    if failures > 50:
                        print("The camera stopped sending pictures.")
                        break
                    continue
                failures = 0
                frames += 1

                # 3. Mirror it like a selfie, so your right hand is on the
                # right of the picture; MediaPipe wants RGB, OpenCV gives BGR.
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ts = max(int(time.monotonic() * 1000), last_ts + 1)   # must always go up
                last_ts = ts
                recognizer.recognize_async(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)

                with latest.lock:
                    result, result_ts, latency = latest.result, latest.timestamp_ms, latest.latency_ms

                # 4. Read the newest result (only once per result, not per frame).
                now = time.monotonic()
                hands = read_hands(result, args.swap_hands) if result is not None else []
                palm = chosen_palm(hands, side, args.min_score)
                if result is not None and result_ts != last_result_ts:
                    last_result_ts = result_ts
                    results += 1
                    if results > 1:                 # the first one includes loading MediaPipe
                        latencies.append(latency)
                    for hand in hands:
                        if hand.side in seen:
                            seen[hand.side] += 1
                    if rule.update(now, palm is not None):
                        accepted += 1
                        accepted_at = now
                        print(f"  {now - start:6.1f} s  palm accepted ({palm.gesture_score:.2f})")

                for hand in hands:
                    draw_hand(cv2, frame, hand, chosen=hand.side == side)

                # 5. Considered vs accepted, and the speed.
                dt = now - prev
                prev = now
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1 / dt) if fps else 1 / dt
                if now - accepted_at < 1.0:
                    status = ("Accepted: Jarvis would stop talking or pause the video", COLOUR_ACCEPTED)
                elif rule.state == "holding":
                    score = palm.gesture_score if palm else 0.0
                    text = f"{side} hand: Open_Palm {score:.2f}, holding {rule.held(now):.1f} of {args.hold:.1f} s"
                    status = (text, COLOUR_CHOSEN)
                elif rule.state in ("fired", "rearming"):
                    status = ("Lower your hand before the next palm", WHITE)
                else:
                    status = (f"Waiting for an open {side.lower()} palm", WHITE)
                draw_status(cv2, frame, [
                    status,
                    (f"{fps:4.1f} fps | {latency:3.0f} ms per frame | palms accepted: {accepted}", WHITE),
                    ("q = quit", WHITE),
                ])

                # 6. Show it; quit on q or when the window is closed.
                cv2.imshow(WINDOW, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()                     # the camera light goes off
        cv2.destroyAllWindows()

    # A summary to paste into the chat.
    seconds = time.monotonic() - start
    print("\nSummary")
    print(f"  {seconds:.0f} s, {frames} frames ({frames / seconds if seconds else 0:.1f} fps), "
          f"{results} results from MediaPipe")
    print(f"  time per frame: p50 {percentile(latencies, 0.5):.0f} ms, p95 {percentile(latencies, 0.95):.0f} ms")
    print(f"  hands seen: Right in {seen['Right']} results, Left in {seen['Left']}"
          f"{' (swapped)' if args.swap_hands else ''}")
    print(f"  palms accepted ({side.lower()} hand, score >= {args.min_score}, held {args.hold} s): {accepted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
