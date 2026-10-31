"""The empathy learner (M2): Jarvis learns which empathy mode suits you from what you tell him anyway.

    signals.py   what counts as feedback: "thanks", "too long", "be more direct", interrupting
                 him, asking the same thing again -> Feedback(mode, reward, weight, why)
    store.py     the good/bad counts per mode (state/empathy.json) and every feedback event
                 (state/empathy-log.jsonl, for your evaluation)
    learner.py   how a mode is chosen from the counts: FixedLearner until yours exists;
                 YOURS goes in thompson.py (docs/TRAINING_EMPATHY.md)
    coach.py     in Jarvis: when to choose, your limits, the distress override, manual commands

The LLM is never retrained: the mode only changes the instruction it gets
and the voice's speed (config/persona.toml). Jarvis adapts his own style; he
never tries to change how you feel.
"""

from .coach import EmpathyCoach
from .learner import FixedLearner, Learner, load_learner
from .signals import Feedback, feedback_from
from .store import EmpathyStore

__all__ = ["EmpathyCoach", "EmpathyStore", "Feedback", "FixedLearner", "Learner", "feedback_from", "load_learner"]
