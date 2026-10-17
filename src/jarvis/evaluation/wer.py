"""Word and character error rates for checking speech recognition.

    WER = (substitutions + deletions + insertions) / words in the reference
    CER = the same, counted in characters (spaces ignored)

CER matters most for Sinhala and Tamil, where one word carries many suffixes
and a single wrong vowel sign makes the whole word count as an error.
Both texts go through the same normalisation as language switching
(lowercase, punctuation and zero-width joiners removed).

Corpus scores add up errors over all sentences before dividing, so long
sentences count more than short ones (the standard way to report WER).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from ..language import normalize


def edit_distance(ref: Sequence, hyp: Sequence) -> int:
    """Levenshtein distance with unit costs, two-row dynamic programming."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1,              # deletion
                         cur[j - 1] + 1,           # insertion
                         prev[j - 1] + (r != h))   # substitution (or match)
        prev = cur
    return prev[-1]


@dataclass
class Score:
    word_errors: int
    words: int
    char_errors: int
    chars: int

    @property
    def wer(self) -> float:
        return self.word_errors / self.words if self.words else 0.0

    @property
    def cer(self) -> float:
        return self.char_errors / self.chars if self.chars else 0.0

    def __add__(self, other: "Score") -> "Score":
        return Score(self.word_errors + other.word_errors, self.words + other.words,
                     self.char_errors + other.char_errors, self.chars + other.chars)


def score(reference: str, hypothesis: str) -> Score:
    ref, hyp = normalize(reference), normalize(hypothesis)
    rw, hw = ref.split(), hyp.split()
    rc, hc = list(ref.replace(" ", "")), list(hyp.replace(" ", ""))
    return Score(edit_distance(rw, hw), len(rw), edit_distance(rc, hc), len(rc))


def corpus_score(pairs: Iterable[tuple[str, str]]) -> Score:
    total = Score(0, 0, 0, 0)
    for ref, hyp in pairs:
        total = total + score(ref, hyp)
    return total


def wer(reference: str, hypothesis: str) -> float:
    return score(reference, hypothesis).wer


def cer(reference: str, hypothesis: str) -> float:
    return score(reference, hypothesis).cer
