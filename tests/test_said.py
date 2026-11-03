"""Jarvis's fixed lines follow the language (said.py, and the tables of the modes and tools): every line
has an English one, and every translation fills in the same values, so none can break a reply."""

from __future__ import annotations

import string

import pytest

from jarvis.explore_mode import ExploreMode  # noqa: F401 - imported so its tables load with the app's
from jarvis.knowledge.problems import MARKS, Given, Part, Problem, Step, check_answer, work
from jarvis.lesson_mode import WORDS as LESSON_WORDS
from jarvis.problem_mode import UNIT_WORDS, UNITS, spoken_number, spoken_unit
from jarvis.problem_mode import WORDS as PROBLEM_WORDS
from jarvis.said import LINES, is_said, said
from jarvis.tools.desk_phrases import LAYER_NAMES, PHRASES, layer_name


def fields(line: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(line) if name}


@pytest.mark.parametrize("table", [LINES, MARKS, LESSON_WORDS, PROBLEM_WORDS], ids=["said", "marks", "lessons",
                                                                                   "problems"])
def test_every_line_has_english_and_the_same_values_in_each_language(table):
    for key, options in table.items():
        assert options.get("en"), key
        for lang, line in options.items():
            assert fields(line) == fields(options["en"]), (key, lang)
            assert line.strip() == line and line, (key, lang)


def test_the_tools_phrases_and_layer_names_match_across_languages():
    assert set(PHRASES["si"]) == set(PHRASES["ta"])
    for key in PHRASES["si"]:
        assert fields(PHRASES["si"][key]) == fields(PHRASES["ta"][key]), key
    for lang in ("si", "ta"):
        assert set(LAYER_NAMES[lang]) == set(LAYER_NAMES["en"])
    assert layer_name("pressure", "si") == "වායු පීඩනය" and layer_name("satellite", "en") == "satellite picture"
    assert layer_name("something new", "si") == "something new"          # a layer with no name yet: as it is


def test_a_language_with_no_line_of_its_own_gets_english():
    assert said("closed_map", "si") == "සිතියම වැහුවා."
    assert said("closed_map", "fr") == "Closed the map."
    assert said("standin_slow", "ta", source=said("source_student", "ta")).startswith("இணைப்பு மெதுவாக")
    assert is_said(said("llm_unavailable", "si"), "llm_unavailable") and not is_said("hello", "llm_unavailable")


def test_the_voice_says_units_and_powers_of_ten_in_the_language():
    assert spoken_number("5.27 × 10^-6") == "5.27 times ten to the minus 6"
    assert spoken_number("5.27 × 10^-6", "si") == "5.27 ගුණ කිරීම දහයේ බලය සෘණ 6"
    assert spoken_number("3 × 10^8", "ta") == "3 பெருக்கல் பத்தின் அடுக்கு 8"
    assert spoken_unit("m/s") == "metres per second" and spoken_unit("m/s", "si") == "මීටර් තත්පරයට"
    assert spoken_unit("J/K", "si") == "J/K"                              # not in the table: said as written
    for lang, table in UNIT_WORDS.items():
        assert set(table) == set(UNITS), lang


def car(lang: str) -> Problem:
    p = Problem("Car", "mechanics", "", [Given("u", "start", 0, "m/s"), Given("a", "acceleration", 2.5, "m/s^2"),
                                          Given("t", "time", 8, "s")],
                parts=[Part("a", "the speed", unit="m/s", steps=[Step("v = u + a t", calc="v = u + a*t", unit="m/s")])],
                lang=lang)
    return work(p)


def test_the_marks_are_in_the_language_the_problem_was_asked_in():
    assert check_answer(car("en"), "a", "20") == (True, "Right: 20 m/s.")
    assert check_answer(car("si"), "a", "20") == (True, "හරි: 20 m/s.")
    assert check_answer(car("si"), "a", "-20")[1] == "අගය හරි, ඒත් ලකුණ වැරදියි: දිශාව ගැන හිතන්න."
    assert check_answer(car("ta"), "a", "72")[1].startswith("நெருக்கம்")       # 72 km/h: a units slip
    assert check_answer(car("si"), "z", "1") == (None, "z කියලා කොටසක් නෑ.")
    assert car("si").as_data()["lang"] == "si"                             # the window's card follows it too


async def test_jarvis_says_the_models_are_out_of_reach_in_the_language_of_the_turn(settings):
    from conftest import FakeClient
    from test_llm_and_app import make_app
    app, _ = make_app(settings, FakeClient(error=ConnectionError("offline")))
    assert "can't reach any language model" in await app.handle_text("what is entropy?")
    reply = await app.handle_text("එන්ට්‍රොපි කියන්නේ මොකක්ද?")           # Sinhala script: Friday
    assert app.lang.current.code == "si" and reply == said("llm_unavailable", "si")
