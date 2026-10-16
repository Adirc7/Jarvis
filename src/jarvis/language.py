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
        if len(words) > MAX_COMMAND_WORDS:
            return None
        if not any(w in self._command_words for w in words):
            return None
        matches = [
            code for code, lang in self.languages.items()
            if any(_contains_tokens(words, name) for name in lang.names)
        ]
        # Exactly one language named -> switch. Two named ("translate English
        # to Tamil") is ambiguous, so treat it as a normal request.
        return matches[0] if len(matches) == 1 else None

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
            return "Reply in English. Keep replies short: they are spoken aloud."
        return (
            f"Always reply in {lang.name} ({lang.native_name}), written in {lang.name} script, "
            f"even if the user mixes in English words. Keep replies short: they are spoken aloud. "
            f"Keep app names, file names and code in their original form."
        )
