"""Score a trained intent model the same way every time.

    uv run python scripts/intent_eval.py                                  every model in models/intent/
    uv run python scripts/intent_eval.py models/intent/level1.joblib      one model
    uv run python scripts/intent_eval.py models/intent/level1.joblib models/intent/level2.joblib   side by side

Uses data/intent/ (make it with scripts/make_intent_sets.py) and the loader
Jarvis uses (src/jarvis/intents/classifier.py), so what you measure is what
Jarvis will run. Prints, for each model:

  dev        accuracy and macro-F1 on templates the training never saw,
             per language
  real test  the 108 real phrasings (eval/commands*.jsonl): right means one
             of the accepted intents, or, for "just answer" lines, no action
             intent; lines that need the video list on screen are left out
  confident  for limits 0.5-0.9: how many real lines the model would decide
             alone (confidence above the limit), and how many of those it got
             right. Below the limit, Jarvis asks the rules and the big model.
  speed      milliseconds per sentence
  mistakes   the real lines it got wrong, with what it said and how sure
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from make_intent_sets import ACTION_INTENTS

from jarvis.intents.classifier import load_classifier

DATA = ROOT / "data" / "intent"


def load(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        sys.exit(f"No {path.relative_to(ROOT)}: run  uv run python scripts/make_intent_sets.py")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def macro_f1(gold: list[str], pred: list[str]) -> float:
    scores = []
    for label in set(gold):
        tp = sum(g == p == label for g, p in zip(gold, pred, strict=True))
        fp = sum(p == label and g != label for g, p in zip(gold, pred, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, pred, strict=True))
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(scores) / len(scores)


def right(row: dict, intent: str) -> bool:
    return intent not in ACTION_INTENTS if row["no_action"] else intent in row["accept"]


def evaluate(path: Path, dev: list[dict], test: list[dict]) -> dict:
    classify, saved = load_classifier(path)
    start = time.perf_counter()
    dev_out = [classify(r["text"], r["lang"]) for r in dev]
    ms = (time.perf_counter() - start) * 1000 / max(1, len(dev))
    out: dict = {"name": path.name, "ms": ms, "kind": saved.get("kind", "?")}
    gold, pred = [r["intent"] for r in dev], [i for i, _ in dev_out]
    out["dev_acc"] = sum(g == p for g, p in zip(gold, pred, strict=True)) / len(gold)
    out["dev_f1"] = macro_f1(gold, pred)
    out["dev_by_lang"] = {}
    for lang in ("en", "si-Latn", "si"):
        idx = [k for k, r in enumerate(dev) if r["lang"] == lang]
        if idx:
            out["dev_by_lang"][lang] = sum(gold[k] == pred[k] for k in idx) / len(idx)
    rows = [r for r in test if not r["context"]]
    results = [(r, *classify(r["text"], r["lang"])) for r in rows]
    out["test_acc"] = sum(right(r, i) for r, i, _ in results) / len(results)
    out["test_by_lang"] = {}
    for lang in ("en", "si-Latn", "si"):
        sub = [(r, i) for r, i, _ in results if r["lang"] == lang]
        if sub:
            out["test_by_lang"][lang] = (sum(right(r, i) for r, i in sub), len(sub))
    out["test_by_set"] = {}
    for name in ("commands", "commands_heldout", "intents_heldout"):
        sub = [(r, i) for r, i, _ in results if r["set"] == name]
        if sub:
            out["test_by_set"][name] = (sum(right(r, i) for r, i in sub), len(sub))
    out["confident"] = []
    for limit in (0.5, 0.6, 0.7, 0.8, 0.9):
        sure = [(r, i) for r, i, c in results if c >= limit]
        out["confident"].append((limit, len(sure), sum(right(r, i) for r, i in sure), len(results)))
    out["mistakes"] = [(r["text"], i, c, r["accept"] or "no action") for r, i, c in results if not right(r, i)]
    out["confusions"] = collections.Counter((g, p) for g, p in zip(gold, pred, strict=True) if g != p).most_common(8)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("models", nargs="*", type=Path,
                    help="saved model files (.joblib); none: every .joblib in models/intent/")
    args = ap.parse_args()
    models = args.models or sorted((ROOT / "models" / "intent").glob("*.joblib"))
    if not models:
        sys.exit("No model in models/intent/ yet: train one first (docs/TRAINING_INTENT.md, step 2)")
    dev, test = load("dev.jsonl"), load("test_real.jsonl")
    for path in models:
        r = evaluate(path, dev, test)
        print(f"\n=== {r['name']} ({r['kind']}), {r['ms']:.1f} ms a sentence")
        langs = ", ".join(f"{k} {v:.0%}" for k, v in r["dev_by_lang"].items())
        print(f"dev        accuracy {r['dev_acc']:.1%}, macro-F1 {r['dev_f1']:.3f}  ({langs})")
        langs = ", ".join(f"{k} {a}/{n}" for k, (a, n) in r["test_by_lang"].items())
        print(f"real test  {r['test_acc']:.1%}  ({langs})")
        sets = ", ".join(f"{k} {a}/{n}" for k, (a, n) in r["test_by_set"].items())
        print(f"           by set: {sets}")
        print("confident  limit  decides alone   right when it does")
        for limit, n, ok, total in r["confident"]:
            print(f"           {limit:.1f}    {n:3}/{total}        {ok}/{n} = {ok / n:.0%}" if n else
                  f"           {limit:.1f}      0/{total}")
        print("dev confusions (true -> said):", "; ".join(f"{g}->{p} x{n}" for (g, p), n in r["confusions"]))
        print("real mistakes:")
        for text, intent, conf, wanted in r["mistakes"]:
            print(f"  {text[:50]:50} -> {intent} {conf:.2f}  (wanted {wanted})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
