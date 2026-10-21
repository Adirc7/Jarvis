"""The intent pattern generator (jarvis/intents)."""

import collections

import pytest

from jarvis.intents.generate import C, Pattern, V, expand, generate
from jarvis.intents.patterns import (
    LANGUAGES,
    PER_INTENT,
    PER_STUDY_INTENT,
    STUDY_INTENTS,
    STUDY_SUBJECTS,
    STUDY_TOPICS,
    examples_per_intent,
)
from jarvis.voice.clarity import foreign_script_share


@pytest.fixture(scope="module")
def examples():
    return generate(LANGUAGES, examples_per_intent)


def test_thousands_of_examples(examples):
    by_lang = collections.Counter(e.lang for e in examples)
    assert len(examples) >= 15000 and by_lang["si"] >= 8000 and by_lang["si-Latn"] >= 4500
    assert len({e.intent for e in examples}) >= 43


def test_every_intent_in_every_language(examples):
    seen = collections.defaultdict(set)
    for e in examples:
        seen[e.intent].add(e.lang)
    assert all(langs == {"si", "si-Latn", "en"} for langs in seen.values()), seen


def test_scripts(examples):
    for e in examples:
        if e.lang == "si":
            assert foreign_script_share(e.text, "si") == 0, e.text          # Sinhala script only
        elif e.lang == "si-Latn":
            assert e.text.isascii(), e.text                                  # English letters only


def test_no_repeats_and_reproducible(examples):
    for lang in LANGUAGES:
        texts = [e.text for e in examples if e.lang == lang]
        assert len(texts) == len(set(texts))
    again = generate(LANGUAGES, examples_per_intent)
    assert [e.text for e in again] == [e.text for e in examples]


def test_no_leftover_gaps_or_spaces(examples):
    for e in examples:
        assert "{" not in e.text and "  " not in e.text and e.text == e.text.strip(), e.text
        assert " ," not in e.text and " ?" not in e.text, e.text


def test_slots_and_forms():
    vocab = {"w": [C("")], "app": [C("ක්‍රෝම් එක", "chrome")], "open": [V("ඕපන් කරන්න", "polite")],
             "country__loc": [C("ලංකාවේ", "sri_lanka")]}
    (ex,) = expand(Pattern("open_app", "{w}{app} {open}"), vocab, "si")
    assert ex.text == "ක්‍රෝම් එක ඕපන් කරන්න" and ex.slots == {"app": "chrome"} and ex.form == "polite"
    (ex,) = expand(Pattern("news", "{country__loc} ප්‍රවෘත්ති?", {"x": "y"}), vocab, "si")
    assert ex.slots == {"country": "sri_lanka", "x": "y"} and ex.text == "ලංකාවේ ප්‍රවෘත්ති?"


def test_balanced_sampling_spreads_over_patterns(examples):
    si_open = [e for e in examples if e.lang == "si" and e.intent == "open_app"]
    patterns = collections.Counter(e.pattern for e in si_open)
    assert len(patterns) == 4 and min(patterns.values()) >= 40           # no single pattern dominates


def test_study_requests_get_more_examples(examples):
    counts = collections.Counter((e.intent, e.lang) for e in examples)
    for intent in ("explain_concept", "derive_proof", "write_code", "exam_prep"):
        assert counts[(intent, "si-Latn")] == PER_STUDY_INTENT["si-Latn"], intent       # Singlish study is full
        assert counts[(intent, "si")] == PER_STUDY_INTENT["si"], intent
    assert counts[("open_app", "si-Latn")] <= PER_INTENT["si-Latn"]
    assert STUDY_INTENTS >= {"derive_proof", "check_answer", "write_code", "debug_code", "exam_prep"}


def test_study_topics_cover_the_degrees():
    ids = {t.id for t in STUDY_TOPICS}
    assert len(ids) == len(STUDY_TOPICS) >= 250                                       # no id twice
    assert {t.area for t in STUDY_TOPICS} == {"pure_maths", "applied_maths", "physics", "statistics",
                                              "data_science", "computing", "research_management"}
    assert {"fourier_series", "schrodinger_equation", "runge_kutta", "backpropagation", "star_schema",
            "radius_of_convergence", "wronskian", "thevenin", "ozone_layer"} <= ids
    for t in STUDY_TOPICS:
        assert t.sl.isascii() and all(t), t                                            # Singlish in English letters
    codes = " ".join(row[2] for row in STUDY_SUBJECTS)
    for code in ("pmat 21272", "pmat 22282", "amat 22282", "phys 22533", "it3091", "it4061"):
        assert code in codes


def test_study_topics_reach_every_language(examples):
    topics = {(e.lang, e.slots["topic"]) for e in examples if "topic" in e.slots and e.intent == "explain_concept"}
    spread = {lang: len({t for la, t in topics if la == lang}) for lang in LANGUAGES}
    assert spread["si"] >= 150 and spread["si-Latn"] >= 150 and spread["en"] >= 80, spread   # many topics, not a few
