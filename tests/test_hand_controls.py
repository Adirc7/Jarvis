"""The 3D explorer's hand controls (perception/hand_controls.py) and models (knowledge/explore_models.py),
with made-up hands: no camera."""

import math

import pytest

from jarvis.knowledge.explore_models import GROUPS, MODELS, ORDER, find_part, model_for
from jarvis.perception.gestures import HandSeen
from jarvis.perception.hand_controls import ExploreHands, pose

W, H = 640, 480


def hand(side="Right", gesture="Open_Palm", shape="open", lean=0.0, cx=320.0, cy=260.0, s=60.0, score=0.9):
    """21 points like MediaPipe's: the wrist below the middle knuckle, fingers up, leaning `lean` radians."""
    pts = {0: (0, 1), 5: (-0.35, 0.05), 9: (0, 0), 13: (0.3, 0.05), 17: (0.55, 0.15),
           1: (-0.4, 0.8), 2: (-0.7, 0.55), 3: (-0.9, 0.3)}
    if shape == "open":
        tips = {4: (-1.2, 0.0), 8: (-0.3, -1.0), 12: (0, -1.0), 16: (0.3, -0.95), 20: (0.65, -0.75)}
    elif shape == "fist":
        tips = {4: (-0.2, 0.25), 8: (-0.25, 0.3), 12: (0, 0.3), 16: (0.25, 0.3), 20: (0.45, 0.35)}
    else:                                             # pinch: thumb tip on index tip, the rest open
        tips = {4: (-0.35, -0.6), 8: (-0.35, -0.62), 12: (0, -1.0), 16: (0.3, -0.95), 20: (0.65, -0.75)}
    pts.update(tips)
    for i in range(21):                               # joints between knuckle and tip
        if i not in pts:
            base, tip = (i // 4) * 4 + 1, (i // 4) * 4 + 4
            pts[i] = pts.get(base, pts[9])
    out = []
    for i in range(21):
        x, y = pts[i]
        y -= 1                                        # rotate about the wrist
        x, y = x * math.cos(lean) - y * math.sin(lean), x * math.sin(lean) + y * math.cos(lean)
        out.append(((cx + x * s) / W, (cy + (y + 1) * s) / H))
    return HandSeen.from_points(side, gesture, score, out, W, H)


def test_how_open_the_hand_is_and_a_pinch():
    open_ = pose(hand())
    fist = pose(hand(gesture="Closed_Fist", shape="fist"))
    pinch = pose(hand(gesture="None", shape="pinch"))
    assert open_["open"] > 0.9 and fist["open"] < 0.06 and not open_["pinch"] and pinch["pinch"]
    assert not fist["pinch"]                                  # a fist's thumb touches the index too: not a pinch
    assert len(open_["points"]) == 21 and 0 <= open_["tip"][0] <= 1
    assert open_["tip"][0] == pytest.approx(1 - (320 - 0.3 * 60) / W, abs=1e-3)       # mirrored, like a mirror
    assert pose(HandSeen("Right", "Open_Palm", 0.9, (1, 1), 1)) is None                # no points: no controls


def test_leaning_the_hand_turns_it():
    assert abs(pose(hand())["roll"]) < 0.01
    left, right = pose(hand(lean=-0.5))["roll"], pose(hand(lean=0.5))["roll"]
    assert left * right < 0 and abs(abs(left) - 0.5) < 0.05


def test_your_hand_leads_a_pinch_picks_once_and_a_peace_sign_brings_the_next_model():
    c = ExploreHands("right")
    two = c.update(0.0, [hand("Left", score=0.99), hand("Right", score=0.7)])
    assert [p["side"] for p in two["hands"]] == ["Right", "Left"] and two["events"] == []
    assert c.update(0.1, [hand(shape="pinch")])["events"] == ["pinch"]
    assert c.update(0.2, [hand(shape="pinch")])["events"] == []                         # held: one pick
    c.update(0.3, [hand()])
    assert c.update(0.35, [hand(shape="pinch")])["events"] == []                        # too soon again
    assert c.update(1.0, [hand()])["events"] == []
    assert c.update(1.1, [hand(shape="pinch")])["events"] == ["pinch"]
    assert c.update(2.0, [hand(gesture="Victory")])["events"] == []
    assert c.update(2.7, [hand(gesture="Victory")])["events"] == ["next"]
    assert c.update(3.5, [hand(gesture="Victory")])["events"] == []                      # once per peace sign
    c.update(3.6, [])
    c.update(4.0, [hand(gesture="Victory")])
    assert c.update(4.7, [hand(gesture="Victory")])["events"] == ["next"]


def test_the_models_are_complete_and_named_parts_are_found():
    assert ORDER == list(MODELS)
    for model in MODELS.values():
        ids = [p["id"] for p in model["parts"]]
        assert len(ids) == len(set(ids)) >= 10
        for part in model["parts"]:
            assert part["group"] in GROUPS and part["shapes"] and len(part["out"]) == 3 and len(part["desc"]) > 30
            for shape in part["shapes"]:
                assert shape["t"] in ("box", "cyl", "torus", "sphere", "tube", "spring")
    assert model_for("take the engine apart") == "engine" and model_for("explode a motorbike") == "motorcycle"
    assert model_for("show me the inside of a car") == "sports_car" and model_for("what is a star") is None
    car, engine = MODELS["sports_car"], MODELS["engine"]
    assert find_part(car, "explain the gear box")["id"] == "gearbox"
    assert find_part(car, "the front left wheel")["id"] == "wheel_front_left"
    assert find_part(engine, "show me a piston")["id"] == "pistons"
    assert find_part(car, "what's for dinner") is None


# ---- in Jarvis -----------------------------------------------------------------------------------------
class FakeCamera:
    def __init__(self):
        self.running, self.on_hands, self.error, self.stopped = False, None, None, 0

    def start(self):
        self.running = True
        return True

    def stop(self):
        self.running, self.stopped = False, self.stopped + 1


def explorer_app(settings, words=("The gearbox changes the ratio between engine and wheels.",)):
    from types import SimpleNamespace as NS

    from conftest import FakeClient

    from jarvis.agent.llm import FallbackLLM, Provider
    from jarvis.app import App
    from jarvis.telemetry import Telemetry
    client = FakeClient(list(words))
    camera = FakeCamera()
    shown = []
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("f", "m", client)]),
              out=lambda *a, **k: None, camera_factory=lambda: camera)
    app.view = NS(publish=lambda kind, **d: shown.append((kind, d)), viewers=1, url="http://127.0.0.1:1/")
    return app, camera, shown, client


async def test_ask_for_a_car_taken_apart_and_your_hand_takes_it_apart(settings):
    import asyncio
    app, camera, shown, client = explorer_app(settings)
    reply = await app.handle_text("show me a car taken apart")
    assert reply.startswith("Here's the sports car, built inside like a Toyota Supra. Open your hand slowly")
    assert client.calls == 0
    kind, data = next(e for e in shown if e[0] == "explore")
    assert data["model"]["id"] == "sports_car" and ["engine", "Four-cylinder engine"] in data["models"]
    assert camera.running and camera.on_hands is not None and app.panel == "explore"
    camera.on_hands([hand()], 1000, W, H)                                   # MediaPipe's thread
    kind, data = shown[-1]
    assert kind == "explore_hand" and data["hands"][0]["open"] > 0.9 and data["events"] == []
    assert await app.handle_text("put it back together") == "Putting it back together."
    assert ("explore_cmd", {"action": "assemble"}) in shown
    app.bus.bind(asyncio.get_running_loop())
    app._loop = asyncio.get_running_loop()
    for t in (2000, 2400, 2700):                                              # a peace sign, held
        camera.on_hands([hand(gesture="Victory")], t, W, H)
    await asyncio.sleep(0.05)
    assert [d["model"]["id"] for k, d in shown if k == "explore"][-1] == "supercar"


async def test_name_a_part_and_jarvis_pulls_it_out_and_explains_it(settings):
    import asyncio
    app, camera, shown, client = explorer_app(settings)
    await app.handle_text("take the car apart")
    assert await app.handle_text("what's the gearbox?") == ""
    for _ in range(50):
        await asyncio.sleep(0.01)
        if client.calls:
            break
    await asyncio.sleep(0.05)
    assert ("explore_cmd", {"action": "select", "part": "gearbox"}) in shown
    question = client.last_messages[-1]["content"]
    assert "gearbox of a sports car" in question and "Background:" in question
    assert ("jarvis", {"text": "The gearbox changes the ratio between engine and wheels.", "speaker": "Jarvis"}) in [
        (k, {x: d[x] for x in ("text", "speaker") if x in d}) for k, d in shown]
    app._loop = asyncio.get_running_loop()                                    # a pinch in the window
    app._window_ui({"explore": "pick", "part": "radiator", "model": ""})
    await asyncio.sleep(0.2)
    assert ("explore_cmd", {"action": "select", "part": "radiator"}) in shown


async def test_the_explorer_owns_the_hand_and_closing_turns_the_camera_off(settings):
    from jarvis.events import GestureEvent
    app, camera, shown, client = explorer_app(settings)
    await app.handle_text("explode the engine")
    stopped = []
    app.sink.stop = lambda: stopped.append(1)
    app._on_gesture(GestureEvent(name="open_palm", x=0.5, y=0.5))
    assert stopped == []                                                     # a palm is "apart" here, not "stop"
    assert await app.handle_text("close the 3D view") == "Closed the 3D view."
    assert camera.stopped == 1 and camera.on_hands is None and app._explore is None and ("explore_close", {}) in shown
    assert await app.handle_text("what is entropy") != "Closed the 3D view."  # back to normal answers


def test_the_window_can_pick_a_part_choose_a_model_or_close_and_nothing_else():
    from jarvis.ui.server import EXPLORE_JS, _ui_event
    assert _ui_event({"explore": "pick", "part": "gearbox"}) == {"explore": "pick", "part": "gearbox", "model": ""}
    assert _ui_event({"explore": "model", "model": "engine"})["model"] == "engine"
    with pytest.raises(ValueError):
        _ui_event({"explore": "run_code"})
    js = EXPLORE_JS.read_text(encoding="utf-8")
    assert "window.JarvisExplore" in js and "innerHTML" not in js               # text is set as text, never HTML


async def test_a_brand_brings_up_the_type_it_is_built_like(settings):
    from jarvis.knowledge.explore_models import model_for
    assert model_for("take a Lamborghini apart") == "supercar" and model_for("how is a Prius built") == "hybrid_car"
    assert model_for("explode a tuk tuk") == "three_wheeler" and model_for("show me a hilux in 3D") == "pickup_4x4"
    assert model_for("take apart a Tesla") == "electric_car" and model_for("a vespa") == "scooter"
    app, camera, shown, client = explorer_app(settings, words=("It splits the power with planetary gears.",))
    reply = await app.handle_text("show me a Prius taken apart")
    assert reply.startswith("Here's the hybrid car, built inside like a Toyota Prius.")
    reply = await app.handle_text("how does a Tesla work?")                    # a question: the model answers
    assert reply == "It splits the power with planetary gears." and client.calls == 1
    assert [d["model"]["id"] for k, d in shown if k == "explore"][-1] == "electric_car"   # and it's on screen


async def test_this_means_the_picked_part_and_the_hand_limits_are_settings(settings):
    settings.raw["explore"] = {"open_fist": 1.0, "open_flat": 1.5, "pinch": 0.2}
    app, camera, shown, client = explorer_app(settings, words=("It cools the coolant.",))
    await app.handle_text("take the car apart")
    assert app._explore_hands.limits == (1.0, 1.5, 0.2)
    seen = pose(hand(), 1.0, 1.5, 0.2)
    assert seen["open"] == 1.0 and seen["spread"] > 1.5 and pose(hand(shape="pinch"), pinch=0.01)["pinch"] is False
    app._explore["part"] = "radiator"
    assert (await app.handle_text("what does this do?")).startswith("It cools the coolant.")
    system = client.last_messages[0]["content"]
    assert "with the radiator picked out" in system and "they mean the radiator" in system
    app._explore_close()
    await app.handle_text("what is entropy?")
    assert "picked out" not in client.last_messages[0]["content"]


async def test_the_explorer_in_singlish_and_sinhala(settings):
    app, camera, shown, client = explorer_app(settings)
    reply = await app.handle_text("car ekak galawala athula pennanna")
    assert reply.startswith("Here's the sports car") and app._explore["model"] == "sports_car"
    assert await app.handle_text("ekathu karanna") == "Putting it back together."
    assert await app.handle_text("galawanna") == "Taking it apart."
    app._explore_close()
    await app.handle_text("ත්‍රීවීල් එකක් ගලවලා පෙන්නන්න")
    assert app._explore["model"] == "three_wheeler"
