"""The results report (scripts/evaluate_all.py) works with no logs and with a few made-up ones."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_all


def run(monkeypatch, logs, out):
    monkeypatch.setattr(sys, "argv", ["evaluate_all.py", "--logs", str(logs), "--out", str(out)])
    assert evaluate_all.main() == 0
    return out.read_text(encoding="utf-8")


def test_nothing_measured_yet_says_so(monkeypatch, tmp_path):
    (tmp_path / "logs").mkdir()
    text = run(monkeypatch, tmp_path / "logs", tmp_path / "RESULTS.md")
    assert "Not run yet on this laptop" in text and "No conversations logged yet" in text
    assert "**0 acted**" in text                       # the gate's risky calls run every time


def test_numbers_from_logs(monkeypatch, tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    events = [{"event": "turn", "kind": "chat", "source": "voice", "marks": {"first_audio": ms}} for ms in (900, 1500, 2100)]
    events += [{"event": "llm_first_token", "provider": "groq", "model": "m", "ms": 800},
               {"event": "stt", "ms": 300, "audio_s": 2.0, "language": "en", "detected": "en"},
               {"event": "turn", "kind": "tool", "source": "voice", "marks": {"reply_ready": 1200}}]
    (logs / "session-20261030-090000.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    (logs / "actions-20261030.jsonl").write_text(json.dumps({"tool": "open_app", "decision": "ran", "ok": True,
                                                             "verified": True}), encoding="utf-8")
    text = run(monkeypatch, logs, tmp_path / "RESULTS.md")
    assert "| First spoken word after you stop talking (voice) | 1.5 s / 2.1 s (n=3) |" in text
    assert "| Request understood and done (PC and web tools) | 1.2 s / 1.2 s (n=1) |" in text
    assert "groq (m)" in text and "By tool: open_app 1." in text
    assert "you said" not in text.lower()               # totals only, never what was said
