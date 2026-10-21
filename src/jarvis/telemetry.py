"""Telemetry: every stage writes one JSON line, so metrics exist from day one.

Usage:
    tel = Telemetry.for_session()
    with tel.span("stt", model="small"):
        ...                                  # logs {"event": "stt", "ms": ...}
    turn = tel.turn()                         # one user request, end to end
    turn.mark("speech_end"); ...; turn.mark("first_audio"); turn.finish()

Summarise a log file (median and p95 per stage, then one line per request):
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


def turn_rows(path: Path) -> list[dict[str, Any]]:
    """One row per request, with the details that explain its timing.

    Events don't carry a turn id, but each request's events are logged before
    its own "turn" line, so the events since the previous turn belong to it.
    The start-up greeting is spoken outside any turn, so its voice events are
    skipped. (A barge-in can interleave two turns; their rows may then mix.)
    """
    rows: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    after_greeting = False
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        event = rec.get("event")
        if event == "tts" and after_greeting:
            continue
        after_greeting = event == "greeting"
        if event != "turn":
            pending.append(rec)
            continue
        stt, llm, tts = (_first(pending, name) for name in ("stt", "llm_first_token", "tts"))
        marks = rec.get("marks", {})
        rows.append({
            "source": rec.get("source", ""), "kind": rec.get("kind", ""), "audio_s": rec.get("audio_s"),
            "heard": stt.get("language"), "p": stt.get("probability"),
            "retranscribed": bool(stt.get("retranscribed")), "stt_ms": stt.get("ms"),
            "logprob": stt.get("logprob"), "compression": stt.get("compression"),
            "unclear": stt.get("unclear"), "stt_chars": stt.get("chars"),
            "llm_ms": llm.get("ms"), "provider": llm.get("provider"),
            "route": rec.get("route") or _first(pending, "route").get("route"),
            "thinking_ms": _thinking_ms(llm), "thinking_chars": llm.get("thinking_chars"),
            "voice_ms": tts.get("ms"), "voice_chars": tts.get("chars"),
            "filler": marks.get("filler"), "first_audio": marks.get("first_audio"),
            "held_back": _held_back(marks),
        })
        pending = []
    return rows


def _first(events: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((e for e in events if e.get("event") == name), {})


def _held_back(marks: dict[str, Any]) -> float | None:
    """How long the ready first sentence waited to be played (behind a filler)."""
    if marks.get("first_tts") is None or marks.get("first_audio") is None:
        return None
    return max(0.0, float(marks["first_audio"]) - float(marks["first_tts"]))


def _thinking_ms(llm: dict[str, Any]) -> float | None:
    """Time between the server's first chunk and the first word of the reply."""
    if not llm.get("thinking_chars") or llm.get("first_chunk_ms") is None or llm.get("ms") is None:
        return None
    return float(llm["ms"]) - float(llm["first_chunk_ms"])


def format_turns(rows: list[dict[str, Any]]) -> list[str]:
    def ms(v: Any) -> str:
        return "-" if v is None else f"{float(v):.0f}"

    lines = [
        "Turn by turn: 'filler' and 'first audio' count from letting go of the key (or pressing Enter);",
        "'speech', 'LLM' and '1st sentence' are how long that one step took; 'of it thinking' is",
        "the part of 'LLM' the model spent reasoning before its first word; 'held back' is how long",
        "the ready first sentence waited for a filler to finish. 'route' is the kind of request, which",
        "picks the models (agent/router.py, [llm.routes] in settings.toml).",
        (f"{'#':>3} {'said':>6} {'heard':<11} {'speech':>7} {'route':<8} {'LLM':>6} {'of it thinking':>15} "
         f"{'provider':<15} "
         f"{'1st sentence':>13} {'filler':>7} {'held back':>10} {'first audio':>12}"),
    ]
    for i, r in enumerate(rows, 1):
        said = f"{r['audio_s']:.1f}s" if r["audio_s"] is not None else "typed"
        heard = "-"
        if r["heard"]:
            heard = r["heard"] + (f" {r['p']:.2f}" if r["p"] is not None else "") + ("*" if r["retranscribed"] else "")
        voice = "-" if r["voice_ms"] is None else f"{ms(r['voice_ms'])} ({r['voice_chars']} ch)"
        think = "-" if r["thinking_ms"] is None else f"{ms(r['thinking_ms'])} ({r['thinking_chars']} ch)"
        lines.append(
            f"{i:>3} {said:>6} {heard:<11} {ms(r['stt_ms']):>7} {r.get('route') or '-':<8} {ms(r['llm_ms']):>6} "
            f"{think:>15} {r['provider'] or '-':<15} "
            f"{voice:>13} {ms(r['filler']):>7} {ms(r['held_back']):>10} {ms(r['first_audio']):>12}"
        )
    if any(r["retranscribed"] for r in rows):
        lines.append("* heard in another language, so Whisper ran a second time")
    spoken = [(i, r) for i, r in enumerate(rows, 1) if r.get("logprob") is not None or r.get("unclear")]
    if spoken:
        lines += [
            "",
            "Speech recognition check (voice/clarity.py): 'confidence' is Whisper's average",
            "log-probability per token (0 = sure, below -1.0 = mostly guessing); 'repeats' is the",
            "compression ratio (ordinary text 1-1.8, above 2.4 = repeating itself).",
            f"{'#':>3} {'heard':<11} {'chars':>6} {'confidence':>11} {'repeats':>8}  result",
        ]
        for i, r in spoken:
            heard = (r["heard"] or "-") + ("*" if r["retranscribed"] else "")
            lp = "-" if r["logprob"] is None else f"{float(r['logprob']):.2f}"
            comp = "-" if r["compression"] is None else f"{float(r['compression']):.2f}"
            result = f"asked again ({r['unclear']})" if r["unclear"] else "sent to the LLM"
            lines.append(f"{i:>3} {heard:<11} {r['stt_chars'] or 0:>6} {lp:>11} {comp:>8}  {result}")
    return lines


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
    rows = turn_rows(path)
    if rows:
        print()
        print("\n".join(format_turns(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
