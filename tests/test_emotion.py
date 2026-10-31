"""How you sound (perception/emotion.py): a tiny stand-in for the speech emotion model, the hint, /mood."""

import json

import numpy as np
import pytest

from jarvis.perception.emotion import EmotionEars, Heard, read_labels, save_label

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")


def tiny_loader(model_id, device):
    """A small random wav2vec2 with the baseline's four labels: the real code path, no download."""
    from transformers import (
        Wav2Vec2Config,
        Wav2Vec2FeatureExtractor,
        Wav2Vec2ForSequenceClassification,
    )
    torch.manual_seed(0)
    config = Wav2Vec2Config(hidden_size=32, num_hidden_layers=2, num_attention_heads=2, intermediate_size=48,
                            conv_dim=(16, 16), conv_stride=(5, 4), conv_kernel=(10, 8), num_conv_pos_embeddings=16,
                            num_conv_pos_embedding_groups=2, classifier_proj_size=16, num_labels=4,
                            id2label={0: "neu", 1: "hap", 2: "ang", 3: "sad"},
                            label2id={"neu": 0, "hap": 1, "ang": 2, "sad": 3})
    model = Wav2Vec2ForSequenceClassification(config).eval()
    return Wav2Vec2FeatureExtractor(), model, "cpu"


def test_the_baseline_hears_and_gives_features():
    ears = EmotionEars(loader=tiny_loader)
    heard = ears.hear(np.random.default_rng(0).normal(0, 0.1, 16000).astype(np.float32))
    assert heard.label in ("calm", "happy", "upset", "sad") and heard.level == 1
    assert heard.confidence == max(heard.scores.values()) and sum(heard.scores.values()) == pytest.approx(1, abs=1e-3)
    assert len(heard.features) == 32 and heard.baseline == heard.scores and heard.ms > 0
    long = ears.hear(np.zeros(16000 * 25, np.float32))                  # only the first 10 s are heard
    assert long.label


def test_your_classifier_on_its_features_takes_over():
    from sklearn.linear_model import LogisticRegression
    rng = np.random.default_rng(1)
    x = np.vstack([rng.normal(-1, 0.3, (20, 32)), rng.normal(1, 0.3, (20, 32))])
    clf = LogisticRegression().fit(x, ["calm"] * 20 + ["frustrated"] * 20)
    heard = EmotionEars(loader=tiny_loader, classifier=clf).hear(np.zeros(16000, np.float32))
    assert heard.level == 2 and heard.label in ("calm", "frustrated") and set(heard.scores) == {"calm", "frustrated"}
    assert set(heard.baseline) == {"calm", "happy", "upset", "sad"}           # the baseline is kept for comparing


def test_the_hint_is_hedged_and_only_when_sure():
    assert Heard("calm", 0.95).note_for_model(0.6) == ""
    assert Heard("frustrated", 0.5).note_for_model(0.6) == ""
    note = Heard("frustrated", 0.72).note_for_model(0.6)
    assert "may sound frustrated (72%)" in note and "never state it as fact" in note and "ask gently" in note


def test_labels_keep_features_and_never_audio(tmp_path):
    heard = Heard("upset", 0.8, {"upset": 0.8}, [0.1, 0.2], 12.0, 1, {"upset": 0.8})
    path = save_label(tmp_path, heard, "frustrated", "s1")
    [row] = read_labels(path)
    assert row["label"] == "frustrated" and row["features"] == [0.1, 0.2] and row["session"] == "s1"
    assert set(row) == {"time", "session", "label", "heard", "heard_confidence", "level", "scores", "baseline",
                        "features"}
    with pytest.raises(ValueError):
        save_label(tmp_path, Heard("calm", 0.9), "calm", "s1")              # no features: nothing to keep


# ---- in Jarvis ----------------------------------------------------------------------------------
class FakeEars:
    def __init__(self, heard=None, delay=0.0, error=None):
        self.heard, self.delay, self.error, self.where = heard, delay, error, "cpu"

    def hear(self, audio):
        import time
        time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.heard


def voice_app(settings, ears, pieces=("Let's take it slowly.",)):
    from test_voice_pipeline import FakeWhisper, make_voice_app
    app, *_ = make_voice_app(settings, list(pieces), FakeWhisper(texts={"en": "this proof makes no sense"}))
    app.ears = ears
    return app


async def test_a_confident_guess_reaches_the_model_as_a_hint(settings):
    app = voice_app(settings, FakeEars(Heard("frustrated", 0.8, {"frustrated": 0.8}, [0.0] * 4)))
    await app.voice_turn(np.zeros(16000, np.float32), 1.0)
    system = app.llm.providers[0].client.last_messages[0]["content"]
    assert "may sound frustrated (80%)" in system and app.heard.label == "frustrated"
    assert app._snapshot()["mood"] == "frustrated 80%"
    app.heard = Heard("frustrated", 0.4)
    assert app._snapshot()["mood"] == ""                               # unsure: the window shows nothing


async def test_a_slow_or_broken_model_never_holds_up_the_reply(settings):
    settings.raw.setdefault("emotion", {})["wait_s"] = 0.05
    app = voice_app(settings, FakeEars(Heard("frustrated", 0.9), delay=0.5))
    await app.voice_turn(np.zeros(16000, np.float32), 1.0)
    assert "may sound" not in app.llm.providers[0].client.last_messages[0]["content"]
    broken = voice_app(settings, FakeEars(error=RuntimeError("CUDA out of memory")))
    assert await broken.voice_turn(np.zeros(16000, np.float32), 1.0) == "Let's take it slowly."
    assert broken.ears is None                                           # off for the rest of the session


async def test_mood_labels_the_last_thing_you_said(settings, tmp_path):
    settings.raw.setdefault("emotion", {})["labels_dir"] = str(tmp_path / "emotion")
    app = voice_app(settings, FakeEars(Heard("upset", 0.7, {"upset": 0.7}, [0.5, 0.25], 10.0, 1, {"upset": 0.7})))
    lines = []
    app.out = lambda *a, **k: lines.append(" ".join(map(str, a)))
    await app._command("/mood frustrated")
    assert "say something first" in lines[-1]
    await app.voice_turn(np.zeros(16000, np.float32), 1.0)
    await app._command("/mood")
    assert "last heard: upset 70%" in lines[-1]
    await app._command("/mood frustrated")
    [row] = read_labels(tmp_path / "emotion" / "labels.jsonl")
    assert row["label"] == "frustrated" and row["heard"] == "upset" and row["features"] == [0.5, 0.25]
    await app._command("/mood grumpy")
    assert "labels:" in lines[-1]
    app.ears = None
    await app._command("/mood")
    assert "off" in lines[-1]


def test_off_by_default_and_your_classifier_is_found(settings, tmp_path):
    assert EmotionEars.from_settings(settings) is None
    import joblib
    from sklearn.dummy import DummyClassifier
    clf = DummyClassifier(strategy="most_frequent").fit([[0.0], [1.0]], ["calm", "calm"])
    joblib.dump({"classifier": clf, "trained_sessions": ["s1"]}, tmp_path / "emotion.joblib")
    settings.raw["emotion"] = {"enabled": True, "classifier": str(tmp_path / "emotion.joblib")}
    ears = EmotionEars.from_settings(settings)
    assert list(ears.classifier.classes_) == ["calm"] and ears.classifier_info == {"trained_sessions": ["s1"]}


def test_the_evaluation_compares_yours_with_the_baseline(tmp_path):
    import importlib.util

    import joblib
    from sklearn.linear_model import LogisticRegression
    spec = importlib.util.spec_from_file_location("emotion_eval", "scripts/emotion_eval.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    rng = np.random.default_rng(2)
    rows = []
    for session in ("s1", "s2", "s3"):
        for label, centre, base in (("calm", -1.0, {"calm": 0.9, "upset": 0.1}),
                                    ("frustrated", 1.0, {"calm": 0.3, "upset": 0.7}),
                                    ("confused", 3.0, {"calm": 0.8, "upset": 0.2})):
            for _ in range(5):
                rows.append({"session": session, "label": label, "baseline": base, "level": 1,
                             "features": list(rng.normal(centre, 0.2, 4))})
    labels = tmp_path / "labels.jsonl"
    labels.write_text("\n".join(json.dumps(r) for r in rows))
    train = [r for r in rows if r["session"] != "s3"]
    clf = LogisticRegression().fit([r["features"] for r in train], [r["label"] for r in train])
    joblib.dump({"classifier": clf, "trained_sessions": ["s1", "s2"]}, tmp_path / "emotion.joblib")
    assert ev.main([str(tmp_path / "emotion.joblib"), "--labels", str(labels), "--out", str(tmp_path / "r.md")]) == 0
    report = (tmp_path / "r.md").read_text()
    assert "| baseline (wav2vec2-base-superb-er) | 15 | 67% |" in report      # it can't say "confused"
    assert "| yours (emotion.joblib) | 15 | 100% | 1.00 | 0% |" in report
    assert ev.main(["--labels", str(tmp_path / "none.jsonl")]) == 1
