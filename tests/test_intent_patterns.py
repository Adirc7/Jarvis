"""The intent pattern generator (jarvis/intents)."""

import collections

import pytest

from jarvis.intents.generate import C, Pattern, V, expand, generate
from jarvis.intents.patterns import LANGUAGES, PER_INTENT
from jarvis.voice.clarity import foreign_script_share


@pytest.fixture(scope="module")
def examples():
    return generate(LANGUAGES, PER_INTENT)


def test_thousands_of_examples(examples):
    by_lang = collections.Counter(e.lang for e in examples)
    assert len(examples) >= 4000 and by_lang["si"] >= 2500


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
    again = generate(LANGUAGES, PER_INTENT)
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
