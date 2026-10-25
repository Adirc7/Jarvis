"""Adhi's trained intent model: saved, loaded, and used by Jarvis (intents/classifier.py)."""

import pytest

pytest.importorskip("sklearn")
joblib = pytest.importorskip("joblib")

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from jarvis.agent.router import IntentRouter, KeywordRouter
from jarvis.app import App
from jarvis.intents.classifier import load_classifier
from jarvis.telemetry import Telemetry

TEXTS = ["open youtube", "youtube eka arinna", "pause the video", "video eka nawaththanna",
         "what is entropy", "explain fourier series", "solve this integral", "derive the wave equation"] * 3
INTENTS = ["open_app", "open_app", "pause_media", "pause_media",
           "explain_concept", "explain_concept", "solve_problem", "solve_problem"] * 3


def tiny_model(tmp_path, **extra):
    pipeline = Pipeline([("features", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))),
                         ("model", LogisticRegression(max_iter=500))])
    pipeline.fit(TEXTS, INTENTS)
    path = tmp_path / "intent.joblib"
    joblib.dump({"kind": "text", "pipeline": pipeline, "trained": "2026-10-25", **extra}, path)
    return path


def test_a_saved_model_classifies(tmp_path):
    classify, saved = load_classifier(tiny_model(tmp_path))
    intent, confidence = classify("youtube eka arinna", "si-Latn")
    assert intent == "open_app" and 0 < confidence <= 1 and saved["trained"] == "2026-10-25"


def test_a_wrong_file_is_refused(tmp_path):
    path = tmp_path / "bad.joblib"
    joblib.dump(["not", "a", "dict"], path)
    with pytest.raises(TypeError):
        load_classifier(path)


def test_jarvis_uses_the_model_when_the_file_exists(settings, tmp_path):
    settings.raw.setdefault("intents", {})["model"] = str(tiny_model(tmp_path))
    out = []
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: out.append("".join(map(str, a))))
    assert isinstance(app.router, IntentRouter) and any("[intent model]" in line for line in out)
    decision = app.router.route("explain fourier series", "en")
    assert decision.intent == "explain_concept"


def test_without_the_file_jarvis_uses_the_keyword_rules(settings, tmp_path):
    settings.raw.setdefault("intents", {})["model"] = str(tmp_path / "missing.joblib")
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None)
    assert isinstance(app.router, KeywordRouter)


def test_a_broken_file_does_not_stop_jarvis(settings, tmp_path):
    path = tmp_path / "broken.joblib"
    path.write_bytes(b"not a joblib file")
    settings.raw.setdefault("intents", {})["model"] = str(path)
    out = []
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: out.append("".join(map(str, a))))
    assert isinstance(app.router, KeywordRouter) and any("couldn't load" in line for line in out)
