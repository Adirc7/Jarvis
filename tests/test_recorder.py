"""Recorder helpers: clip names never overwrite earlier recordings."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from jarvis.config import PROJECT_ROOT


def _load():
    spec = importlib.util.spec_from_file_location("record_eval_set", PROJECT_ROOT / "scripts" / "record_eval_set.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["record_eval_set"] = module
    spec.loader.exec_module(module)
    return module


def test_clip_names_are_unique(tmp_path):
    rec = _load()
    sentences = Path("eval/sentences_si.txt")
    first = rec.clip_name(tmp_path, "me", sentences, 3)
    assert first == "me_sentences_si_003.wav"
    (tmp_path / first).write_bytes(b"x")
    second = rec.clip_name(tmp_path, "me", sentences, 3)
    assert second == "me_sentences_si_003-2.wav"
    (tmp_path / second).write_bytes(b"x")
    assert rec.clip_name(tmp_path, "me", sentences, 3) == "me_sentences_si_003-3.wav"
    assert rec.clip_name(tmp_path, "friend1", sentences, 3) == "friend1_sentences_si_003.wav"


def test_sentence_files():
    rec = _load()
    assert rec.read_sentences(PROJECT_ROOT / "eval" / "sentences_singlish.txt") == []   # template, not filled yet
    assert len(rec.read_sentences(PROJECT_ROOT / "eval" / "sentences_en.txt")) == 20
    from jarvis.voice.clarity import foreign_script_share
    for name, at_least in (("sentences_si.txt", 30), ("sentences_si_study.txt", 50), ("sentences_si_talk.txt", 30)):
        si = rec.read_sentences(PROJECT_ROOT / "eval" / name)
        assert len(si) >= at_least, name
        assert all(foreign_script_share(s, "si") == 0 for s in si), name        # all in Sinhala script
        assert not any(ch.isdigit() for s in si for ch in s), name              # no numbers (see sentences_si.txt)
        assert len(set(si)) == len(si), name                                    # no repeats
