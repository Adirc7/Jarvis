"""Settings for one computer (settings.local.toml) and the push-to-talk key picker."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.config import LOCAL_SETTINGS, PROJECT_ROOT, load_settings, merge, set_local_value
from jarvis.voice.capture import check_push_to_talk_key, describe_key


@pytest.fixture
def config_dir(tmp_path):
    for name in ("settings.toml", "languages.toml"):
        shutil.copy(PROJECT_ROOT / "config" / name, tmp_path / name)
    return tmp_path


def test_merge_keeps_other_values_and_replaces_leaves():
    base = {"a": {"x": 1, "y": 2}, "b": [1, 2], "c": "keep"}
    out = merge(base, {"a": {"y": 3, "z": 4}, "b": [9]})
    assert out == {"a": {"x": 1, "y": 3, "z": 4}, "b": [9], "c": "keep"}
    assert base["a"] == {"x": 1, "y": 2}          # input not modified


def test_local_file_overrides_only_what_it_names(config_dir):
    (config_dir / LOCAL_SETTINGS).write_text('[hotkeys]\npush_to_talk = "f9"\n[stt]\nmodel = "large-v3-turbo"\n',
                                             encoding="utf-8")
    s = load_settings(config_dir)
    assert s.get("hotkeys.push_to_talk") == "f9"
    assert s.get("stt.model") == "large-v3-turbo"
    assert s.get("hotkeys.kill_switch") == "<ctrl>+<alt>+k"        # untouched
    assert s.get("stt.beam_size") == load_settings(config_dir, local=False).get("stt.beam_size")


def test_local_file_ignored_when_asked(config_dir):
    (config_dir / LOCAL_SETTINGS).write_text('[hotkeys]\npush_to_talk = "f9"\n', encoding="utf-8")
    assert load_settings(config_dir, local=False).get("hotkeys.push_to_talk") == "ctrl_r"


def test_set_local_value_creates_file(tmp_path):
    path = tmp_path / LOCAL_SETTINGS
    set_local_value(path, "hotkeys", "push_to_talk", "f9")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Your settings")
    assert tomllib.loads(text) == {"hotkeys": {"push_to_talk": "f9"}}


def test_set_local_value_replaces_and_keeps_the_rest(tmp_path):
    path = tmp_path / LOCAL_SETTINGS
    path.write_text(
        "# mine\n[hotkeys]  # keys\nmute = \"<ctrl>+<alt>+n\"\npush_to_talk = \"ctrl_r\"\n\n"
        "[stt]\nmodel = \"small\"\npush_to_talk = \"not this one\"\n",
        encoding="utf-8",
    )
    set_local_value(path, "hotkeys", "push_to_talk", "insert")
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["hotkeys"] == {"mute": "<ctrl>+<alt>+n", "push_to_talk": "insert"}
    assert data["stt"] == {"model": "small", "push_to_talk": "not this one"}
    assert text.startswith("# mine\n")


def test_set_local_value_adds_key_to_existing_table(tmp_path):
    path = tmp_path / LOCAL_SETTINGS
    path.write_text('[hotkeys]\nmute = "<ctrl>+<alt>+n"\n\n[audio]\ninput_device = 2\n', encoding="utf-8")
    set_local_value(path, "hotkeys", "push_to_talk", "alt_r")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data == {"hotkeys": {"mute": "<ctrl>+<alt>+n", "push_to_talk": "alt_r"}, "audio": {"input_device": 2}}


def test_set_local_value_adds_missing_table(tmp_path):
    path = tmp_path / LOCAL_SETTINGS
    path.write_text('[stt]\nmodel = "small"\n', encoding="utf-8")
    set_local_value(path, "hotkeys", "push_to_talk", "f9")
    assert tomllib.loads(path.read_text(encoding="utf-8"))["hotkeys"] == {"push_to_talk": "f9"}


@pytest.mark.parametrize("name, label", [
    ("ctrl_r", "Right Ctrl"), ("f9", "F9"), ("alt_gr", "AltGr"), ("scroll_lock", "Scroll Lock"),
    ("insert", "Insert"), ("`", "the ` key"),
])
def test_describe_key(name, label):
    assert describe_key(name) == label


@pytest.mark.parametrize("name", ["ctrl_r", "alt_r", "alt_gr", "f9", "f12", "insert", "pause", "menu", "scroll_lock"])
def test_good_push_to_talk_keys(name):
    assert check_push_to_talk_key(name) is None


@pytest.mark.parametrize("name, words", [
    ("a", "typing"), ("space", "typing"), ("shift_r", "typing"), ("ctrl_l", "typing"), ("enter", "typing"),
    ("cmd", "Copilot"), ("cmd_l", "Windows"), ("media_volume_up", "Fn"), ("print_screen", "Windows"),
    ("esc", "cancel"), (None, "which key"), ("f23", "Copilot"),
])
def test_bad_push_to_talk_keys(name, words):
    problem = check_push_to_talk_key(name)
    assert problem and words in problem


def _load_choose_key():
    spec = importlib.util.spec_from_file_location("choose_key", PROJECT_ROOT / "scripts" / "choose_key.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["choose_key"] = module
    spec.loader.exec_module(module)
    return module


def test_choose_key_names_and_saves(tmp_path, monkeypatch, capsys):
    ck = _load_choose_key()
    assert ck.key_name(SimpleNamespace(name="ctrl_r")) == "ctrl_r"
    assert ck.key_name(SimpleNamespace(char="a")) == "a"
    assert ck.key_name(SimpleNamespace(char=None)) is None

    monkeypatch.setattr(ck, "LOCAL_PATH", tmp_path / LOCAL_SETTINGS)
    assert ck.save("space") == 1
    assert not (tmp_path / LOCAL_SETTINGS).exists()
    assert ck.save("f9") == 0
    assert tomllib.loads((tmp_path / LOCAL_SETTINGS).read_text(encoding="utf-8"))["hotkeys"]["push_to_talk"] == "f9"
    assert "Hold F9" in capsys.readouterr().out
