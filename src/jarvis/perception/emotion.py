"""How you sound (M5): a speech emotion model beside Whisper, on the same push-to-talk audio.

    ears = EmotionEars.from_settings(settings)     # None when [emotion] enabled = false
    heard = ears.hear(audio_16k)                   # Heard("frustrated", 0.71, {...}, features, ms)

Two levels, like the intent model (docs/TRAINING_EMOTION.md):

  level 1, the baseline: a ready-made model, superb/wav2vec2-base-superb-er
     (Apache-2.0; trained on IEMOCAP, acted American English, four labels:
     neutral, happy, angry, sad). No training. Its labels are said as calm,
     happy, upset, sad.
  level 2, YOURS: a small classifier on that model's features (768 numbers
     per utterance, its last layer averaged over time), trained on your own
     /mood labels, with the labels an assistant needs (calm, rushed,
     frustrated, confused, ...). Saved by your training script as
     models/emotion/emotion.joblib: {"classifier": <scikit-learn>, ...}.

Jarvis never states your emotion as fact: the model's guess goes to the LLM
as a hedged hint only above [emotion] min_confidence, and never "calm".
No audio is kept: /mood stores the features and your label, nothing else.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

BASELINE = "superb/wav2vec2-base-superb-er"
SAID_AS = {"neu": "calm", "hap": "happy", "ang": "upset", "sad": "sad"}     # the baseline's labels, said plainly
MOODS = ("calm", "happy", "rushed", "frustrated", "confused", "tired", "sad", "upset", "excited")
MAX_SECONDS = 10.0                  # longer utterances: the first 10 s (it's about tone, not content)


@dataclass
class Heard:
    label: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    features: list[float] | None = None          # what level 2 learns from (never audio)
    ms: float = 0.0
    level: int = 1
    baseline: dict[str, float] = field(default_factory=dict)    # the ready-made model's scores, always

    def note_for_model(self, min_confidence: float) -> str:
        """The hint for the LLM, or "" when it isn't sure enough (or you sound calm)."""
        if self.confidence < min_confidence or self.label in ("calm", "neutral"):
            return ""
        return (f"From the user's voice (a model's guess, often wrong; never state it as fact): they may sound "
                f"{self.label} ({self.confidence:.0%}). Let it shape your tone; if it matters, ask gently "
                f"(\"You sound a bit {self.label}; want the short version?\") rather than assume.")


class EmotionEars:
    """The baseline model, and your classifier on its features when you've trained one."""

    def __init__(self, model_id: str = BASELINE, device: str = "cuda", classifier: Any = None,
                 classifier_info: dict | None = None, loader: Callable[[str, str], tuple[Any, Any, str]] | None = None):
        self.model_id, self.device = model_id, device
        self.classifier, self.classifier_info = classifier, classifier_info or {}
        self._loader = loader or _load_pretrained
        self._model = self._extractor = None
        self.where = ""

    @classmethod
    def from_settings(cls, settings) -> EmotionEars | None:
        if not settings.get("emotion.enabled", False):
            return None
        classifier, info = None, {}
        path = settings.path("emotion.classifier", "models/emotion/emotion.joblib")
        if path.is_file():
            import joblib
            saved = joblib.load(path)
            if isinstance(saved, dict) and "classifier" in saved:
                classifier, info = saved["classifier"], {k: v for k, v in saved.items() if k != "classifier"}
        return cls(str(settings.get("emotion.model", BASELINE)), str(settings.get("emotion.device", "cuda")),
                   classifier, info)

    def load(self) -> None:
        if self._model is None:
            self._extractor, self._model, self.where = self._loader(self.model_id, self.device)

    def hear(self, audio: np.ndarray, rate: int = 16000) -> Heard:
        start = time.perf_counter()
        self.load()
        audio = np.asarray(audio, dtype=np.float32)[: int(MAX_SECONDS * rate)]
        labels, probs, features = self._run(audio, rate)
        scores = {SAID_AS.get(lab, lab): round(float(p), 4) for lab, p in zip(labels, probs, strict=True)}
        best = max(scores, key=scores.get)
        heard = Heard(best, scores[best], scores, [round(float(x), 5) for x in features], 0.0, 1, dict(scores))
        if self.classifier is not None:
            p = self.classifier.predict_proba(np.asarray([features]))[0]
            classes = [str(c) for c in self.classifier.classes_]
            i = int(np.argmax(p))
            heard.label, heard.confidence, heard.level = classes[i], float(p[i]), 2
            heard.scores = {c: round(float(x), 4) for c, x in zip(classes, p, strict=True)}
        heard.ms = round((time.perf_counter() - start) * 1000, 1)
        return heard

    def _run(self, audio: np.ndarray, rate: int) -> tuple[list[str], np.ndarray, np.ndarray]:
        import torch
        inputs = self._extractor(audio, sampling_rate=rate, return_tensors="pt")
        inputs = {k: v.to(self.where) for k, v in inputs.items()}
        with torch.no_grad():
            out = self._model(**inputs, output_hidden_states=True)
        probs = torch.softmax(out.logits, dim=-1)[0].float().cpu().numpy()
        features = out.hidden_states[-1].mean(dim=1)[0].float().cpu().numpy()
        labels = [self._model.config.id2label[i] for i in range(len(probs))]
        return labels, probs, features


def _load_pretrained(model_id: str, device: str) -> tuple[Any, Any, str]:
    import torch
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
    where = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
    extractor = AutoFeatureExtractor.from_pretrained(model_id)
    model = AutoModelForAudioClassification.from_pretrained(model_id).to(where).eval()
    return extractor, model, where


def save_label(folder: Path, heard: Heard, mood: str, session: str, now: datetime | None = None) -> Path:
    """/mood <label>: your label for the last thing you said, with its features (no audio)."""
    if heard.features is None:
        raise ValueError("no features to label")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "labels.jsonl"
    row = {"time": (now or datetime.now()).isoformat(timespec="seconds"),  # noqa: DTZ005 - local, like the logs
           "session": session, "label": mood, "heard": heard.label, "heard_confidence": heard.confidence,
           "level": heard.level, "scores": heard.scores, "baseline": heard.baseline, "features": heard.features}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return path


def read_labels(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


__all__ = ["BASELINE", "MOODS", "EmotionEars", "Heard", "read_labels", "save_label"]
