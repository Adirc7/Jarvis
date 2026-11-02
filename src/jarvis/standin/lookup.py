"""Version 1 of the stand-in: no training, just the nearest question you asked before.

    lookup = Lookup(pairs, E5())                   # or TfidfChars(): no download, works offline at once
    match = lookup.answer("whats entropy again")   # Match(pair, 0.93) when a past question is close enough

The encoder turns a question into a vector of unit length, so the dot product of two is their cosine
similarity. multilingual-e5-small (the encoder of your intent model's level 2) understands paraphrases in
English, Sinhala and Singlish; the TF-IDF of character n-grams is the fallback when e5 isn't there.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from .pairs import Pair

E5_MODEL = "intfloat/multilingual-e5-small"


class TfidfChars:
    """Character n-grams (2-4, within words), TF-IDF weighted: catches the same question with typos or
    small changes, not real paraphrases. Refitted when questions are added (a few thousand at most)."""

    name = "tfidf"
    threshold = 0.88                    # typos score above 0.9; "heat capacity" against "a capacitor", 0.83
    student_threshold = 0.45            # your student may answer near its data, not only the same question

    def __init__(self):
        self._vectorizer = None

    def fit(self, texts: list[str]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), lowercase=True,
                                           sublinear_tf=True).fit(texts or [""])

    def encode(self, texts: list[str], kind: str = "query") -> np.ndarray:
        if self._vectorizer is None:
            self.fit(texts)
        m = self._vectorizer.transform(texts).toarray().astype(np.float32)
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        return m / np.where(norms == 0, 1, norms)


class E5:
    """multilingual-e5-small through sentence-transformers (downloads about 470 MB once, to HF_HOME)."""

    name = "e5"
    threshold = 0.9                      # e5's cosines run high: unrelated questions are often near 0.8
    student_threshold = 0.85

    def __init__(self, model: str = E5_MODEL, device: str = "cpu"):
        self.model_name, self.device = model, device
        self._model = None

    def fit(self, texts: list[str]) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)

    def encode(self, texts: list[str], kind: str = "query") -> np.ndarray:
        self.fit([])
        return np.asarray(self._model.encode([f"{kind}: {t}" for t in texts], normalize_embeddings=True,
                                             batch_size=32, show_progress_bar=False), dtype=np.float32)


@dataclass(frozen=True)
class Match:
    pair: Pair
    score: float


class Lookup:
    def __init__(self, pairs: list[Pair], encoder, min_similarity: float | None = None):
        self.encoder = encoder
        self.min_similarity = encoder.threshold if min_similarity is None else min_similarity
        self._lock = threading.Lock()
        self.pairs: list[Pair] = []
        self._vectors = np.zeros((0, 0), np.float32)
        self.add(pairs)

    def add(self, pairs: list[Pair]) -> None:
        if not pairs:
            return
        with self._lock:
            self.pairs = self.pairs + list(pairs)
            if isinstance(self.encoder, TfidfChars):              # its vocabulary changes: encode all again
                questions = [p.question for p in self.pairs]
                self.encoder.fit(questions)
                self._vectors = self.encoder.encode(questions)
            else:
                new = self.encoder.encode([p.question for p in pairs])
                self._vectors = new if not self._vectors.size else np.vstack([self._vectors, new])

    def nearest(self, question: str) -> Match | None:
        with self._lock:
            if not self.pairs:
                return None
            v = self.encoder.encode([question])[0]
            scores = self._vectors @ v
            i = int(np.argmax(scores))
            return Match(self.pairs[i], float(scores[i]))

    def answer(self, question: str) -> Match | None:
        """The past answer to the closest past question, if it's close enough to be the same question."""
        match = self.nearest(question)
        return match if match is not None and match.score >= self.min_similarity else None


def make_encoder(name: str):
    """"" or "tfidf": the TF-IDF fallback; anything else: that e5 model, or TF-IDF if it can't load."""
    if not name or name == "tfidf":
        return TfidfChars()
    try:
        encoder = E5(name)
        encoder.fit([])
        return encoder
    except Exception:  # noqa: BLE001 - not installed, no internet the first time: the fallback still works
        return TfidfChars()


__all__ = ["E5", "E5_MODEL", "Lookup", "Match", "TfidfChars", "make_encoder"]
