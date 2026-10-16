import pytest

from jarvis.language import LanguageManager, normalize


@pytest.fixture
def lm(settings):
    return LanguageManager(settings.languages, "en")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Switch to Sinhala", "si"),
        ("Jarvis, speak Tamil please.", "ta"),
        ("can you talk to me in sinhalese", "si"),
        ("reply in English", "en"),
        ("Sinhala please", "si"),
        ("සිංහලෙන් කතා කරන්න", "si"),                 # "speak in Sinhala"
        ("ඉංග්‍රීසියෙන් කතා කරන්න", "en"),            # "speak in English" (with ZWJ)
        ("ඉංග්රීසියෙන් කතා කරන්න", "en"),             # same, ZWJ dropped by STT
        ("தமிழில் பேசு", "ta"),                        # "speak in Tamil"
        ("ஆங்கிலத்தில் பேசுங்கள்", "en"),              # "please speak in English"
    ],
)
def test_detects_switch(lm, text, expected):
    assert lm.detect_switch(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "translate this sentence to Tamil",          # no command word
        "how do you say thank you in Sinhala",       # 'say' is deliberately not a command word
        "translate English to Tamil",                # two languages named
        "open the browser",
        "what is the weather today",
        "speak",                                     # command word, no language
        "please speak slowly and tell me a long story about the history of the english language in detail",
    ],
)
def test_ignores_non_switch(lm, text):
    assert lm.detect_switch(text) is None


def test_normalize_keeps_vowel_signs():
    # \w-based cleaning would strip these combining marks and break matching
    assert normalize("සිංහලෙන්!") == "සිංහලෙන්"
    assert normalize("தமிழில்?") == "தமிழில்"


def test_set_and_on_change(settings):
    seen = []
    lm = LanguageManager(settings.languages, "en", on_change=seen.append)
    ev = lm.set("si", source="test")
    assert lm.current.code == "si"
    assert ev.old == "en" and ev.new == "si"
    assert seen == [ev]
    assert lm.set("si", source="test") is None      # no change, no event
    with pytest.raises(ValueError):
        lm.set("xx", source="test")


def test_retranscribe_decision(settings):
    lm = LanguageManager(settings.languages, "si", retranscribe_threshold=0.8)
    assert lm.needs_retranscribe("en", 0.95) == "en"   # heard English in Sinhala mode
    assert lm.needs_retranscribe("en", 0.55) is None   # not confident enough
    assert lm.needs_retranscribe("si", 0.99) is None   # same language
    assert lm.needs_retranscribe("fr", 0.99) is None   # language Jarvis doesn't have
    assert lm.needs_retranscribe(None, None) is None


def test_llm_instruction_mentions_script(settings):
    lm = LanguageManager(settings.languages, "ta")
    assert "Tamil" in lm.llm_instruction() and "தமிழ்" in lm.llm_instruction()
