"""The confirm box: for "ask first" actions, only a click confirms (ROADMAP Phase 2, piece 8).

A small always-on-top window (tkinter, built into Python) shows exactly what
will happen, in words written by the tool's code from the checked arguments,
never by the model. Cancel has the focus, so Enter or Escape cancels; voice
can't confirm (a mishearing can only make Jarvis more careful); no click
within 60 seconds counts as cancelled.
"""

from __future__ import annotations

import threading
from typing import Any

_one_at_a_time = threading.Lock()


def confirm_box(tool: Any, args: dict, words: str, timeout_s: float = 60.0) -> bool:
    """True only if Adhi clicked "Yes, do it" before the time ran out."""
    import tkinter as tk

    with _one_at_a_time:
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

        deadline = {"s": int(timeout_s)}

        def tick() -> None:
            if deadline["s"] <= 0:
                root.destroy()
                return
            left.config(text=f"Cancels by itself in {deadline['s']} s")
            deadline["s"] -= 1
            root.after(1000, tick)

        tick()
        root.lift()
        root.mainloop()
        return answer["yes"]
