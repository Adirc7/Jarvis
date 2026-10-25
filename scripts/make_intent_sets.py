"""Prepare the data for Adhi's intent model: train, dev and a real test set.

    uv run python scripts/make_intent_sets.py

Writes data/intent/ (gitignored; run again any time, the same seed gives the same sets):

  train.jsonl      generated sentences (scripts/make_intent_data.py, remade each
                   time so they match the current patterns) to learn from
  dev.jsonl        generated sentences from PATTERNS the training set never saw:
                   choose settings on this (which features, the limit, ...)
  test_real.jsonl  the real phrasings of eval/commands.jsonl and
                   eval/commands_heldout.jsonl, with the intents that count as
                   right for each; report on this, never tune on it
  labels.txt       the 46 intents

Your own sentences go in data/intent/mine.jsonl, one per line, written by
you (or reviewed by you from Jarvis's logs):

  {"text": "pull up youtube", "lang": "en", "intent": "open_app"}

They are added to train (each counted --mine-weight times, default 3, since
they're real), never to dev or the real test; a line that is also in the
real test is left out and named, so the test stays fair.

Why split dev by pattern and not at random: generated sentences come from
templates ("{please} {open} {app}"). A random split would put sentences from
the same template in both sets, and the model would look better than it is.
Holding whole templates out asks: does it understand a way of saying it that
it never saw?

See docs/TRAINING_INTENT.md for what to do with these.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data" / "generated" / "intents.jsonl"
OUT = ROOT / "data" / "intent"

# What the command tests expect (tools/web.py actions) -> the intents that
# count as right for an intent model, which knows meanings, not tools.
ACCEPT = {
    "open_site": ["open_app"],
    "search_youtube": ["play_music", "search_web"],
    "search_bing": ["search_web"],
    "pause_media": ["pause_media", "stop"],
    "resume_media": ["resume_media"],
    "go_back": ["go_back"],
}
# Intents that make Jarvis do something; a "just answer" line must not get one.
ACTION_INTENTS = {
    "open_app", "close_app", "open_folder", "search_files", "search_web", "play_music", "pause_media",
    "resume_media", "go_back", "stop", "volume_up", "volume_down", "brightness_up", "brightness_down",
    "set_timer", "set_alarm", "set_reminder", "take_screenshot", "send_message", "create_note",
    "system_power", "toggle_setting", "switch_language", "remember_fact",
}


def split_by_pattern(rows: list[dict], dev_share: float, seed: int) -> tuple[list[dict], list[dict]]:
    """Hold out whole templates, per intent, keeping at least one template of each intent for training."""
    by_intent: dict[str, dict[str, list[dict]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        by_intent[r["intent"]][r.get("pattern") or r["text"]].append(r)
    rng = random.Random(seed)
    train, dev = [], []
    for intent in sorted(by_intent):
        patterns = sorted(by_intent[intent])
        rng.shuffle(patterns)
        total = sum(len(by_intent[intent][p]) for p in patterns)
        held = 0
        for i, pattern in enumerate(patterns):
            group = by_intent[intent][pattern]
            if i < len(patterns) - 1 and held + len(group) <= dev_share * total + 1:
                dev += group
                held += len(group)
            else:
                train += group
    return train, dev


def real_tests() -> list[dict]:
    rows = []
    for name in ("commands.jsonl", "commands_heldout.jsonl"):
        for line in (ROOT / "eval" / name).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            expect = case["expect"]
            rows.append({
                "text": case["text"], "lang": {"singlish": "si-Latn"}.get(case["lang"], case["lang"]),
                "expect": expect, "setup": case.get("setup", "none"), "set": name.split(".")[0],
                # "play the second one" needs the list on screen: not something an
                # intent model can know from the sentence alone.
                "context": expect == "play_video",
                "accept": ACCEPT.get(expect, []), "no_action": expect == "none",
            })
    return rows


def read_mine(path: Path, labels: set[str], test_texts: set[str]) -> tuple[list[dict], list[str]]:
    """Your sentences, checked: known intent, not a copy of a real test line."""
    rows, problems = [], []
    if not path.exists():
        return rows, problems
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            text, intent = str(r["text"]).strip(), str(r["intent"])
        except (ValueError, KeyError, TypeError):
            problems.append(f"line {n}: not like {{\"text\": ..., \"lang\": ..., \"intent\": ...}}")
            continue
        if intent not in labels:
            problems.append(f"line {n}: unknown intent {intent!r} (see labels.txt)")
        elif text.lower() in test_texts:
            problems.append(f"line {n}: \"{text}\" is in the real test; left out so the test stays fair")
        else:
            rows.append({"text": text, "lang": r.get("lang", "en"), "intent": intent, "pattern": "mine"})
    return rows, problems


def write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dev-share", type=float, default=0.15, help="share of each intent's sentences held out")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--mine-weight", type=int, default=3, help="how many times each of your sentences counts")
    args = ap.parse_args()
    # Always remake them (7 s, same sentences every time): an old file from an
    # earlier version of the patterns would quietly train on less.
    print("Making the generated sentences (scripts/make_intent_data.py)...")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_intent_data.py")], check=True,
                   stdout=subprocess.DEVNULL)
    rows = [json.loads(line) for line in GENERATED.read_text(encoding="utf-8").splitlines() if line.strip()]
    keep = ("text", "lang", "intent", "pattern")
    rows = [{k: r[k] for k in keep if k in r} for r in rows]
    train, dev = split_by_pattern(rows, args.dev_share, args.seed)
    test = real_tests()
    labels = sorted({r["intent"] for r in rows})
    mine, problems = read_mine(OUT / "mine.jsonl", set(labels), {r["text"].lower() for r in test})
    train += mine * args.mine_weight
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "train.jsonl", train)
    write(OUT / "dev.jsonl", dev)
    write(OUT / "test_real.jsonl", test)
    (OUT / "labels.txt").write_text("\n".join(labels) + "\n", encoding="utf-8")

    def langs(rs: list[dict]) -> str:
        c = collections.Counter(r["lang"] for r in rs)
        return ", ".join(f"{k} {v}" for k, v in sorted(c.items()))

    print(f"train     {len(train):6} sentences ({langs(train)})")
    print(f"dev       {len(dev):6} sentences from templates train never saw ({langs(dev)})")
    print(f"test_real {len(test):6} real phrasings ({langs(test)}); "
          f"{sum(r['context'] for r in test)} need the list on screen (left to the rules and the model)")
    print(f"labels    {len(labels):6} intents -> {OUT.relative_to(ROOT)}")
    print(f"mine      {len(mine):6} of your sentences (data/intent/mine.jsonl), each counted {args.mine_weight}x in train")
    for problem in problems:
        print(f"  mine.jsonl {problem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
