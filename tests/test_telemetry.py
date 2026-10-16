import json
import time

import pytest

from jarvis.telemetry import Telemetry, percentile, summarize


def test_span_and_turn_write_jsonl(tmp_path):
    tel = Telemetry(tmp_path / "t.jsonl")
    with tel.span("stt", model="small") as extra:
        time.sleep(0.01)
        extra["chars"] = 12
    turn = tel.turn(source="voice")
    turn.mark("first_token")
    turn.finish(kind="chat")
    lines = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert lines[0]["event"] == "stt" and lines[0]["ms"] >= 10 and lines[0]["chars"] == 12
    assert lines[1]["event"] == "turn" and "first_token" in lines[1]["marks"]


def test_span_records_errors(tmp_path):
    tel = Telemetry(tmp_path / "t.jsonl")
    with pytest.raises(ValueError):
        with tel.span("tool"):
            raise ValueError("boom")
    rec = json.loads((tmp_path / "t.jsonl").read_text())
    assert rec["ok"] is False and "boom" in rec["error"]


def test_percentile_nearest_rank():
    data = list(range(1, 101))            # 1..100
    assert percentile(data, 50) == 50
    assert percentile(data, 95) == 95
    assert percentile([7], 95) == 7


def test_summarize(tmp_path):
    tel = Telemetry(tmp_path / "t.jsonl")
    for ms in (100, 200, 300):
        tel.log("stt", ms=ms)
    stats = summarize(tmp_path / "t.jsonl")
    assert stats["stt"]["n"] == 3 and stats["stt"]["p50"] == 200


def test_disabled_telemetry_writes_nothing(tmp_path):
    tel = Telemetry.disabled()
    tel.log("anything", ms=1)
    with tel.span("x"):
        pass
    assert list(tmp_path.iterdir()) == []
