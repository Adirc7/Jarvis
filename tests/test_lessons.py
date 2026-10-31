"""Visual lessons: the plan, what the window needs, and Jarvis teaching it step by step."""

import asyncio
import http.client
import json
from types import SimpleNamespace as NS

import pytest

from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.knowledge.lessons import SCENES, PlanError, lesson_for_the_model, parse_plan, plan_prompt, resolve, \
    sketch_html
from jarvis.knowledge.mathcheck import MathError, sample_surface
from jarvis.lesson_mode import LESSON_SPEC, OFFER_NOTE, asks_to_see_it, lesson_action, said_yes
from jarvis.telemetry import Telemetry
from jarvis.ui.server import LiveView

PLAN = {"title": "Entropy", "steps": [
    {"say": "Watch the gas: every molecule starts on the left, behind the wall.",
     "show": {"scene": "gas_box", "params": {"molecules": 60, "wall": True}}, "formula": "S = k_B \\ln W"},
    {"say": "Now the wall comes out, and they spread through the whole box.",
     "show": {"scene": "gas_box", "params": {"molecules": 60, "wall": False}}},
    {"say": "The number of ways grows so fast that we count it with a logarithm.",
     "show": {"plot": ["log(x)"], "from": 1, "to": 50}},
]}


class Scripted:
    """A model that replies from a script: text (streamed in two pieces) or ("tool", name, arguments)."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []
        self.chat = NS(completions=NS(create=self.create))

    async def create(self, model, messages, stream=False, **kwargs):
        self.requests.append({"messages": messages, **kwargs})
        reply = self.replies.pop(0) if self.replies else "(nothing more)"
        if isinstance(reply, tuple):
            chunks = [NS(choices=[NS(delta=NS(content=None, tool_calls=[NS(index=0, function=NS(
                name=reply[1], arguments=reply[2]))]))])]
        else:
            half = len(reply) // 2
            chunks = [NS(choices=[NS(delta=NS(content=part, tool_calls=None))]) for part in (reply[:half], reply[half:])]
        return Chunks(chunks)


class Chunks:
    def __init__(self, chunks):
        self.chunks = chunks

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for c in self.chunks:
            yield c


def lesson_app(settings, *replies, viewers=1):
    said, events = [], []

    def out(*args, **kwargs):
        text = " ".join(str(a) for a in args)
        if text.startswith("Jarvis: ") and kwargs.get("end") != "":     # what's said (not a streamed reply)
            said.append(text[8:])

    model = Scripted(*replies)
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]), out=out)
    app.view = NS(publish=lambda kind, **d: events.append((kind, d)), viewers=viewers, url="http://127.0.0.1:1/")
    app._open_window = lambda url: events.append(("opened", {"url": url}))

    async def no_pause(words, token):           # text mode waits to let you read; not in tests
        await asyncio.sleep(0)
    app._reading_pause = no_pause
    return app, model, said, events


def kinds(events, kind):
    return [d for k, d in events if k == kind]


# ---- the plan ------------------------------------------------------------------------------------
def test_a_plan_is_checked_and_clamped():
    text = "```json\n" + json.dumps({"title": "Waves", "steps": [
        {"say": "Two sources make ripples.", "show": {"scene": "waves_3d", "params": {"sources": 9, "wavelength": -4,
                                                                                         "speed": "fast"}}},
        {"say": "Keep watching.", "show": {}},
        {"say": "A made-up scene.", "show": {"scene": "black_hole_9000"}},
        {"say": "", "show": {"scene": "orbit"}},
        {"say": "The flow.", "show": {"diagram": "%%{init: {'theme':'forest'}}%%\nflowchart LR\n A --> B"}},
        {"say": "Not a diagram.", "show": {"diagram": "<script>alert(1)</script>"}},
        {"say": "Pendulum.", "show": {"scene": "pendulum", "params": {"show_energy": "yes"}}},
        {"say": "Over the limit.", "show": {"scene": "orbit"}},
    ]}) + "\n```"
    lesson = parse_plan(text)
    assert lesson.title == "Waves" and len(lesson.steps) == 6          # empty "say" dropped; at most 7 read
    waves = lesson.steps[0].visual
    assert waves == {"kind": "scene", "name": "waves_3d",
                     "params": {"sources": 2, "separation": 4.0, "wavelength": 0.5, "speed": 1.0}}
    assert lesson.steps[1].visual is None and lesson.steps[2].visual is None   # kept the one before; unknown dropped
    assert lesson.steps[3].visual == {"kind": "diagram", "mermaid": "flowchart LR\n A --> B"}  # no init directive
    assert lesson.steps[4].visual is None
    assert lesson.steps[5].visual["params"]["show_energy"] is True       # a string isn't a yes: the default
    assert any("black_hole" in n for n in lesson.notes) and any("Mermaid" in n for n in lesson.notes)
    for bad in ("I'd love to show you!", '{"title": "x"}', '{"steps": [{"say": ""}]}', "[1, 2]"):
        with pytest.raises(PlanError):
            parse_plan(bad)


def test_every_scene_default_is_inside_its_range():
    for name, (about, params) in SCENES.items():
        assert about and params, name
        for p, (kind, low, high, default) in params.items():
            if kind == "choice":
                assert default in low, (name, p)
            elif kind != "bool":
                assert low <= default <= high, (name, p)
    prompt = plan_prompt("explain entropy", "Entropy counts the ways...", "Sinhala")
    assert "JSON only" in prompt and "gas_box" in prompt and "in Sinhala" in prompt and "'explain entropy'" in prompt


def test_resolve_works_out_graphs_surfaces_and_pictures():
    lesson = parse_plan(json.dumps({"title": "t", "steps": [
        {"say": "a", "show": {"plot": ["sin(x)", "os.system('x')"], "from": 0, "to": 6.3}},
        {"say": "b", "show": {"surface": "sin(x) cos(y)", "x": [-3, 3], "y": [-2, 2]}},
        {"say": "c", "show": {"image": "human heart"}},
        {"say": "d", "show": {"image": "nothing at all"}},
        {"say": "e", "show": {"surface": "x + z"}},
        {"say": "f", "show": {"plot": "1/0"}},
    ]}))

    class Research:
        def wikipedia(self, query, language="en"):
            if query == "human heart":
                return NS(image="https://upload.wikimedia.org/heart.jpg", title="Heart",
                          url="https://en.wikipedia.org/wiki/Heart")
            return None

    resolve(lesson, Research())
    plot = lesson.steps[0].visual
    assert [c["label"] for c in plot["curves"]] == ["sin(x)"] and len(plot["curves"][0]["points"]) == 300
    surface = lesson.steps[1].visual
    assert len(surface["z"]) == 48 and len(surface["z"][0]) == 48 and surface["z"][0][0] == pytest.approx(
        -0.1411 * -0.4161, abs=1e-3)                                     # z[y][x]: sin(-3) cos(-2)
    assert lesson.steps[2].visual["url"].startswith("https://upload.wikimedia.org/")
    assert lesson.steps[2].visual["credit"] == "Wikipedia: Heart"
    assert lesson.steps[3].visual is None and lesson.steps[4].visual is None and lesson.steps[5].visual is None
    assert any("os.system" in n for n in lesson.notes) and any("nothing at all" in n for n in lesson.notes)
    with pytest.raises(MathError):
        sample_surface("x", (3, 1), (0, 1))


def test_a_sketch_is_cleaned_for_the_sandbox():
    code = ('```html\n<!doctype html><html><head><meta http-equiv="refresh" content="0;url=https://evil.example">'
            '</head><body><canvas id="c"></canvas><script>draw()</script></body></html>\n```')
    clean = sketch_html(code)
    assert clean == '<canvas id="c"></canvas><script>draw()</script>'
    assert sketch_html("Here's a drawing of a helix.") == ""            # no script: nothing to run
    assert sketch_html("<script>" + "x" * 30000 + "</script>") == ""


def test_what_counts_as_yes_a_control_and_show_me():
    assert all(said_yes(t) for t in ("yes", "Yes please!", "sure, go ahead", "ok", "ඔව්", "ow", "hari", "show me"))
    assert not any(said_yes(t) for t in ("no", "no thanks", "not now", "yes but not now", "එපා",
                                         "yes I think entropy is about disorder in a closed system really"))
    assert lesson_action("Next") == "next" and lesson_action("ok next please") == "next"
    assert lesson_action("Jarvis, say that again") == "again" and lesson_action("ආයේ") == "again"
    assert lesson_action("pause") == "pause" and lesson_action("go back") == "prev"
    assert lesson_action("from the start") == "restart" and lesson_action("continue") == "play"
    assert lesson_action("what happens next to the molecules") is None
    assert all(asks_to_see_it(t) for t in ("show me", "Can you show it in 3D?", "visualise that please",
                                           "ok show it on the screen", "පෙන්නන්න", "eka pennanna"))
    assert not any(asks_to_see_it(t) for t in ("show me the map of Sri Lanka", "show me YouTube", "show"))


# ---- teaching it ---------------------------------------------------------------------------------
async def test_explain_then_yes_teaches_it_step_by_step(settings):
    answer = "Entropy counts the ways a system can be arranged. Want me to show it?"
    app, model, said, events = lesson_app(settings, answer, json.dumps(PLAN))
    assert await app.handle_text("explain entropy") == answer
    first = model.requests[0]
    assert OFFER_NOTE in first["messages"][0]["content"]
    assert "show_lesson" in {t["function"]["name"] for t in first["tools"]}
    reply = await app.handle_text("yes")
    assert reply == "Entropy: a lesson in 3 steps, in the window."
    await app._lesson_task
    plan_request = model.requests[1]["messages"]
    assert "'explain entropy'" in plan_request[0]["content"] and "Entropy counts the ways" in plan_request[0]["content"]
    assert said == ["Let me draw that for you.", PLAN["steps"][0]["say"], PLAN["steps"][1]["say"],
                    PLAN["steps"][2]["say"], "That's the whole picture. Ask me about any part of it, or say again."]
    shown = kinds(events, "lesson")[0]
    assert shown["id"] == 1 and shown["title"] == "Entropy" and len(shown["steps"]) == 3
    assert shown["steps"][0]["visual"]["params"]["wall"] is True and shown["steps"][1]["visual"]["params"]["wall"] is False
    assert len(shown["steps"][2]["visual"]["curves"][0]["points"]) == 300       # SymPy's points, ready to draw
    steps = kinds(events, "lesson_step")
    assert [(s["i"], s["playing"]) for s in steps] == [(0, True), (1, True), (2, True), (2, False)]
    assert steps[-1]["done"] is True and app.panel == "lesson" and not app.lesson_playing
    assert app.history[-1]["content"].startswith("(Jarvis showed a visual lesson in his window: Entropy)")
    assert app._snapshot()["lesson"] == {"id": 1, "title": "Entropy", "step": 2, "steps": 3, "playing": False}


async def test_the_lesson_answers_to_next_back_again_and_the_buttons(settings):
    app, model, said, events = lesson_app(settings, "Here it is. Want me to show it?", json.dumps(PLAN))
    await app.handle_text("explain entropy")
    await app.handle_text("sure")
    await app._lesson_task
    said.clear()
    assert await app.handle_text("next") == "That was the last step."           # the end: nowhere to go
    assert await app.handle_text("again") == ""
    await app._lesson_task
    assert said[:2] == ["That was the last step.", PLAN["steps"][2]["say"]]
    said.clear()
    await app.handle_text("go back")
    await app._lesson_task
    assert said[0] == PLAN["steps"][1]["say"] and said[1] == PLAN["steps"][2]["say"]
    said.clear()
    app._window_ui({"lesson": "goto", "step": 0})                               # a step's dot in the window
    await app._lesson_task
    assert said[0] == PLAN["steps"][0]["say"] and len(said) == 4
    assert model.requests and len(model.requests) == 2                            # none of it asked the model


async def test_a_question_in_the_middle_pauses_it_and_continue_carries_on(settings):
    app, model, said, events = lesson_app(settings, "Want me to show it?", json.dumps(PLAN),
                                          "Because more arrangements means more entropy.")
    gate = asyncio.Event()
    real_say = app.sink.say

    async def slow_say(text, lang, token=None):
        await real_say(text, lang, token)
        if text == PLAN["steps"][1]["say"]:
            await gate.wait()                                  # step 2 is still being spoken
    app.sink.say = slow_say
    await app.handle_text("explain entropy")
    await app.handle_text("yes")
    while app.lesson_index < 1:
        await asyncio.sleep(0.01)
    assert app.lesson_playing
    reply = await app.handle_text("why does the wall matter?")
    assert reply == "Because more arrangements means more entropy." and not app.lesson_playing
    gate.set()
    await asyncio.sleep(0.05)
    assert app.lesson_index == 1 and PLAN["steps"][2]["say"] not in said     # it waited
    said.clear()
    await app.handle_text("continue")
    await app._lesson_task
    assert said[0] == PLAN["steps"][1]["say"]                                 # step 2 again: it was cut off
    app._window_ui({"panel": "map"})                                         # the window went to the map
    assert app.panel == "map"


async def test_show_me_and_the_tool_start_a_lesson_and_a_bad_plan_is_tried_again(settings):
    app, model, said, events = lesson_app(
        settings, "A lens bends light to a focus.", "Sure! Here's my plan: steps", json.dumps(PLAN),
        ("tool", "show_lesson", json.dumps({"topic": "electric field of a dipole", "focus": "in 3D"})),
        json.dumps({"title": "Dipole", "steps": [{"say": "Two charges.", "show": {"scene": "field_3d"}}]}))
    await app.handle_text("explain how a converging lens works")
    assert app._offer is None and app._teachable is not None                # no offer, but it was teaching
    assert await app.handle_text("show me") == "Entropy: a lesson in 3 steps, in the window."
    retry = model.requests[2]["messages"]
    assert "isn't a usable plan" in retry[-1]["content"]
    assert "converging lens" in model.requests[1]["messages"][0]["content"]
    await app._lesson_task
    reply = await app.handle_text("can you visualise the field of a dipole")
    assert reply == "Dipole: a lesson in 1 steps, in the window."
    assert "'electric field of a dipole (focus: in 3D)'" in model.requests[4]["messages"][0]["content"]
    assert kinds(events, "lesson")[-1]["id"] == 2


async def test_a_lesson_that_cant_be_planned_says_so(settings):
    app, model, said, events = lesson_app(settings, "Want me to show it?", "no", "still no")
    await app.handle_text("explain entropy")
    reply = await app.handle_text("yes")
    assert reply.startswith("Sorry, I couldn't put that lesson together") and app.lesson is None
    assert not kinds(events, "lesson")
    no_window, _, _, _ = lesson_app(settings, "Want me to show it?", "I can't show things here.")
    no_window.view = None
    await no_window.handle_text("explain entropy")
    assert await no_window.handle_text("yes") == "I can't show things here."        # the model answers it
    _, specs, groups = no_window._tools_for("visualise entropy", "teach")
    assert "visual" not in groups and LESSON_SPEC not in specs


async def test_the_model_sketches_what_no_scene_shows_and_fixes_it_once(settings):
    plan = {"title": "DNA", "steps": [
        {"say": "The double helix.", "show": {"sketch": "a rotating DNA double helix with labelled base pairs"}},
        {"say": "Another sketch.", "show": {"sketch": "dropped: one sketch a lesson"}}]}
    app, model, said, events = lesson_app(
        settings, "Want me to show it?", json.dumps(plan), "```html\n<canvas></canvas><script>helix()</script>\n```",
        "<canvas></canvas><script>fixedHelix()</script>")
    await app.handle_text("explain the structure of DNA")
    await app.handle_text("yes")
    await app._lesson_task
    shown = kinds(events, "lesson")[0]
    assert shown["steps"][0]["visual"]["code"] == "<canvas></canvas><script>helix()</script>"
    assert shown["steps"][1]["visual"] is None
    assert "rotating DNA double helix" in model.requests[2]["messages"][0]["content"]
    app._window_ui({"sketch_error": "ReferenceError: helix is not defined", "step": 0})
    await asyncio.sleep(0.05)
    patch = kinds(events, "lesson_patch")
    assert patch == [{"id": 1, "step": 0, "code": "<canvas></canvas><script>fixedHelix()</script>"}]
    assert "helix is not defined" in model.requests[3]["messages"][-1]["content"]
    app._window_ui({"sketch_error": "again", "step": 0})                      # one repair a sketch
    await asyncio.sleep(0.05)
    assert len(model.requests) == 4 and len(kinds(events, "lesson_patch")) == 1


def test_the_window_serves_the_lesson_and_takes_its_buttons():
    pressed = []
    v = LiveView(port=0, on_ui=pressed.append, lesson=lambda: {"id": 3, "title": "Waves", "steps": [], "step": 0})
    v.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", v.port, timeout=5)
        conn.request("GET", "/lesson.js", headers={"Host": f"127.0.0.1:{v.port}"})
        r = conn.getresponse()
        body = r.read().decode()
        assert r.status == 200 and r.getheader("Content-Type").startswith("text/javascript")
        assert "window.JarvisLesson" in body and "sandbox" in body
        conn.request("GET", "/", headers={"Host": f"127.0.0.1:{v.port}"})
        r = conn.getresponse()
        r.read()
        assert "frame-src 'self'" in r.getheader("Content-Security-Policy")
        conn.request("GET", "/lesson", headers={"Host": f"127.0.0.1:{v.port}"})
        assert json.loads(conn.getresponse().read())["title"] == "Waves"
        conn.close()

        def ui(body):
            c = http.client.HTTPConnection("127.0.0.1", v.port, timeout=5)
            c.request("POST", "/ui", body=json.dumps(body), headers={
                "Host": f"127.0.0.1:{v.port}", "Origin": f"http://127.0.0.1:{v.port}", "X-Jarvis-Token": v.token,
                "Content-Type": "application/json"})
            status = c.getresponse().status
            c.close()
            return status
        assert ui({"lesson": "next"}) == 202 and ui({"lesson": "goto", "step": 2}) == 202
        assert ui({"lesson": "rm -rf"}) == 400 and ui({"sketch_error": "x" * 999, "step": 1}) == 202
        assert ui({"other": 1}) == 400
        assert pressed == [{"lesson": "next"}, {"lesson": "goto", "step": 2},
                           {"sketch_error": "x" * 300, "step": 1}]
    finally:
        v.stop()


def test_what_the_model_hears_about_the_lesson_afterwards():
    lesson = parse_plan(json.dumps(PLAN))
    text = lesson_for_the_model(lesson)
    assert text.splitlines()[0] == "(Jarvis showed a visual lesson in his window: Entropy)"
    assert "[showing scene gas_box]" in text and "[showing plot]" in text
