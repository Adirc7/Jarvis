"""Load Adhi's trained intent model (docs/TRAINING_INTENT.md).

The training script saves one file with joblib, a dict in one of two forms:

    level 1: {"kind": "text", "pipeline": <scikit-learn pipeline that takes raw text>}
    level 2: {"kind": "embedding", "encoder": "intfloat/multilingual-e5-small",
              "prefix": "query: ", "classifier": <scikit-learn classifier on the vectors>}

plus anything else useful ("trained": date, "dev_macro_f1": ...), which is
kept but not needed. load_classifier turns either into the function that
agent/router.py IntentRouter expects: classify(text, lang) -> (intent,
confidence from 0 to 1).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

Classify = Callable[[str, str], tuple[str, float]]


def _best(classes: Any, probs: Any) -> tuple[str, float]:
    i = max(range(len(probs)), key=lambda k: probs[k])
    return str(classes[i]), float(probs[i])


def load_classifier(path: Path | str) -> tuple[Classify, dict[str, Any]]:
    """The classify function, and the saved dict (for its notes)."""
    import joblib

    saved = joblib.load(path)
    if not isinstance(saved, dict):
        raise TypeError(f"{path}: expected a dict saved with joblib (see docs/TRAINING_INTENT.md)")
    kind = saved.get("kind", "text" if "pipeline" in saved else "embedding")
    if kind == "text":
        pipeline = saved["pipeline"]

        def classify(text: str, lang: str = "en") -> tuple[str, float]:
            return _best(pipeline.classes_, pipeline.predict_proba([text])[0])

    elif kind == "embedding":
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(saved["encoder"])
        prefix = saved.get("prefix", "query: ")
        model = saved["classifier"]

        def classify(text: str, lang: str = "en") -> tuple[str, float]:
            vector = encoder.encode([prefix + text], normalize_embeddings=True)
            return _best(model.classes_, model.predict_proba(vector)[0])

    else:
        raise ValueError(f"{path}: unknown kind {kind!r} (expected 'text' or 'embedding')")
    return classify, saved
