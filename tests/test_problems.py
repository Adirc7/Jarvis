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


async def test_singlish_and_sinhala_drive_the_problem_too(settings):
    plan = (HERE / "car.json").read_text(encoding="utf-8")
    app, model, said, events = lesson_app(settings, plan)
    await app.handle_text(CAR_TEXT)
    assert (await app.handle_text("c kotasa pennanna")).startswith("Part c:")             # Singlish
    assert await app.handle_text("hint ekak denna") == "It slows from v1 to zero at a3."
    assert (await app.handle_text("hari ilaga piyawara")).endswith("That gives 3.333 seconds.")
    assert await app.handle_text("mage uththaraya 33.3") == "Right: 33.33 m."
    assert "So part c is 33.33" in await app.handle_text("mulu uththaraya pennanna")
    assert (await app.handle_text("kalin eka")).startswith("The time to stop is")
    # Sinhala script: Friday takes over, and the lines are Sinhala
    assert (await app.handle_text("ඊළඟ පියවර")).endswith("ඉතින් c කොටසේ උත්තරය 33.33 metres.")
    assert app.lang.current.code == "si"
    assert (await app.handle_text("b කොටස")).startswith("b කොටස: the distance while accelerating.")
    assert "Split the motion into phases" in await app.handle_text("සාරාංශය කියන්න")
    assert len(model.requests) == 1


async def test_the_conversation_column_and_the_map_layer_by_voice(settings):
    app, model, said, events = lesson_app(settings, "x")
    assert await app.handle_text("conversation eka hide karanna") == "Hid the conversation."
    assert kinds(events, "wide")[-1] == {"on": True}
    await app.handle_text("show the conversation")
    assert kinds(events, "wide")[-1] == {"on": False}
    asked = []
    from types import SimpleNamespace as NS
    app.info = NS(call=lambda name, args: asked.append((name, json.loads(args))) or NS(result=NS(summary="Showing the wind.")),
                  names=lambda: set(), board=None)
    app.panel = "map"
    assert await app.handle_text("sulanga pennanna") == "Showing the wind."
    assert asked[-1] == ("map_view", {"action": "layer", "layer": "wind"})
    assert await app.handle_text("වලාකුළු පෙන්නන්න") == "Showing the wind."    # the stand-in's words
    assert asked[-1][1]["layer"] == "clouds"


# ---- the views of modern physics, quantum computing, linear algebra, statistics ------------------------------
def view_of(spec, given=()):
    from jarvis.knowledge.problems import Given, Part, Problem, Step
    p = Problem("t", "other", "", [Given(s, s, v) for s, v in given], {"v": spec},
                [Part("a", "x", steps=[Step("x", view="v")])])
    work(p)
    return p.shown_views.get("v"), p.notes


def test_quantum_levels_tunnelling_and_spectral_lines():
    box, _ = view_of({"quantum": {"system": "box", "L": "L", "n": [1, 2]}}, [("L", 1e-9)])
    assert box["E_shown"] == ["0.376 eV", "1.504 eV"]                              # E = n^2 h^2 / 8 m L^2
    ho, _ = view_of({"quantum": {"system": "oscillator", "omega": 1e15, "n": [0, 1]}})
    assert ho["E_eV"][1] / ho["E_eV"][0] == pytest.approx(3)                       # (n + 1/2) hbar omega
    wall, _ = view_of({"quantum": {"system": "barrier", "V0": 10, "a": 1e-10, "E": 5}})
    assert wall["T"] + wall["R"] == pytest.approx(1) and wall["T_shown"] == "0.3337"
    h, _ = view_of({"quantum": {"system": "hydrogen", "n": [2, 3], "transition": [3, 2]}})
    assert h["transition"]["shown"] == "656.1 nm" and h["transition"]["colour"] == "red"   # H-alpha


def test_a_quantum_circuit_is_simulated_exactly():
    bell, notes = view_of({"qcircuit": {"qubits": 2, "gates": [["H", 0], ["CNOT", 0, 1]]}})
    assert notes == [] and bell["states"][-1]["probs"] == [0.5, 0, 0, 0.5]
    assert bell["states"][-1]["bloch"] == [[0, 0, 0], [0, 0, 0]]                    # entangled: no direction
    ry, _ = view_of({"qcircuit": {"qubits": 1, "gates": [["RY", 0, "pi/2"]]}})
    assert ry["states"][-1]["bloch"][0] == pytest.approx([1, 0, 0], abs=1e-9)
    tof, _ = view_of({"qcircuit": {"qubits": 3, "initial": "110", "gates": [["CCX", 0, 1, 2]]}})
    assert tof["states"][-1]["probs"][7] == 1
    _, notes = view_of({"qcircuit": {"qubits": 2, "gates": [["CNOT", 0, 5]]}})
    assert notes and "isn't there" in notes[0]


def test_relativity_the_twins_and_a_black_hole():
    st, _ = view_of({"minkowski": {"beta": 0.6, "events": [{"name": "A", "x": 3, "ct": 5}],
                                   "worldlines": [{"name": "away", "path": [[0, 0], [4, 5], [0, 10]]},
                                                  {"name": "home", "path": [[0, 0], [0, 10]]}]}})
    assert st["gamma"] == pytest.approx(1.25) and st["events"][0]["x2"] == pytest.approx(0)
    assert st["events"][0]["ct2"] == pytest.approx(4) and [w["tau"] for w in st["worldlines"]] == [6, 10]
    _, notes = view_of({"minkowski": {"worldlines": [{"name": "fast", "path": [[0, 0], [5, 1]]}]}})
    assert "faster than light" in notes[0]
    sun, _ = view_of({"black_hole": {"M": 1.989e30}})
    assert sun["rs_shown"] == "2954 m" and sun["T_shown"] == "6.168 × 10^-8 K"


def test_matrices_distributions_monte_carlo_and_fields():
    m, _ = view_of({"matrix": {"A": [[2, 1], [1, 2]]}})
    assert m["det"] == pytest.approx(3) and sorted(e["value"] for e in m["eigen"]) == pytest.approx([1, 3])
    for spec, p in (({"kind": "normal", "params": {"sigma": 1}, "region": {"from": -1.96, "to": 1.96}}, 0.95),
                    ({"kind": "t", "params": {"df": 5}, "region": {"from": -2.571, "to": 2.571}}, 0.95),
                    ({"kind": "chi2", "params": {"df": 3}, "region": {"to": 7.815}}, 0.95),
                    ({"kind": "binomial", "params": {"n": 10, "p": 0.3}, "region": {"to": 3}}, 0.6496),
                    ({"kind": "poisson", "params": {"lam": 2}, "region": {"from": 0, "to": 0}}, 0.1353)):
        d, _ = view_of({"distribution": spec})
        assert d["prob"] == pytest.approx(p, abs=1e-3), spec
    mc, _ = view_of({"montecarlo": {"kind": "pi", "n": 4000, "seed": 3}})
    assert abs(mc["estimate"] - 3.1416) < 0.1 and len(mc["points"]) == 4000
    f, _ = view_of({"field": {"Fx": "-y", "Fy": "x"}})
    assert f["div"] == "0" and f["curl"] == "2"
    slope, _ = view_of({"field": {"slope": "y", "solutions": [[0, 1]], "x": [0, 1], "y": [0, 3]}})
    import math
    sol = slope["solutions"][0]
    assert sol[-1][0] > 0.99 and max(abs(y - math.exp(x)) for x, y in sol) < 1e-6    # y' = y: RK4 follows e^x


def test_a_molecule_from_pubchem_and_a_feynman_diagram(monkeypatch, tmp_path):
    from jarvis.knowledge import problem_views_more as more
    sdf = ("water\n\n\n  3  2  0  0  0  0  0  0  0  0999 V2000\n"
           "    0.0000    0.0000    0.0000 O   0  0\n    0.9572    0.0000    0.0000 H   0  0\n"
           "   -0.2400    0.9266    0.0000 H   0  0\n  1  2  1  0\n  1  3  1  0\nM  END\n")
    asked = []
    monkeypatch.setattr(more, "MOLECULE_DIR", tmp_path)
    monkeypatch.setattr("jarvis.knowledge.fetch.get_text", lambda url, timeout=None: asked.append(url) or sdf)
    water, notes = view_of({"molecule": {"name": "water"}})
    assert notes == [] and water["formula"] == "H2O" and len(water["bonds"]) == 2
    view_of({"molecule": {"name": "water"}})
    assert len(asked) == 1 and "pubchem.ncbi.nlm.nih.gov" in asked[0]              # kept on disk after once
    fey, _ = view_of({"feynman": {"lines": [{"from": [0, 0], "to": [0.5, 0.5], "type": "photon", "label": "γ"},
                                            {"from": [0, 1], "to": [0.5, 0.5], "type": "quark-ish"}]}})
    assert [ln["type"] for ln in fey["lines"]] == ["photon", "fermion"]


def test_a_lesson_can_use_the_tested_views_and_an_impossible_one_is_dropped():
    from jarvis.knowledge.lessons import parse_plan, plan_prompt, resolve
    plan = {"title": "Time dilation", "steps": [
        {"say": "The twins.", "show": {"view": {"minkowski": {"beta": 0.6, "worldlines": [
            {"name": "away", "path": [[0, 0], [4, 5], [0, 10]]}]}}}},
        {"say": "Faster than light?", "show": {"view": {"minkowski": {"worldlines": [
            {"name": "x", "path": [[0, 0], [5, 1]]}]}}}}]}
    lesson = resolve(parse_plan(json.dumps(plan)))
    assert lesson.steps[0].visual["kind"] == "pview" and lesson.steps[0].visual["data"]["worldlines"][0]["tau"] == 6
    assert lesson.steps[1].visual is None and "faster than light" in lesson.notes[0]
    prompt = plan_prompt("explain tunnelling", "", "English")
    assert '{"view":' in prompt and '"qcircuit"' in prompt and "a last resort" in prompt


def test_units_are_checked_through_the_steps_and_a_wrong_set_up_is_caught():
    from jarvis.knowledge.dimensions import dims
    assert dims("m/s^2") == (1, 0, -2, 0, 0, 0) and dims("J/(mol K)") == dims("J/mol/K") == (2, 1, -2, 0, -1, -1)
    assert dims("kg·m/s²") == dims("N") and dims("1/s") == dims("Hz") and dims("furlong") is None
    car = worked("car")
    assert all(s.result.get("units") == "ok" for p in car.parts for s in p.steps)
    acid = worked("titration")                                                   # Ka, Kw: chemistry's convention
    assert acid.notes == [] and {s.result.get("units") for p in acid.parts for s in p.steps} <= {"ok", None}
    plan = json.loads((HERE / "car.json").read_text(encoding="utf-8"))
    plan["parts"][2]["steps"][1]["calc"] = "s3 = v1*a3"                          # speed times acceleration: not metres
    wrong = work(parse_problem(json.dumps(plan)))
    assert wrong.parts[2].steps[1].result["units"] == "wrong"
    assert "(c) s3 = v1*a3: the units don't come out as m" in wrong.notes
    assert wrong.parts[0].steps[0].result["units"] == "ok"                       # the right steps stay right


def test_each_answer_is_checked_against_its_animation():
    maths, car = worked("maths"), worked("car")
    assert maths.answer_of(maths.parts[2])["view_check"] == {"ok": True, "said": "the animation agrees: the rule's estimate"}
    assert car.answer_of(car.parts[2])["view_check"]["said"] == "the animation agrees: brakes (ABS): distance"
    assert "view_check" not in car.answer_of(car.parts[4])                       # a diagram of symbols: nothing to compare
    plan = json.loads((HERE / "car.json").read_text(encoding="utf-8"))
    plan["views"]["road"]["motion"]["bodies"][0]["phases"][2]["a"] = "-a3/2"     # the animation brakes half as hard
    odd = work(parse_problem(json.dumps(plan)))
    assert odd.answer_of(odd.parts[2])["view_check"]["ok"] is False
    assert any("isn't what the animation works out" in n for n in odd.notes)


async def test_every_plan_is_kept_to_look_at(settings, tmp_path):
    settings.raw["general"]["state_dir"] = str(tmp_path / "state")
    plan = (HERE / "car.json").read_text(encoding="utf-8")
    app, model, said, events = lesson_app(settings, plan)
    await app.handle_text(CAR_TEXT)
    kept = list((tmp_path / "state" / "problems").glob("*.json"))
    assert len(kept) == 1 and kept[0].name.endswith("a-car-accelerate-cruise-brake-with-abs.json")
    data = json.loads(kept[0].read_text(encoding="utf-8"))
    assert data["question"] == CAR_TEXT and data["plan"] == plan and data["answers"]["c"]["shown"] == "33.33"


def test_collisions_rotation_heat_engines_induction_doppler_and_interference():
    from jarvis.knowledge.problem_views import view_facts

    def facts(spec):
        v, notes = view_of(spec)
        assert notes == [], notes
        return {label: value for value, unit, label in view_facts(v)}
    f = facts({"collision": {"m1": 2, "u1": 3, "m2": 1, "u2": 0, "type": "elastic"}})
    assert f["first body after"] == pytest.approx(1) and f["second body after"] == pytest.approx(4)
    assert f["kinetic energy lost"] == pytest.approx(0)
    f = facts({"collision": {"m1": 2, "u1": 3, "m2": 1, "type": "perfectly_inelastic"}})
    assert f["second body after"] == pytest.approx(2) and f["kinetic energy lost"] == pytest.approx(3)
    f = facts({"rotation": {"mode": "roll", "shape": "solid_sphere", "angle": 30, "L": 2}})
    assert f["acceleration down the slope"] == pytest.approx(9.81 * 0.5 / 1.4)      # a = g sin(theta) / (1 + 2/5)
    f = facts({"rotation": {"mode": "spin", "I": 0.5, "torque": 2, "t1": 4}})
    assert f["angular speed at the end"] == pytest.approx(16) and f["angle turned"] == pytest.approx(32)
    carnot = facts({"pv": {"gas": {"n": 1, "gamma": 1.4}, "start": {"P": 2e5, "T": 600}, "steps": [
        {"process": "isothermal", "to": {"V": 0.0499}}, {"process": "adiabatic", "to": {"V": 0.0499 * 2 ** 2.5}},
        {"process": "isothermal", "to": {"V": 0.02494 * 2 ** 2.5}},
        {"process": "adiabatic", "to": {"V": 0.02494}}]}})
    assert carnot["efficiency"] == pytest.approx(1 - 300 / 600, abs=2e-3)           # Carnot: 1 - Tc/Th
    f = facts({"induction": {"mode": "flux", "N": 100, "B": 0.2, "A": 0.01, "omega": 50, "t1": 0.3}})
    assert f["largest emf"] == pytest.approx(10, abs=0.01)                          # N B A omega
    f = facts({"induction": {"mode": "rod", "B": 0.5, "L": 0.2, "v": 3, "R": 2}})
    assert f["emf"] == pytest.approx(0.3) and f["force on the rod"] == pytest.approx(0.015)
    f = facts({"doppler": {"f": 440, "v_source": 30}})
    assert f["frequency approaching"] == pytest.approx(440 * 343 / 313)
    f = facts({"interference": {"kind": "double_slit", "wavelength": 6.5e-7, "d": 2.5e-4, "L": 1.5}})
    assert f["fringe spacing"] == pytest.approx(3.9e-3)                             # lambda L / d
    f = facts({"interference": {"kind": "grating", "wavelength": 5.89e-7, "d": 1 / 600e3, "N": 50}})
    assert f["highest order"] == 2 and f["angle of the first bright fringe"] == pytest.approx(20.7, abs=0.05)
    _, notes = view_of({"doppler": {"f": 440, "v_source": 400}})
    assert "shock wave" in notes[0]
