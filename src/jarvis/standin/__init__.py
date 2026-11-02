"""Your stand-in model: answers when the language models can't (docs/TRAINING_STANDIN.md).

Jarvis keeps the questions you asked and the answers the language models gave (pairs.py). When no model
can be reached, or none has started answering after a few seconds on a weak connection, the stand-in
answers instead, and says so:

- version 1, the lookup (lookup.py): the answer to the nearest past question, when it's the same question;
- version 2, YOUR student (student.py): a small model trained on those pairs on Kaggle's free GPU
  (kaggle/standin/train_standin.py, scripts/train_standin.py), used only after it beat the lookup on
  conversations it never saw (evaluate.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lookup import Lookup, make_encoder
from .pairs import PairLog
from .student import Student


@dataclass(frozen=True)
class StandInReply:
    text: str
    how: str             # "lookup" or "student"
    score: float         # how close the question was to one asked before


class StandIn:
    def __init__(self, data_folder: Path, model_folder: Path, encoder: str = "", min_similarity: float | None = None,
                 student_min_similarity: float | None = None, save: bool = True):
        self.log = PairLog(data_folder)
        self.model_folder = Path(model_folder)
        self.encoder_name, self.min_similarity, self.student_min = encoder, min_similarity, student_min_similarity
        self.save = save
        self.lookup: Lookup | None = None
        self.student: Student | None = None
        self.problem = ""

    def prepare(self) -> str:
        """Load the encoder, the saved pairs and an adopted student (slow: in a worker thread at start)."""
        self.lookup = Lookup(self.log.read(), make_encoder(self.encoder_name), self.min_similarity)
        if self.student_min is None:
            self.student_min = getattr(self.lookup.encoder, "student_threshold", self.lookup.min_similarity)
        try:
            self.student = Student.load(self.model_folder / "current")
        except Exception as exc:  # noqa: BLE001 - a broken model folder: the lookup still works
            self.student, self.problem = None, f"your student model didn't load ({type(exc).__name__}: {exc})"[:200]
        return self.describe()

    def describe(self) -> str:
        if self.lookup is None:
            return "not ready yet"
        who = (f"your {self.student.kind} model ({self.student.manifest.get('base', '?')}) and the lookup"
               if self.student else "the lookup")
        return f"{who}, over {len(self.lookup.pairs)} saved answers ({self.lookup.encoder.name})"

    def add(self, question: str, reply: str, **meta) -> None:
        if not self.save:
            return
        pair = self.log.add(question, reply, **meta)
        if pair is not None and self.lookup is not None:
            self.lookup.add([pair])

    def answer(self, question: str) -> StandInReply | None:
        """An answer to give instead of the language model's, or None when it would only be a guess."""
        if self.lookup is None:
            return None
        return reply_for(question, self.lookup, self.student, self.student_min)


def reply_for(question: str, lookup: Lookup, student: Student | None = None,
              student_min: float | None = None) -> StandInReply | None:
    """Your student answers when the question is near what it learned from; else the lookup, when it's the
    same question as before; else nothing. Jarvis and the test before use (scripts/train_standin.py) both
    decide this way."""
    match = lookup.nearest(question)
    if match is None:
        return None
    if student is not None and match.score >= float(student_min if student_min is not None else 0):
        text = student.answer(question)
        if text:
            return StandInReply(text, "student", match.score)
    if match.score >= lookup.min_similarity:
        return StandInReply(match.pair.reply, "lookup", match.score)
    return None


__all__ = ["StandIn", "StandInReply", "reply_for"]
