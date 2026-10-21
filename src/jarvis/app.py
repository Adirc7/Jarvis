"""The Jarvis application: one request pipeline for typed and spoken input.

    text mode   keyboard -> language rules -> LLM -> printed reply
    voice mode  push-to-talk -> Whisper -> language rules -> LLM -> spoken reply
                (typing still works in voice mode)

Background tasks on the asyncio loop:
    control     kill switch and mute (from global hotkeys or typed commands)
    voice       push-to-talk events -> transcription -> handle_text
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable

from .agent.llm import FallbackLLM, LLMUnavailable, configured_providers
from .agent.router import KeywordRouter, Router
from .bus import EventBus
from .config import Settings
from .events import (
    KillSwitchPressed, LanguageChanged, MuteToggled, PushToTalkPressed, UtteranceCaptured,
)
from .greeting import FULL, Greeter, Presence, fill, greeting_kind
from .killswitch import HotkeyListener, Once
from .language import LanguageManager, normalize
from .memory import Memory, detect_fact, detect_name
from .persona import Persona
from .state import Mode, SharedState
from .telemetry import Telemetry, Turn
from .voice.sink import TextSink

HISTORY_TURNS = 12
LLM_UNAVAILABLE = "I can't reach any language model right now. Check the internet connection or start Ollama."


class App:
    def __init__(
        self,
        settings: Settings,
        telemetry: Telemetry,
        llm: FallbackLLM | None = None,
        out: Callable[..., Any] = print,
        sink: TextSink | None = None,
        transcriber=None,
        recorder=None,
        persona: Persona | None = None,
        presence: Presence | None = None,
        memory: Memory | None = None,
        router: Router | None = None,
    ):
        self.settings = settings
        self.persona = persona or Persona.load()
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
            configured_providers(settings.providers(), settings.get("llm.timeout_s", 20),
                                 float(settings.get("llm.keepalive_s", 120))),
            telemetry,
            routes=settings.routes(),
        )
        # Which kind of request, so which models (agent/router.py). Adhi's
        # intent classifier replaces the keyword rules later (IntentRouter).
        self.router = router or KeywordRouter(int(settings.get("llm.long_prompt_chars", 12000)))
        self.sink = sink or TextSink(out)
        self.state.empathy = self.persona.default_mode
        self._apply_empathy_voice()
        self.transcriber = transcriber
        self.recorder = recorder
        self.history: list[dict[str, str]] = []
        self._hotkeys: HotkeyListener | None = None
        self._ptt = None
        self._stt_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stt")
        # When you last talked to Jarvis, so greetings follow sessions, not restarts.
        self.presence = presence if presence is not None else Presence.load(
            settings.path("general.state_dir", "state") / "presence.json")
        self.greeter = Greeter()
        self.greeted_with: str | None = None
        # What Jarvis remembers between sessions (memory.py): your name, facts
        # you asked it to keep, and the conversation if it was recent.
        if memory is not None:
            self.memory = memory
        elif settings.get("memory.enabled", True):
            self.memory = Memory.load(settings.path("general.state_dir", "state") / "memory.json")
        else:
            self.memory = Memory(None)
        if self.memory.name:
            self.persona.user_name = self.memory.name
        if self.settings.get("memory.keep_conversation", True):
            self.history = self.memory.recent_if_fresh(float(self.settings.get("memory.continue_hours", 12)))

    # ---- language -------------------------------------------------------
    def _on_language_changed(self, ev: LanguageChanged) -> None:
        self.state.language = ev.new
        self.telemetry.log("language_changed", old=ev.old, new=ev.new, source=ev.source)
        if self.bus.is_bound:
            self.bus.publish(ev)
            prepare = getattr(self.sink, "prepare_fillers", None)
            if prepare is not None:   # get the new language's fillers ready in the background
                self.bus.loop.run_in_executor(None, prepare, self.lang.current)

    def system_prompt(self) -> str:
        prompt = self.persona.system_prompt(
            language_instruction=self.lang.llm_instruction(),
            spoken=self.sink.spoken,
            mode=self.state.empathy,
            assistant_name=self.lang.current.assistant_name,
        )
        if self.greeted_with:
            prompt += (f'\n\nYou already said "{self.greeted_with}" when this session started. '
                       "Don't greet the user again; just carry on.")
        if self.memory.enabled:
            prompt += "\n\n" + self.memory.prompt_block()
        return prompt

    # ---- greeting -------------------------------------------------------
    async def greet(self, now: datetime | None = None) -> str | None:
        """Say the greeting that fits: full once a day, a pick-up after a break,
        or just "I'm here" within the same session (see greeting.py)."""
        if not self.settings.get("greeting.enabled", True):
            return None
        now = now or datetime.now()
        kind = greeting_kind(now, self.presence.last_active, self.presence.last_full,
                             float(self.settings.get("greeting.same_session_minutes", 15)))
        lang = self.lang.current
        if not lang.greetings and "en" in self.lang.languages:
            lang = self.lang.languages["en"]
        text = self.greeter.pick(kind, now, lang.greetings, self.persona.address)
        if not text:
            return None
        if kind == FULL:
            self.presence.last_full = now.date()
        self.presence.touch(now)
        self.presence.save()
        self.greeted_with = text
        self.telemetry.log("greeting", kind=kind, language=lang.code)
        await self.sink.say(text, lang, self.state.token())
        return text

    # ---- empathy mode ---------------------------------------------------
    def _apply_empathy_voice(self) -> None:
        mode = self.persona.modes.get(self.state.empathy)
        if hasattr(self.sink, "speed_factor") and mode is not None:
            self.sink.speed_factor = mode.speed

    def set_empathy(self, mode: str, source: str) -> bool:
        if mode not in self.persona.modes:
            return False
        if mode != self.state.empathy:
            self.telemetry.log("empathy_changed", old=self.state.empathy, new=mode, source=source)
        self.state.empathy = mode
        self._apply_empathy_voice()
        return True

    # ---- one request ----------------------------------------------------
    async def handle_text(self, text: str, source: str = "keyboard", turn: Turn | None = None) -> str:
        turn = turn or self.telemetry.turn(source=source)
        self.presence.touch()
        self.presence.save()
        if self.state.mode == Mode.PAUSED:
            self.state.mode = Mode.IDLE   # a new request resumes after the kill switch

        # "be more direct" / "be gentler": change style, then let the model
        # acknowledge it naturally, in whatever language is active.
        mode = self.persona.detect_mode_command(text)
        if mode is not None:
            self.set_empathy(mode, source=f"{source}_command")
            turn.mark("empathy_switch")

        code = self.lang.detect_switch(text)
        if code is not None:
            self.lang.set(code, source=f"{source}_command")
            lang = self.lang.current
            confirm = lang.confirm or f"Switched to {lang.name}."
            if len(normalize(text).split()) <= 5:
                await self.sink.say(confirm, lang, self.state.token())
                turn.finish(kind="language_switch", language=code)
                return confirm
            self.out(f"Jarvis: {confirm}")
            turn.mark("language_switch")   # longer request: switch AND answer it

        self._learn_from(text)

        messages = (
            [{"role": "system", "content": self.system_prompt()}]
            + self.history[-HISTORY_TURNS * 2:]
            + [{"role": "user", "content": text}]
        )
        token = self.state.token()
        lang = self.lang.current
        decision = self.router.route(text, lang.code, sum(len(m["content"]) for m in messages))
        self.telemetry.log("route", route=decision.route, reason=decision.reason, intent=decision.intent)
        self.state.mode = Mode.THINKING
        try:
            reply = await self.sink.stream(
                self.llm.stream_text(messages, token=token, route=decision.route, lang=lang.code), lang, token, turn)
        except LLMUnavailable as exc:
            await self.sink.say(LLM_UNAVAILABLE, self.lang.languages["en"] if "en" in self.lang.languages else lang)
            turn.finish(kind="llm_unavailable", failures=exc.failures, route=decision.route)
            return LLM_UNAVAILABLE
        finally:
            if self.state.mode in (Mode.THINKING, Mode.SPEAKING):
                self.state.mode = Mode.IDLE

        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        if self.memory.enabled and self.settings.get("memory.keep_conversation", True):
            self.memory.set_recent(self.history[-HISTORY_TURNS * 2:])
            self.memory.save()
        turn.finish(kind="chat", provider=self.llm.last_provider, route=decision.route, language=lang.code,
                    chars=len(reply), cancelled=token.cancelled)
        return reply

    # ---- voice ----------------------------------------------------------
    async def _voice_task(self) -> None:
        q = self.bus.subscribe(PushToTalkPressed, UtteranceCaptured, name="voice")
        min_s = float(self.settings.get("audio.min_utterance_s", 0.35))
        max_s = float(self.settings.get("audio.max_utterance_s", 30))
        current: asyncio.Task | None = None
        while True:
            ev = await q.get()
            if isinstance(ev, PushToTalkPressed):
                if (current is not None and not current.done()) or self.sink.busy:
                    self.state.cancel_all()          # barge-in: stop the current reply
                    self.sink.stop()
                    self.telemetry.log("barge_in")
                self.state.mode = Mode.LISTENING
                self.out("\n[listening... release the key to send]")
                if self.settings.get("llm.prewarm", True):
                    # Connect to the LLM while you speak, not after (llm.py, warm).
                    self._warm_task = asyncio.create_task(self.llm.warm())
            elif isinstance(ev, UtteranceCaptured):
                if ev.seconds < min_s:
                    self.state.mode = Mode.IDLE
                    self.out("(too short: hold the key while you speak)")
                    continue
                if ev.seconds >= max_s - 0.05:
                    # The recorder stops keeping audio at the limit but waits for the key.
                    self.out(f"(the key was held for the {max_s:.0f}-second limit; anything after that "
                             "was cut off)")
                    self.telemetry.log("utterance_limit", seconds=round(ev.seconds, 2))
                current = asyncio.create_task(self.voice_turn(ev.audio, ev.seconds))

    async def voice_turn(self, audio, seconds: float) -> str | None:
        turn = self.telemetry.turn(source="voice", audio_s=round(seconds, 2))
        self.state.mode = Mode.THINKING
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(self._stt_executor, self.transcriber.transcribe, audio)
        except Exception as exc:
            self.out(f"[speech recognition failed] {exc}")
            self.state.mode = Mode.IDLE
            turn.finish(kind="stt_error", error=str(exc)[:200])
            return None
        turn.mark("stt_done")
        if not result.text:
            self.out("(I didn't catch anything)")
            self.state.mode = Mode.IDLE
            turn.finish(kind="empty")
            return None
        heard = self.lang.languages[result.language].name
        note = f", p={result.detected_probability}" if result.detected_probability is not None else ""
        if result.unclear:
            # Whisper wrote something, but it looks like nonsense: ask again
            # rather than let the LLM answer it (voice/clarity.py).
            self.out(f"You [{heard}{note}, unclear: {result.unclear}]: {result.text}")
            lang = self.lang.current
            line = lang.unclear or self.lang.languages["en"].unclear or "Sorry, could you say that again?"
            await self.sink.say(fill(line, self.persona.address), lang, self.state.token())
            self.state.mode = Mode.IDLE
            turn.finish(kind="unclear", reason=result.unclear, heard=result.language)
            return None
        self.out(f"You [{heard}{note}]: {result.text}")
        if self.settings.get("general.language_mode", "fixed") == "auto" and result.language != self.state.language:
            self.lang.set(result.language, source="auto")
        return await self.handle_text(result.text, source="voice", turn=turn)

    def _start_push_to_talk(self) -> None:
        from .voice.capture import PushToTalk

        def pressed() -> None:
            self.recorder.begin()
            self.bus.publish_threadsafe(PushToTalkPressed())

        def released() -> None:
            audio = self.recorder.end()
            self.bus.publish_threadsafe(UtteranceCaptured(audio=audio, seconds=len(audio) / self.recorder.sample_rate))

        key = self.settings.get("hotkeys.push_to_talk", "ctrl_r")
        self._ptt = PushToTalk(key, pressed, released)
        self._ptt.start()

    async def _prepare_voice(self) -> None:
        loop = asyncio.get_running_loop()
        self.out("Loading speech models (the first run downloads Whisper)...")
        await loop.run_in_executor(self._stt_executor, self.transcriber.warm_up)
        warm = getattr(self.sink, "warm_up", None)
        if warm is not None:
            device = await loop.run_in_executor(None, warm, self.lang.current)
            if device:
                where = "the graphics card (CUDA)" if device == "cuda" else "the CPU"
                self.out(f"{self.lang.current.name} voice runs on {where}.")
        self.recorder.open()
        self._start_push_to_talk()

    # ---- control (kill switch, mute) ------------------------------------
    async def _control_task(self) -> None:
        q = self.bus.subscribe(KillSwitchPressed, MuteToggled, name="control")
        while True:
            ev = await q.get()
            if isinstance(ev, KillSwitchPressed):
                gen = self.state.cancel_all()
                self.sink.stop()
                self.state.mode = Mode.PAUSED
                self.telemetry.log("kill_switch", source=ev.source, generation=gen)
                self.out("\n[kill switch] everything stopped. Type or speak to resume.")
            elif isinstance(ev, MuteToggled):
                toggle = getattr(self.sink, "toggle_mute", None)
                if toggle is None:
                    self.out("(mute only applies in voice mode)")
                    continue
                muted = toggle()
                self.telemetry.log("mute", muted=muted)
                self.out(f"\n[voice {'muted: replies are text only' if muted else 'on'}]")

    def _start_hotkeys(self) -> None:
        bindings = {
            self.settings.get("hotkeys.kill_switch", "<ctrl>+<alt>+k"):
                Once(lambda: self.bus.publish_threadsafe(KillSwitchPressed(source="hotkey"))),
            self.settings.get("hotkeys.mute", "<ctrl>+<alt>+m"):
                Once(lambda: self.bus.publish_threadsafe(MuteToggled(source="hotkey"))),
        }
        try:
            self._hotkeys = HotkeyListener(bindings)
            self._hotkeys.start()
        except Exception as exc:  # no display, missing pynput, etc.
            self.out(f"(Global hotkeys not available: {exc}. Use /stop and /mute instead.)")

    # ---- main loop -------------------------------------------------------
    async def run(self, enable_hotkey: bool = True, voice: bool = False) -> None:
        loop = asyncio.get_running_loop()
        self.bus.bind(loop)
        tasks = [asyncio.create_task(self._control_task())]
        if enable_hotkey:
            self._start_hotkeys()
        names = ", ".join(p.name for p in self.llm.chain("general")) or "none (add keys to .env)"
        mode = "voice" if voice else "text"
        self.out(f"Jarvis Phase 1 ({mode} mode). Language: {self.lang.current.name}. LLM order: {names}")
        routes = [r for r in self.llm.routes if r != "general" and ":" not in r]
        if routes:
            self.out("Models by kind of request: " + "; ".join(
                f"{r} {self.llm.chain(r)[0].name}" for r in routes if self.llm.chain(r)))
        if voice:
            try:
                await self._prepare_voice()
            except Exception as exc:
                voice = False
                self.out(f"[voice] could not start ({type(exc).__name__}: {exc}). Continuing in text mode; "
                         "run scripts/smoke_test.py to see what's missing.")
                self.telemetry.log("voice_start_failed", error=str(exc)[:300])
        if voice:
            tasks.append(asyncio.create_task(self._voice_task()))
            from .voice.capture import describe_key

            ptt = describe_key(self.settings.get("hotkeys.push_to_talk", "ctrl_r"))
            self.out(
                f"Hold {ptt} and speak. "
                f"{self.settings.get('hotkeys.mute')} mutes, {self.settings.get('hotkeys.kill_switch')} stops everything. "
                "You can also type."
            )
        self.out("Commands: /lang <code>, /empathy <mode>, /name <name>, /remember <fact>, /memory, /forget, "
                     "/mute, /stop, /status, /quit")
        self.telemetry.log("session_start", language=self.state.language, providers=names, mode=mode)
        try:
            await self.greet()
        except Exception as exc:   # a greeting must never stop Jarvis from starting
            self.telemetry.log("greeting_failed", error=str(exc)[:300])
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
            for t in tasks:
                t.cancel()
            if self._hotkeys:
                self._hotkeys.stop()
            if self._ptt:
                self._ptt.stop()
            if self.recorder is not None and voice:
                self.recorder.close()
            self.sink.stop()
            self.presence.save()
            self.telemetry.log("session_end")
            self.out(f"\nLog saved to {self.telemetry.path}")

    def _learn_from(self, text: str) -> None:
        """Keep what the user tells Jarvis to remember (only what they said)."""
        if not self.memory.enabled:
            return
        changed = False
        name = detect_name(text)
        if name and name != self.memory.name:
            self.memory.set_name(name)
            self.persona.user_name = name
            self.out(f"[memory] I'll remember your name: {name}  (/memory to see, /forget to clear)")
            changed = True
        fact = detect_fact(text)
        if fact and self.memory.remember(fact):
            self.out(f"[memory] Remembered: {fact}")
            changed = True
        if changed:
            self.memory.save()
            self.telemetry.log("memory_saved", name=bool(name), fact=bool(fact))

    async def _command(self, line: str) -> bool:
        cmd, _, arg = line.partition(" ")
        if cmd == "/quit":
            return False
        if cmd == "/stop":
            self.bus.publish(KillSwitchPressed(source="command"))
            await asyncio.sleep(0)
        elif cmd == "/mute":
            self.bus.publish(MuteToggled(source="command"))
            await asyncio.sleep(0)
        elif cmd == "/lang":
            arg = arg.strip()
            if arg not in self.lang.languages:
                self.out(f"Unknown language. Available: {', '.join(self.lang.languages)}")
            else:
                self.lang.set(arg, source="command")
                lang = self.lang.current
                await self.sink.say(lang.confirm or f"Switched to {lang.name}.", lang, self.state.token())
        elif cmd == "/empathy":
            arg = arg.strip()
            if not self.set_empathy(arg, source="command"):
                self.out(f"Empathy modes: {', '.join(self.persona.modes)} (now: {self.state.empathy})")
            else:
                self.out(f"[empathy: {arg}]")
        elif cmd == "/name":
            if arg.strip():
                self.memory.set_name(arg.strip())
                self.persona.user_name = arg.strip()
                self.memory.save()
                self.out(f"[memory] Name: {arg.strip()}")
            else:
                self.out(f"[memory] Name: {self.memory.name or '(not set)'}. Set it with /name <your name>.")
        elif cmd == "/remember":
            if arg.strip() and self.memory.remember(arg.strip()):
                self.memory.save()
                self.out(f"[memory] Remembered: {arg.strip()}")
            else:
                self.out("Usage: /remember <something to keep between sessions>")
        elif cmd == "/memory":
            self.out(self.memory.describe() if self.memory.enabled else "[memory] Memory is off ([memory] enabled).")
        elif cmd == "/forget":
            self.memory.forget()
            self.memory.save()
            self.history = []
            self.persona.user_name = ""
            self.out("[memory] Forgotten: name, facts and the saved conversation.")
        elif cmd == "/status":
            self.out(
                f"mode={self.state.mode.value} language={self.state.language} "
                f"generation={self.state.cancel_generation} empathy={self.state.empathy} last_llm={self.llm.last_provider} "
                f"muted={getattr(self.sink, 'muted', None)}"
            )
        else:
            self.out("Commands: /lang <code>, /empathy <mode>, /name <name>, /remember <fact>, /memory, /forget, "
                     "/mute, /stop, /status, /quit")
        return True
