"""The board (working, formulas, graphs) and moving the map, in Jarvis's window; tools offered by topic."""

import json
from types import SimpleNamespace as NS

import pytest
from conftest import FakeClient
from test_knowledge import NOW, TwoStep, make_info
from test_weather import weather

from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.knowledge.mathcheck import MathError, check, sample
from jarvis.telemetry import Telemetry
from jarvis.tools.info import InfoTools


class Screen:
    """The window as the tools see it: what was shown, and whether a window is open."""

    def __init__(self, open_=True):
        self.open, self.shown = open_, []

    def __call__(self, kind, data):
        self.shown.append((kind, data))
        return self.open


def info_with_screen(tmp_path, open_=True):
    screen = Screen(open_)
    info = InfoTools(tmp_path / "Jarvis", weather=weather(), opener=lambda u: None, now=lambda: NOW, screen=screen)
    return info, screen


# ---- the board ------------------------------------------------------------------------------
def test_sympy_writes_the_board_and_draws_graphs():
    done = check("integrate", "x^2 sin(x)", "x")
    assert done.latex.startswith("\\int x^{2} \\sin{\\left(x \\right)}\\, dx = ") and done.latex.endswith("+ C")
    assert check("solve", "x^2 - 5x + 6 = 0").latex.endswith("x = 2, \\; 3")
    points = sample("1/x", "x", -1, 1, 21)
    assert len(points) == 21 and points[10] == [0.0, None]              # undefined at 0: a gap, not a spike
    assert points[0] == [-1.0, -1.0]
    gauss = sample("exp(-x^2/2)/sqrt(2 pi)", "x", -3, 3, 61)
    assert max(y for _, y in gauss) == pytest.approx(0.398942, abs=1e-5)
    with pytest.raises(MathError):
        sample("x + y", "x")                                              # one variable only
    with pytest.raises(MathError):
        sample("__import__('os')", "x")                                   # never Python
    with pytest.raises(MathError):
        sample("x", "x", 5, 1)


def test_show_on_board_puts_working_and_graphs_in_the_window(tmp_path):
    info, screen = info_with_screen(tmp_path)
    args = {"title": "The Gaussian (normal) distribution",
            "steps": [{"text": "The density of a normal distribution", "math": "f(x)=\\frac{1}{\\sigma\\sqrt{2\\pi}}e^{-\\frac{(x-\\mu)^2}{2\\sigma^2}}"},
                      {"text": "About 68% of the area lies within one sigma of the mean"}],
            "graphs": [{"expression": "exp(-x^2/2)/sqrt(2 pi)", "from": -4, "to": 4, "label": "mu = 0, sigma = 1"},
                       {"expression": "os.system(1)", "label": "bad"}]}
    out = info.call("show_on_board", json.dumps(args))
    assert out.status == "claimed"
    kind, board = screen.shown[-1]
    assert kind == "board" and board["title"] == args["title"] and len(board["steps"]) == 2
    assert len(board["plots"]) == 1 and board["plots"][0]["label"] == "mu = 0, sigma = 1"
    text = out.result.data["for_model"]
    assert "on the board in Jarvis's window" in text and "couldn't draw os.system(1)" in text
    assert "explain it in words" in text and info.board is board
    too_many = {"title": "x", "steps": [{"text": "a"}] * 13}
    assert info.call("show_on_board", json.dumps(too_many)).status == "refused"
    odd = {"title": "x", "steps": [{"text": "a", "script": "alert(1)"}]}
    assert info.call("show_on_board", json.dumps(odd)).status == "refused"    # unknown keys: refused


def test_checked_maths_lands_on_the_board(tmp_path):
    info, screen = info_with_screen(tmp_path)
    info.call("check_maths", json.dumps({"task": "differentiate", "expression": "x^3"}))
    info.call("check_maths", json.dumps({"task": "integrate", "expression": "x^2"}))
    kind, board = screen.shown[-1]
    assert kind == "board" and [s["math"] for s in board["steps"]] == [
        "\\frac{d}{d x} x^{3} = 3 x^{2}", "\\int x^{2}\\, dx = \\frac{x^{3}}{3} + C"]


# ---- moving the map -------------------------------------------------------------------------------
def test_the_map_moves_where_asked(tmp_path):
    info, screen = info_with_screen(tmp_path)
    out = info.call("map_view", '{"action": "focus", "place": "Sri Lanka"}')
    assert out.status == "claimed" and out.result.summary == "Showing Sri Lanka."
    cmd = screen.shown[-1][1]
    assert cmd["action"] == "focus" and (cmd["lat"], cmd["lon"], cmd["zoom"]) == (7.9, 80.8, 7)
    info.call("map_view", '{"action": "focus", "place": "Malabe"}')         # a town: Open-Meteo finds it
    assert screen.shown[-1][1]["zoom"] == 11 and screen.shown[-1][1]["lat"] == pytest.approx(6.904)
    assert info.call("map_view", '{"action": "zoom_in"}').result.summary == "Zooming in."
    assert info.call("map_view", '{"action": "focus"}').status == "failed"
    assert info.call("map_view", '{"action": "focus", "place": "Nowhere at all"}').status == "failed"
    closed, _ = info_with_screen(tmp_path, open_=False)
    assert "isn't open" in closed.call("map_view", '{"action": "zoom_in"}').text


async def test_leaving_the_map_closes_it_without_asking_the_model(settings):
    client = FakeClient(["should not be asked"])
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", client)]),
              out=lambda *a, **k: None)
    events = []
    app.view = NS(publish=lambda kind, **d: events.append((kind, d)), viewers=1)
    app.panel = "map"
    assert await app.handle_text("Okay, please leave from the map") == "Closed the map."
    assert ("panel", {"action": "close"}) in events and app.panel == "" and client.calls == 0
    await app.handle_text("go back to the menu")                          # no panel open: the model decides
    assert client.calls == 1


def test_the_window_tells_jarvis_which_panel_it_shows(settings):
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None)
    app._window_ui({"panel": "board"})
    assert app.panel == "board"
    app._window_ui({"panel": "weird"})
    assert app.panel == "board"
    app._window_ui({"panel": ""})
    assert app.panel == ""


# ---- only the tools a request is about -----------------------------------------------------------
def offered(app, text, route="general"):
    _, specs, groups = app._tools_for(text, route)
    return {s["function"]["name"] for s in specs}, groups


def test_tools_are_offered_by_topic(settings, tmp_path):
    info, _ = make_info(tmp_path)
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None, info=info)
    names, groups = offered(app, "will it rain in Kaduwela this week?")
    assert groups == {"weather"} and "get_weather" in names and "get_news" not in names
    names, _ = offered(app, "what's going on in England right now?")
    assert "get_news" in names and "get_weather" not in names
    names, groups = offered(app, "can we solve x^2 - 5x + 6 = 0", route="maths")
    assert {"check_maths", "show_on_board"} <= names and "get_news" not in names
    assert offered(app, "hello Jarvis") == (set(), set())                     # just talk: no tools to pay for
    app.panel = "map"
    assert "map_view" in offered(app, "show Sri Lanka and zoom in")[0]
    app.panel = ""
    app.recent_info, app.recent_kinds = (__import__("time").monotonic(), "data"), ["news"]
    assert "read_article" in offered(app, "tell me more about the second one")[0]   # a follow-up
    settings.raw["tools"]["model_tools"] = "always"
    assert {"get_news", "get_weather", "check_maths", "map_view"} <= offered(app, "hello")[0]


async def test_a_board_question_end_to_end(settings, tmp_path):
    info, screen = info_with_screen(tmp_path)
    model = TwoStep("show_on_board", json.dumps({"title": "Gaussian", "steps": [{"math": "e^{-x^2}"}]}),
                    ["Here's the Gaussian on the board, sir."])
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]),
              out=lambda *a, **k: None, info=info)
    reply = await app.handle_text("explain the gaussian distribution on the board")
    assert reply == "Here's the Gaussian on the board, sir." and screen.shown[-1][0] == "board"
    first = {s["function"]["name"] for s in model.requests[0]["tools"]}
    assert "show_on_board" in first and "get_news" not in first


# ---- the answer goes to another model than the tool call -----------------------------------------
async def test_the_answer_tries_another_model_first():
    a, b = FakeClient(["from a"]), FakeClient(["from b"])
    llm = FallbackLLM([Provider("groq_oss", "big", a), Provider("groq_qwen", "qwen", b)])
    text = "".join([x async for x in llm.stream_text([{"role": "user", "content": "hi"}], avoid="groq_oss")])
    assert text == "from b" and a.calls == 0
    text = "".join([x async for x in llm.stream_text([{"role": "user", "content": "hi"}])])
    assert text == "from a"


def test_a_table_in_a_reply_goes_on_the_board(settings, tmp_path):
    from jarvis.app import markdown_tables
    reply = ("Here's the comparison, sir.\n\n| Model | Speed | Notes |\n|---|:---:|---|\n| **gpt-oss** | fast | good |\n"
             "| qwen | faster | ok |\n\nAnything else?")
    assert markdown_tables(reply) == [[["Model", "Speed", "Notes"], ["gpt-oss", "fast", "good"],
                                       ["qwen", "faster", "ok"]]]
    assert markdown_tables("a | b, no table here") == []
    info, screen = info_with_screen(tmp_path)
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None, info=info)
    app.view = NS(viewers=1, publish=lambda *a, **k: None)
    app._tables_to_board(reply)
    kind, board = screen.shown[-1]
    assert kind == "board" and board["steps"][0]["table"][1] == ["gpt-oss", "fast", "good"]
    app.view.viewers = 0
    screen.shown.clear()
    app._tables_to_board(reply)                                      # no window open: nothing to show
    assert screen.shown == []


def test_a_place_found_once_is_remembered_and_a_service_error_isnt_nowhere():
    from test_weather import Web, web

    from jarvis.knowledge.weather import Weather, WeatherError
    w = web()
    finder = Weather(get=w)
    assert finder.find("Malabe").name == "Malabe"
    asked = len(w.asked)
    assert finder.find("malabe ").name == "Malabe" and len(w.asked) == asked     # not asked again
    failing = Weather(get=Web({"geocoding-api": json.dumps({"error": True, "reason": "busy"})}))
    with pytest.raises(WeatherError):
        failing.find("New York")
