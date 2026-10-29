"""Every measurement in one place, for the report: writes docs/RESULTS.md.

    uv run python scripts/evaluate_all.py              from logs/ (what Jarvis recorded on this laptop)
    uv run python scripts/evaluate_all.py --tests      also run the unit tests and count them
    uv run python scripts/evaluate_all.py --intent     also score the intent models in models/intent/

Reads what the other checks already saved, so run those first when you want
fresh numbers: scripts/smoke_test.py, scripts/command_check.py (both sets),
scripts/safety_check.py, and real conversations (uv run jarvis --voice). Each
section says where its numbers came from, and says plainly when something
hasn't been measured yet. Only totals and percentiles go in: no transcripts,
nothing you said.

Sections: tests; hardware (smoke test); responsiveness (first spoken word,
speech recognition, each model's first chunk, voices, fallbacks); spoken
language detection; understanding commands; safety (the gate's 22 risky
calls, run here, and the model-level check); PC tools in use; intent model.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from jarvis.telemetry import percentile


def ms(value: float) -> str:
    if math.isnan(value):
        return "-"
    return f"{value / 1000:.1f} s" if value >= 1000 else f"{value:.0f} ms"


def p50_p95(values: list[float]) -> str:
    return f"{ms(percentile(values, 50))} / {ms(percentile(values, 95))} (n={len(values)})" if values else "-"


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def stamp_of(path: Path) -> str:
    m = re.search(r"(\d{8})-(\d{6})", path.name)
    return f"{m[1][:4]}-{m[1][4:6]}-{m[1][6:]} {m[2][:2]}:{m[2][2:4]}" if m else path.name


# ---- sections ------------------------------------------------------------------------
def tests_section() -> list[str]:
    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT,
                         capture_output=True, text=True, check=False)
    last = (run.stdout.strip().splitlines() or ["(no output)"])[-1]
    return ["## Unit tests", "", f"`pytest`: {last}. Hardware-free: made-up audio, frames, models and PC.", ""]


def smoke_section(logs: Path) -> list[str]:
    files = sorted(logs.glob("smoke-*.json"))
    out = ["## Hardware check (scripts/smoke_test.py)", ""]
    if not files:
        return [*out, "Not run yet on this laptop.", ""]
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    results = data.get("results", [])
    count = collections.Counter(r["status"] for r in results)
    out += [(f"Latest run {stamp_of(files[-1])}: {count.get('PASS', 0)} pass, {count.get('WARN', 0)} warnings, "
             f"{count.get('FAIL', 0)} failed."), "", "| Check | Result | Detail |", "|---|---|---|"]
    keep = re.compile(r"python$|cuda for whisper|nvidia-smi|whisper (load|speed)|^llm [a-z_]+$|^voice ")
    out += [f"| {r['check']} | {r['status']} | {r['detail'][:90]} |" for r in results if keep.search(r["check"])]
    return [*out, ""]


def sessions(logs: Path) -> tuple[list[dict], list[Path]]:
    files = sorted(logs.glob("session-*.jsonl"))
    return [e for f in files for e in read_jsonl(f)], files


def responsiveness_section(events: list[dict], files: list[Path]) -> list[str]:
    out = ["## Responsiveness (Jarvis's own logs)", ""]
    if not events:
        return [*out, "No conversations logged yet.", ""]
    turns = [e for e in events if e.get("event") == "turn"]
    answered = [t for t in turns if t.get("kind") == "chat" and "first_audio" in (t.get("marks") or {})]
    by_source = collections.defaultdict(list)
    for t in answered:
        by_source[t.get("source", "?")].append(t["marks"]["first_audio"])
    tools = [t["marks"]["reply_ready"] for t in turns if t.get("kind") == "tool" and "reply_ready" in (t.get("marks") or {})]
    stt = [e for e in events if e.get("event") == "stt" and e.get("audio_s")]
    tts = [e["ms"] for e in events if e.get("event") == "tts" and e.get("ok")]
    kinds = ", ".join(f"{k} {v}" for k, v in collections.Counter(t.get("kind") for t in turns).most_common())
    out += [f"{len(files)} sessions, {stamp_of(files[0])} to {stamp_of(files[-1])}; {len(turns)} turns ({kinds}).",
            "", "| Measure | p50 / p95 |", "|---|---|",
            f"| First spoken word after you stop talking (voice) | {p50_p95(by_source.get('voice', []))} |",
            f"| First spoken word after you press Enter (typed) | {p50_p95(by_source.get('keyboard', []))} |",
            f"| Request understood and done (PC and web tools) | {p50_p95(tools)} |",
            f"| Speech recognition (Whisper) | {p50_p95([e['ms'] for e in stt])} |",
            f"| ... per second of speech | {p50_p95([e['ms'] / e['audio_s'] for e in stt])} |",
            f"| A voice speaking one sentence (TTS) | {p50_p95(tts)} |", ""]
    first = collections.defaultdict(list)
    for e in events:
        if e.get("event") == "llm_first_token":
            first[(e.get("provider"), e.get("model"))].append(e["ms"])
    out += ["Each model's first words (from sending the question):", "", "| Model | p50 / p95 | slowest |",
            "|---|---|---|"]
    out += [f"| {prov} ({model}) | {p50_p95(v)} | {ms(max(v))} |"
            for (prov, model), v in sorted(first.items(), key=lambda kv: -len(kv[1]))]
    fallbacks = collections.Counter((e.get("provider"), (e.get("error") or "").split(":")[0])
                                    for e in events if e.get("event") == "llm_fallback")
    slow = sum(e.get("event") == "llm_slow_first_chunk" for e in events)
    out += ["", "Fallbacks to the next model: " + (", ".join(f"{p} {why} x{n}" for (p, why), n in fallbacks.items())
                                                    or "none") + f"; first-reply deadline used {slow} times; "
            f"interrupted by talking over Jarvis {sum(e.get('event') == 'barge_in' for e in events)} times.", ""]
    return out


def hearing_section(events: list[dict]) -> list[str]:
    stt = [e for e in events if e.get("event") == "stt"]
    out = ["## Speech recognition: language and clarity", ""]
    if not stt:
        return [*out, "No speech logged yet.", ""]
    by_lang = collections.defaultdict(list)
    for e in stt:
        by_lang[e.get("language", "?")].append(e)
    out += ["| Language Jarvis was in | utterances | detected as it | asked to repeat (unclear) |", "|---|---|---|---|"]
    for lang, rows in sorted(by_lang.items()):
        same = sum(r.get("detected") == lang for r in rows)
        unclear = sum(bool(r.get("unclear")) for r in rows)
        out.append(f"| {lang} | {len(rows)} | {same} ({same / len(rows):.0%}) | {unclear} |")
    return [*out, "", "Word and character error rates come from scripts/eval_stt.py on the recorded test sentences.", ""]


def command_section(logs: Path) -> list[str]:
    out = ["## Understanding commands (scripts/command_check.py)", ""]
    sets = {}
    for name in ("commands", "commands_heldout"):
        path = ROOT / "eval" / f"{name}.jsonl"
        sets[name] = {json.loads(x)["text"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}
    latest: dict[str, tuple[Path, list[dict]]] = {}
    for f in sorted(logs.glob("command_check-*.json")):
        rows = json.loads(f.read_text(encoding="utf-8"))
        texts = {r["text"] for r in rows}
        if not texts:
            continue
        name, wanted = max(sets.items(), key=lambda kv: len(texts & kv[1]))
        if len(texts & wanted) >= 0.9 * len(texts) and len(texts) >= 0.9 * len(wanted):
            latest[name] = (f, rows)                    # the newest full run of that set
    if not latest:
        return [*out, "Not run yet on this laptop.", ""]
    out += ["| Set | when | English | Singlish | Sinhala | all | actions nobody asked for |", "|---|---|---|---|---|---|---|"]
    for name, (f, rows) in latest.items():
        cell = []
        for lang in ("en", "singlish", "si"):
            sub = [r for r in rows if r["lang"] == lang]
            cell.append(f"{sum(r['ok'] for r in sub)}/{len(sub)}" if sub else "-")
        unasked = sum(r["expect"] == "none" and r["tool"] != "none" for r in rows)
        out.append(f"| {name} | {stamp_of(f)} | {' | '.join(cell)} | {sum(r['ok'] for r in rows)}/{len(rows)} "
                   f"({sum(r['ok'] for r in rows) / len(rows):.0%}) | {unasked} |")
    return [*out, "", "commands_heldout was written and committed before any tuning.", ""]


def safety_section(logs: Path) -> list[str]:
    from datetime import datetime as dt
    from tempfile import TemporaryDirectory

    from jarvis.tools.desktop import DesktopTools
    from jarvis.tools.gate import ActionLog

    cases = read_jsonl(ROOT / "eval" / "safety_calls.jsonl")
    acted = []
    with TemporaryDirectory() as tmp:
        desk = DesktopTools(Path(tmp) / "Jarvis", ActionLog(None), confirm=lambda t, a, w: False,
                            start=lambda t: None, running=set, press_volume=lambda d, n: None,
                            read_volume=lambda: None, screenshot=lambda p: None, wait=lambda s: None,
                            timer_factory=lambda s, f: None, now=lambda: dt(2026, 1, 1))  # noqa: DTZ001
        statuses = collections.Counter()
        for c in cases:
            args = dict(c.get("args", {}))
            if "args_text_repeat" in c:
                args["text"] = args["text"] * c["args_text_repeat"]
            out = desk.call(c["tool"], c.get("raw") or json.dumps(args), untrusted=c.get("untrusted", False),
                            remote=c.get("remote", False))
            statuses[out.status] += 1
            if out.acted:
                acted.append(c["why"])
    out = ["## Safety", "", f"The gate, {len(cases)} risky tool calls (eval/safety_calls.jsonl, run now, nobody "
           f"clicking): {statuses.get('refused', 0)} refused, {statuses.get('cancelled', 0)} waited for a click; "
           f"**{len(acted)} acted**" + (f" ({'; '.join(acted)})" if acted else "") + ".", ""]
    files = sorted(logs.glob("safety_check-*.json"))
    if not files:
        return [*out, ("The model-level check (scripts/safety_check.py, 20 risky requests) hasn't run on this "
                       "laptop yet."), ""]
    rows = json.loads(files[-1].read_text(encoding="utf-8"))
    seen = [s for r in rows for s in r["seen"]]
    out += [(f"The model ({stamp_of(files[-1])}, {len(rows)} risky requests in English, Singlish and Sinhala): "
            f"{len(seen)} tool calls tried, {sum(s['status'] == 'refused' for s in seen)} refused by the gate, "
            f"{sum(s['status'] == 'cancelled' for s in seen)} waited for a click; harmless wrong actions "
            f"{sum(len(r.get('wrong', [])) for r in rows)}; **unsafe actions {sum(len(r['unsafe']) for r in rows)}**."), ""]
    return out


def tools_section(logs: Path) -> list[str]:
    rows = [e for f in sorted(logs.glob("actions-*.jsonl")) for e in read_jsonl(f)]
    out = ["## PC tools in use (logs/actions-*.jsonl)", ""]
    if not rows:
        return [*out, "No PC tool used yet.", ""]
    ran = [r for r in rows if r.get("decision") == "ran"]
    verified = collections.Counter("checked" if r.get("verified") else "not measurable" if r.get("verified") is None
                                   else "check failed" for r in ran if r.get("ok"))
    out += [f"{len(rows)} decisions: " + ", ".join(f"{k} {v}" for k, v in
                                                   collections.Counter(r.get("decision") for r in rows).most_common()),
            "Of the actions that ran: " + ", ".join(f"{k} {v}" for k, v in verified.most_common()) + ".",
            "By tool: " + ", ".join(f"{k} {v}" for k, v in collections.Counter(r.get("tool") for r in ran).most_common())
            + ".", ""]
    return out


def intent_section() -> list[str]:
    out = ["## Intent model (scripts/intent_eval.py)", ""]
    models = sorted((ROOT / "models" / "intent").glob("*.joblib"))
    if not models or not (ROOT / "data" / "intent" / "dev.jsonl").exists():
        return [*out, "No trained model or data sets on this laptop yet (docs/TRAINING_INTENT.md).", ""]
    from intent_eval import evaluate, load
    dev, test = load("dev.jsonl"), load("test_real.jsonl")
    out += ["| Model | dev accuracy / macro-F1 | real test | by set | decides alone at 0.7 (right) | ms |",
            "|---|---|---|---|---|---|"]
    for path in models:
        r = evaluate(path, dev, test)
        sure = next((n, ok) for limit, n, ok, _ in r["confident"] if limit == 0.7)
        sets = ", ".join(f"{k} {a}/{n}" for k, (a, n) in r["test_by_set"].items())
        out.append(f"| {path.name} ({r['kind']}) | {r['dev_acc']:.1%} / {r['dev_f1']:.3f} | {r['test_acc']:.1%} | "
                   f"{sets} | {sure[0]} ({sure[1]}) | {r['ms']:.1f} |")
    return [*out, ""]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--logs", type=Path, default=ROOT / "logs")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "RESULTS.md")
    ap.add_argument("--tests", action="store_true", help="run the unit tests too (about a minute)")
    ap.add_argument("--intent", action="store_true", help="score the intent models too")
    args = ap.parse_args()
    events, files = sessions(args.logs)
    made = f"{datetime.now():%Y-%m-%d %H:%M}"  # noqa: DTZ005 - local time
    lines = ["# Results", "", (f"Made by scripts/evaluate_all.py on {made} from {args.logs.name}/. "
                               "Run it again for fresh numbers; the DEVLOG says what changed between runs."), ""]
    if args.tests:
        lines += tests_section()
    lines += smoke_section(args.logs) + responsiveness_section(events, files) + hearing_section(events)
    lines += command_section(args.logs) + safety_section(args.logs) + tools_section(args.logs)
    if args.intent:
        lines += intent_section()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
