"""Make the intent training data: thousands of labelled sentences from patterns.

    uv run python scripts/make_intent_data.py            # writes data/generated/
    uv run python scripts/make_intent_data.py --show 20  # and prints 20 random Sinhala examples

Outputs (gitignored; run again any time, the same seed gives the same data):
  data/generated/intents.jsonl          one example per line: text, lang, intent, slots, form
  data/generated/sinhala_sentences.txt  the Sinhala-script sentences only (vocabulary, TTS tests)

Patterns live in src/jarvis/intents/patterns.py. This is TRAINING data for
the intent classifier; the test set is your own real sentences.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.intents.generate import generate  # noqa: E402
from jarvis.intents.patterns import LANGUAGES, PER_INTENT  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "generated")
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--show", type=int, default=0, help="print this many random Sinhala examples")
    args = ap.parse_args()

    examples = generate(LANGUAGES, PER_INTENT, seed=args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "intents.jsonl", "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex.as_dict(), ensure_ascii=False) + "\n")
    si = sorted({ex.text for ex in examples if ex.lang == "si"})
    (args.out / "sinhala_sentences.txt").write_text("\n".join(si) + "\n", encoding="utf-8")

    counts = collections.Counter((ex.intent, ex.lang) for ex in examples)
    langs = list(LANGUAGES)
    print(f"{len(examples)} examples -> {args.out / 'intents.jsonl'}")
    print(f"{'intent':20} " + " ".join(f"{lang:>8}" for lang in langs))
    for intent in sorted({ex.intent for ex in examples}):
        print(f"{intent:20} " + " ".join(f"{counts[(intent, lang)]:>8}" for lang in langs))
    forms = collections.Counter(ex.form for ex in examples if ex.lang == "si" and ex.form)
    print("Sinhala verb forms: " + ", ".join(f"{k} {v}" for k, v in forms.most_common()))
    if args.show:
        for ex in random.Random(args.seed).sample([e for e in examples if e.lang == "si"], args.show):
            print(f"  [{ex.intent}] {ex.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
