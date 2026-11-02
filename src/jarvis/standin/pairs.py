"""What your stand-in model learns from: the questions you asked and the language model's answers.

    log = PairLog(Path("data/standin"))
    log.add("what is entropy?", "Entropy measures ...", route="teach", lang="en", provider="groq_oss", session="ab12")
    train, held_out = split(log.read(), held_out=0.15)      # the newest 15% are never trained on

Only answers that stay true are kept: a plain reply (no tools: no news, weather, PC action or MATLAB run),
and not a question about the time, today or the latest anything, which would be wrong when replayed later.
Text only, never audio, in data/standin/pairs.jsonl (gitignored, like the rest of data/).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Replayed tomorrow, these answers would be wrong
TIME_BOUND = re.compile(
    r"\b(what time|the time|time is it|date|today|tonight|tomorrow|yesterday|right now|latest|recent|news|"
    r"weather|forecast|prices?|scores?|currently|this (?:week|month|year)|ada|heta|iye)\b", re.IGNORECASE)
# ("time" and "current" alone stay: time dilation and electric current are timeless)
SKIP_ROUTES = {"command"}                 # "open notepad": an action, not an answer
MIN_QUESTION, MAX_REPLY = 6, 4000


@dataclass(frozen=True)
class Pair:
    id: str
    time: str
    question: str
    reply: str
    route: str = ""
    lang: str = "en"
    provider: str = ""
    session: str = ""

    def row(self) -> dict:
        return {"id": self.id, "time": self.time, "question": self.question, "reply": self.reply,
                "route": self.route, "lang": self.lang, "provider": self.provider, "session": self.session}


def keepable(question: str, reply: str, route: str = "") -> bool:
    """Would this answer still be right if Jarvis said it again next week?"""
    q = question.strip()
    return (len(q) >= MIN_QUESTION and bool(reply.strip()) and route not in SKIP_ROUTES
            and not TIME_BOUND.search(q) and not q.startswith("/"))


class PairLog:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.path = self.folder / "pairs.jsonl"

    def add(self, question: str, reply: str, route: str = "", lang: str = "en", provider: str = "",
            session: str = "", now: datetime | None = None) -> Pair | None:
        """Keep one exchange if it's timeless; returns it, or None when it isn't kept."""
        if not keepable(question, reply, route):
            return None
        when = (now or datetime.now()).isoformat(timespec="seconds")  # noqa: DTZ005 - local, like the logs
        pid = hashlib.sha1(f"{when}|{question}".encode()).hexdigest()[:12]
        pair = Pair(pid, when, question.strip()[:1000], reply.strip()[:MAX_REPLY], route, lang, provider, session)
        self.folder.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(pair.row(), ensure_ascii=False) + "\n")
        return pair

    def read(self) -> list[Pair]:
        if not self.path.is_file():
            return []
        pairs = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                pairs.append(Pair(**{k: row.get(k, "") for k in Pair.__dataclass_fields__}))
        return pairs


def split(pairs: list[Pair], held_out: float = 0.15, minimum: int = 5) -> tuple[list[Pair], list[Pair]]:
    """Train on the older pairs, test on the newest: a model is judged on conversations it never saw."""
    ordered = sorted(pairs, key=lambda p: p.time)
    n = max(minimum, round(len(ordered) * held_out)) if len(ordered) > 2 * minimum else 0
    return (ordered[:-n], ordered[-n:]) if n else (ordered, [])


__all__ = ["Pair", "PairLog", "TIME_BOUND", "keepable", "split"]
