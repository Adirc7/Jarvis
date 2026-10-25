"""The camera for palm to pause: a background thread, MediaPipe and PalmTrigger.

    camera frame (unmirrored) -> MediaPipe Gesture Recognizer (live stream)
        -> HandSeen for each hand -> PalmTrigger -> on_palm(GestureEvent)

MediaPipe gets the camera's own, unmirrored picture: fed a mirrored one, it
swaps left and right hands (found on the laptop, 25 Oct). The camera runs
only while switched on ([gestures] enabled = true, or /camera on), and frames
are dropped as soon as MediaPipe has read them: nothing is saved (D7).

The parts that need a real camera and MediaPipe (open_camera,
MediaPipeHands) can be swapped for fakes, so tests run without either.
"""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ..events import GestureEvent
from .gestures import HandSeen, PalmSettings, PalmTrigger

HandsCallback = Callable[[list[HandSeen], int, int, int], None]   # hands, timestamp_ms, width, height


def hands_from_result(result: Any, width: int, height: int) -> list[HandSeen]:
    """MediaPipe's GestureRecognizerResult -> one HandSeen per hand, in pixels."""
    hands = []
    for i, points in enumerate(result.hand_landmarks):
        side = result.handedness[i][0] if result.handedness and result.handedness[i] else None
        best = result.gestures[i][0] if result.gestures and result.gestures[i] else None
        hands.append(HandSeen.from_points(
            side.category_name if side else "?",
            best.category_name if best else "None",
            best.score if best else 0.0,
            [(p.x, p.y) for p in points], width, height,
            side_score=side.score if side else 0.0))
    return hands


class MediaPipeHands:
    """MediaPipe's Gesture Recognizer in live-stream mode: send frames, get hands back.

    Live stream means MediaPipe skips frames while it's busy, so it never
    falls behind the camera; results arrive on its own thread.
    """

    def __init__(self, model_path: Path, on_hands: HandsCallback):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        self._size: dict[int, tuple[int, int]] = {}

        def on_result(result, image, timestamp_ms: int) -> None:
            width, height = self._size.pop(timestamp_ms, (image.width, image.height))
            on_hands(hands_from_result(result, width, height), timestamp_ms, width, height)

        options = vision.GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=2,                       # so the chosen hand can be picked out
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            result_callback=on_result)
        self._recognizer = vision.GestureRecognizer.create_from_options(options)

    def send(self, rgb, timestamp_ms: int) -> None:
        height, width = rgb.shape[:2]
        if len(self._size) > 100:             # results for skipped frames never come back
            self._size.clear()
        self._size[timestamp_ms] = (width, height)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        self._recognizer.recognize_async(image, timestamp_ms)

    def close(self) -> None:
        self._recognizer.close()


def open_camera(index: int):
    """The laptop camera at 640 x 480 through OpenCV (DirectShow on Windows: it opens faster)."""
    import cv2

    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return cap


class PalmCamera:
    """Watches for a deliberate right palm in a background thread.

    `on_palm` is called (from the camera's thread) with a GestureEvent named
    "open_palm" once per accepted palm; pass `bus.publish_threadsafe`.
    """

    def __init__(self, settings: Any, on_palm: Callable[[GestureEvent], None], *,
                 trigger: PalmTrigger | None = None,
                 camera_factory: Callable[[int], Any] = open_camera,
                 hands_factory: Callable[[Path, HandsCallback], Any] = MediaPipeHands,
                 clock: Callable[[], float] = time.monotonic,
                 log: Callable[..., None] | None = None):
        self.settings = settings
        self.on_palm = on_palm
        self.trigger = trigger or PalmTrigger(PalmSettings.from_settings(settings))
        self.camera_factory = camera_factory
        self.hands_factory = hands_factory
        self.clock = clock
        self.log = log or (lambda event, **fields: None)
        self.index = int(settings.get("vision.camera_index", 0))
        self.model = settings.path("vision.gesture_model", "models/gesture_recognizer.task")
        self.fps = float(settings.get("gestures.fps", 15))
        self.error: str | None = None        # why it stopped or couldn't start, in plain words
        self.palms = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()        # the trigger is used from MediaPipe's thread only, but be safe

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Open the camera and start watching. False (with `error` set) if it can't."""
        if self.running:
            return True
        self.error = None
        if not Path(self.model).exists():
            self.error = f"no gesture model at {self.model}; run: uv run python scripts/download_models.py"
            return False
        try:
            hands = self.hands_factory(Path(self.model), self._on_hands)
        except ImportError as exc:
            self.error = f"MediaPipe isn't installed ({exc}); run scripts\\update.cmd"
            return False
        except Exception as exc:  # noqa: BLE001 - e.g. a broken model file
            self.error = (f"MediaPipe couldn't load the gesture model ({type(exc).__name__}); "
                          "download it again: uv run python scripts/download_models.py")
            return False
        try:
            cap = self.camera_factory(self.index)
            if not cap.isOpened():
                cap.release()
                raise OSError(f"camera {self.index} didn't open (is another app using it?)")
        except Exception as exc:  # noqa: BLE001 - any camera failure just means no camera
            hands.close()
            self.error = str(exc)
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(cap, hands), name="palm-camera", daemon=True)
        self._thread.start()
        self.log("camera_on", camera=self.index, fps=self.fps)
        return True

    def stop(self, timeout: float = 2.0) -> None:
        """Stop watching and release the camera (its light goes off)."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
            self.log("camera_off", palms=self.palms)

    # ---- the camera's thread --------------------------------------------------
    def _run(self, cap, hands) -> None:
        last_sent = 0.0
        last_ts = -1
        failures = 0
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    failures += 1
                    if failures > 50:
                        self.error = "the camera stopped sending pictures"
                        self.log("camera_failed", reason=self.error)
                        break
                    time.sleep(0.02)
                    continue
                failures = 0
                now = self.clock()
                if now - last_sent < 1 / self.fps:      # about 15 a second is plenty for a palm
                    continue
                last_sent = now
                rgb = frame[:, :, ::-1].copy()          # OpenCV gives BGR; MediaPipe wants RGB
                ts = max(int(now * 1000), last_ts + 1)  # must always go up
                last_ts = ts
                hands.send(rgb, ts)
                # The frame is dropped here: nothing keeps it.
        except Exception as exc:  # noqa: BLE001 - never take Jarvis down with the camera
            self.error = f"{type(exc).__name__}: {exc}"
            self.log("camera_failed", reason=self.error[:200])
        finally:
            cap.release()
            try:
                hands.close()
            except Exception as exc:  # noqa: BLE001
                self.log("camera_close_failed", error=str(exc)[:200])

    def _on_hands(self, hands: Sequence[HandSeen], timestamp_ms: int, width: int, height: int) -> None:
        try:
            with self._lock:
                accepted = self.trigger.update(timestamp_ms / 1000, hands)
                hand = self.trigger.chosen(hands) if accepted else None
            if hand is not None:
                self.palms += 1
                x, y = hand.centre
                # The picture isn't mirrored, so x is flipped to match what you see.
                self.on_palm(GestureEvent(name="open_palm", x=1 - x / width, y=y / height,
                                          confidence=hand.score))
        except Exception as exc:  # noqa: BLE001 - runs on MediaPipe's thread; must not raise
            self.log("camera_callback_failed", error=str(exc)[:200])
