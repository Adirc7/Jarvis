import numpy as np
import pytest

from jarvis.evaluation.wer import corpus_score, edit_distance, score
from jarvis.voice.audio_io import load_wav, resample, save_wav


def test_edit_distance_basics():
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance([], ["a"]) == 1
    assert edit_distance(["a", "b"], ["a", "b"]) == 0


def test_word_and_char_error_rates():
    s = score("Open Google Chrome.", "open google chrome")      # case and punctuation ignored
    assert s.wer == 0 and s.cer == 0
    s = score("make this bigger", "make it bigger")
    assert s.wer == pytest.approx(1 / 3)
    s = score("switch to tamil", "")
    assert s.wer == 1.0


def test_sinhala_cer_sees_partial_word_errors():
    s = score("සිංහලෙන් කතා කරන්න", "සිංහලෙන් කථා කරන්න")       # one letter differs
    assert s.wer == pytest.approx(1 / 3)
    assert 0 < s.cer < 0.15


def test_corpus_score_weights_by_length():
    total = corpus_score([("a b c d", "a b c d"), ("x", "y")])
    assert total.wer == pytest.approx(1 / 5)


def test_wav_roundtrip_and_resample(tmp_path):
    sr = 24000
    audio = (0.3 * np.sin(2 * np.pi * 440 * np.arange(sr) / sr)).astype(np.float32)
    save_wav(tmp_path / "x.wav", audio, sr)
    back, rate = load_wav(tmp_path / "x.wav")
    assert rate == sr and np.max(np.abs(back - audio)) < 1e-3
    down = resample(back, sr, 16000)
    assert len(down) == 16000


def test_telemetry_cli_picks_newest_session(tmp_path, capsys):
    from jarvis.telemetry import _main
    (tmp_path / "session-20261021-034202.jsonl").write_text('{"event": "turn", "ms": 900}\n', encoding="utf-8")
    (tmp_path / "session-20261021-041323.jsonl").write_text('{"event": "turn", "ms": 1200}\n', encoding="utf-8")
    assert _main([], log_dir=tmp_path) == 0
    assert "041323" in capsys.readouterr().out
    assert _main([str(tmp_path / "session-20261021-093512.jsonl")], log_dir=tmp_path) == 1
    assert "041323" in capsys.readouterr().out          # lists the real ones instead of a traceback


def test_turn_rows_explain_each_request(tmp_path):
    import json

    from jarvis.telemetry import format_turns, turn_rows
    events = [
        {"event": "session_start"},
        {"event": "greeting", "kind": "pickup"},
        {"event": "tts", "ms": 300.0, "chars": 30},                       # the greeting: not a turn
        {"event": "stt", "ms": 884.1, "language": "en", "detected": "en", "probability": 0.97,
         "retranscribed": False, "logprob": -0.31, "compression": 1.12, "unclear": None, "chars": 18},
        {"event": "llm_first_token", "ms": 588.3, "provider": "groq_oss", "first_chunk_ms": 200.3,
         "thinking_chars": 340},
        {"event": "filler", "index": 2},
        {"event": "tts", "ms": 410.0, "chars": 18},
        {"event": "tts", "ms": 1500.0, "chars": 160},
        {"event": "turn", "source": "voice", "audio_s": 2.4, "kind": "chat",
         "marks": {"stt_done": 884.6, "first_token": 1520.3, "filler": 1584.8, "first_audio": 3220.7}},
        {"event": "llm_first_token", "ms": 300.0, "provider": "groq"},
        {"event": "tts", "ms": 350.0, "chars": 14},
        {"event": "turn", "source": "text", "kind": "chat", "marks": {"first_audio": 700.0}},
    ]
    path = tmp_path / "session-20261021-041323.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    first, second = turn_rows(path)
    assert (first["stt_ms"], first["heard"], first["p"]) == (884.1, "en", 0.97)
    assert (first["voice_ms"], first["voice_chars"]) == (410.0, 18)        # not the greeting's
    assert (first["filler"], first["first_audio"]) == (1584.8, 3220.7)
    assert first["thinking_ms"] == pytest.approx(388.0)
    assert second["stt_ms"] is None and second["provider"] == "groq" and second["voice_ms"] == 350.0
    assert second["thinking_ms"] is None                                   # older logs: no thinking data
    text = "\n".join(format_turns([first, second]))
    assert "2.4s" in text and "typed" in text and "410 (18 ch)" in text and "388 (340 ch)" in text
    assert "-0.31" in text and "1.12" in text and "sent to the LLM" in text
