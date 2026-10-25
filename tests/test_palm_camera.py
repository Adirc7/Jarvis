"""The camera thread (perception/camera.py) and what a palm does in Jarvis (D29).

No real camera or MediaPipe: a pretend camera hands out frames, and pretend
"MediaPipe" reports a right palm for the first second.
"""

import asyncio
import time
from types import SimpleNamespace as NS

import numpy as np
from conftest import FakeClient

from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.events import GestureEvent
from jarvis.perception.camera import PalmCamera, hands_from_result
from jarvis.perception.gestures import HandSeen
from jarvis.state import Mode
from jarvis.telemetry import Telemetry
from jarvis.tools.web import WebTools


class FakeCap:
    def __init__(self, opened=True, frames=None):
        self.opened, self.frames, self.released = opened, frames, False

    def isOpened(self):
        return self.opened

    def read(self):
        time.sleep(1 / 60)
        if self.frames is not None:
            if self.frames == 0:
                return False, None
            self.frames -= 1
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[:, :, 2] = 200                       # red in OpenCV's BGR order
        return True, frame

    def release(self):
        self.released = True


class FakeHands:
    """Stands in for MediaPipeHands: a right palm for the first `palm_s` seconds."""

    def __init__(self, palm_s=1.0):
        self.palm_s, self.closed, self.rgb_ok, self.start = palm_s, False, True, None

    def __call__(self, model, on_hands):          # used as the hands_factory
        self.on_hands = on_hands
        return self

    def send(self, rgb, ts):
        self.rgb_ok &= bool(rgb[0, 0, 0] == 200)  # red arrived first: converted to RGB
        self.start = self.start if self.start is not None else ts
        palm = (ts - self.start) / 1000 < self.palm_s
        hands = [HandSeen("Right", "Open_Palm", 0.7, (400.0, 240.0), 90.0)] if palm else []
        self.on_hands(hands, ts, 640, 480)

    def close(self):
        self.closed = True


def make_camera(settings, tmp_path, cap=None, hands=None, events=None):
    model = tmp_path / "gesture_recognizer.task"
    model.write_bytes(b"pretend")
    events = events if events is not None else []
    cam = PalmCamera(settings, events.append, camera_factory=lambda i: cap or FakeCap(),
                     hands_factory=hands or FakeHands())
    cam.model = model
    return cam, events


def test_one_palm_gives_one_event_and_the_camera_is_released(settings, tmp_path):
    cap, hands = FakeCap(), FakeHands(palm_s=1.0)
    cam, events = make_camera(settings, tmp_path, cap, hands)
    assert cam.start() and cam.running
    time.sleep(1.6)
    cam.stop()
    assert not cam.running and cap.released and hands.closed
    assert [e.name for e in events] == ["open_palm"] and cam.palms == 1
    assert 0 <= events[0].x <= 1 and events[0].x == 1 - 400 / 640     # mirrored to match the screen
    assert hands.rgb_ok


def test_a_camera_that_does_not_open(settings, tmp_path):
    hands = FakeHands()
    cam, _ = make_camera(settings, tmp_path, FakeCap(opened=False), hands)
    assert not cam.start() and "didn't open" in cam.error and hands.closed


def test_no_model_says_how_to_get_it(settings, tmp_path):
    cam, _ = make_camera(settings, tmp_path)
    cam.model = tmp_path / "missing.task"
    assert not cam.start() and "download_models.py" in cam.error


def test_no_mediapipe_says_how_to_install(settings, tmp_path):
    def no_mediapipe(model, cb):
        raise ImportError("No module named 'mediapipe'")
    cam, _ = make_camera(settings, tmp_path, hands=no_mediapipe)
    assert not cam.start() and "update.cmd" in cam.error


def test_a_camera_that_stops_sending_ends_quietly(settings, tmp_path):
    cap = FakeCap(frames=3)
    cam, _ = make_camera(settings, tmp_path, cap)
    assert cam.start()
    cam._thread.join(5)
    assert not cam.running and "stopped sending" in cam.error and cap.released


def test_a_broken_model_file_is_reported_not_raised(settings, tmp_path):
    from jarvis.perception.camera import MediaPipeHands
    cam, _ = make_camera(settings, tmp_path, hands=MediaPipeHands)     # the real one, on a pretend model
    assert not cam.start() and "gesture model" in cam.error


def test_hands_from_a_mediapipe_result():
    def cat(name, score):
        return NS(category_name=name, score=score)

    points = [NS(x=0.5, y=0.8)] + [NS(x=0.5, y=0.5)] * 20
    result = NS(hand_landmarks=[points], handedness=[[cat("Right", 0.98)]], gestures=[[cat("Open_Palm", 0.66)]])
    (hand,) = hands_from_result(result, 640, 480)
    assert (hand.side, hand.gesture, hand.score, hand.side_score) == ("Right", "Open_Palm", 0.66, 0.98)
    assert round(hand.size) == 144


# ---- what a palm does in Jarvis -------------------------------------------------
class BusySink:
    """A voice that is still talking."""
    spoken = True

    def __init__(self):
        self.stops = 0

    @property
    def busy(self):
        return True

    def stop(self):
        self.stops += 1


def make_app(settings, sink=None, web=None, camera_factory=None):
    out = []
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", FakeClient(["Ok."]))]),
              out=lambda *a, **k: out.append("".join(map(str, a))), web=web, camera_factory=camera_factory)
    if sink is not None:
        app.sink = sink
    return app, out


async def palm(app):
    app.bus.bind()
    task = asyncio.create_task(app._control_task())
    await asyncio.sleep(0)
    app.bus.publish(GestureEvent(name="open_palm", x=0.6, y=0.5, confidence=0.7))
    await asyncio.sleep(0.01)
    task.cancel()


async def test_a_palm_while_jarvis_talks_stops_it(settings):
    sink = BusySink()
    app, out = make_app(settings, sink=sink)
    gen = app.state.cancel_generation
    await palm(app)
    assert sink.stops == 1 and app.state.cancel_generation == gen + 1
    assert app.state.mode == Mode.IDLE                 # not PAUSED: Jarvis stays ready
    assert any("[palm] stopped" in line for line in out)


async def test_a_palm_pauses_and_plays_a_video_jarvis_opened(settings):
    keys = []
    web = WebTools(opener=lambda url: None, media_key=lambda: keys.append("play/pause"))
    web.pages, web.playing = ["https://www.youtube.com/watch?v=a1"], True
    app, _ = make_app(settings, web=web)
    await palm(app)
    assert keys == ["play/pause"] and web.playing is False
    await palm(app)
    assert keys == ["play/pause"] * 2 and web.playing is True


async def test_a_palm_otherwise_does_nothing(settings):
    keys = []
    web = WebTools(opener=lambda url: None, media_key=lambda: keys.append("play/pause"))
    web.pages = ["https://www.youtube.com/results?search_query=x"]   # a results page, not a video
    app, out = make_app(settings, web=web)
    gen = app.state.cancel_generation
    await palm(app)
    assert keys == [] and app.state.cancel_generation == gen and not any("[palm]" in line for line in out)


async def test_camera_on_and_off_by_command(settings):
    class FakeCamera:
        error, palms = None, 0

        def __init__(self):
            self.running = False

        def start(self):
            self.running = True
            return True

        def stop(self):
            self.running = False

    cam = FakeCamera()
    app, out = make_app(settings, camera_factory=lambda: cam)
    await app._command("/camera on")
    assert cam.running and any("[camera on]" in line for line in out)
    await app._command("/camera off")
    assert not cam.running and any("[camera off]" in line for line in out)


def test_the_camera_is_off_by_default(settings):
    assert settings.get("gestures.enabled") is False
