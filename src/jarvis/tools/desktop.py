"""The first desktop tools, all through the gate (Phase 2, ROADMAP "First tools").

    just do it   open_app (a fixed list), change_volume, take_screenshot, set_timer,
                 undo_last_action
    do and log   create_note (undo moves it to Jarvis's recycle folder)
    ask first    delete_file (moves a file from Jarvis's folder to the recycle
                 folder, never deletes; only a click confirms)

Files live in one folder, [tools] jarvis_folder (default ~/Documents/Jarvis):
notes/, screenshots/ and recycle/. Every tool checks the real result
afterwards (verify) where Windows lets it. Everything that touches Windows
is passed in, so the tests run anywhere with stand-ins.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .gate import ActionLog, Confirm, Gate
from .registry import Args, Registry, Result, Tier, Tool

# name -> (what Windows starts, process names that show it opened)
APPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "notepad": ("notepad.exe", ("notepad.exe",)),
    "calculator": ("calc.exe", ("calculatorapp.exe", "calc.exe")),
    "file explorer": ("explorer.exe", ("explorer.exe",)),
    "chrome": ("chrome.exe", ("chrome.exe",)),
    "edge": ("msedge.exe", ("msedge.exe",)),
    "vs code": ("code", ("code.exe",)),
    "word": ("winword.exe", ("winword.exe",)),
    "excel": ("excel.exe", ("excel.exe",)),
    "powerpoint": ("powerpnt.exe", ("powerpnt.exe",)),
    "spotify": ("spotify:", ("spotify.exe",)),
    "settings": ("ms-settings:", ("systemsettings.exe",)),
    "paint": ("mspaint.exe", ("mspaint.exe",)),
}


# ---- what touches Windows (replaced by stand-ins in the tests) ---------------------
def start_on_windows(target: str) -> None:
    if target == "code":                                   # VS Code: its own exe, else the `code` command
        exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe"
        target = str(exe) if exe.exists() else (shutil.which("code") or target)
    os.startfile(target)                                   # type: ignore[attr-defined]  # Windows only


def running_on_windows() -> set[str]:
    """Names of running programs, lower case (tasklist ships with Windows)."""
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=10,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False).stdout
    return {line.split('","')[0].strip('"').lower() for line in out.splitlines() if line.startswith('"')}


def volume_keys(direction: str, steps: int) -> None:
    """The keyboard's volume keys (each press is about 2%)."""
    from pynput.keyboard import Controller, Key
    key = {"up": Key.media_volume_up, "down": Key.media_volume_down, "mute": Key.media_volume_mute}[direction]
    keys = Controller()
    for _ in range(1 if direction == "mute" else steps):
        keys.press(key)
        keys.release(key)
        time.sleep(0.03)


def volume_level() -> float | None:
    """The speakers' volume 0-1 when pycaw is installed (optional), else None: no check possible."""
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        speakers = AudioUtilities.GetSpeakers()
        endpoint = getattr(speakers, "EndpointVolume", None)
        if endpoint is None:
            endpoint = cast(speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
                            POINTER(IAudioEndpointVolume))
        return float(endpoint.GetMasterVolumeLevelScalar())
    except Exception:  # noqa: BLE001 - no pycaw, or no speakers: Jarvis just can't check
        return None


def grab_screen(path: Path) -> None:
    import mss
    import mss.tools
    with mss.mss() as screen:
        shot = screen.grab(screen.monitors[0])            # every monitor
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))


def _safe_name(text: str, limit: int = 40) -> str:
    name = re.sub(r"[^\w\- ]+", "", text, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", name)[:limit].strip() or "note"


class DesktopTools:
    """The tools, the gate in front of them, and the timers that are running."""

    def __init__(self, jarvis_folder: Path | str, log: ActionLog | None = None, confirm: Confirm | None = None,
                 stopped: Callable[[], bool] = lambda: False, extra_folders: list[Path | str] | None = None, *,
                 start: Callable[[str], None] = start_on_windows,
                 running: Callable[[], set[str]] = running_on_windows,
                 press_volume: Callable[[str, int], None] = volume_keys,
                 read_volume: Callable[[], float | None] = volume_level,
                 screenshot: Callable[[Path], None] = grab_screen,
                 wait: Callable[[float], None] = time.sleep,
                 timer_factory: Callable[[float, Callable[[], None]], Any] | None = None,
                 now: Callable[[], datetime] = datetime.now):
        self.home = Path(jarvis_folder).expanduser()
        self.notes, self.shots, self.recycle = self.home / "notes", self.home / "screenshots", self.home / "recycle"
        self.start, self.running, self.press_volume, self.read_volume = start, running, press_volume, read_volume
        self.screenshot, self.wait, self.now = screenshot, wait, now
        self.timer_factory = timer_factory or self._thread_timer
        self.timers: dict[int, tuple[str, Any, datetime]] = {}
        self._next_timer = 1
        self.on_timer: Callable[[str], None] = lambda label: None     # the app says it out loud
        self.registry = Registry(self._tools())
        self.gate = Gate(self.registry, [self.home, *(extra_folders or [])], log, confirm, stopped)

    # ---- open_app ----------------------------------------------------------------
    def _open_app(self, args: Args) -> Result:
        target, _ = APPS[args["name"]]
        self.start(target)
        return Result(True, f"Opening {args['name']}.")

    def _app_opened(self, args: Args, result: Result) -> bool:
        names = APPS[args["name"]][1]
        for _ in range(6):                                  # up to about 3 seconds
            if set(names) & self.running():
                return True
            self.wait(0.5)
        return False

    # ---- change_volume -------------------------------------------------------------
    def _change_volume(self, args: Args) -> Result:
        before = self.read_volume()
        self.press_volume(args["direction"], int(args.get("steps", 3)))
        words = {"up": "Volume up.", "down": "Volume down.", "mute": "Sound muted or unmuted."}[args["direction"]]
        return Result(True, words, data={"before": before})

    def _volume_changed(self, args: Args, result: Result) -> bool | None:
        before, after = result.data.get("before"), self.read_volume()
        if before is None or after is None or args["direction"] == "mute":
            return None                                     # can't measure: the keys were pressed, no more
        if args["direction"] == "up":
            return after > before or after >= 0.99
        return after < before or after <= 0.01

    # ---- take_screenshot -------------------------------------------------------------
    def _take_screenshot(self, args: Args) -> Result:
        self.shots.mkdir(parents=True, exist_ok=True)
        path = self.shots / f"screenshot {self.now():%Y-%m-%d %H%M%S}.png"
        self.screenshot(path)
        return Result(True, f"Screenshot saved in {self.shots.name}.", data={"path": str(path)})

    def _screenshot_saved(self, args: Args, result: Result) -> bool:
        path = Path(result.data["path"])
        return path.exists() and path.stat().st_size > 100

    # ---- set_timer ---------------------------------------------------------------------
    @staticmethod
    def _thread_timer(seconds: float, done: Callable[[], None]) -> threading.Timer:
        timer = threading.Timer(seconds, done)
        timer.daemon = True
        timer.start()
        return timer

    def _set_timer(self, args: Args) -> Result:
        minutes = float(args["minutes"])
        label = str(args.get("label") or "").strip()
        number, self._next_timer = self._next_timer, self._next_timer + 1

        def ring() -> None:
            self.timers.pop(number, None)
            self.on_timer(label)

        self.timers[number] = (label, self.timer_factory(minutes * 60, ring), self.now())
        shown = f"{minutes:g} minute" + ("" if minutes == 1 else "s")
        return Result(True, f"Timer set for {shown}" + (f": {label}." if label else "."), undo_data=number)

    def _timer_running(self, args: Args, result: Result) -> bool:
        return result.undo_data in self.timers

    def _cancel_timer(self, args: Args, result: Result) -> Result:
        entry = self.timers.pop(result.undo_data, None)
        if entry is None:
            return Result(False, "That timer has already finished.")
        entry[1].cancel()
        return Result(True, "Timer cancelled.")

    # ---- create_note -------------------------------------------------------------------
    def _create_note(self, args: Args) -> Result:
        self.notes.mkdir(parents=True, exist_ok=True)
        title = _safe_name(args.get("title") or args["text"])
        path = self.notes / f"{self.now():%Y-%m-%d %H%M} {title}.txt"
        n = 2
        while path.exists():
            path = path.with_name(f"{self.now():%Y-%m-%d %H%M} {title} ({n}).txt")
            n += 1
        path.write_text(args["text"], encoding="utf-8")
        return Result(True, f"Saved a note: {path.stem}.", data={"path": str(path)}, undo_data=str(path))

    def _note_saved(self, args: Args, result: Result) -> bool:
        path = Path(result.data["path"])
        return path.exists() and path.read_text(encoding="utf-8") == args["text"]

    def _to_recycle(self, path: Path) -> Path:
        self.recycle.mkdir(parents=True, exist_ok=True)
        target = self.recycle / path.name
        n = 2
        while target.exists():
            target = self.recycle / f"{path.stem} ({n}){path.suffix}"
            n += 1
        shutil.move(str(path), str(target))
        return target

    def _unsave_note(self, args: Args, result: Result) -> Result:
        path = Path(result.undo_data)
        if not path.exists():
            return Result(False, "That note isn't there any more.")
        self._to_recycle(path)
        return Result(True, "Note removed (it's in Jarvis's recycle folder).")

    # ---- delete_file -------------------------------------------------------------------
    def _delete_file(self, args: Args) -> Result:
        path = Path(args["path"])
        if not path.is_file():
            return Result(False, "I can't find that file in Jarvis's folder.")
        if self.recycle in path.parents:
            return Result(False, "That's already in the recycle folder; empty it yourself if you want it gone.")
        target = self._to_recycle(path)
        return Result(True, f"Moved {path.name} to Jarvis's recycle folder.",
                      data={"from": str(path), "to": str(target)}, undo_data=(str(path), str(target)))

    def _deleted(self, args: Args, result: Result) -> bool:
        return not Path(result.data["from"]).exists() and Path(result.data["to"]).exists()

    def _restore(self, args: Args, result: Result) -> Result:
        original, recycled = (Path(p) for p in result.undo_data)
        if original.exists() or not recycled.exists():
            return Result(False, "I couldn't put it back.")
        shutil.move(str(recycled), str(original))
        return Result(True, f"Put {original.name} back.")

    # ---- undo_last_action ----------------------------------------------------------------
    def _undo_last(self, args: Args) -> Result:
        out = self.gate.undo_last()
        return Result(out.status == "done", out.text)

    # ---- the list --------------------------------------------------------------------------
    def _tools(self) -> list[Tool]:
        def obj(props: dict, required: list[str]) -> dict:
            return {"type": "object", "properties": props, "required": required}

        return [
            Tool("open_app", "Open one of these programs on the PC: " + ", ".join(APPS) + ".",
                 obj({"name": {"type": "string", "enum": list(APPS)}}, ["name"]), Tier.JUST_DO,
                 self._open_app, verify=self._app_opened),
            Tool("change_volume", "Turn the PC's sound up or down, or mute/unmute it. steps: 1-10, each about 2%.",
                 obj({"direction": {"type": "string", "enum": ["up", "down", "mute"]},
                      "steps": {"type": "integer", "minimum": 1, "maximum": 10}}, ["direction"]),
                 Tier.JUST_DO, self._change_volume, verify=self._volume_changed),
            Tool("take_screenshot", "Save a picture of the whole screen in Jarvis's screenshots folder.",
                 obj({}, []), Tier.JUST_DO, self._take_screenshot, verify=self._screenshot_saved),
            Tool("set_timer", "Start a timer; Jarvis says when it's done. minutes: 0.5 to 600.",
                 obj({"minutes": {"type": "number", "minimum": 0.5, "maximum": 600},
                      "label": {"type": "string", "maxLength": 60}}, ["minutes"]),
                 Tier.JUST_DO, self._set_timer, verify=self._timer_running, undo=self._cancel_timer),
            Tool("create_note", "Write a short text note into Jarvis's notes folder.",
                 obj({"text": {"type": "string", "minLength": 1, "maxLength": 4000},
                      "title": {"type": "string", "maxLength": 60}}, ["text"]),
                 Tier.DO_AND_LOG, self._create_note, verify=self._note_saved, undo=self._unsave_note),
            Tool("delete_file", "Move a file from Jarvis's folder (e.g. notes/2026-10-28 0930 shopping.txt) to "
                 "Jarvis's recycle folder. The user must confirm with a click.",
                 obj({"path": {"type": "string", "maxLength": 300}}, ["path"]), Tier.ASK_FIRST,
                 self._delete_file, verify=self._deleted, undo=self._restore, path_params=("path",),
                 describe=lambda a: f"Move \"{Path(a['path']).name}\" to Jarvis's recycle folder"),
            Tool("undo_last_action", "Undo the last thing Jarvis did that can be undone (a note, a timer, a "
                 "moved file).", obj({}, []), Tier.JUST_DO, self._undo_last,
                 verify=lambda a, r: True),                  # each undo checks its own result
        ]

    def call(self, name: str, arguments: str = "{}", *, untrusted: bool = False, remote: bool = False):
        return self.gate.call(name, arguments, untrusted=untrusted, remote=remote)

    def names(self) -> set[str]:
        return set(self.registry.names())


def available() -> bool:
    """The real tools only make sense on Windows."""
    return sys.platform == "win32"
