"""How well the emotion model hears YOU: the ready-made baseline, and your classifier, on your /mood labels.

    uv run python scripts/emotion_eval.py                                  # the baseline
    uv run python scripts/emotion_eval.py models/emotion/emotion.joblib    # yours against it

Reads data/emotion/labels.jsonl (made by /mood in Jarvis: your label, the
model's features and the baseline's scores; no audio). Your classifier is
scored only on sessions it didn't train on (its saved "trained_sessions"),
because utterances from one session sound alike: testing on the same
session would flatter it (docs/TRAINING_EMOTION.md, step 4).

The baseline only knows calm, happy, upset and sad (IEMOCAP's labels), so
it counts as right when its label is the nearest one (upset for frustrated
or angry, sad for sad or tired, happy for happy or excited). It can never
be right on "rushed" or "confused": that's the gap level 2 is for.

Reports accuracy, macro-F1 (each label counts the same, however rare), F1
per label, the confusion table, and the false alarm rate: how often Jarvis
would hint at an emotion when you were calm. Writes docs/emotion_results.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEAREST = {"upset": {"upset", "frustrated", "angry"}, "calm": {"calm"}, "happy": {"happy", "excited"},
           "sad": {"sad", "tired"}}


def read(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def baseline_guess(row: dict, min_confidence: float) -> str:
    scores = row.get("baseline") or (row.get("scores") if row.get("level", 1) == 1 else {}) or {}
    if not scores:
        return "?"
    best = max(scores, key=scores.get)
    if scores[best] < min_confidence:
        return "calm"                       # below the gate Jarvis says nothing: as good as "calm"
    return next((lab for lab in NEAREST.get(best, {best}) if lab == row["label"]), best)


def scores(truth: list[str], guess: list[str]) -> dict:
    labels = sorted(set(truth))
    f1 = {}
    for lab in labels:
        tp = sum(t == lab and g == lab for t, g in zip(truth, guess, strict=True))
        fp = sum(t != lab and g == lab for t, g in zip(truth, guess, strict=True))
        fn = sum(t == lab and g != lab for t, g in zip(truth, guess, strict=True))
        f1[lab] = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    calm = [g for t, g in zip(truth, guess, strict=True) if t == "calm"]
    return {"n": len(truth), "accuracy": sum(t == g for t, g in zip(truth, guess, strict=True)) / max(1, len(truth)),
            "macro_f1": sum(f1.values()) / max(1, len(f1)), "f1": f1,
            "false_alarm": sum(g != "calm" for g in calm) / len(calm) if calm else None,
            "confusion": Counter(zip(truth, guess, strict=True))}


def table(name: str, s: dict) -> str:
    fa = "n/a" if s["false_alarm"] is None else f"{s['false_alarm']:.0%}"
    per = ", ".join(f"{k} {v:.2f}" for k, v in s["f1"].items())
    return f"| {name} | {s['n']} | {s['accuracy']:.0%} | {s['macro_f1']:.2f} | {fa} | {per} |"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("model", nargs="?", help="your saved classifier (models/emotion/emotion.joblib)")
    ap.add_argument("--labels", default=str(ROOT / "data" / "emotion" / "labels.jsonl"))
    ap.add_argument("--min-confidence", type=float, default=0.6)
    ap.add_argument("--out", default=str(ROOT / "docs" / "emotion_results.md"))
    args = ap.parse_args(argv)
    rows = read(Path(args.labels))
    if not rows:
        print(f"No labels yet in {args.labels}. In Jarvis (with [emotion] enabled = true): say something, then "
              "/mood <label> (docs/TRAINING_EMOTION.md, step 2).")
        return 1
    print(f"{len(rows)} labelled utterances in {len({r.get('session') for r in rows})} sessions: "
          + ", ".join(f"{k} {v}" for k, v in Counter(r["label"] for r in rows).most_common()))
    test = rows
    lines = ["| model | n | accuracy | macro-F1 | false alarms (calm) | F1 per label |", "|---|---|---|---|---|---|"]
    if args.model:
        import joblib
        import numpy as np
        saved = joblib.load(args.model)
        trained = set(saved.get("trained_sessions", []))
        test = [r for r in rows if r.get("session") not in trained]
        if not test:
            print("Every labelled session was used for training: label a new session (or train on fewer) to test.")
            return 1
        model = saved["classifier"]
        probs = model.predict_proba(np.asarray([r["features"] for r in test]))
        classes = [str(c) for c in model.classes_]
        yours = []
        for p in probs:
            i = int(np.argmax(p))
            yours.append(classes[i] if p[i] >= args.min_confidence else "calm")
        print(f"Testing on {len(test)} utterances from {len({r.get('session') for r in test})} sessions it didn't "
              "train on.")
    truth = [r["label"] for r in test]
    base = scores(truth, [baseline_guess(r, args.min_confidence) for r in test])
    lines.append(table("baseline (wav2vec2-base-superb-er)", base))
    if args.model:
        mine = scores(truth, yours)
        lines.append(table(f"yours ({Path(args.model).name})", mine))
    report = "\n".join(lines)
    print("\n" + report)
    Path(args.out).write_text("# Emotion model on your labels\n\nMade by `scripts/emotion_eval.py`; held-out "
                              f"sessions only for your classifier.\n\n{report}\n", encoding="utf-8")
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
