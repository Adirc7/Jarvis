"""Run Jarvis.

    python -m jarvis --voice       talk to it (hold Right Ctrl), Phase 1
    python -m jarvis               text chat: type instead of speaking
    python -m jarvis --no-hotkey   without global hotkeys (kill switch, mute)

Typed commands (both modes):
    /lang si     switch language by code (en, si, ta, ...)
    /mute        voice replies on/off
    /stop        same as pressing the kill switch
    /status      show state and which LLM answered last
    /quit        exit
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .app import App
from .config import load_settings
from .telemetry import Telemetry


def audio_device(value):
    """None (the system default) for an empty setting; device 0 stays device 0."""
    return None if value in (None, "") else value


def build_voice_app(settings, telemetry) -> App:
    from .voice.capture import MicRecorder
    from .voice.player import AudioPlayer, SoundDeviceBackend
    from .voice.sink import VoiceSink
    from .voice.stt import Transcriber
    from .voice.tts import TTSRouter

    player = AudioPlayer(SoundDeviceBackend(audio_device(settings.get("audio.output_device"))))
    sink = VoiceSink(settings, TTSRouter(settings), player, telemetry=telemetry)
    recorder = MicRecorder(
        sample_rate=int(settings.get("audio.sample_rate", 16000)),
        device=audio_device(settings.get("audio.input_device")),
        max_seconds=float(settings.get("audio.max_utterance_s", 30)),
    )
    app = App(settings, telemetry, sink=sink, recorder=recorder)
    app.transcriber = Transcriber(settings, app.lang, telemetry)
    return app


def carry(settings, args) -> int:
    """--carry-out / --carry-in (carry.py): moving Jarvis to another PC."""
    from pathlib import Path

    from .carry import CarryError, carry_in, carry_out
    from .config import PROJECT_ROOT
    from .machines import this_machine
    home = Path(str(settings.get("tools.jarvis_folder", "~/Documents/Jarvis"))).expanduser()
    if args.carry_out is not None:
        out = Path(args.carry_out).expanduser() if args.carry_out else desktop_folder()
        path, files = carry_out(PROJECT_ROOT, home, out, this_machine().name, with_keys=args.with_keys)
        print(f"Packed {len(files)} files into:\n  {path}")
        print("Copy it to the new PC (USB, OneDrive, ...). There: clone Jarvis, run \"Setup Jarvis.cmd\", then\n"
              f"  uv run jarvis --carry-in \"{path.name}\"")
        if args.with_keys:
            print("It includes your API keys: keep it private, and delete it once it's moved.")
        return 0
    try:
        manifest, done = carry_in(Path(args.carry_in).expanduser(), PROJECT_ROOT, home)
    except (CarryError, OSError) as exc:
        print(f"Couldn't bring it in: {exc}")
        return 1
    print(f"Brought in Jarvis from {manifest.get('from_pc') or 'another PC'} ({manifest.get('made', '?')}):")
    for line in done:
        print(f"  {line}")
    print("Start Jarvis as usual; he'll know he's on a new computer.")
    return 0


def desktop_folder():
    from pathlib import Path
    for candidate in (Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop"):
        if candidate.is_dir():
            return candidate
    return Path.home()


def open_running_window(settings) -> bool:
    """One Jarvis at a time: if he's already running (the desktop icon clicked again), bring
    up his window instead of starting a second one that would fight over the microphone."""
    from .ui.server import running_jarvis
    port = int(settings.get("window.port", 8765))
    if not settings.get("window.enabled", True) or not running_jarvis(port):
        return False
    url = f"http://127.0.0.1:{port}/"
    from .ui.app_window import open_app_window
    from .ui.server import open_page
    size = settings.get("window.size", [1280, 820])
    if str(settings.get("window.style", "app")) != "app" or not open_app_window(url, (int(size[0]), int(size[1]))):
        open_page(url, str(settings.get("tools.browser", "edge")))
    print(f"Jarvis is already running; opened his window ({url}).")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis", description=__doc__.split("\n\n")[0])
    parser.add_argument("--voice", action="store_true", help="push-to-talk voice mode")
    parser.add_argument("--no-hotkey", action="store_true", help="don't register global hotkeys")
    parser.add_argument("--window", action="store_true", help="open the window of the Jarvis already running")
    parser.add_argument("--carry-out", nargs="?", const="", metavar="PATH",
                        help="pack Jarvis's memory, notes and your trained model into one file, for a new PC")
    parser.add_argument("--carry-in", metavar="FILE", help="bring in a file made with --carry-out (on the new PC)")
    parser.add_argument("--with-keys", action="store_true", help="with --carry-out: include the API keys (.env)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Sinhala and Tamil in the Windows console
    settings = load_settings()
    if args.carry_out is not None or args.carry_in:
        return carry(settings, args)
    if open_running_window(settings):
        return 0
    if args.window:
        print("Jarvis isn't running. Start him from the desktop icon or with: uv run jarvis --voice")
        return 1
    telemetry = Telemetry.for_session(settings.path("telemetry.dir", "logs"))
    voice = args.voice
    app = None
    if voice:
        try:
            app = build_voice_app(settings, telemetry)
        except Exception as exc:   # missing voice libraries, no audio device, ...
            print(f"[voice] could not start ({type(exc).__name__}: {exc}). Continuing in text mode; "
                  "run scripts/smoke_test.py to see what's missing.")
            voice = False
    app = app or App(settings, telemetry)
    asyncio.run(app.run(enable_hotkey=not args.no_hotkey, voice=voice))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
