"""The confirm box, and the other ways to answer it (ROADMAP Phase 2, piece 8).

A small always-on-top window (tkinter, built into Python) shows exactly what will happen, in words
written by the tool's code from the checked arguments, never by the model. Jarvis also says the
question. It is answered by:

    a click             "Yes, do it" or Cancel (Enter and Escape cancel; Cancel has the focus)
    your voice          "yes" / "ඔව්" / "ஆம்" or "no" / "එපා", said with push-to-talk or typed on this PC
                        (4 Nov, Adhi: "ask me, and do it when I confirm"; app.py)
    your hand           a thumbs up held for a second confirms, a thumbs down cancels (the camera must be
                        on; perception/gestures.py)

Not from the phone (the gate asks for a click there), and not from words in a web page or a file: only
these answers, while the box is open. No answer within 60 seconds counts as cancelled.
"""

from __future__ import annotations

import gc
import threading
from collections.abc import Callable
from typing import Any

_one_at_a_time = threading.Lock()

YES = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed", "ow", "owu", "ou", "ov", "hari",
       "ha", "ඔව්", "ඔව", "හරි", "හා", "ஆம்", "சரி", "aam", "sari", "do it", "go ahead", "yes please"}
NO = {"no", "nope", "nah", "cancel", "stop", "dont", "don't", "wait", "epa", "එපා", "නෑ", "නැහැ", "naa", "na",
      "nehe", "wenda", "வேண்டாம்", "இல்லை", "illai", "nawaththanna", "නවත්තන්න"}


def yes_or_no(text: str) -> bool | None:
    """A short answer: True for yes ("ඔව් කරන්න", "yes do it"), False for no; None when it's something else.
    No wins over yes ("yes, no, wait": no), so a muddled answer never confirms."""
    import re
    words = re.sub(r"[^\w\s'\u0D80-\u0DFF\u0B80-\u0BFF]", " ", text.lower().replace("\u200d", "")).split()
    words = [w for w in words if w not in {"jarvis", "friday", "please", "sir", "karanna", "කරන්න", "it", "that"}]
    if not words or len(words) > 5:
        return None
    joined = " ".join(words)
    if any(w in NO for w in words) or "don t" in joined:
        return False
    if words[0] in YES or joined in YES or " ".join(words[:2]) in YES:
        return True
    return None


class Asker:
    """Callable like the gate's Confirm: (tool, args, words) -> True only when you said yes in one of the ways."""

    def __init__(self, show: Callable[[str, float, dict], bool] | None = None):
        self.show = show or _show
        self.on_ask: Callable[[str], None] | None = None     # the app says the question out loud
        self.on_done: Callable[[], None] | None = None
        self.last_how = "click"
        self._pending: dict | None = None

    def __call__(self, tool: Any, args: dict, words: str, timeout_s: float = 60.0) -> bool:
        with _one_at_a_time:
            state: dict[str, Any] = {"answer": None, "how": None, "words": words}
            self._pending = state
            if self.on_ask is not None:
                try:
                    self.on_ask(words)
                except Exception:  # noqa: BLE001 - the box still asks
                    pass
            try:
                clicked = self.show(words, timeout_s, state)
            finally:
                self._pending = None
                gc.collect()        # Tk's objects freed on this thread (see _show)
                if self.on_done is not None:
                    try:
                        self.on_done()
                    except Exception:  # noqa: BLE001
                        pass
            if state["answer"] is not None:
                self.last_how = state["how"]
                return bool(state["answer"])
            self.last_how = "click"
            return clicked

    @property
    def waiting(self) -> str | None:
        """What Jarvis is asking about, while the box is open."""
        pending = self._pending
        return None if pending is None or pending["answer"] is not None else pending["words"]

    def answer(self, yes: bool, how: str) -> bool:
        """A spoken or typed yes/no, or a thumbs up/down. False when nothing is being asked."""
        pending = self._pending
        if pending is None or pending["answer"] is not None:
            return False
        pending["how"], pending["answer"] = how, yes
        return True


def _show(words: str, timeout_s: float, state: dict) -> bool:
    """True only if the user clicked "Yes, do it" before the time ran out; closes when `state` gets an answer.

    Runs on the gate's worker thread. Tk must also be torn down on the thread that made it ("Tcl_AsyncDelete:
    async handler deleted by the wrong thread" aborts the whole program otherwise), so the window's objects
    are freed there, before returning, not later by the garbage collector elsewhere.
    """
    import tkinter as tk

    answer = {"yes": False}
    root = tk.Tk()
    root.title("Jarvis asks")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    frame = tk.Frame(root, padx=18, pady=14)
    frame.pack()
    tk.Label(frame, text="Jarvis wants to:", font=("Segoe UI", 10)).pack(anchor="w")
    tk.Label(frame, text=words, font=("Segoe UI", 12, "bold"), wraplength=440,
             justify="left").pack(anchor="w", pady=(4, 10))
    tk.Label(frame, text="Click, or say yes / ඔව් (or no), or hold a thumbs up.", font=("Segoe UI", 9),
             fg="gray").pack(anchor="w")
    left = tk.Label(frame, text="", font=("Segoe UI", 9), fg="gray")
    left.pack(anchor="w")
    buttons = tk.Frame(frame, pady=8)
    buttons.pack(anchor="e")

    def yes() -> None:
        answer["yes"] = True
        root.destroy()

    tk.Button(buttons, text="Yes, do it", width=12, command=yes).pack(side="left", padx=4)
    cancel = tk.Button(buttons, text="Cancel", width=12, command=root.destroy, default="active")
    cancel.pack(side="left", padx=4)
    cancel.focus_set()
    root.bind("<Return>", lambda e: root.destroy())          # Enter cancels, it never confirms
    root.bind("<Escape>", lambda e: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    deadline = {"ticks": int(timeout_s * 10)}

    def tick() -> None:
        if state.get("answer") is not None or deadline["ticks"] <= 0:   # answered by voice or hand, or too late
            root.destroy()
            return
        if deadline["ticks"] % 10 == 0:
            left.config(text=f"Cancels by itself in {deadline['ticks'] // 10} s")
        deadline["ticks"] -= 1
        root.after(100, tick)

    tick()
    root.lift()
    root.mainloop()
    return answer["yes"]


confirm_box = Asker()      # one for Jarvis: the PC tools and MATLAB share it, and the app answers it

__all__ = ["Asker", "confirm_box", "yes_or_no"]
