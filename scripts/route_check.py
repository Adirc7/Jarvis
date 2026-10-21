"""How well do the keyword rules route requests? A baseline for the intent classifier.

    uv run python scripts/route_check.py              # accuracy per language and per route
    uv run python scripts/route_check.py --wrong 20   # and 20 sentences it routed wrongly

Every generated sentence (scripts/make_intent_data.py) has an intent, and
each intent has a route (agent/router.py, INTENT_ROUTE). This routes each
sentence with the keyword rules and counts how often the route is right.
Your classifier should beat this number; report both. (Generated sentences
are easier than real ones: the real test is your own sentences.)
"""

from __future__ import annotations

import argparse
import collections
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.agent.router import ROUTES, KeywordRouter, route_for_intent  # noqa: E402
from jarvis.intents.generate import generate  # noqa: E402
from jarvis.intents.patterns import LANGUAGES, examples_per_intent  # noqa: E402


def check(seed: int = 21) -> tuple[dict[str, tuple[int, int]], collections.Counter, list]:
    router = KeywordRouter()
    per_lang: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    confusion: collections.Counter = collections.Counter()
    wrong = []
    for ex in generate(LANGUAGES, examples_per_intent, seed=seed):
        want = route_for_intent(ex.intent)
        got = router.route(ex.text, ex.lang).route
        per_lang[ex.lang][0] += got == want
        per_lang[ex.lang][1] += 1
        confusion[(want, got)] += 1
        if got != want:
            wrong.append((ex, want, got))
    return {k: (v[0], v[1]) for k, v in per_lang.items()}, confusion, wrong


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wrong", type=int, default=0, help="print this many wrongly routed sentences")
    args = ap.parse_args()
    per_lang, confusion, wrong = check()
    right = sum(r for r, _ in per_lang.values())
    total = sum(n for _, n in per_lang.values())
    print(f"Keyword rules: {right / total:.1%} of {total} generated sentences go to the right route")
    for lang, (r, n) in per_lang.items():
        print(f"  {lang:8} {r / n:6.1%}  ({r} of {n})")
    print("\nRows: the right route; columns: where the rules sent it.")
    print(f"{'':9}" + "".join(f"{r[:7]:>8}" for r in ROUTES))
    for want in ROUTES:
        if any(confusion[(want, g)] for g in ROUTES):
            print(f"{want:9}" + "".join(f"{confusion[(want, g)] or '.':>8}" for g in ROUTES))
    for ex, want, got in random.Random(1).sample(wrong, min(args.wrong, len(wrong))):
        print(f"  [{ex.intent} -> {want}, rules said {got}] {ex.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
