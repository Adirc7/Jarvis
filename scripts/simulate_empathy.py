"""Measure an empathy learner on simulated users, before trusting it with a real one.

    uv run python scripts/simulate_empathy.py                  # fixed vs random vs yours (if it exists)
    uv run python scripts/simulate_empathy.py --turns 400 --runs 200 --seed 7

Each simulated user secretly likes one mode best: after a reply in mode m
they give good feedback with probability p[m] (a Bernoulli "arm"). The
learner only sees the feedback, through the same counts Jarvis keeps
(empathy/store.py). Regret after T replies = sum over replies of
(p_best - p_chosen): how much good feedback was lost by not always using the
best mode. A learner that learns has regret that flattens out; one that
doesn't (fixed, random) grows in a straight line.

Users (made up, to cover the cases that matter):
  wants-logical       p = logical 0.8, balanced 0.5, supportive 0.2
  wants-supportive    p = logical 0.2, balanced 0.5, supportive 0.75
  close-call          p = logical 0.55, balanced 0.6, supportive 0.5   (hard: modes nearly equal)
  changes-mind        wants-logical for the first half, then wants-supportive (non-stationary)
  sparse              wants-logical, but gives feedback only 30% of the time (most replies get none)

Writes docs/empathy_simulation.md (a table) and docs/empathy_simulation.svg
(regret over time) for your report. Learners: "fixed (balanced)", "random",
"epsilon-greedy" (a simple reference: the best mode so far, 10% of the time a
random one), and yours (jarvis.empathy.thompson.ThompsonLearner) when it
exists. Runs are seeded, so the numbers repeat.
"""

from __future__ import annotations

import argparse
import importlib
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.empathy.learner import FixedLearner

MODES = ["logical", "balanced", "supportive"]
USERS = {
    "wants-logical": lambda t, T: {"logical": 0.8, "balanced": 0.5, "supportive": 0.2},
    "wants-supportive": lambda t, T: {"logical": 0.2, "balanced": 0.5, "supportive": 0.75},
    "close-call": lambda t, T: {"logical": 0.55, "balanced": 0.6, "supportive": 0.5},
    "changes-mind": lambda t, T: ({"logical": 0.8, "balanced": 0.5, "supportive": 0.2} if t < T // 2
                                  else {"logical": 0.2, "balanced": 0.5, "supportive": 0.75}),
    "sparse": lambda t, T: {"logical": 0.8, "balanced": 0.5, "supportive": 0.2},
}
FEEDBACK_RATE = {"sparse": 0.3}


class RandomLearner:
    name = "random"

    def choose(self, modes, counts, rng):
        return rng.choice(modes)


class EpsilonGreedy:
    """A reference, not the answer: the best average so far, and 10% of the time a random mode."""

    name = "epsilon-greedy (0.1)"

    def __init__(self, epsilon: float = 0.1):
        self.epsilon = epsilon

    def choose(self, modes, counts, rng):
        if rng.random() < self.epsilon:
            return rng.choice(modes)
        def mean(m):
            good, bad = counts.get(m, (0.0, 0.0))
            return (good + 1) / (good + bad + 2)          # unseen modes start at 0.5
        return max(modes, key=lambda m: (mean(m), rng.random()))


def learners():
    found = [FixedLearner("balanced"), RandomLearner(), EpsilonGreedy()]
    try:
        found.append(importlib.import_module("jarvis.empathy.thompson").ThompsonLearner())
    except (ImportError, AttributeError) as exc:
        print(f"(your learner isn't there yet: src/jarvis/empathy/thompson.py, {type(exc).__name__})")
    return found


def run(learner, user: str, turns: int, seed: int) -> list[float]:
    """Cumulative regret after each reply, for one simulated user."""
    rng = random.Random(seed)
    counts: dict[str, list[float]] = {}
    regret, total = [], 0.0
    for t in range(turns):
        p = USERS[user](t, turns)
        view = {m: (c[0], c[1]) for m, c in counts.items()}
        mode = learner.choose(list(MODES), view, rng)
        if mode not in MODES:
            raise ValueError(f"{learner.name} chose {mode!r}, not one of the allowed modes")
        total += max(p.values()) - p[mode]
        regret.append(total)
        if rng.random() < FEEDBACK_RATE.get(user, 1.0):
            good = rng.random() < p[mode]
            cell = counts.setdefault(mode, [0.0, 0.0])
            cell[0 if good else 1] += 1.0
    return regret


def svg(curves: dict[str, list[float]], title: str) -> str:
    W, H, L, B, T, R = 720, 360, 56, 36, 30, 180
    top = max(max(c) for c in curves.values()) or 1
    n = max(len(c) for c in curves.values())
    colours = ["#8fa7ba", "#ff766f", "#ffb43b", "#4de1ff", "#64efb7"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Segoe UI, sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#091522"/>',
             f'<text x="{L}" y="20" fill="#eaf5ff" font-size="14">{title}</text>']
    for k in range(5):
        y = T + (H - T - B) * k / 4
        parts.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.0f}" y2="{y:.0f}" stroke="#12314a"/>')
        parts.append(f'<text x="{L - 6}" y="{y + 4:.0f}" fill="#8fa7ba" font-size="11" text-anchor="end">'
                     f'{top * (1 - k / 4):.0f}</text>')
    parts.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 8}" fill="#8fa7ba" font-size="11" text-anchor="middle">'
                 f'replies (0 to {n})</text>')
    for i, (name, c) in enumerate(curves.items()):
        pts = " ".join(f"{L + (W - L - R) * t / max(1, n - 1):.1f},{T + (H - T - B) * (1 - v / top):.1f}"
                       for t, v in enumerate(c))
        colour = colours[i % len(colours)]
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2"/>')
        parts.append(f'<text x="{W - R + 8}" y="{T + 16 + i * 18}" fill="{colour}" font-size="12">{name}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--turns", type=int, default=300)
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=str(ROOT / "docs" / "empathy_simulation"))
    args = ap.parse_args(argv)
    found = learners()
    rows = ["| user | " + " | ".join(lr.name for lr in found) + " |", "|---|" + "---|" * len(found)]
    mean_curves: dict[str, list[float]] = {}
    for user in USERS:
        cells = []
        for lr in found:
            finals, curves = [], []
            for r in range(args.runs):
                curve = run(lr, user, args.turns, args.seed * 10_000 + r)
                finals.append(curve[-1])
                curves.append(curve)
            spread = statistics.stdev(finals) if len(finals) > 1 else 0.0
            cells.append(f"{statistics.mean(finals):.1f} ± {spread:.1f}")
            if user == "changes-mind":
                mean_curves[lr.name] = [statistics.mean(c[t] for c in curves) for t in range(args.turns)]
        rows.append(f"| {user} | " + " | ".join(cells) + " |")
    table = "\n".join(rows)
    print(f"Regret after {args.turns} replies (mean ± sd over {args.runs} runs; lower is better):\n")
    print(table)
    out = Path(args.out)
    out.with_suffix(".md").write_text(
        f"# Empathy learner on simulated users\n\nRegret after {args.turns} replies, mean ± sd over "
        f"{args.runs} seeded runs (lower is better); made by `scripts/simulate_empathy.py`.\n\n{table}\n\n"
        f"![regret over time, user who changes their mind]({out.with_suffix('.svg').name})\n", encoding="utf-8")
    out.with_suffix(".svg").write_text(svg(mean_curves, "Regret over time: a user who changes their mind"),
                                       encoding="utf-8")
    print(f"\nWrote {out.with_suffix('.md')} and {out.with_suffix('.svg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
