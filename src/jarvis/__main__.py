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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis", description=__doc__.split("\n\n")[0])
    parser.add_argument("--voice", action="store_true", help="push-to-talk voice mode")
    parser.add_argument("--no-hotkey", action="store_true", help="don't register global hotkeys")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Sinhala and Tamil in the Windows console
    settings = load_settings()
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
