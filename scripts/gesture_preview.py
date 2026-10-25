"""See what Jarvis's camera sees: hands, gestures, and when a palm would count.

    uv run python scripts/gesture_preview.py                  right hand (the default)
    uv run python scripts/gesture_preview.py --camera 1       another camera
    uv run python scripts/gesture_preview.py --swap-hands     if "Right" shows for your left hand
    uv run python scripts/gesture_preview.py --min-score 0.6  a lower limit for the open palm
    uv run python scripts/gesture_preview.py --max-move 0     don't require the palm to be still

The limits (hand, min_score, max_move, facing_sign) come from [gestures] in
config/settings.toml; the options above override them for one run.

A window shows the camera like a mirror (MediaPipe itself gets the unmirrored
picture, so it tells your hands apart), the 21 points of each hand, which
hand MediaPipe thinks it is, and the gesture it sees. When your right hand
holds an open palm for half a second, the window shows "accepted": that is
the moment Jarvis would stop talking or pause the video (decision D29).
Then the hand has to drop for half a second before the next palm counts.

It also checks the palm a second way, from the 21 points: how many fingers
are out, and whether the palm (not the back of the hand) faces the camera.

Recording, for choosing the limit and training your own palm classifier:
click the window first so it gets the keys, then
    P      record "palm": the "stop" palm, held still and facing the camera,
           at different distances and in different light; lower the hand
           between palms
    N      record "not palm": no open hands at all (fist, typing, pointing,
           thumbs up, chin on hand, holding a cup or phone)
    W      record "wave": waving as if to greet someone (an open hand that
           moves; Jarvis should ignore it)
    space  stop recording
Each result of your chosen hand becomes one row in data/gestures/palm-<time>.csv:
the 21 points as numbers, MediaPipe's guess and the points check. No pictures
are saved, and the folder stays on the laptop (it's in .gitignore).

Nothing in Jarvis is controlled: this only shows. Press q (or close the
window) to quit; a summary prints to paste into the chat. The plan is
docs/IMPLEMENTATION_PLAN.md, M8, "Palm to pause".
"""

from __future__ import annotations

import argparse
import csv
import math
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
COLOUR_RECORDING = (80, 80, 255)    # recording: red
WHITE = (255, 255, 255)

RECORD_DIR = ROOT / "data" / "gestures"
FINGERS = ("thumb", "index", "middle", "ring", "little")
# If the points check says "back of hand" while your palm faces the camera,
# the camera is the other way round: gestures.facing_sign = -1 in settings.
FACING_SIGN = 1


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
        """Feed one result. Returns True only on the frame the palm is accepted.

        `centre` and `size` (in pixels) let the rule check the palm is still.
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

    def _moved(self, centre, size) -> bool:
        if not self.max_move or centre is None or self.anchor is None or not size:
            return False
        return math.dist(centre, self.anchor) > self.max_move * size

    def held(self, t: float) -> float:
        return t - self.since if self.state == "holding" else 0.0


@dataclass
class Hand:
    side: str            # "Right" or "Left", after --swap-hands
    side_score: float
    gesture: str         # "Open_Palm", "Closed_Fist", ..., or "None"
    gesture_score: float
    points: list         # 21 (x, y, z): x and y from 0 to 1 across the picture, z depth
    world: list          # 21 (x, y, z) in metres, centred on the hand


def read_hands(result, swap: bool) -> list[Hand]:
    """Turn MediaPipe's result into a plain list of hands, in mirror coordinates.

    MediaPipe gets the camera's own picture (its "Left" and "Right" are only
    right for an unmirrored picture: fed a mirrored one, it swapped the hands
    on the laptop, 25 Oct). What you see is mirrored, so x becomes 1 - x here
    and every later step (drawing, the points check, recordings) works in the
    mirror picture.
    """
    hands = []
    world = getattr(result, "hand_world_landmarks", None) or []
    for i, points in enumerate(result.hand_landmarks):
        side = result.handedness[i][0] if result.handedness and result.handedness[i] else None
        best = result.gestures[i][0] if result.gestures and result.gestures[i] else None
        name = side.category_name if side else "?"
        if swap and name in ("Left", "Right"):
            name = "Left" if name == "Right" else "Right"
        hands.append(Hand(
            side=name, side_score=side.score if side else 0.0,
            gesture=best.category_name if best else "None", gesture_score=best.score if best else 0.0,
            points=[(1.0 - p.x, p.y, getattr(p, "z", 0.0)) for p in points],
            world=[(-p.x, p.y, p.z) for p in world[i]] if len(world) > i else []))
    return hands


def chosen_hand(hands: list[Hand], side: str) -> Hand | None:
    """The hand Jarvis listens to (if two look like it, the surer one)."""
    return max((h for h in hands if h.side == side), key=lambda h: h.side_score, default=None)


# --------------------------------------------------------------------------
# The second opinion: an open palm judged from the 21 points
# (step 3 of "how to improve it"). Distances are in pixels, so a wide
# picture doesn't stretch them.
# --------------------------------------------------------------------------
def fingers_out(hand: Hand, width: int, height: int) -> list[bool]:
    """Thumb, index, middle, ring, little: is each one stretched out?"""
    p = [(x * width, y * height) for x, y, _ in hand.points]

    def d(a: int, b: int) -> float:
        return math.dist(p[a], p[b])

    # The thumb is out when its tip (4) is farther from the little-finger
    # knuckle (17) than its own base (2) is; folded across the palm, it's nearer.
    thumb = d(4, 17) > d(2, 17)
    # A finger is out when its tip is clearly farther from the wrist (0) than
    # its middle joint; curled, the tip comes back towards the wrist.
    others = [d(0, tip) > 1.1 * d(0, joint) for tip, joint in ((8, 6), (12, 10), (16, 14), (20, 18))]
    return [thumb, *others]


def palm_facing(hand: Hand, width: int, height: int) -> bool:
    """Does the palm (not the back of the hand) face the camera?

    Wrist -> index knuckle and wrist -> little-finger knuckle: their cross
    product's sign says which way round the hand is. In a mirrored picture,
    a right palm facing the camera has the thumb side on the left.
    """
    (x0, y0, _), (x5, y5, _), (x17, y17, _) = hand.points[0], hand.points[5], hand.points[17]
    cross = (x5 - x0) * width * (y17 - y0) * height - (y5 - y0) * height * (x17 - x0) * width
    hand_sign = 1 if hand.side == "Right" else -1
    return cross * hand_sign * FACING_SIGN > 0


def palm_geometry(hand: Hand | None, width: int, height: int) -> tuple[tuple[float, float] | None, float | None]:
    """The middle of the palm and its size (wrist to middle knuckle), in pixels."""
    if hand is None:
        return None, None
    ids = (0, 5, 9, 13, 17)                      # wrist and the four knuckles
    cx = sum(hand.points[i][0] for i in ids) / len(ids) * width
    cy = sum(hand.points[i][1] for i in ids) / len(ids) * height
    (x0, y0, _), (x9, y9, _) = hand.points[0], hand.points[9]
    return (cx, cy), math.dist((x0 * width, y0 * height), (x9 * width, y9 * height))


def points_say_palm(hand: Hand, width: int, height: int) -> bool:
    return all(fingers_out(hand, width, height)) and palm_facing(hand, width, height)


class Recorder:
    """Writes one row per result while P or N is on. Numbers only, no pictures."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.path: Path | None = None
        self.file = None
        self.writer = None
        self.label: str | None = None          # "palm", "other", "wave" or None (not recording)
        self.counts = {"palm": 0, "other": 0, "wave": 0}

    def write(self, t: float, hand: Hand, width: int, height: int) -> None:
        if self.label is None:
            return
        if self.writer is None:
            self.folder.mkdir(parents=True, exist_ok=True)
            self.path = self.folder / f"palm-{time.strftime('%Y%m%d-%H%M%S')}.csv"
            self.file = self.path.open("w", newline="", encoding="utf-8")
            self.writer = csv.writer(self.file)
            header = ["t", "label", "side", "side_score", "mp_gesture", "mp_score",
                      "fingers_out", "palm_facing", "frame_w", "frame_h"]
            header += [f"{axis}{i}" for i in range(21) for axis in "xyz"]
            header += [f"w{axis}{i}" for i in range(21) for axis in "xyz"]
            self.writer.writerow(header)
        out = fingers_out(hand, width, height)
        row = [f"{t:.3f}", self.label, hand.side, f"{hand.side_score:.3f}", hand.gesture,
               f"{hand.gesture_score:.3f}", sum(out), int(palm_facing(hand, width, height)), width, height]
        row += [f"{v:.5f}" for point in hand.points for v in point]
        row += [f"{v:.5f}" for point in hand.world for v in point] or [""] * 63
        self.writer.writerow(row)
        self.counts[self.label] += 1

    def close(self) -> None:
        if self.file is not None:
            self.file.close()


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
    pts = [(int(x * w), int(y * h)) for x, y, _ in hand.points]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], colour, 2)
    for p in pts:
        cv2.circle(frame, p, 4, colour, -1)
    wx, wy = pts[0]                                    # label under the wrist
    label = f"{hand.side} {hand.side_score:.2f} | {hand.gesture} {hand.gesture_score:.2f}"
    cv2.putText(frame, label, (max(5, wx - 120), min(h - 10, wy + 28)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2)


def draw_status(cv2, frame, lines: list[tuple[str, tuple[int, int, int]]]) -> None:
    """The lines at the top, on a dark see-through band so they read on any background.

    (Drawing each line twice, thick black then thin colour, doubled the text
    on the laptop: OpenCV 5 draws thick text with a wider font.)
    """
    font, scale = cv2.FONT_HERSHEY_SIMPLEX, 0.6
    widest = max(cv2.getTextSize(text, font, scale, 1)[0][0] for text, _ in lines)
    bottom = min(frame.shape[0], 12 + 24 * len(lines))
    right = min(frame.shape[1], widest + 20)
    band = frame[:bottom, :right]
    band[:] = (band * 0.4).astype(band.dtype)          # darken behind the text
    y = 26
    for text, colour in lines:
        cv2.putText(frame, text, (10, y), font, scale, colour, 1, cv2.LINE_AA)
        y += 24


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--camera", type=int, default=None, help="camera number (default: vision.camera_index, 0)")
    ap.add_argument("--hand", choices=["right", "left"], default=None, help="which hand counts (default: right)")
    ap.add_argument("--swap-hands", action="store_true", help="swap Left and Right, if they show the wrong way round")
    ap.add_argument("--min-score", type=float, default=None,
                    help="how sure the open palm must be, 0-1 (default: gestures.min_score)")
    ap.add_argument("--max-move", type=float, default=None,
                    help="how still the palm must be, as a share of its size; 0 = off (default: gestures.max_move)")
    ap.add_argument("--facing-sign", type=int, choices=[1, -1], default=None,
                    help="-1 if the points check says 'back of hand' for your palm (default: gestures.facing_sign)")
    ap.add_argument("--hold", type=float, default=0.5, help="seconds the palm must be held")
    args = ap.parse_args()

    settings = load_settings(load_env=False)
    side = (args.hand or settings.get("gestures.hand", "right")).capitalize()
    if args.min_score is None:
        args.min_score = float(settings.get("gestures.min_score", 0.7))
    if args.max_move is None:
        args.max_move = float(settings.get("gestures.max_move", 0.35))
    global FACING_SIGN
    FACING_SIGN = args.facing_sign or int(settings.get("gestures.facing_sign", 1))
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

    rule = PalmHold(hold_s=args.hold, max_move=args.max_move or None)
    latencies: list[float] = []
    seen = {"Right": 0, "Left": 0}            # results where each hand was seen
    palm_scores: list[float] = []             # every Open_Palm score of the chosen hand
    agree = {"both": 0, "mediapipe": 0, "points": 0, "neither": 0}   # the two opinions, chosen hand
    recorder = Recorder(RECORD_DIR)
    frames = results = accepted = 0
    accepted_at = -10.0
    last_ts = -1
    last_result_ts = -1
    fps = 0.0
    start = prev = time.monotonic()
    still = f"still within {args.max_move:.2f} of its size" if args.max_move else "no stillness check"
    print(f"Palm: {side.lower()} hand, score >= {args.min_score}, held {args.hold} s, {still}, "
          f"facing sign {FACING_SIGN}.")
    print(f"Showing camera {index}. Hold up your {side.lower()} hand. "
          "In the window: P record palm, N not palm, W wave, space stop, q quit.")

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

                # 3. MediaPipe gets the camera's own picture (so it tells
                # left from right correctly), in RGB; OpenCV gives BGR. You see
                # it mirrored like a selfie, so your right hand is on the right.
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.flip(frame, 1)
                height, width = frame.shape[:2]
                ts = max(int(time.monotonic() * 1000), last_ts + 1)   # must always go up
                last_ts = ts
                recognizer.recognize_async(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)

                with latest.lock:
                    result, result_ts, latency = latest.result, latest.timestamp_ms, latest.latency_ms

                # 4. Read the newest result (only once per result, not per frame).
                now = time.monotonic()
                hands = read_hands(result, args.swap_hands) if result is not None else []
                palm = chosen_palm(hands, side, args.min_score)
                mine = chosen_hand(hands, side)
                if result is not None and result_ts != last_result_ts:
                    last_result_ts = result_ts
                    results += 1
                    if results > 1:                 # the first one includes loading MediaPipe
                        latencies.append(latency)
                    for hand in hands:
                        if hand.side in seen:
                            seen[hand.side] += 1
                        if hand.side == side and hand.gesture == "Open_Palm":
                            palm_scores.append(hand.gesture_score)
                    if mine is not None:
                        by_mp = mine.gesture == "Open_Palm" and mine.gesture_score >= args.min_score
                        by_points = points_say_palm(mine, width, height)
                        key = ("both" if by_points else "mediapipe") if by_mp else ("points" if by_points else "neither")
                        agree[key] += 1
                        recorder.write(now - start, mine, width, height)
                    if rule.update(now, palm is not None, *palm_geometry(mine, width, height)):
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
                elif rule.state == "holding" and now - rule.moved_at < 0.3:
                    status = ("Moving: hold your palm still", WHITE)
                elif rule.state == "holding":
                    score = palm.gesture_score if palm else 0.0
                    text = f"{side} hand: Open_Palm {score:.2f}, holding {rule.held(now):.1f} of {args.hold:.1f} s"
                    status = (text, COLOUR_CHOSEN)
                elif rule.state in ("fired", "rearming"):
                    status = ("Lower your hand before the next palm", WHITE)
                else:
                    status = (f"Waiting for an open {side.lower()} palm", WHITE)
                if mine is not None:
                    out = fingers_out(mine, width, height)
                    named = ", ".join(n for n, o in zip(FINGERS, out, strict=True) if o) or "none"
                    facing = "palm facing" if palm_facing(mine, width, height) else "back of hand"
                    check = (f"Points check: {sum(out)} of 5 out ({named}); {facing}",
                             COLOUR_CHOSEN if points_say_palm(mine, width, height) else WHITE)
                else:
                    check = (f"Points check: no {side.lower()} hand", WHITE)
                if recorder.label is not None:
                    label = {"palm": "palm", "other": "not palm", "wave": "wave"}[recorder.label]
                    rec = (f"Recording {label}: {recorder.counts[recorder.label]} rows | space = stop",
                           COLOUR_RECORDING)
                else:
                    rec = ("P = record palm | N = not palm | W = wave | q = quit", WHITE)
                draw_status(cv2, frame, [
                    status,
                    check,
                    (f"{fps:4.1f} fps | {latency:3.0f} ms per frame | palms accepted: {accepted}", WHITE),
                    rec,
                ])

                # 6. Show it; quit on q or when the window is closed.
                cv2.imshow(WINDOW, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key in (ord("p"), ord("P")):
                    recorder.label = "palm"
                elif key in (ord("n"), ord("N")):
                    recorder.label = "other"
                elif key in (ord("w"), ord("W")):
                    recorder.label = "wave"
                elif key == ord(" "):
                    recorder.label = None
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()                     # the camera light goes off
        cv2.destroyAllWindows()
        recorder.close()

    # A summary to paste into the chat.
    seconds = time.monotonic() - start
    print("\nSummary")
    print(f"  {seconds:.0f} s, {frames} frames ({frames / seconds if seconds else 0:.1f} fps), "
          f"{results} results from MediaPipe")
    print(f"  time per frame: p50 {percentile(latencies, 0.5):.0f} ms, p95 {percentile(latencies, 0.95):.0f} ms")
    print(f"  hands seen: Right in {seen['Right']} results, Left in {seen['Left']}"
          f"{' (swapped)' if args.swap_hands else ''}")
    print(f"  palms accepted ({side.lower()} hand, score >= {args.min_score}, held {args.hold} s, "
          f"{still}): {accepted}")
    if palm_scores:
        # How sure MediaPipe was whenever it saw your open palm: if many scores
        # sit just under --min-score, real palms are being missed.
        below = sum(score < args.min_score for score in palm_scores) / len(palm_scores)
        print(f"  open-palm scores ({side.lower()} hand, {len(palm_scores)} results): "
              f"low 10% {percentile(palm_scores, 0.1):.2f}, middle {percentile(palm_scores, 0.5):.2f}, "
              f"high 10% {percentile(palm_scores, 0.9):.2f}; {below:.0%} under {args.min_score}")
    if sum(agree.values()):
        print(f"  open palm, {side.lower()} hand, per result: both say yes {agree['both']}, "
              f"only MediaPipe {agree['mediapipe']}, only the points check {agree['points']}, "
              f"neither {agree['neither']}")
    if recorder.path is not None:
        print(f"  recorded {recorder.counts['palm']} palm, {recorder.counts['other']} not-palm and "
              f"{recorder.counts['wave']} wave rows "
              f"in {recorder.path.relative_to(ROOT) if recorder.path.is_relative_to(ROOT) else recorder.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
