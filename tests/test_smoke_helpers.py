import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_test.py"
spec = importlib.util.spec_from_file_location("smoke_test", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
sys.modules["smoke_test"] = smoke     # dataclasses look the module up here
spec.loader.exec_module(smoke)


def test_frame_stats():
    s = smoke.frame_stats([10.0] * 90 + [40.0] * 10, elapsed_s=4.0, hand_frames=75)
    assert s["frames"] == 100 and s["fps"] == 25
    assert s["p50_ms"] == 10 and s["p95_ms"] == 40
    assert s["hand_rate"] == 0.75


def test_frame_stats_empty():
    s = smoke.frame_stats([], elapsed_s=1.0, hand_frames=0)
    assert s["frames"] == 0 and s["fps"] == 0


def test_script_detection():
    assert smoke.has_script("ආයුබෝවන්", "si")
    assert smoke.has_script("வணக்கம்", "ta")
    assert not smoke.has_script("Hello", "si")
