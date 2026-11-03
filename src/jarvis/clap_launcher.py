"""Clap three times to open Jarvis (4 Nov, Adhi: "triple clap, and the app opens").

A small program with no window that starts when you sign in to Windows (scripts/clap_launcher.cmd
install puts it in the Startup folder). It listens to the microphone for claps only, the way Jarvis's
double clap does (perception/clap.py): each 10 ms of sound is measured and dropped, nothing is recorded
or sent anywhere. Three claps, each 0.2-0.6 s after the one before, then quiet, start Jarvis the way the
desktop icon does; if Jarvis is already running, that brings his window to the front.

    pythonw -m jarvis.clap_launcher            what the Startup shortcut runs
    python -m jarvis.clap_launcher --console   the same, printing each clap it hears (to tune it)

Settings: [clap] in config/settings.toml (the same loudness and pitch limits as the double clap) and
[clap_launcher] enabled. It writes what it did to logs/clap_launcher.log.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT, load_settings
from .perception.clap import ClapDetector, ClapSettings, TripleClap

RATE = 16000


def one_instance() -> object | None:
    """A Windows mutex, so a second copy (the shortcut run twice) quits at once. None: one is running."""
    if sys.platform != "win32":
        return object()
    import ctypes
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\JarvisClapLauncher")
    if ctypes.windll.kernel32.GetLastError() == 183:          # ERROR_ALREADY_EXISTS
        return None
    return handle


def start_jarvis(root: Path = PROJECT_ROOT) -> None:
    """As the desktop icon does: scripts/run_jarvis.cmd app, in a minimized console."""
    runner = root / "scripts" / "run_jarvis.cmd"
    subprocess.Popen(["cmd.exe", "/c", "start", "Jarvis", "/min", "cmd", "/c", str(runner), "app"],
                     cwd=str(root), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class Launcher:
    """Claps in, Jarvis started: the part that runs anywhere (the tests feed it made-up audio)."""

    def __init__(self, settings: ClapSettings | None = None, start=start_jarvis, log=print, console: bool = False):
        self.detector = ClapDetector(RATE, settings)
        self.triple = TripleClap(self.detector.s)
        self.start, self.log, self.console = start, log, console
        self.started = 0

    def feed(self, samples) -> bool:
        for event in self.detector.feed(samples):
            if event.kind == "peak" and event.counted:
                self.triple.peak(event.t)
                if self.console:
                    self.log(f"clap {len(self.triple.times)} at {event.t:.2f} s ({event.above:.0f} dB above the room)")
            elif event.kind == "peak" and self.console:
                self.log(f"not a clap at {event.t:.2f} s ({event.why})")
        if self.triple.done(self.detector._t):
            self.started += 1
            self.log("three claps: starting Jarvis")
            try:
                self.start()
            except Exception as exc:  # noqa: BLE001 - keep listening
                self.log(f"couldn't start Jarvis: {type(exc).__name__}: {exc}")
            return True
        return False


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    console = "--console" in argv
    settings = load_settings(load_env=False)        # no API keys needed to hear claps
    log_path = settings.path("general.log_dir", "logs") / "clap_launcher.log"

    def log(line: str) -> None:
        stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"  # noqa: DTZ005 - local time
        if console:
            print(f"{stamp} {line}", flush=True)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"{stamp} {line}\n")
        except OSError:
            pass

    if not settings.get("clap_launcher.enabled", True):
        log("off: [clap_launcher] enabled = false")
        return 0
    lock = one_instance()
    if lock is None:
        log("already running")
        return 0
    import sounddevice as sd
    launcher = Launcher(ClapSettings.from_settings(settings), log=log, console=console)
    log("listening for three claps (nothing is recorded)")
    while True:
        try:
            with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=1600) as stream:
                while True:
                    block, _ = stream.read(1600)
                    launcher.feed(block[:, 0])
        except KeyboardInterrupt:
            return 0
        except Exception as exc:  # noqa: BLE001 - no microphone yet (asleep, unplugged): try again later
            log(f"microphone unavailable ({type(exc).__name__}: {str(exc)[:120]}); trying again in 30 s")
            time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
