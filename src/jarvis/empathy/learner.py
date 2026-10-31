"""How a mode is chosen from the counts. YOURS goes in thompson.py (docs/TRAINING_EMPATHY.md).

A learner is anything with this method:

    choose(modes, counts, rng) -> mode
        modes   the modes allowed right now, e.g. ["logical", "balanced", "supportive"]
        counts  {mode: (good, bad)} so far (fractional; a mode never tried isn't in it)
        rng     a random.Random to draw from (the tests and the simulator seed it)

It must return one of `modes`. It never sees what you said, only counts.
"""

from __future__ import annotations

import importlib
import random
from typing import Protocol


class Learner(Protocol):
    name: str

    def choose(self, modes: list[str], counts: dict[str, tuple[float, float]], rng: random.Random) -> str: ...


class FixedLearner:
    """Always the same mode (the default): what Jarvis did before learning. The baseline to beat."""

    def __init__(self, mode: str = "balanced"):
        self.mode, self.name = mode, f"fixed ({mode})"

    def choose(self, modes: list[str], counts: dict[str, tuple[float, float]], rng: random.Random) -> str:
        return self.mode if self.mode in modes else modes[0]


def load_learner(name: str, default_mode: str = "balanced") -> tuple[Learner, str]:
    """[empathy] learner: "fixed", or "thompson" (yours: jarvis.empathy.thompson.ThompsonLearner).
    Returns the learner and a note when the one asked for couldn't be used."""
    if name == "thompson":
        try:
            module = importlib.import_module("jarvis.empathy.thompson")
            return module.ThompsonLearner(), ""
        except (ImportError, AttributeError) as exc:
            return FixedLearner(default_mode), (f"[empathy] learner = \"thompson\", but src/jarvis/empathy/thompson.py "
                                                f"isn't there yet ({type(exc).__name__}); using the fixed mode")
    return FixedLearner(default_mode), ""
