"""The safety gate with made-up tools: nothing here touches the real PC (tools/gate.py, tools/registry.py)."""

import json
import os

import pytest

from jarvis.tools.gate import ActionLog, Gate, schema_problems
from jarvis.tools.registry import Registry, Result, Tier, Tool

NOTE_SCHEMA = {"type": "object", "properties": {"path": {"type": "string", "maxLength": 300},
                                                 "text": {"type": "string", "maxLength": 2000}},
               "required": ["path", "text"]}


class Fake:
    """Made-up tools that only remember what they were asked to do."""

    def __init__(self):
        self.ran = []
        self.verify_says = True

    def tool(self, name, tier, schema=None, verify=True, undo=False, paths=(), boom=False, describe=None):
        def run(args):
            if boom:
                raise OSError("disk on fire")
            self.ran.append((name, dict(args)))
            return Result(True, f"{name} done", undo_data=args.get("path"))

        return Tool(name, f"fake {name}", schema or {"type": "object", "properties": {}}, tier, run,
                    verify=(lambda a, r: self.verify_says) if verify else None,
                    undo=(lambda a, r: Result(True, f"undid {name}")) if undo else None,
                    path_params=paths, describe=describe)


@pytest.fixture
def world(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    fake = Fake()
    asked = []
    answer = {"click": True}

    def confirm(tool, args, words):
        asked.append(words)
        return answer["click"]

    registry = Registry([
        fake.tool("open_app", Tier.JUST_DO, {"type": "object", "properties": {
            "name": {"type": "string", "enum": ["chrome", "vscode"]}}, "required": ["name"]}),
        fake.tool("set_volume", Tier.JUST_DO, {"type": "object", "properties": {
            "percent": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["percent"]}, verify=False),
        fake.tool("create_note", Tier.DO_AND_LOG, NOTE_SCHEMA, undo=True, paths=("path",)),
        fake.tool("delete_file", Tier.ASK_FIRST, {"type": "object", "properties": {"path": {"type": "string"}},
                                                  "required": ["path"]}, paths=("path",),
                  describe=lambda a: f"Move {os.path.basename(a['path'])} to Jarvis's recycle folder"),
        fake.tool("raw_shell", Tier.NEVER, {"type": "object", "properties": {"cmd": {"type": "string"}}}),
        fake.tool("broken", Tier.JUST_DO, boom=True),
    ])
    logs = tmp_path / "logs"
    gate = Gate(registry, [allowed], ActionLog(logs), confirm=confirm)
    return gate, fake, asked, answer, allowed, logs, tmp_path


def log_lines(logs):
    return [json.loads(line) for f in sorted(logs.glob("actions-*.jsonl")) for line in f.read_text().splitlines()]


# ---- refusals --------------------------------------------------------------------
def test_only_registered_tools_run(world):
    gate, fake, *_ , logs, _ = world
    out = gate.call("format_disk", "{}")
    assert out.status == "refused" and fake.ran == [] and log_lines(logs)[-1]["decision"] == "refused"


def test_never_tools_are_not_offered_and_never_run(world):
    gate, fake, *_ = world
    assert "raw_shell" not in [s["function"]["name"] for s in gate.registry.specs()]
    assert gate.call("raw_shell", '{"cmd": "del /s C:\\\\"}').status == "refused" and fake.ran == []


@pytest.mark.parametrize("arguments, why", [
    ("not json", "valid JSON"),
    ("[1, 2]", "should be object"),
    ("{}", "missing 'name'"),
    ('{"name": "regedit"}', "one of"),
    ('{"name": "chrome", "admin": true}', "unknown 'admin'"),
])
def test_bad_arguments_are_refused(world, arguments, why):
    gate, fake, *_ = world
    out = gate.call("open_app", arguments)
    assert out.status == "refused" and fake.ran == [] and any(why in r for r in out.reasons)


def test_numbers_are_checked(world):
    gate, fake, *_ = world
    assert gate.call("set_volume", '{"percent": 400}').status == "refused"
    assert gate.call("set_volume", '{"percent": true}').status == "refused"     # True is not a number here
    assert gate.call("set_volume", '{"percent": 40}').acted and fake.ran == [("set_volume", {"percent": 40})]


@pytest.mark.parametrize("path", [
    "../outside.txt", "notes/../../outside.txt", "/etc/passwd",
    pytest.param("C:/Windows/System32/x.txt", marks=pytest.mark.skipif(os.name != "nt", reason="a Windows path")),
])
def test_paths_outside_the_allowed_folders_are_refused(world, path):
    gate, fake, *_ = world
    out = gate.call("create_note", {"path": path, "text": "hi"})
    assert out.status == "refused" and fake.ran == [] and "outside" in out.reasons[0]


def test_a_link_pointing_outside_is_refused(world):
    gate, _, _, _, allowed, _, tmp = world
    (tmp / "secret").mkdir()
    try:
        (allowed / "sneaky").symlink_to(tmp / "secret", target_is_directory=True)
    except OSError:
        pytest.skip("this system can't make links")
    assert gate.call("create_note", {"path": str(allowed / "sneaky" / "x.txt"), "text": "hi"}).status == "refused"


def test_a_relative_path_lands_in_the_first_allowed_folder(world):
    gate, fake, _, _, allowed, _, _ = world
    assert gate.call("create_note", {"path": "notes/today.txt", "text": "hi"}).acted
    assert fake.ran[-1][1]["path"] == str((allowed / "notes" / "today.txt").resolve())


# ---- tiers and confirming ------------------------------------------------------------
def test_just_do_it_runs_without_asking(world):
    gate, _, asked, *_ = world
    out = gate.call("open_app", '{"name": "chrome"}')
    assert out.status == "done" and out.text == "open_app done" and asked == []


def test_do_and_log_asks_when_the_turn_holds_outside_text_or_comes_from_the_phone(world):
    gate, fake, asked, answer, allowed, *_ = world
    note = {"path": str(allowed / "a.txt"), "text": "hi"}
    assert gate.call("create_note", note).acted and asked == []
    answer["click"] = False
    assert gate.call("create_note", note, untrusted=True).status == "cancelled"
    assert gate.call("create_note", note, remote=True).status == "cancelled"
    assert len(asked) == 2 and len(fake.ran) == 1


def test_ask_first_runs_only_after_a_click(world):
    gate, fake, asked, answer, allowed, *_ = world
    target = {"path": str(allowed / "old.txt")}
    answer["click"] = False
    assert gate.call("delete_file", target).status == "cancelled" and fake.ran == []
    answer["click"] = True
    assert gate.call("delete_file", target).acted and fake.ran[-1][0] == "delete_file"
    assert asked == ["Move old.txt to Jarvis's recycle folder"] * 2       # the code's words, not the model's


def test_without_a_confirm_box_ask_first_never_runs(world):
    gate, fake, _, _, allowed, logs, _ = world
    gate.confirm = None
    assert gate.call("delete_file", {"path": str(allowed / "x")}).status == "cancelled" and fake.ran == []
    assert log_lines(logs)[-1]["decision"] == "cancelled"


def test_the_kill_switch_stops_it_before_it_runs(world):
    gate, fake, *_ = world
    gate.stopped = lambda: True
    assert gate.call("open_app", '{"name": "chrome"}').status == "cancelled" and fake.ran == []


# ---- verify, failures, log and undo ---------------------------------------------------
def test_verified_claimed_and_unconfirmed_are_told_apart(world):
    gate, fake, *_ = world
    assert gate.call("open_app", '{"name": "vscode"}').status == "done"
    assert gate.call("set_volume", '{"percent": 10}').status == "claimed"         # this tool has no check
    fake.verify_says = False
    out = gate.call("open_app", '{"name": "chrome"}')
    assert out.status == "unconfirmed" and out.text.startswith("I tried, but I couldn't confirm it")


def test_a_crashing_tool_is_a_failure_not_a_crash(world):
    gate, *_, logs, _ = world
    out = gate.call("broken", "{}")
    assert out.status == "failed" and "disk on fire" in log_lines(logs)[-1]["error"]


def test_the_action_log_keeps_every_decision(world):
    gate, _, _, _, allowed, logs, _ = world
    gate.call("open_app", '{"name": "chrome"}')
    gate.call("create_note", {"path": str(allowed / "n.txt"), "text": "x" * 500})
    gate.call("format_disk")
    entries = log_lines(logs)
    assert [e["decision"] for e in entries] == ["ran", "ran", "refused"]
    assert entries[0]["tier"] == "just do it" and entries[0]["verified"] is True
    assert len(entries[1]["args"]["text"]) < 300                                  # long text is cut


def test_undo_that(world):
    gate, *_ , allowed, _, _ = world
    assert gate.undo_last().status == "refused"
    gate.call("create_note", {"path": str(allowed / "n.txt"), "text": "hi"})
    out = gate.undo_last()
    assert out.status == "done" and out.text == "undid create_note" and gate.undo_last().status == "refused"


def test_schema_checks_lists_too():
    schema = {"type": "object", "properties": {"files": {"type": "array", "items": {"type": "string"}}}}
    assert schema_problems({"files": ["a", "b"]}, schema) == []
    assert schema_problems({"files": ["a", 3]}, schema) == ["files[1] should be string"]
