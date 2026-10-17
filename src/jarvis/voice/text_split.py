"""Turn a streamed LLM reply into speakable chunks.

Speaking starts after the first short sentence instead of after the whole reply,
which is most of the latency saving in plan section 10.1. Later chunks are
longer so the voice doesn't sound choppy.
"""

from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"[.!?…।](?:[\"')\]]*)(?=\s)|\n+")
_CLAUSE_END = re.compile(r"[,;:](?=\s)")
_ABBREVIATIONS = {"mr.", "mrs.", "ms.", "dr.", "e.g.", "i.e.", "etc.", "vs.", "st.", "no."}

_MARKDOWN = [
    (re.compile(r"```.*?```", re.S), " "),          # code blocks aren't speakable
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),     # images
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),  # links: keep the text
    (re.compile(r"https?://\S+"), "a link"),
    (re.compile(r"[*_]{1,3}([^*_\n]+)[*_]{1,3}"), r"\1"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""),
    (re.compile(r"^\s*[-*•]\s+", re.M), ""),
    (re.compile(r"^\s*\d+[.)]\s+", re.M), ""),
]


def clean_for_speech(text: str) -> str:
    """Strip markdown and symbols that a TTS voice would read out literally."""
    for pattern, repl in _MARKDOWN:
        text = pattern.sub(repl, text)
    return " ".join(text.split())


class SentenceChunker:
    def __init__(self, first_min_chars: int = 12, min_chars: int = 40, max_chars: int = 220):
        self.first_min = first_min_chars
        self.min = min_chars
        self.max = max_chars
        self._buf = ""
        self._emitted = 0

    def feed(self, text: str) -> list[str]:
        """Add streamed text; return any chunks that are ready to speak."""
        self._buf += text
        out = []
        while True:
            chunk = self._take()
            if chunk is None:
                break
            out.append(chunk)
        return out

    def flush(self) -> list[str]:
        """Return whatever is left at the end of the reply."""
        rest = clean_for_speech(self._buf)
        self._buf = ""
        return [rest] if rest else []

    # ------------------------------------------------------------------
    def _take(self) -> str | None:
        minimum = self.first_min if self._emitted == 0 else self.min
        cut = self._sentence_cut(minimum)
        if cut is None and self._emitted == 0 and len(self._buf) >= 60:
            cut = self._clause_cut(minimum)       # long first sentence: start at a comma
        if cut is None and len(self._buf) > self.max:
            cut = self._buf.rfind(" ", 0, self.max)
            cut = cut if cut > 0 else self.max
        if cut is None:
            return None
        chunk, self._buf = self._buf[:cut], self._buf[cut:].lstrip()
        chunk = clean_for_speech(chunk)
        if not chunk:
            return None if not self._buf else self._take()
        self._emitted += 1
        return chunk

    def _sentence_cut(self, minimum: int) -> int | None:
        for m in _SENTENCE_END.finditer(self._buf):
            end = m.end()
            if end < minimum:
                continue
            words = self._buf[:end].split()
            last_word = words[-1].lower() if words else ""
            if last_word in _ABBREVIATIONS:
                continue
            return end
        return None

    def _clause_cut(self, minimum: int) -> int | None:
        for m in _CLAUSE_END.finditer(self._buf):
            if m.end() >= minimum:
                return m.end()
        return None
