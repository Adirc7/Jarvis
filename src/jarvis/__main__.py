"""Run Jarvis.

    python -m jarvis               text chat (Phase 0): type instead of speaking
    python -m jarvis --no-hotkey   same, without the global kill-switch hotkey

Phase 1 swaps keyboard input for mic + Whisper, and printing for TTS. Everything
else here stays: event bus, shared state, language switching, kill switch,
LLM fallback and telemetry.

Typed commands:
    /lang si     switch language by code (en, si, ta, ...)
    /stop        same as pressing the kill switch
    /status      show state and which LLM answered last
    /quit        exit
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Callable

from .agent.llm import FallbackLLM, LLMUnavailable, configured_providers
from .bus import EventBus
from .config import Settings, load_settings
from .events import KillSwitchPressed, LanguageChanged
from .killswitch import HotkeyListener, Once, kill_switch_binding
from .language import LanguageManager, normalize
from .state import Mode, SharedState
from .telemetry import Telemetry

SYSTEM_PROMPT = (
    "You are Jarvis, a desktop assistant on the user's Windows laptop. "
    "You cannot control the computer yet; if asked to act, say that tools arrive in a later phase. "
    "Be concise and plain-spoken."
)
HISTORY_TURNS = 12


class App:
    def __init__(
        self,
        settings: Settings,
        telemetry: Telemetry,
        llm: FallbackLLM | None = None,
        out: Callable[..., Any] = print,
    ):
        self.settings = settings
        self.telemetry = telemetry
        self.out = out
        default = settings.get("general.default_language", "en")
        self.state = SharedState(language=default)
        self.bus = EventBus()
        self.lang = LanguageManager(
            settings.languages,
            default,
            retranscribe_threshold=settings.get("stt.retranscribe_threshold", 0.8),
            on_change=self._on_language_changed,
        )
        self.llm = llm or FallbackLLM(
            configured_providers(settings.providers(), settings.get("llm.timeout_s", 20)),
            telemetry,
        )
        self.history: list[dict[str, str]] = []
        self._hotkeys: HotkeyListener | None = None

    # ---- language -------------------------------------------------------
    def _on_language_changed(self, ev: LanguageChanged) -> None:
        self.state.language = ev.new
        self.telemetry.log("language_changed", old=ev.old, new=ev.new, source=ev.source)
        if self.bus.is_bound:
            self.bus.publish(ev)

    def say(self, text: str) -> None:
        """Phase 0 'speech' is printing. Phase 1 sends a SpeakRequest to TTS."""
        self.out(f"Jarvis: {text}")

    # ---- one request ----------------------------------------------------
    async def handle_text(self, text: str, source: str = "keyboard") -> str:
        turn = self.telemetry.turn(source=source, language=self.state.language)
        if self.state.mode == Mode.PAUSED:
            self.state.mode = Mode.IDLE   # a new request resumes after the kill switch

        code = self.lang.detect_switch(text)
        if code is not None:
            self.lang.set(code, source=f"{source}_command")
            lang = self.lang.current
            self.say(lang.confirm or f"Switched to {lang.name}.")
            if len(normalize(text).split()) <= 5:
                turn.finish(kind="language_switch", language=code)
                return lang.confirm
            # Longer utterance: switch AND answer the rest in the new language.
            turn.mark("language_switch")

        messages = (
            [{"role": "system", "content": f"{SYSTEM_PROMPT}\n{self.lang.llm_instruction()}"}]
            + self.history[-HISTORY_TURNS * 2:]
            + [{"role": "user", "content": text}]
        )
        token = self.state.token()
        self.state.mode = Mode.THINKING
        parts: list[str] = []
        try:
            async for piece in self.llm.stream_text(messages, token=token):
                if not parts:
                    turn.mark("first_token")
                    self.out("Jarvis: ", end="", flush=True)
                parts.append(piece)
                self.out(piece, end="", flush=True)
        except LLMUnavailable as exc:
            msg = "I can't reach any language model right now. Check the internet connection or start Ollama."
            self.say(msg)
            turn.finish(kind="llm_unavailable", failures=exc.failures)
            return msg
        finally:
            if self.state.mode == Mode.THINKING:
                self.state.mode = Mode.IDLE

        reply = "".join(parts)
        self.out(" [stopped]" if token.cancelled else "")
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        turn.finish(kind="chat", provider=self.llm.last_provider, chars=len(reply), cancelled=token.cancelled)
        return reply

    # ---- background tasks -----------------------------------------------
    async def _kill_switch_task(self) -> None:
        q = self.bus.subscribe(KillSwitchPressed, name="kill_switch")
        while True:
            ev = await q.get()
            gen = self.state.cancel_all()
            self.state.mode = Mode.PAUSED
            self.telemetry.log("kill_switch", source=ev.source, generation=gen)
            self.out("\n[kill switch] everything stopped. Type or speak to resume.")

    def _start_hotkeys(self) -> None:
        hotkey = self.settings.get("hotkeys.kill_switch", "<ctrl>+<alt>+k")
        try:
            self._hotkeys = HotkeyListener({hotkey: Once(kill_switch_binding(self.bus))})
            self._hotkeys.start()
            self.out(f"Kill switch: {hotkey}")
        except Exception as exc:  # no display, missing pynput, etc.
            self.out(f"(Kill-switch hotkey not available: {exc}. Use /stop instead.)")

    async def run(self, enable_hotkey: bool = True) -> None:
        loop = asyncio.get_running_loop()
        self.bus.bind(loop)
        background = asyncio.create_task(self._kill_switch_task())
        if enable_hotkey:
            self._start_hotkeys()
        names = ", ".join(p.name for p in self.llm.providers) or "none (add keys to .env)"
        self.out(f"Jarvis Phase 0 text chat. Language: {self.lang.current.name}. LLM order: {names}")
        self.out("Commands: /lang <code>, /stop, /status, /quit")
        self.telemetry.log("session_start", language=self.state.language, providers=names)
        try:
            while True:
                line = await loop.run_in_executor(None, input, "\nYou: ")
                line = line.strip()
                if not line:
                    continue
                if line.startswith("/"):
                    if not await self._command(line):
                        break
                    continue
                await self.handle_text(line)
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            background.cancel()
            if self._hotkeys:
                self._hotkeys.stop()
            self.telemetry.log("session_end")
            self.out(f"\nLog saved to {self.telemetry.path}")

    async def _command(self, line: str) -> bool:
        cmd, _, arg = line.partition(" ")
        if cmd == "/quit":
            return False
        if cmd == "/stop":
            self.bus.publish(KillSwitchPressed(source="command"))
            await asyncio.sleep(0)
        elif cmd == "/lang":
            arg = arg.strip()
            if arg not in self.lang.languages:
                self.out(f"Unknown language. Available: {', '.join(self.lang.languages)}")
            else:
                self.lang.set(arg, source="command")
                self.say(self.lang.current.confirm or f"Switched to {self.lang.current.name}.")
        elif cmd == "/status":
            self.out(
                f"mode={self.state.mode.value} language={self.state.language} "
                f"generation={self.state.cancel_generation} last_llm={self.llm.last_provider}"
            )
        else:
            self.out("Commands: /lang <code>, /stop, /status, /quit")
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis", description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-hotkey", action="store_true", help="don't register the global kill-switch hotkey")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Sinhala and Tamil in the Windows console
    settings = load_settings()
    telemetry = Telemetry.for_session(settings.path("telemetry.dir", "logs"))
    app = App(settings, telemetry)
    asyncio.run(app.run(enable_hotkey=not args.no_hotkey))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
