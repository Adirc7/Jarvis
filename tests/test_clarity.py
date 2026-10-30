"""Nonsense transcripts are caught before they reach the LLM (voice/clarity.py)."""

from types import SimpleNamespace

import numpy as np
import pytest

from jarvis.language import LanguageManager
from jarvis.voice.clarity import compression_ratio, foreign_script_share, unclear_reason
from jarvis.voice.stt import Transcriber
from test_voice_pipeline import FakeWhisper, make_voice_app

# What Whisper "small" wrote on the laptop on 21 Oct when Adhi spoke Sinhala.
REPEATS = ("වකප ලල් පපිනේයියයියය එය ලල්ල් ලල්ශ නිනිත්වක්යයිය කෙන් ලල්ල් එය වකපින් "
           "කෙන්ල්ශ්න්මී ඔදයියිය ලෞල්ලය ඔභෙනදයය මේල් ලලල්පිට්කන්දයින")
WRONG_ALPHABET = "Р說                                  D ."
GOOD_SINHALA = "ඔබට අවශ්‍ය නම් සිංහලෙන් කතා කරමි, සර්. මොන වගේ උදව්වක් අවශ්‍යද?"


def test_real_nonsense_is_caught():
    assert unclear_reason(REPEATS, "si") == "repetitive"
    assert unclear_reason(WRONG_ALPHABET, "si") == "wrong alphabet"


@pytest.mark.parametrize("text, code", [
    (GOOD_SINHALA, "si"),
    ("මට thermodynamics assignment එක ගැන උදව් ඕනේ", "si"),     # English words mixed in
    ("Can you help me revise thermodynamics for tomorrow?", "en"),
    ("Café, résumé, naïve.", "en"),                           # accents are still Latin
    ("Yes.", "en"),
    ("ok ok ok", "en"),                                       # too short to judge repetition
])
def test_ordinary_speech_passes(text, code):
    assert unclear_reason(text, code) is None


def test_low_confidence():
    assert unclear_reason("open the browser", "en", avg_logprob=-1.4) == "low confidence"
    assert unclear_reason("open the browser", "en", avg_logprob=-0.3) is None


def test_measures():
    assert compression_ratio("") == 0.0
    assert compression_ratio("la " * 50) > 5
    assert foreign_script_share("Привет", "en") == 1.0
    assert foreign_script_share("hello", "xx") == 0.0              # unknown language: no check


def test_transcriber_marks_nonsense_and_keeps_the_text(settings):
    lm = LanguageManager(settings.languages, "si")
    r = Transcriber(settings, lm, loader=lambda n: FakeWhisper(detected=("si", 0.95), texts={"si": REPEATS})
                    ).transcribe(np.zeros(16000, np.float32))
    assert r.unclear == "repetitive" and r.text == REPEATS


def test_transcriber_uses_whisper_confidence(settings):
    class UnsureWhisper(FakeWhisper):
        def transcribe(self, audio, language=None, **kwargs):
            segs = [SimpleNamespace(text="open the", avg_logprob=-1.6, tokens=[1, 2]),
                    SimpleNamespace(text="browser", avg_logprob=-1.2, tokens=[3])]
            return segs, SimpleNamespace(language=language)

    lm = LanguageManager(settings.languages, "en")
    r = Transcriber(settings, lm, loader=lambda n: UnsureWhisper()).transcribe(np.zeros(16000, np.float32))
    assert r.avg_logprob == pytest.approx((-1.6 * 2 - 1.2) / 3, abs=1e-3)
    assert r.unclear == "low confidence"


def test_check_can_be_switched_off(settings):
    settings.raw["stt"]["reject_unclear"] = False
    lm = LanguageManager(settings.languages, "si")
    r = Transcriber(settings, lm, loader=lambda n: FakeWhisper(detected=("si", 0.95), texts={"si": REPEATS})
                    ).transcribe(np.zeros(16000, np.float32))
    assert r.unclear is None


async def test_unclear_speech_is_not_sent_to_the_llm(settings):
    app, spoken, backend, out = make_voice_app(
        settings, ["This should never be said."], FakeWhisper(detected=("en", 0.9), texts={"en": WRONG_ALPHABET}))
    reply = await app.voice_turn(np.zeros(16000, np.float32), 1.0)
    assert reply is None
    assert any("unclear: wrong alphabet" in line for line in out)
    assert spoken and "couldn't make that out" in spoken[-1][1]
    assert not any("never be said" in text for _, text in spoken)


def test_misheard_sinhala_request_still_switches(settings):
    lm = LanguageManager(settings.languages, "en")
    assert lm.detect_switch("I prefer to now in Singhala") == "si"     # Whisper's version of "talk in Sinhala"
    assert lm.detect_switch("I prefer tea") is None


def test_whisper_expects_local_place_names_in_english_only(settings):
    # 30 Oct: "Kaduwela" was heard as "Cardwell". English gets Sri Lankan place names;
    # Sinhala keeps the plain prompt (Latin words could pull it into Latin letters).
    whisper = FakeWhisper(detected=("en", 0.99), texts={"en": "will it rain in Kaduwela"})
    Transcriber(settings, LanguageManager(settings.languages, "en"), loader=lambda n: whisper
                ).transcribe(np.zeros(16000, np.float32))
    assert "Kaduwela" in whisper.transcribe_options[-1]["initial_prompt"]
    sinhala = FakeWhisper(detected=("si", 0.99), texts={"si": "හෙලෝ"})
    Transcriber(settings, LanguageManager(settings.languages, "si"), loader=lambda n: sinhala
                ).transcribe(np.zeros(16000, np.float32))
    assert "Kaduwela" not in (sinhala.transcribe_options[-1]["initial_prompt"] or "")
