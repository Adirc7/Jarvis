"""What counts as feedback on Jarvis's last reply, and how much.

Only what you say or do right after a reply counts, and it counts for the
mode that reply was in. Explicit words weigh most; an interruption weighs
half (you may just have thought of something else); asking the same thing
again soon after weighs a lot (the reply missed). Mode commands ("be more
direct") say the current mode was wrong.

reward 1.0 = that worked, 0.0 = it didn't; weight = how much to trust it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..language import normalize

POSITIVE = re.compile(
    r"\b(thanks?|thank you|that helped|helpful|perfect|great|nice|good answer|exactly|got it|makes sense|"
    r"well explained|love it|awesome|niyamai|elakiri|supiri|hari hari|thanks machan)\b|ස්තූතියි|නියමයි|"
    r"හරි හරි|තේරුණා|සුපිරි", re.IGNORECASE)
NEGATIVE = re.compile(
    r"\b(too long|too much|too slow|shorter|get to the point|not helpful|useless|that's not what i asked|"
    r"not what i asked|you're not listening|you are not listening|annoying|stop lecturing|i didn't ask|"
    r"whatever|ugh|meh|dige wadi|epa)\b|එපා|දිග වැඩියි|කෙටියෙන්|තේරෙන්නේ නෑ", re.IGNORECASE)
REPEAT_WINDOW_S = 120
FEEDBACK_WINDOW_S = 300


@dataclass(frozen=True)
class Feedback:
    mode: str               # the mode the reply was in
    reward: float           # 1.0 good, 0.0 bad
    weight: float           # how much this signal is trusted (0-1)
    why: str                # "thanks", "too long", "interrupted", "repeated", "asked for logical"
    context: str = "all"    # later: the emotion Jarvis heard (a contextual bandit)


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def feedback_from(text: str, *, last_mode: str | None, last_question: str = "", seconds_since_reply: float = 1e9,
                  interrupted: bool = False, asked_mode: str | None = None, context: str = "all") -> list[Feedback]:
    """The feedback in what the user just said (or did) about the reply before it."""
    if not last_mode or seconds_since_reply > FEEDBACK_WINDOW_S:
        return []
    out: list[Feedback] = []
    if interrupted:
        out.append(Feedback(last_mode, 0.0, 0.5, "interrupted", context))
    if asked_mode is not None:
        if asked_mode != last_mode:
            out.append(Feedback(last_mode, 0.0, 1.0, f"asked for {asked_mode}", context))
        return out                              # a mode command is all it says
    short = len(normalize(text).split()) <= 12  # "thanks, that helped" is about the reply; a long message isn't
    if short and NEGATIVE.search(text):
        out.append(Feedback(last_mode, 0.0, 1.0, NEGATIVE.search(text).group(0).lower(), context))
    elif short and POSITIVE.search(text):
        out.append(Feedback(last_mode, 1.0, 1.0, POSITIVE.search(text).group(0).lower(), context))
    elif last_question and seconds_since_reply <= REPEAT_WINDOW_S and _similar(text, last_question) >= 0.8:
        out.append(Feedback(last_mode, 0.0, 0.8, "repeated", context))
    return out
