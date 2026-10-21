"""Make the intent training data: thousands of labelled sentences from patterns.

    uv run python scripts/make_intent_data.py            # writes data/generated/
    uv run python scripts/make_intent_data.py --show 20  # and prints 20 random Sinhala examples
    uv run python scripts/make_intent_data.py --show 20 --lang si-Latn   # ... Singlish examples

Outputs (gitignored; run again any time, the same seed gives the same data):
  data/generated/intents.jsonl          one example per line: text, lang, intent, slots, form
  data/generated/sinhala_sentences.txt  the Sinhala-script sentences only (vocabulary, TTS tests)
  data/generated/study_topics.tsv       every study topic: id, area, Sinhala, Singlish, English
  data/generated/si_reading_list.txt    with --reading-list N: N Sinhala sentences to record for
                                        TRAINING the speech model (none from the test set)

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
from jarvis.intents.patterns import LANGUAGES, STUDY_INTENTS, STUDY_TOPICS, examples_per_intent  # noqa: E402


def write_reading_list(examples, n: int, path: Path, seed: int) -> Path:
    """N Sinhala sentences spread over every intent, for recording training audio.

    Sentences in the test files (eval/sentences_si*.txt) are left out: the
    speech model must never train on what it is tested on.
    """
    test = set()
    for f in (ROOT / "eval").glob("sentences_si*.txt"):
        test |= {ln.strip() for ln in f.read_text(encoding="utf-8-sig").splitlines()}
    by_intent: dict[str, list[str]] = collections.defaultdict(list)
    for ex in examples:
        if ex.lang == "si" and ex.text not in test and len(ex.text.split()) >= 3:
            by_intent[ex.intent].append(ex.text)
    rng = random.Random(seed)
    for texts in by_intent.values():
        rng.shuffle(texts)
    picked: list[str] = []
    while len(picked) < n and any(by_intent.values()):
        for intent in sorted(by_intent):                       # one from each intent in turn
            if by_intent[intent] and len(picked) < n:
                picked.append(by_intent[intent].pop())
    header = ["# Sinhala sentences to read aloud for TRAINING the speech model (not the test set).",
              "# Record: uv run python scripts/record_eval_set.py data/generated/si_reading_list.txt "
              "--lang si --set si-train",
              "# Read naturally, as you would talk to Jarvis. Skip (s) any you'd never say."]
    path.write_text("\n".join(header + picked) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "generated")
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--show", type=int, default=0, help="print this many random examples")
    ap.add_argument("--lang", default="si", choices=["si", "si-Latn", "en"], help="language for --show")
    ap.add_argument("--reading-list", type=int, default=0, metavar="N",
                    help="also write N Sinhala sentences to read aloud for training Whisper")
    args = ap.parse_args()

    examples = generate(LANGUAGES, examples_per_intent, seed=args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "intents.jsonl", "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex.as_dict(), ensure_ascii=False) + "\n")
    si = sorted({ex.text for ex in examples if ex.lang == "si"})
    (args.out / "sinhala_sentences.txt").write_text("\n".join(si) + "\n", encoding="utf-8")
    rows = ["id\tarea\tsinhala\tsinglish\tenglish"] + ["\t".join(t) for t in STUDY_TOPICS]
    (args.out / "study_topics.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    if args.reading_list:
        path = write_reading_list(examples, args.reading_list, args.out / "si_reading_list.txt", args.seed)
        print(f"Reading list: {args.reading_list} sentences -> {path}")

    counts = collections.Counter((ex.intent, ex.lang) for ex in examples)
    langs = list(LANGUAGES)
    print(f"{len(examples)} examples -> {args.out / 'intents.jsonl'}")
    print(f"{'intent':20} " + " ".join(f"{lang:>8}" for lang in langs))
    for intent in sorted({ex.intent for ex in examples}):
        mark = "  (study)" if intent in STUDY_INTENTS else ""
        print(f"{intent:20} " + " ".join(f"{counts[(intent, lang)]:>8}" for lang in langs) + mark)
    forms = collections.Counter(ex.form for ex in examples if ex.lang == "si" and ex.form)
    print("Sinhala verb forms: " + ", ".join(f"{k} {v}" for k, v in forms.most_common()))
    by_lang = collections.Counter(ex.lang for ex in examples)
    print("By language: " + ", ".join(f"{lang} {by_lang[lang]}" for lang in langs)
          + f"; {len(STUDY_TOPICS)} study topics -> {args.out / 'study_topics.tsv'}")
    if args.show:
        for ex in random.Random(args.seed).sample([e for e in examples if e.lang == args.lang], args.show):
            print(f"  [{ex.intent}] {ex.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
