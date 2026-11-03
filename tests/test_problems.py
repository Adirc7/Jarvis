"""Worked problems: the plan, SymPy working out every step, the views' numbers, practice, marking an answer,
and Jarvis taking you through it part by part (problem_mode.py)."""

import json
from pathlib import Path

import pytest
from test_lessons import Scripted, kinds, lesson_app  # noqa: F401 - Scripted: the app's model

from jarvis.knowledge.problems import (
    ProblemError,
    check_answer,
    evaluate,
    parse_problem,
    practice,
    show_number,
    work,
)
from jarvis.problem_mode import read_questions, spoken_number

HERE = Path(__file__).parent / "problems"


def worked(name: str):
    return work(parse_problem((HERE / f"{name}.json").read_text(encoding="utf-8")))


def answers(problem):
    return {p.id: problem.answer_of(p).get("shown") for p in problem.parts}


# ---- SymPy works it out ------------------------------------------------------------------------------
def test_the_car_every_number_from_sympy_and_the_road_from_the_same_numbers():
    car = worked("car")
    assert car.notes == []
    assert answers(car) == {"a": "20", "b": "80", "c": "33.33", "d": "16.38", "e": "7.848"}
    road = car.shown_views["road"]
    stop = road["bodies"][0]["phases"][-1]
    assert road["T"] == pytest.approx(31.333, abs=1e-3) and stop["abs"] and stop["t0"] == 28 and stop["s0"] == 480
    assert road["bodies"][0]["s_end"] == pytest.approx(513.33, abs=0.01)          # the same as part (d)
    braking = car.parts[2].steps[1]
    assert braking.calc.startswith("s3 = solve(0 = v1^2") and braking.result["shown"] == "33.33"
    assert braking.highlight == {"area": [28.0, pytest.approx(31.333, abs=1e-3)], "graph": "v"}
    assert car.shown_views["tyre"]["forces"][1] == {"name": "friction", "symbol": "f", "value": None,
                                                    "shown": "mu*m*g", "angle": 180}   # no mass given: a symbol


def test_maths_titration_and_circuit_are_worked_out_and_drawn():
    maths = worked("maths")
    assert answers(maths) == {"a": "2.095", "b": "6.234", "c": "6.275"}
    ann = maths.shown_views["area"]["annotations"]
    assert ann["area"]["shown"] == "6.234" and ann["riemann"]["shown"] == "6.275"   # the view agrees with part (c)
    assert maths.shown_views["newton"]["annotations"]["points"][0][1] == 0.0       # a root's y is 0
    acid = worked("titration")
    assert answers(acid) == {"a": "2.875", "b": "25", "c": "4.745", "d": "8.722"}
    curve = acid.shown_views["curve"]
    assert curve["V_eq"] == 25 and curve["pH_half"] == pytest.approx(4.745, abs=1e-3)
    assert curve["pH_eq"] == pytest.approx(8.722, abs=0.01)                        # the exact curve agrees with (d)
    circuit = worked("circuit")
    assert circuit.notes == [] and answers(circuit) == {"a": "6.5", "b": "1.846", "c": "1.231"}   # I is a current
    r3 = next(e for e in circuit.shown_views["circ"]["elements"] if e["name"] == "R3")
    assert r3["I"] == pytest.approx(1.2308, abs=1e-4)
    assert circuit.shown_views["eq"]["K_shown"] == "0.01447"


def test_a_step_is_maths_only_and_a_bad_one_is_marked_not_made_up():
    assert float(evaluate("v = sqrt(u^2 + 2*a*s)", {"u": 0, "a": 2, "s": 4})[1]) == 4
    assert float(evaluate("x = solve(x^2 = 9, x)", {}, "negative")[1]) == -3
    for bad in ("x = __import__('os')", "x = a.real", "x = open(1)", "x = exec(1)", "sin = 2", "x = [1, 2]"):
        with pytest.raises(ProblemError):
            evaluate(bad, {"a": 1})
    plan = json.loads((HERE / "car.json").read_text(encoding="utf-8"))
    plan["parts"][0]["steps"][0]["calc"] = "v1 = speed_of_light * 2"
    car = work(parse_problem(json.dumps(plan)))
    assert car.parts[0].steps[0].result == {"ok": False, "note": "unknown name 'speed_of_light'"}
    assert check_answer(car, "a", "20")[0] is None                                  # nothing to mark it against


def test_answers_are_marked_with_the_slip_named():
    car = worked("car")
    assert check_answer(car, "a", "v = 20 m/s") == (True, "Right: 20 m/s.")
    assert check_answer(car, "a", "72 km/h")[1].startswith("Close: the number is off by a unit")
    assert check_answer(car, "a", "-20")[1].startswith("The size is right but the sign")
    assert check_answer(car, "c", "33.3")[0] is True and check_answer(car, "c", "40")[0] is False
    assert check_answer(car, "b", "8 x 10^1")[0] is True
    assert check_answer(car, "z", "1")[0] is None
    assert show_number(5.27e-6) == "5.27 × 10^-6" and spoken_number("5.27 × 10^-6") == "5.27 times ten to the minus 6"


def test_practice_is_the_same_problem_with_new_numbers_worked_out_again():
    car = worked("car")
    new = practice(car, seed=4)
    g, g0 = {x.symbol: x.value for x in new.given}, {x.symbol: x.value for x in car.given}
    assert g["g"] == 9.81 and g["a1"] != g0["a1"]                                   # constants stay
    assert f"{g['a1']:g} m/s^2" in new.statement_text()
    assert answers(new)["a"] == show_number(g["a1"] * g["t1"])
    assert new.as_data()["seed"] == new.seed != 0


def test_a_plan_with_no_parts_or_a_sketch_view_is_refused_or_dropped():
    with pytest.raises(ProblemError):
        parse_problem('{"title": "x", "parts": []}')
    plan = json.loads((HERE / "car.json").read_text(encoding="utf-8"))
    plan["views"]["doodle"] = {"lesson": {"sketch": "a car"}}
    car = work(parse_problem(json.dumps(plan)))
    assert "doodle" not in car.shown_views and any("no model-drawn sketches" in n for n in car.notes)


def test_a_sheet_read_from_a_photo_becomes_questions():
    qs = read_questions('```json\n{"questions": [{"label": "1", "text": "A ball is thrown up at 20 m/s. Find its height."},'
                        ' {"label": "2", "text": "x"}]}\n```')
    assert qs == [{"label": "1", "text": "A ball is thrown up at 20 m/s. Find its height."}]
    with pytest.raises(ProblemError):
        read_questions("I can't see a problem.")


# ---- Jarvis takes you through it -------------------------------------------------------------------
CAR_TEXT = ("Solve this problem: a car starts from rest and accelerates at 2.5 m/s^2 for 8 s, travels at constant "
            "speed for 20 s, then brakes with ABS at 6 m/s^2 until it stops. (a) top speed (b) distance accelerating")


async def test_jarvis_opens_the_problem_and_goes_part_by_part(settings):
    plan = (HERE / "car.json").read_text(encoding="utf-8")
    app, model, said, events = lesson_app(settings, plan)
    reply = await app.handle_text(CAR_TEXT)
    assert reply.startswith("A car: accelerate, cruise, brake with ABS. 5 parts.")
    assert "Plan it. JSON only." in model.requests[0]["messages"][-1]["content"]
    shown = kinds(events, "problem")[-1]
    assert shown["data"]["parts"][0]["answer"] == "20" and app.panel == "problem"
    assert "road" in shown["data"]["views"] and shown["state"]["part"] == ""
    assert (await app.handle_text("part c")).startswith("Part c: the time and distance to stop.")
    assert await app.handle_text("hint") == "It slows from v1 to zero at a3."
    assert (await app.handle_text("next step")).endswith("That gives 3.333 seconds.")
    last = await app.handle_text("next")
    assert "That gives 33.33 metres. So part c is 33.33 metres." in last
    assert kinds(events, "problem_state")[-1]["state"] == {"part": "c", "shown": 2, "hint": True, "check": None,
                                                           "summary": False}
    assert await app.handle_text("I got 33.3") == "Right: 33.33 m."
    assert len(model.requests) == 1                                                 # no model needed for any of it
    app._window_ui({"problem": "solution", "part": "b", "answer": "", "index": -1})   # a button in the window
    import asyncio
    app._loop = asyncio.get_running_loop()
    app._window_ui({"problem": "solution", "part": "b", "answer": "", "index": -1})
    await asyncio.sleep(0.05)
    assert kinds(events, "problem_state")[-1]["state"]["part"] == "b"
    await app.handle_text("practice")
    assert kinds(events, "problem")[-1]["data"]["seed"] != 0
    note = app._problem_note()
    assert "(Jarvis opened a worked problem" in note


async def test_a_question_about_the_step_goes_to_the_model_with_the_problem_in_view(settings):
    plan = (HERE / "car.json").read_text(encoding="utf-8")
    app, model, said, events = lesson_app(settings, plan, "Because the speed falls to zero.")
    await app.handle_text(CAR_TEXT)
    await app.handle_text("part c")
    await app.handle_text("next step")
    reply = await app.handle_text("why do we divide the speed by the deceleration here?")
    assert reply == "Because the speed falls to zero."
    system = model.requests[-1]["messages"][0]["content"]
    assert "The user is on part (c), step 1: Time to stop" in system and "'This' and 'it' mean that step" in system


async def test_a_short_or_matlab_question_isnt_taken_for_a_problem(settings):
    app, model, said, events = lesson_app(settings, "Two.")
    assert not app._wants_problem("solve x + 2 = 4")
    assert not app._wants_problem("solve y double dash plus half y dash plus 4y equals 0 in MATLAB and plot it")
    assert app._wants_problem(CAR_TEXT)
    assert app._wants_problem("A 2 kg box slides down a 30 degree slope. (a) Find its acceleration. "
                              "(b) Find its speed after 3 s.")


def test_the_window_sends_only_known_problem_actions_and_files():
    from jarvis.ui.server import PROBLEM_JS, UPLOAD_TYPES, _ui_event
    assert _ui_event({"problem": "check", "part": "b", "answer": "25 m/s"}) == {
        "problem": "check", "part": "b", "answer": "25 m/s", "index": -1}
    with pytest.raises(ValueError):
        _ui_event({"problem": "run"})
    assert "application/pdf" in UPLOAD_TYPES and "text/html" not in UPLOAD_TYPES
    js = PROBLEM_JS.read_text(encoding="utf-8")
    assert "window.JarvisProblem" in js and "innerHTML" not in js                  # text set as text, never HTML


def test_an_upload_comes_only_from_the_page_and_only_as_a_photo_or_pdf():
    import http.client

    from jarvis.ui.server import LiveView
    got = []
    v = LiveView(port=0, on_upload=lambda kind, data: got.append((kind, len(data))))
    v.start()

    def up(body, kind="image/png", token=None, origin=None):
        conn = http.client.HTTPConnection("127.0.0.1", v.port, timeout=5)
        conn.request("POST", "/upload", body=body, headers={
            "Host": f"127.0.0.1:{v.port}", "Content-Type": kind, "X-Jarvis-Token": token or v.token,
            "Origin": origin or f"http://127.0.0.1:{v.port}"})
        status = conn.getresponse().status
        conn.close()
        return status
    try:
        assert up(b"\x89PNG fake") == 202 and got == [("image/png", 9)]
        assert up(b"<html>", kind="text/html") == 415
        assert up(b"x", token="guess") == 403 and up(b"x", origin="https://evil.example") == 403
        assert len(got) == 1
    finally:
        v.stop()
