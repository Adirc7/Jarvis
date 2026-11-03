"""The first desktop tools, all through the gate (Phase 2, ROADMAP "First tools").

    just do it   open_app (any program in the Start menu, e.g. MATLAB or RStudio; never a
                 shell, a system tool or a file path), change_volume, take_screenshot,
                 set_timer, lock_pc, cancel_shutdown, undo_last_action
    do and log   create_note (undo moves it to Jarvis's recycle folder)
    ask first    delete_file (moves a file from Jarvis's folder to the recycle
                 folder, never deletes), sleep_pc, sign_out, restart_pc, shutdown_pc
                 (in 30 seconds, so "cancel the shutdown" still stops it): Jarvis
                 asks, and a click, "yes" or a thumbs up confirms (tools/confirm.py)

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


# Never opened by name, though the Start menu lists them: a shell or a system tool would let a command do
# anything (ROADMAP "never": a raw shell, administrator rights, system settings).
NOT_OPENED = re.compile(
    r"\b(power ?shell|cmd|command prompt|terminal|console|bash|wsl|ubuntu|regedit|registry|msconfig|"
    r"system configuration|computer management|disk management|diskpart|group policy|security policy|"
    r"services|task scheduler|event viewer|administrative|windows tools|recovery|reset|uninstall|"
    r"installer|setup|repair|run)\b", re.IGNORECASE)
EXTRAS = re.compile(r"\b(help|documentation|docs|readme|manual|licen[cs]e|release notes|website|web site|faq|"
                    r"tutorials?|examples|support|what's new)\b", re.IGNORECASE)
POWER_DELAY_S = 30            # a shutdown or restart waits this long, so it can still be cancelled


# ---- what touches Windows (replaced by stand-ins in the tests) ---------------------
def start_apps_on_windows() -> list[tuple[str, str]]:
    """Everything in the Start menu: (name, AppID), desktop programs and Store apps alike."""
    import json as _json
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                          "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
                         capture_output=True, text=True, timeout=15, check=False,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    rows = _json.loads(out or "[]")
    rows = [rows] if isinstance(rows, dict) else rows
    return [(str(r.get("Name") or ""), str(r.get("AppID") or "")) for r in rows if r.get("Name") and r.get("AppID")]


def launch_start_app(app_id: str) -> None:
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def power_on_windows(action: str, delay_s: int = POWER_DELAY_S) -> None:
    """Lock, sleep, sign out, restart or shut down; "cancel" stops a pending shutdown or restart."""
    import ctypes
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def run(*args: str) -> None:
        subprocess.run(["shutdown", *args], creationflags=hidden, check=False, timeout=15)

    def later(seconds: float, do: Callable[[], None]) -> None:   # after Jarvis has said what he's doing
        timer = threading.Timer(seconds, do)
        timer.daemon = True
        timer.start()

    if action == "lock":
        later(1.5, lambda: ctypes.windll.user32.LockWorkStation())
    elif action == "sleep":
        later(4, lambda: ctypes.windll.powrprof.SetSuspendState(False, False, False))  # sleep, not hibernate
    elif action == "sign_out":
        later(4, lambda: run("/l"))
    elif action in ("shutdown", "restart"):
        run("/s" if action == "shutdown" else "/r", "/t", str(delay_s), "/c",
            f"Jarvis: {action} in {delay_s} seconds. Say 'cancel the shutdown' to stop it.")
    elif action == "cancel":
        run("/a")
    else:
        raise ValueError(action)


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
                 now: Callable[[], datetime] = datetime.now,
                 start_apps: Callable[[], list[tuple[str, str]]] = start_apps_on_windows,
                 launch: Callable[[str], None] = launch_start_app,
                 power: Callable[[str], None] = power_on_windows):
        self.home = Path(jarvis_folder).expanduser()
        self.notes, self.shots, self.recycle = self.home / "notes", self.home / "screenshots", self.home / "recycle"
        self.start, self.running, self.press_volume, self.read_volume = start, running, press_volume, read_volume
        self.screenshot, self.wait, self.now = screenshot, wait, now
        self.start_apps, self.launch, self.power = start_apps, launch, power
        self._apps: tuple[float, list[tuple[str, str]]] | None = None   # the Start menu, read at most every 10 min
        self.shutdown_pending = False
        self.timer_factory = timer_factory or self._thread_timer
        self.timers: dict[int, tuple[str, Any, datetime]] = {}
        self._next_timer = 1
        self.on_timer: Callable[[str], None] = lambda label: None     # the app says it out loud
        self.registry = Registry(self._tools())
        self.gate = Gate(self.registry, [self.home, *(extra_folders or [])], log, confirm, stopped)

    # ---- open_app ----------------------------------------------------------------
    def _open_refusals(self, args: Args) -> list[str]:
        name = str(args.get("name", "")).strip()
        if re.search(r"[\\/:]|\.(exe|bat|cmd|ps1|vbs|msi|lnk)\b", name, re.IGNORECASE):
            return ["a program's name, not a path or a file"]
        if NOT_OPENED.search(name):
            return ["not a program Jarvis opens (a shell or a system tool)"]
        return []

    def start_menu(self) -> list[tuple[str, str]]:
        now = time.monotonic()
        if self._apps is None or now - self._apps[0] > 600:
            try:
                apps = self.start_apps()
            except Exception:  # noqa: BLE001 - no PowerShell, a timeout: only the fixed list then
                apps = []
            self._apps = (now, [(n, i) for n, i in apps if not NOT_OPENED.search(n)])
        return self._apps[1]

    def find_app(self, name: str) -> tuple[str, str] | None:
        """The Start menu entry `name` means: the same name, one that starts with it, one that has all its
        words ("rstudio" -> RStudio, "matlab" -> MATLAB R2024b), or a close spelling."""
        import difflib
        want = re.sub(r"\s+", " ", name.lower().replace("the ", " ")).strip()
        apps = self.start_menu()
        if not want or not apps:
            return None
        lower = [(n.lower(), n, i) for n, i in apps]
        for test in (lambda n: n == want, lambda n: n.startswith(want),
                     lambda n: all(w in n for w in want.split()),
                     lambda n: n.replace(" ", "").startswith(want.replace(" ", ""))):
            hits = [(n, shown, i) for n, shown, i in lower if test(n)]
            if hits:
                # the program itself before its help, manual or website: "MATLAB R2024b", not "MATLAB Help"
                _, shown, i = min(hits, key=lambda h: (bool(EXTRAS.search(h[0])), len(h[0])))
                return shown, i
        close = difflib.get_close_matches(want, [n for n, _, _ in lower], n=1, cutoff=0.75)
        return next(((shown, i) for n, shown, i in lower if close and n == close[0]), None)

    def _open_app(self, args: Args) -> Result:
        name = str(args["name"]).strip()
        key = name.lower()
        if key in APPS:
            target, _ = APPS[key]
            self.start(target)
            return Result(True, f"Opening {key}.", data={"say": ("opening", {"name": key})})
        found = self.find_app(name)
        if found is None:
            return Result(False, f"I couldn't find a program called {name} in the Start menu.",
                          data={"say": ("app_not_found", {"name": name})})
        shown, app_id = found
        self.launch(app_id)
        return Result(True, f"Opening {shown}.", data={"say": ("opening", {"name": shown}), "app": shown})

    def _app_opened(self, args: Args, result: Result) -> bool | None:
        if str(args["name"]).strip().lower() not in APPS:
            return None                                     # a Start menu program: its process name isn't known
        names = APPS[str(args["name"]).strip().lower()][1]
        for _ in range(6):                                  # up to about 3 seconds
            if set(names) & self.running():
                return True
            self.wait(0.5)
        return False

    # ---- the computer's power ------------------------------------------------------------
    def _power(self, action: str, words: str, say: str) -> Callable[[Args], Result]:
        def run(args: Args) -> Result:
            self.power(action)
            if action in ("shutdown", "restart"):
                self.shutdown_pending = True
            return Result(True, words, undo_data=action, data={"say": (say, {"s": POWER_DELAY_S})})
        return run

    def _cancel_shutdown(self, args: Args | None = None, result: Result | None = None) -> Result:
        if not self.shutdown_pending:
            return Result(False, "There's no shutdown or restart waiting.", data={"say": ("no_shutdown", {})})
        self.power("cancel")
        self.shutdown_pending = False
        return Result(True, "Cancelled: the computer stays on.", data={"say": ("shutdown_cancelled", {})})

    # ---- change_volume -------------------------------------------------------------
    def _change_volume(self, args: Args) -> Result:
        before = self.read_volume()
        self.press_volume(args["direction"], int(args.get("steps", 3)))
        words = {"up": "Volume up.", "down": "Volume down.", "mute": "Sound muted or unmuted."}[args["direction"]]
        return Result(True, words, data={"before": before, "say": (f"volume_{args['direction']}", {})})

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
        return Result(True, f"Screenshot saved in {self.shots.name}.", data={"path": str(path), "say": ("screenshot", {})})

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
        return Result(True, f"Timer set for {shown}" + (f": {label}." if label else "."), undo_data=number,
                      data={"say": ("timer_label" if label else "timer", {"minutes": f"{minutes:g}", "label": label})})

    def _timer_running(self, args: Args, result: Result) -> bool:
        return result.undo_data in self.timers

    def _cancel_timer(self, args: Args, result: Result) -> Result:
        entry = self.timers.pop(result.undo_data, None)
        if entry is None:
            return Result(False, "That timer has already finished.", data={"say": ("timer_finished", {})})
        entry[1].cancel()
        return Result(True, "Timer cancelled.", data={"say": ("timer_cancelled", {})})

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
        return Result(True, f"Saved a note: {path.stem}.", undo_data=str(path),
                      data={"path": str(path), "say": ("note_saved", {"title": path.stem})})

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
            return Result(False, "That note isn't there any more.", data={"say": ("note_gone", {})})
        self._to_recycle(path)
        return Result(True, "Note removed (it's in Jarvis's recycle folder).", data={"say": ("note_removed", {})})

    # ---- delete_file -------------------------------------------------------------------
    def _delete_file(self, args: Args) -> Result:
        path = Path(args["path"])
        if not path.is_file():
            return Result(False, "I can't find that file in Jarvis's folder.", data={"say": ("not_found", {})})
        if self.recycle in path.parents:
            return Result(False, "That's already in the recycle folder; empty it yourself if you want it gone.",
                          data={"say": ("already_recycled", {})})
        target = self._to_recycle(path)
        return Result(True, f"Moved {path.name} to Jarvis's recycle folder.", undo_data=(str(path), str(target)),
                      data={"from": str(path), "to": str(target), "say": ("moved", {"name": path.name})})

    def _deleted(self, args: Args, result: Result) -> bool:
        return not Path(result.data["from"]).exists() and Path(result.data["to"]).exists()

    def _restore(self, args: Args, result: Result) -> Result:
        original, recycled = (Path(p) for p in result.undo_data)
        if original.exists() or not recycled.exists():
            return Result(False, "I couldn't put it back.", data={"say": ("cant_restore", {})})
        shutil.move(str(recycled), str(original))
        return Result(True, f"Put {original.name} back.", data={"say": ("restored", {"name": original.name})})

    # ---- undo_last_action ----------------------------------------------------------------
    def _undo_last(self, args: Args) -> Result:
        out = self.gate.undo_last()
        say = out.result.data.get("say") if out.result else ("nothing_to_undo", {})
        return Result(out.status == "done", out.text, data={"say": say})

    # ---- the list --------------------------------------------------------------------------
    def _tools(self) -> list[Tool]:
        def obj(props: dict, required: list[str]) -> dict:
            return {"type": "object", "properties": props, "required": required}

        def power(name: str, action: str, what: str, words: str, say: str, tier: Tier, describe: str,
                  undo: Callable[[Args, Result], Result] | None = None) -> Tool:
            return Tool(name, what, obj({}, []), tier, self._power(action, words, say), verify=lambda a, r: None,
                        undo=undo, describe=lambda a: describe)

        later = f"in {POWER_DELAY_S} seconds; until then 'cancel the shutdown' stops it"
        return [
            Tool("open_app", "Open a program on the PC by its name: anything in the Start menu (e.g. MATLAB, "
                 "RStudio, Octave, Zoom), or " + ", ".join(APPS) + ". Not shells or system tools.",
                 obj({"name": {"type": "string", "minLength": 1, "maxLength": 60}}, ["name"]), Tier.JUST_DO,
                 self._open_app, verify=self._app_opened, check=self._open_refusals),
            power("lock_pc", "lock", "Lock the computer's screen (Windows asks for the PIN to come back).",
                  "Locking the screen.", "locking", Tier.JUST_DO, "Lock the screen"),
            power("sleep_pc", "sleep", "Put the computer to sleep. Jarvis asks first.",
                  "Going to sleep in a few seconds.", "sleeping", Tier.ASK_FIRST, "Put the computer to sleep"),
            power("sign_out", "sign_out", "Sign out of Windows (closes every program). Jarvis asks first.",
                  "Signing out in a few seconds.", "signing_out", Tier.ASK_FIRST,
                  "Sign out of Windows (every program closes)"),
            power("restart_pc", "restart", f"Restart the computer ({later}). Jarvis asks first.",
                  f"Restarting in {POWER_DELAY_S} seconds. Say cancel the shutdown to stop it.", "restarting",
                  Tier.ASK_FIRST, f"Restart the computer {later}", undo=self._cancel_shutdown),
            power("shutdown_pc", "shutdown", f"Shut down / turn off the computer ({later}). Jarvis asks first.",
                  f"Shutting down in {POWER_DELAY_S} seconds. Say cancel the shutdown to stop it.",
                  "shutting_down", Tier.ASK_FIRST, f"Shut down the computer {later}", undo=self._cancel_shutdown),
            Tool("cancel_shutdown", "Stop a shutdown or restart Jarvis started that hasn't happened yet.",
                 obj({}, []), Tier.JUST_DO, lambda a: self._cancel_shutdown(a), verify=lambda a, r: None),
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
