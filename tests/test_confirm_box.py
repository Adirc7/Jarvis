"""The confirm box on a real screen (tools/confirm.py). It opens real windows, so it only runs
when asked: JARVIS_GUI_TESTS=1 (on Linux without a screen: xvfb-run -a env JARVIS_GUI_TESTS=1 pytest ...).
Each window is driven by a script after it opens, from a worker thread, as the gate does."""

import os
import threading

import pytest

tkinter = pytest.importorskip("tkinter")
pytestmark = pytest.mark.skipif(os.environ.get("JARVIS_GUI_TESTS") != "1",
                                reason="opens real windows: set JARVIS_GUI_TESTS=1")

from jarvis.tools import confirm

WORDS = 'Move "plan.txt" to Jarvis\'s recycle folder'


def widgets(root):
    found, todo = [], [root]
    while todo:
        w = todo.pop()
        found.append(w)
        todo += w.winfo_children()
    return found


def button(root, text):
    return next(w for w in widgets(root) if isinstance(w, tkinter.Button) and w.cget("text") == text)


def run_box(monkeypatch, action, timeout_s=10.0):
    """Open the box on a worker thread; `action(root, seen)` runs 300 ms after it appears."""
    seen = {}
    real_tk = tkinter.Tk

    class Scripted(real_tk):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.after(300, lambda: action(self, seen))

    monkeypatch.setattr(tkinter, "Tk", Scripted)
    out = {}
    worker = threading.Thread(target=lambda: out.update(answer=confirm.confirm_box(None, {}, WORDS, timeout_s)))
    worker.start()
    worker.join(timeout=timeout_s + 10)
    assert not worker.is_alive(), "the box never closed"
    return out["answer"], seen


def test_clicking_yes_confirms(monkeypatch):
    def act(root, seen):
        seen["texts"] = [w.cget("text") for w in widgets(root) if isinstance(w, tkinter.Label)]
        seen["focus"] = str(root.focus_lastfor())           # names only: no Tk objects leave the thread
        seen["cancel"] = str(button(root, "Cancel"))
        button(root, "Yes, do it").invoke()

    answer, seen = run_box(monkeypatch, act)
    assert answer is True
    assert WORDS in seen["texts"]                        # the tool's own words, shown as they are
    assert seen["focus"] == seen["cancel"]               # Cancel has the focus


@pytest.mark.parametrize("how", ["cancel button", "enter", "escape", "close window"])
def test_everything_else_cancels(monkeypatch, how):
    def act(root, seen):
        if how == "cancel button":
            button(root, "Cancel").invoke()
        elif how == "close window":
            root.tk.call(root.protocol("WM_DELETE_WINDOW"))
        else:
            root.event_generate("<Return>" if how == "enter" else "<Escape>", when="tail")

    answer, _ = run_box(monkeypatch, act)
    assert answer is False


def test_no_click_in_time_cancels(monkeypatch):
    answer, _ = run_box(monkeypatch, lambda root, seen: None, timeout_s=1.5)
    assert answer is False


def test_two_boxes_never_open_at_once(monkeypatch):
    open_now, most = [0], [0]

    def act(root, seen):
        open_now[0] += 1
        most[0] = max(most[0], open_now[0])
        root.after(200, lambda: (open_now.__setitem__(0, open_now[0] - 1), button(root, "Cancel").invoke()))

    real_tk = tkinter.Tk

    class Scripted(real_tk):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.after(100, lambda: act(self, {}))

    monkeypatch.setattr(tkinter, "Tk", Scripted)
    workers = [threading.Thread(target=confirm.confirm_box, args=(None, {}, WORDS, 10)) for _ in range(2)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=20)
    assert most[0] == 1
