"""The empathy learner inside Jarvis: when to choose a mode, within your limits.

    coach = EmpathyCoach(store, learner, allowed=["logical", "balanced", "supportive"])
    feedback = coach.after_user_turn(text, interrupted=..., asked_mode=...)   # counts it
    mode = coach.mode_for(text, current)                                      # for the reply

Rules (ROADMAP "Empathy modes"):
- Only the modes you allow ([empathy] allowed); the learner can't leave them.
- You decide first: "be more direct" sets the mode for the rest of the session
  (and counts against the mode you were in).
- Real distress always gets the supportive mode, whatever was learned (it isn't
  counted as the learner's choice).
- Not every turn: Jarvis chooses again after feedback or every few replies, so
  the style doesn't flicker.
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable

from .learner import Learner
from .signals import Feedback, feedback_from
from .store import EmpathyStore

DISTRESS = re.compile(
    r"\b(want to die|kill myself|end my life|hopeless|can'?t take (it|this) anymore|panic attack|"
    r"breaking down|can'?t cope|so depressed|nobody cares|worthless)\b|මැරෙන්න|බලාපොරොත්තු නෑ|"
    r"දරාගන්න බෑ", re.IGNORECASE)


class EmpathyCoach:
    def __init__(self, store: EmpathyStore, learner: Learner, allowed: list[str], *, rechoose_every: int = 5,
                 rng: random.Random | None = None, clock: Callable[[], float] = time.monotonic):
        self.store, self.learner, self.allowed = store, learner, list(allowed)
        self.rechoose_every, self.rng, self.clock = max(1, rechoose_every), rng or random.Random(), clock
        self.manual: str | None = None          # a mode you asked for: kept for the session
        self.last_mode: str | None = None       # the mode of Jarvis's last reply
        self.last_question = ""
        self.last_reply_at = -1e9
        self.replies_since_choice = 10**6       # choose at the first reply
        self.due = True

    # ---- after you speak ---------------------------------------------------------------
    def after_user_turn(self, text: str, *, interrupted: bool = False, asked_mode: str | None = None,
                        context: str = "all") -> list[Feedback]:
        found = feedback_from(text, last_mode=self.last_mode, last_question=self.last_question,
                              seconds_since_reply=self.clock() - self.last_reply_at, interrupted=interrupted,
                              asked_mode=asked_mode, context=context)
        for fb in found:
            self.store.add(fb)
        if found:
            self.store.save()
            self.due = True                     # feedback: think again before the next reply
        if asked_mode is not None and asked_mode in self.allowed:
            self.manual = asked_mode
        return found

    # ---- before Jarvis answers -------------------------------------------------------------
    def mode_for(self, text: str, current: str, context: str = "all") -> tuple[str, str]:
        """(mode, why) for the reply to `text`. why: "distress", "manual", "learner" or "kept"."""
        if DISTRESS.search(text):
            return ("supportive" if "supportive" in self.allowed or not self.allowed else current), "distress"
        if self.manual:
            return self.manual, "manual"
        if self.due or self.replies_since_choice >= self.rechoose_every:
            choice = self.learner.choose(self.allowed, self.store.for_context(context), self.rng)
            if choice not in self.allowed:      # a learner can't leave your limits
                choice = current if current in self.allowed else self.allowed[0]
            self.due, self.replies_since_choice = False, 0
            return choice, "learner"
        return (current if current in self.allowed else self.allowed[0]), "kept"

    def replied(self, question: str, mode: str) -> None:
        self.last_mode, self.last_question, self.last_reply_at = mode, question, self.clock()
        self.replies_since_choice += 1
