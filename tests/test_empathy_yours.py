"""Checks for YOUR learner (src/jarvis/empathy/thompson.py, docs/TRAINING_EMPATHY.md).

Skipped until the file exists. Then: uv run pytest tests/test_empathy_yours.py -v
"""

import random
from collections import Counter

import pytest

thompson = pytest.importorskip("jarvis.empathy.thompson", reason="write src/jarvis/empathy/thompson.py first")
MODES = ["logical", "balanced", "supportive"]


def learner():
    return thompson.ThompsonLearner()


def picks(counts, n=400, seed=3, modes=MODES):
    rng = random.Random(seed)
    lr = learner()
    return Counter(lr.choose(list(modes), counts, rng) for _ in range(n))


def test_it_has_a_name_and_only_picks_allowed_modes():
    assert isinstance(learner().name, str) and learner().name
    assert set(picks({}, 200)) <= set(MODES)
    assert set(picks({}, 50, modes=["balanced", "supportive"])) <= {"balanced", "supportive"}


def test_with_no_feedback_it_tries_every_mode():
    seen = picks({})
    assert all(seen[m] >= 60 for m in MODES), seen          # about a third each


def test_with_clear_feedback_it_mostly_picks_the_best():
    seen = picks({"logical": (20.0, 2.0), "balanced": (5.0, 10.0), "supportive": (2.0, 20.0)})
    assert seen["logical"] >= 0.9 * 400, seen


def test_it_still_explores_when_unsure():
    seen = picks({"logical": (2.0, 1.0), "balanced": (1.0, 2.0)})      # little feedback; supportive untried
    assert seen["supportive"] >= 40 and seen["balanced"] >= 20, seen


def test_fractional_counts_work_and_the_rng_decides():
    counts = {"logical": (1.5, 0.5), "balanced": (0.5, 1.5)}
    a = [learner().choose(MODES, counts, random.Random(7)) for _ in range(3)]
    b = [learner().choose(MODES, counts, random.Random(7)) for _ in range(3)]
    assert a == b                                            # the same rng, the same choice: no other randomness
