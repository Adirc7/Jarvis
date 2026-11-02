"""Test before use: a new stand-in is used only if it beats the current one on conversations it never saw.

    report = score(answer_fn, held_out, similar)     # answer_fn(question) -> str, or None when it declines

For each held-out pair (the newest ones, never uploaded for training), the stand-in answers the question
and its answer is compared with what the language model really said, by meaning: the cosine similarity
of the two answers' e5 embeddings (or TF-IDF words when e5 isn't there).

- coverage: how often it dared to answer;
- quality: how close its answers were, when it answered;
- overall: the mean over all questions, a declined one counting 0. This is what decides: a stand-in
  that answers rarely but well, and one that answers often but badly, both score low.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from .pairs import Pair

MARGIN = 0.01        # a candidate must win by at least this much: ties keep what's tested and working


@dataclass
class Score:
    name: str
    n: int
    answered: int
    quality: float
    overall: float

    @property
    def coverage(self) -> float:
        return self.answered / self.n if self.n else 0.0

    def line(self) -> str:
        return (f"| {self.name} | {self.n} | {self.coverage:.0%} | {self.quality:.3f} | {self.overall:.3f} |")


def similarity_with(encoder) -> Callable[[list[str], list[str]], list[float]]:
    """Pairwise similarity of answers by meaning, with the stand-in's encoder (e5), or TF-IDF of words."""
    if getattr(encoder, "name", "") == "e5":
        def e5(a: list[str], b: list[str]) -> list[float]:
            va, vb = encoder.encode(a, kind="passage"), encoder.encode(b, kind="passage")
            return [float(x) for x in np.sum(va * vb, axis=1)]
        return e5

    def words(a: list[str], b: list[str]) -> list[float]:
        from sklearn.feature_extraction.text import TfidfVectorizer
        m = TfidfVectorizer(sublinear_tf=True).fit(a + b)
        va, vb = m.transform(a).toarray(), m.transform(b).toarray()
        na, nb = np.linalg.norm(va, axis=1), np.linalg.norm(vb, axis=1)
        return [float(x) for x in np.sum(va * vb, axis=1) / np.where(na * nb == 0, 1, na * nb)]
    return words


def score(name: str, answer: Callable[[str], str | None], held_out: list[Pair],
          similar: Callable[[list[str], list[str]], list[float]]) -> Score:
    got = [(p, answer(p.question)) for p in held_out]
    said = [(p, a) for p, a in got if a]
    sims = similar([a for _, a in said], [p.reply for p, _ in said]) if said else []
    total = float(sum(sims))
    return Score(name, len(held_out), len(said), total / len(said) if said else 0.0,
                 total / len(held_out) if held_out else 0.0)


def better(candidate: Score, current: Score) -> bool:
    return candidate.n > 0 and candidate.overall >= current.overall + MARGIN


def report(scores: list[Score], verdict: str) -> str:
    return "\n".join(["| stand-in | held-out questions | answered | quality | overall |",
                      "|---|---|---|---|---|", *[s.line() for s in scores], "", verdict])


__all__ = ["MARGIN", "Score", "better", "report", "score", "similarity_with"]
