"""Telemetry: every stage writes one JSON line, so metrics exist from day one.

Usage:
    tel = Telemetry.for_session()
    with tel.span("stt", model="small"):
        ...                                  # logs {"event": "stt", "ms": ...}
    turn = tel.turn()                         # one user request, end to end
    turn.mark("speech_end"); ...; turn.mark("first_audio"); turn.finish()

Summarise a log file (median and p95 per stage):
    python -m jarvis.telemetry                 the newest session in logs/
    python -m jarvis.telemetry logs/session-20261021-041323.jsonl
"""

from __future__ import annotations

import json
import math
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


class Telemetry:
    def __init__(self, path: Path | None):
        self.path = path
        self.session_id = uuid.uuid4().hex[:8]
        self._lock = threading.Lock()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_session(cls, log_dir: Path | str = "logs", prefix: str = "session") -> "Telemetry":
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return cls(Path(log_dir) / f"{prefix}-{stamp}.jsonl")

    @classmethod
    def disabled(cls) -> "Telemetry":
        return cls(None)

    def log(self, event: str, **fields: Any) -> None:
        if self.path is None:
            return
        record = {"t": round(time.time(), 3), "session": self.session_id, "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    @contextmanager
    def span(self, event: str, **fields: Any) -> Iterator[dict[str, Any]]:
        """Time a block. Add result fields to the yielded dict inside the block."""
        extra: dict[str, Any] = {}
        start = time.perf_counter()
        ok = True
        try:
            yield extra
        except BaseException as exc:
            ok = False
            extra["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            ms = (time.perf_counter() - start) * 1000
            self.log(event, ms=round(ms, 1), ok=ok, **fields, **extra)

    def turn(self, **fields: Any) -> "Turn":
        return Turn(self, fields)


class Turn:
    """Marks the timeline of one request so the whole chain can be measured."""

    def __init__(self, tel: Telemetry, fields: dict[str, Any]):
        self._tel = tel
        self._fields = fields
        self.id = uuid.uuid4().hex[:8]
        self._t0 = time.perf_counter()
        self.marks: dict[str, float] = {}

    def mark(self, name: str) -> float:
        ms = (time.perf_counter() - self._t0) * 1000
        self.marks.setdefault(name, round(ms, 1))
        return ms

    def finish(self, **fields: Any) -> None:
        merged = {**self._fields, **fields}   # finish() values override start values
        self._tel.log("turn", turn=self.id, marks=self.marks, **merged)


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile: p95 = smallest value with >= 95% of data at or below it."""
    if not values:
        return math.nan
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize(path: Path) -> dict[str, dict[str, float]]:
    """Median, p95 and count of `ms` for every event name in a log file."""
    by_event: dict[str, list[float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if "ms" in rec:
            by_event.setdefault(rec["event"], []).append(float(rec["ms"]))
        if rec.get("event") == "turn":
            for mark, ms in rec.get("marks", {}).items():
                by_event.setdefault(f"turn.{mark}", []).append(float(ms))
    return {
        name: {"n": len(v), "p50": percentile(v, 50), "p95": percentile(v, 95), "mean": sum(v) / len(v)}
        for name, v in sorted(by_event.items())
    }


def newest_session(log_dir: Path) -> Path | None:
    sessions = sorted(log_dir.glob("session-*.jsonl"))   # names sort by date and time
    return sessions[-1] if sessions else None


def _main(argv: list[str], log_dir: Path = Path("logs")) -> int:
    if len(argv) > 1:
        print("usage: python -m jarvis.telemetry [logs/session-....jsonl]  (default: the newest session)")
        return 2
    if argv:
        path = Path(argv[0])
        if not path.is_file():
            print(f"No file {path}. Sessions in {log_dir}:")
            for f in sorted(log_dir.glob("session-*.jsonl")):
                print(f"  {f}")
            return 1
    else:
        path = newest_session(log_dir)
        if path is None:
            print(f"No session logs in {log_dir} yet: talk to Jarvis first.")
            return 1
    print(f"{path}\n")
    stats = summarize(path)
    print(f"{'event':32} {'n':>5} {'p50 ms':>9} {'p95 ms':>9} {'mean ms':>9}")
    for name, s in stats.items():
        print(f"{name:32} {s['n']:>5} {s['p50']:>9.1f} {s['p95']:>9.1f} {s['mean']:>9.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
