"""The first desktop tools, through the gate, with stand-ins for Windows (tools/desktop.py)."""

import json
from datetime import datetime

import pytest

from jarvis.tools.desktop import APPS, DesktopTools
from jarvis.tools.gate import ActionLog


class FakeTimer:
    def __init__(self, seconds, done):
        self.seconds, self.done, self.cancelled = seconds, done, False

    def cancel(self):
        self.cancelled = True


class Windows:
    """What the tools did to 'Windows'."""

    def __init__(self):
        self.started, self.keys, self.procs = [], [], set()
        self.level = 0.5
        self.timers = []
        self.clicks = []
        self.click_answer = True

    def start(self, target):
        self.started.append(target)
        self.procs |= {n for t, names in APPS.values() if t == target for n in names}

    def press(self, direction, steps):
        self.keys.append((direction, steps))
        self.level = min(1.0, self.level + 0.02 * steps) if direction == "up" else max(0.0, self.level - 0.02 * steps)

    def timer(self, seconds, done):
        t = FakeTimer(seconds, done)
        self.timers.append(t)
        return t

    def confirm(self, tool, args, words):
        self.clicks.append(words)
        return self.click_answer


@pytest.fixture
def desk(tmp_path):
    win = Windows()
    tools = DesktopTools(tmp_path / "Jarvis", ActionLog(tmp_path / "logs"), win.confirm,
                         start=win.start, running=lambda: set(win.procs), press_volume=win.press,
                         read_volume=lambda: win.level, screenshot=lambda p: p.write_bytes(b"\x89PNG" + b"0" * 500),
                         wait=lambda s: None, timer_factory=win.timer, now=lambda: datetime(2026, 10, 28, 9, 30))  # noqa: DTZ001
    return tools, win, tmp_path


def test_open_an_app_from_the_list_and_check_it_opened(desk):
    tools, win, _ = desk
    out = tools.call("open_app", '{"name": "calculator"}')
    assert out.status == "done" and win.started == ["calc.exe"] and out.text == "Opening calculator."


def test_an_app_that_never_appears_is_not_claimed(desk):
    tools, _, _ = desk
    tools.start = lambda target: None                       # Windows ignored it
    assert tools.call("open_app", '{"name": "excel"}').status == "unconfirmed"


def test_only_apps_on_the_list(desk):
    tools, win, _ = desk
    for name in ("cmd", "powershell", "regedit", "C:/evil.exe"):
        assert tools.call("open_app", json.dumps({"name": name})).status == "refused"
    assert win.started == []


def test_volume_up_down_and_its_check(desk):
    tools, win, _ = desk
    assert tools.call("change_volume", '{"direction": "up", "steps": 5}').status == "done"
    assert tools.call("change_volume", '{"direction": "down"}').status == "done"
    assert win.keys == [("up", 5), ("down", 3)]
    assert tools.call("change_volume", '{"direction": "up", "steps": 50}').status == "refused"


def test_screenshot_lands_in_jarvis_folder(desk):
    tools, _, tmp = desk
    out = tools.call("take_screenshot")
    assert out.status == "done" and list((tmp / "Jarvis" / "screenshots").glob("*.png"))


def test_timer_rings_and_can_be_undone(desk):
    tools, win, _ = desk
    rang = []
    tools.on_timer = rang.append
    out = tools.call("set_timer", '{"minutes": 25, "label": "pomodoro"}')
    assert out.status == "done" and out.text == "Timer set for 25 minutes: pomodoro."
    assert win.timers[0].seconds == 1500
    win.timers[0].done()                                    # 25 minutes later
    assert rang == ["pomodoro"] and tools.timers == {}
    tools.call("set_timer", '{"minutes": 1}')
    assert tools.call("undo_last_action").text == "Timer cancelled." and win.timers[1].cancelled


def test_note_is_written_checked_and_undone_into_the_recycle_folder(desk):
    tools, _, tmp = desk
    out = tools.call("create_note", json.dumps({"text": "buy milk\ncall amma", "title": "today"}))
    note = tmp / "Jarvis" / "notes" / "2026-10-28 0930 today.txt"
    assert out.status == "done" and note.read_text(encoding="utf-8") == "buy milk\ncall amma"
    assert tools.call("undo_last_action").status == "done"
    assert not note.exists() and (tmp / "Jarvis" / "recycle" / note.name).exists()   # moved, never deleted


def test_a_title_cannot_escape_the_notes_folder(desk):
    tools, _, tmp = desk
    tools.call("create_note", json.dumps({"text": "x", "title": "../../../Windows/evil"}))
    assert [p.parent.name for p in (tmp / "Jarvis").rglob("*.txt")] == ["notes"]


def test_delete_needs_a_click_and_only_moves_to_the_recycle_folder(desk):
    tools, win, tmp = desk
    tools.call("create_note", '{"text": "old", "title": "old"}')
    target = "notes/2026-10-28 0930 old.txt"
    win.click_answer = False
    assert tools.call("delete_file", json.dumps({"path": target})).status == "cancelled"
    assert (tmp / "Jarvis" / target).exists()
    win.click_answer = True
    assert tools.call("delete_file", json.dumps({"path": target})).status == "done"
    assert win.clicks == ['Move "2026-10-28 0930 old.txt" to Jarvis\'s recycle folder'] * 2
    assert not (tmp / "Jarvis" / target).exists() and list((tmp / "Jarvis" / "recycle").iterdir())
    assert tools.call("undo_last_action").text == "Put 2026-10-28 0930 old.txt back."
    assert (tmp / "Jarvis" / target).exists()


def test_delete_outside_jarvis_folder_is_refused_before_asking(desk):
    tools, win, tmp = desk
    (tmp / "thesis.docx").write_text("years of work")
    for path in (str(tmp / "thesis.docx"), "../thesis.docx", "notes/../../thesis.docx", "/etc/hosts"):
        assert tools.call("delete_file", json.dumps({"path": path})).status == "refused"
    assert win.clicks == [] and (tmp / "thesis.docx").exists()


def test_outside_text_makes_a_note_ask_first(desk):
    tools, win, tmp = desk
    win.click_answer = False
    assert tools.call("create_note", '{"text": "hello"}', untrusted=True).status == "cancelled"
    assert not (tmp / "Jarvis" / "notes").exists()


def test_every_action_is_logged(desk):
    tools, _, tmp = desk
    tools.call("open_app", '{"name": "notepad"}')
    tools.call("open_app", '{"name": "cmd"}')
    lines = [json.loads(x) for f in (tmp / "logs").glob("*.jsonl") for x in f.read_text().splitlines()]
    assert [(e["tool"], e["decision"]) for e in lines] == [("open_app", "ran"), ("open_app", "refused")]


def test_filler_arguments_on_a_tool_that_takes_none_are_ignored(desk):
    # Seen on the laptop, 28 Oct: gpt-oss-120b called undo_last_action with {"action": {}}.
    tools, _, _ = desk
    tools.call("create_note", '{"text": "exam on Friday", "title": "exam"}')
    out = tools.call("undo_last_action", '{"action": {}}')
    assert out.status == "done" and out.text.startswith("Note removed")
    assert tools.call("open_app", '{"name": "notepad", "action": {}}').status == "refused"   # still strict here
