"""Language switching.

One language is active at a time. Switching it changes three things together:
  1. the language Whisper transcribes in,
  2. the language the LLM is told to reply in,
  3. the TTS voice.

Switch commands are detected by deterministic rules *before* the LLM sees the
text (same idea as the allow-list: a fixed decision doesn't belong in the model).
The LLM can also switch through a `set_language` tool later, for phrasings the
rules miss.

The tricky case: in Sinhala mode Whisper is told to expect Sinhala, so an
English "switch to English" may come out garbled. To handle it, the voice
pipeline runs Whisper's language detection on every utterance; if it hears a
different known language with high probability, it re-transcribes in that
language and checks for a switch command (`needs_retranscribe`).
"""

from __future__ import annotations

import unicodedata
from typing import Callable

from .config import Language
from .events import LanguageChanged

_ZERO_WIDTH = {"​", "‌", "‍", "﻿"}
MAX_COMMAND_WORDS = 10   # longer utterances are treated as normal requests

# Calling the assistant by name: "Friday", "hey Friday", "I need to talk Friday".
_NAME_FILLERS = {"hey", "hi", "hello", "ok", "okay", "please", "yes", "oh", "now", "ane", "hari", "අනේ", "හරි"}
_TALK_WORDS = {"talk", "speak", "switch", "call", "want", "need", "bring", "change", "get", "let",
               "කතා", "මාරු", "එක්ක", "katha", "ekka", "maru"}
# ...but not the day: "on Friday", "Friday's lecture", "move my exam to Friday".
_DAY_WORDS = {"on", "about", "this", "next", "last", "every", "until", "till", "by", "before", "after",
              "coming", "day", "morning", "evening", "night", "week", "lecture", "lectures", "exam", "exams",
              "class", "meeting", "deadline", "due", "remind", "reminder", "timetable", "schedule"}
# Non-Latin letters of each script, by Whisper code: text mostly in one of
# these is that language whatever mode Jarvis is in.
_NATIVE_SCRIPT = {"si": (0x0D80, 0x0DFF), "ta": (0x0B80, 0x0BFF)}


def language_by_script(text: str, languages: dict[str, Language], min_share: float = 0.25) -> str | None:
    """The language whose own (non-Latin) script a good share of the letters are in.

    A quarter is enough: Sinhala as people type it mixes in English words
    ("Fourier series එක explain කරන්න"), and those are Friday's to answer.
    """
    letters = [c for c in text if unicodedata.category(c)[0] in "LM"]
    if not letters:
        return None
    best, best_share = None, 0.0
    for code, lang in languages.items():
        span = _NATIVE_SCRIPT.get(lang.whisper_code)
        share = sum(span[0] <= ord(c) <= span[1] for c in letters) / len(letters) if span else 0.0
        if share > best_share:
            best, best_share = code, share
    return best if best_share >= min_share else None


# Indic scripts a model sometimes slips into Sinhala or Tamil words ("खेළ", "সাফল্য"):
# Devanagari (0900) up to Malayalam (0D7F), and Sinhala (0D80-0DFF) for a Tamil reply.
_OTHER_INDIC = {"si": ((0x0900, 0x0D7F),), "ta": ((0x0900, 0x0B7F), (0x0C00, 0x0DFF))}


def stray_letters(text: str, code: str) -> int:
    """Letters from another Indic script in a reply meant to be Sinhala or Tamil (0 for English)."""
    spans = _OTHER_INDIC.get(code, ())
    return sum(any(a <= ord(c) <= b for a, b in spans) for c in text)


def normalize(text: str) -> str:
    """Lowercase, NFC, drop zero-width joiners, turn punctuation into spaces.

    Punctuation is removed by Unicode category rather than with a regex like
    [^\\w\\s], because \\w does not match Sinhala and Tamil vowel signs.
    """
    text = unicodedata.normalize("NFC", text).lower()
    out = []
    for ch in text:
        if ch in _ZERO_WIDTH:
            continue
        cat = unicodedata.category(ch)
        out.append(" " if cat[0] in ("P", "S") else ch)
    return " ".join("".join(out).split())


def _contains_tokens(words: list[str], phrase: str) -> bool:
    target = normalize(phrase).split()
    if not target:
        return False
    n = len(target)
    return any(words[i:i + n] == target for i in range(len(words) - n + 1))


class LanguageManager:
    def __init__(
        self,
        languages: dict[str, Language],
        current: str,
        retranscribe_threshold: float = 0.80,
        on_change: Callable[[LanguageChanged], None] | None = None,
    ):
        if current not in languages:
            raise ValueError(f"unknown language '{current}'")
        self.languages = languages
        self._current = current
        self.retranscribe_threshold = retranscribe_threshold
        self._on_change = on_change
        self._by_whisper = {lang.whisper_code: code for code, lang in languages.items()}
        self._command_words = {normalize(w) for lang in languages.values() for w in lang.command_words}
        self._voice_names = {code: {normalize(n) for n in lang.voice_names} for code, lang in languages.items()}

    @property
    def current(self) -> Language:
        return self.languages[self._current]

    def detect_switch(self, text: str) -> str | None:
        """Return a language code if `text` asks Jarvis to switch, else None."""
        norm = normalize(text)
        words = norm.split()
        if not words:
            return None
        for code, lang in self.languages.items():
            if any(norm == normalize(p) for p in lang.switch_phrases):
                return code
        matches = [
            code for code, lang in self.languages.items()
            if any(_contains_tokens(words, name) for name in lang.names)
        ]
        if not matches:
            return self._called_by_name(words)
        if len(words) > MAX_COMMAND_WORDS:
            return None
        if not any(w in self._command_words for w in words):
            return None
        # Exactly one language named -> switch. Two named ("translate English
        # to Tamil") is ambiguous, so treat it as a normal request.
        return matches[0] if len(matches) == 1 else None

    def _called_by_name(self, words: list[str]) -> str | None:
        """"Friday" / "hey Friday" / "I need to talk Friday" -> Friday's language."""
        named = {code for code, names in self._voice_names.items() if any(w in names for w in words)}
        if len(named) != 1:
            return None
        code = named.pop()
        if all(w in self._voice_names[code] or w in _NAME_FILLERS for w in words):
            return code
        if len(words) > MAX_COMMAND_WORDS or any(w in _DAY_WORDS for w in words):
            return None
        return code if any(w in _TALK_WORDS for w in words) else None

    def script_language(self, text: str) -> str | None:
        """A language whose own script the text is written in (Sinhala, Tamil), if any."""
        return language_by_script(text, self.languages)

    def needs_retranscribe(self, detected_whisper_code: str | None, probability: float | None) -> str | None:
        """If Whisper confidently heard another known language, return its code."""
        if not detected_whisper_code or probability is None:
            return None
        code = self._by_whisper.get(detected_whisper_code)
        if code is None or code == self._current:
            return None
        return code if probability >= self.retranscribe_threshold else None

    def set(self, code: str, source: str) -> LanguageChanged | None:
        """Switch language. Returns the change event, or None if nothing changed."""
        if code not in self.languages:
            raise ValueError(f"unknown language '{code}'")
        if code == self._current:
            return None
        event = LanguageChanged(old=self._current, new=code, source=source)
        self._current = code
        if self._on_change:
            self._on_change(event)
        return event

    def llm_instruction(self) -> str:
        lang = self.current
        if lang.code == "en":
            return "Reply in English, all of it (any comment or take of your own too)."
        return (
            f"Always reply in {lang.name} ({lang.native_name}), written in {lang.name} script, "
            f"even if the user mixes in English words. Every word in {lang.name} letters only: never mix "
            f"Hindi (Devanagari), Bengali or any other script into a word. "
            f"Keep app names, file names and code in their original form."
        )
