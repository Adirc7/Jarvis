"""Did Whisper really hear words, or is the transcript nonsense?

Whisper always writes *something*, even when it can't understand the audio.
For a language it knows poorly (Sinhala with the base models) the result can
be a string of repeated syllables or letters from the wrong alphabet. Passing
that to the LLM gives a confused answer, so Jarvis asks again instead.

Three checks, each cheap:

1. Repetition: Whisper's own hallucination test. Text that zlib compresses
   very well (ratio above 2.4) is mostly repeats: "ලල්ල් ලල්ල් ලලල්...".
2. Wrong alphabet: in Sinhala mode the text should be Sinhala letters, plus
   Latin for mixed-in English words. Cyrillic or Chinese means nonsense.
3. Low confidence: Whisper's average log-probability per token. Below -1.0
   (Whisper's own retry threshold) it was mostly guessing.
"""

from __future__ import annotations

import unicodedata
import zlib

# Letters allowed in each language's transcripts, as Unicode ranges. Latin is
# always allowed because people mix English words into Sinhala and Tamil.
_LATIN = ((0x0041, 0x024F),)
SCRIPTS: dict[str, tuple[tuple[int, int], ...]] = {
    "en": _LATIN,
    "si": _LATIN + ((0x0D80, 0x0DFF),),          # Sinhala block
    "ta": _LATIN + ((0x0B80, 0x0BFF),),          # Tamil block
}


def compression_ratio(text: str) -> float:
    """Bytes before zlib / bytes after. Ordinary sentences: about 1 to 1.8."""
    data = text.encode("utf-8")
    return len(data) / len(zlib.compress(data)) if data else 0.0


def foreign_script_share(text: str, whisper_code: str) -> float:
    """Share of letters outside the scripts expected for this language (0 to 1)."""
    allowed = SCRIPTS.get(whisper_code)
    if allowed is None:
        return 0.0
    letters = [c for c in text if unicodedata.category(c)[0] in "LM"]   # letters and vowel signs
    if not letters:
        return 0.0
    foreign = sum(1 for c in letters if not any(lo <= ord(c) <= hi for lo, hi in allowed))
    return foreign / len(letters)


def unclear_reason(
    text: str,
    whisper_code: str,
    avg_logprob: float | None = None,
    *,
    max_compression: float = 2.4,
    min_logprob: float = -1.0,
    max_foreign_share: float = 0.2,
) -> str | None:
    """Why this transcript looks like nonsense, or None if it looks fine."""
    if len(text) >= 20 and compression_ratio(text) > max_compression:
        return "repetitive"
    if foreign_script_share(text, whisper_code) > max_foreign_share:
        return "wrong alphabet"
    if avg_logprob is not None and avg_logprob < min_logprob:
        return "low confidence"
    return None
