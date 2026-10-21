"""Where Jarvis's replies go: printed only (TextSink) or printed and spoken (VoiceSink).

The app hands a sink the LLM's token stream. VoiceSink cuts it into sentences,
synthesizes each one on a worker thread and queues it on the player, so the
first sentence is playing while the LLM is still writing the rest.
"""

from __future__ import annotations

import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator, Callable

from ..config import Language, Settings
from ..state import CancelToken
from ..telemetry import Telemetry, Turn
from .player import AudioPlayer
from .text_split import SentenceChunker, clean_for_speech
from .tts import TTSRouter


class TextSink:
    spoken = False

    def __init__(self, out: Callable[..., Any] = print):
        self.out = out

    async def say(self, text: str, lang: Language, token: CancelToken | None = None) -> None:
        self.out(f"Jarvis: {text}")

    async def stream(self, pieces: AsyncIterator[str], lang: Language, token: CancelToken, turn: Turn) -> str:
        parts: list[str] = []
        async for piece in pieces:
            if not parts:
                turn.mark("first_token")
                self.out("Jarvis: ", end="", flush=True)
            parts.append(piece)
            self.out(piece, end="", flush=True)
        if parts:
            self.out(" [stopped]" if token.cancelled else "")
        return "".join(parts)

    def stop(self) -> None:
        pass

    @property
    def busy(self) -> bool:
        return False


class VoiceSink(TextSink):
    spoken = True

    def __init__(
        self,
        settings: Settings,
        tts: TTSRouter,
        player: AudioPlayer,
        out: Callable[..., Any] = print,
        telemetry: Telemetry | None = None,
    ):
        super().__init__(out)
        self.tts = tts
        self.player = player
        self.muted = False
        self._tel = telemetry or Telemetry.disabled()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts")
        self._broken: dict[str, str] = {}      # language code -> TTS error, reported once
        self._chunk_cfg = dict(
            first_min_chars=int(settings.get("tts.first_chunk_min_chars", 12)),
            min_chars=int(settings.get("tts.chunk_min_chars", 40)),
            max_chars=int(settings.get("tts.chunk_max_chars", 220)),
        )
        self.speed_factor = 1.0                 # set by the empathy mode
        # Fillers: tiny pre-rendered phrases ("Mm. One moment.") that cover
        # thinking time when the real reply is slow.
        self.fillers_enabled = bool(settings.get("tts.fillers", True))
        self.filler_after_s = float(settings.get("tts.filler_after_ms", 700)) / 1000
        self._fillers: dict[str, list[tuple[Any, int]]] = {}
        self._last_filler: dict[str, int] = {}
        self._rng = random.Random()

    # ---- public ---------------------------------------------------------
    async def say(self, text: str, lang: Language, token: CancelToken | None = None) -> None:
        self.out(f"Jarvis: {text}")
        if self._can_speak(lang):
            q: asyncio.Queue = asyncio.Queue()
            q.put_nowait(clean_for_speech(text))
            q.put_nowait(None)
            await self._synth_worker(q, lang, token, None)
            await self._wait_playback(token)

    async def stream(self, pieces: AsyncIterator[str], lang: Language, token: CancelToken, turn: Turn) -> str:
        speak = self._can_speak(lang)
        chunker = SentenceChunker(**self._chunk_cfg)
        q: asyncio.Queue = asyncio.Queue()
        reply_started = asyncio.Event()             # the LLM has sent its first text
        worker = asyncio.create_task(self._synth_worker(q, lang, token, turn)) if speak else None
        filler = (asyncio.create_task(self._filler_if_slow(lang, token, turn, reply_started))
                  if speak and self.fillers_enabled else None)
        parts: list[str] = []
        try:
            async for piece in pieces:
                if not parts:
                    turn.mark("first_token")
                    reply_started.set()
                    self.out("Jarvis: ", end="", flush=True)
                parts.append(piece)
                self.out(piece, end="", flush=True)
                if speak:
                    for chunk in chunker.feed(piece):
                        q.put_nowait(chunk)
            if speak:
                for chunk in chunker.flush():
                    q.put_nowait(chunk)
        finally:
            q.put_nowait(None)
            if worker is not None:
                await worker
            if filler is not None and not filler.done():
                filler.cancel()
        if parts:
            self.out(" [stopped]" if token.cancelled else "")
        await self._wait_playback(token)
        return "".join(parts)

    def stop(self) -> None:
        self.player.stop()

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.muted:
            self.player.stop()
        return self.muted

    @property
    def busy(self) -> bool:
        return self.player.busy

    def warm_up(self, lang: Language) -> None:
        """Load the voice for `lang` and run it once (first inference is slow)."""
        try:
            self.tts.render("Ready.", lang)
        except Exception as exc:
            self._report_broken(lang, exc)
            return
        self.prepare_fillers(lang)

    def prepare_fillers(self, lang: Language) -> None:
        """Pre-render this language's fillers so they can play instantly (blocking)."""
        if not self.fillers_enabled or lang.code in self._fillers or not lang.fillers:
            return
        if lang.code in self._broken:
            return
        try:
            self._fillers[lang.code] = [self.tts.render(t, lang, self.speed_factor) for t in lang.fillers]
        except Exception as exc:
            self._report_broken(lang, exc)

    # ---- internals ------------------------------------------------------
    def _can_speak(self, lang: Language) -> bool:
        return not self.muted and lang.code not in self._broken

    def _report_broken(self, lang: Language, exc: Exception) -> None:
        if lang.code not in self._broken:
            self._broken[lang.code] = str(exc)
            self.out(f"\n[voice] {lang.name} voice unavailable, replies will be text only: {exc}")
            self._tel.log("tts_error", language=lang.code, error=str(exc)[:300])

    async def _filler_if_slow(self, lang: Language, token: CancelToken, turn: Turn,
                              reply_started: asyncio.Event) -> None:
        """If the LLM hasn't sent any text in time, say one short filler.

        Once text is arriving, the real voice is only a sentence away; a filler
        started then plays first and pushes the real reply back by its own
        length (it cost 1.3 s at p50 in the first laptop test).
        """
        try:
            await asyncio.wait_for(reply_started.wait(), timeout=self.filler_after_s)
            return                                  # the reply is on its way: no filler
        except asyncio.TimeoutError:
            pass
        if token.cancelled or self.muted:
            return
        options = self._fillers.get(lang.code)
        if not options:
            return                                  # not rendered yet (prepare_fillers runs at start-up)
        choices = [i for i in range(len(options)) if i != self._last_filler.get(lang.code)] or [0]
        i = self._rng.choice(choices)
        self._last_filler[lang.code] = i
        audio, sr = options[i]
        self._tel.log("filler", language=lang.code, index=i)
        self.player.play(audio, sr, token, on_start=lambda: turn.mark("filler"))

    async def _synth_worker(self, q: asyncio.Queue, lang: Language, token: CancelToken | None,
                            turn: Turn | None) -> None:
        loop = asyncio.get_running_loop()
        first = True
        while True:
            chunk = await q.get()
            if chunk is None or (token is not None and token.cancelled):
                return
            try:
                with self._tel.span("tts", language=lang.code, chars=len(chunk)):
                    audio, sr = await loop.run_in_executor(
                        self._executor, self.tts.render, chunk, lang, self.speed_factor)
            except Exception as exc:
                self._report_broken(lang, exc)
                return
            if token is not None and token.cancelled:
                return
            if turn is not None and first:
                turn.mark("first_tts")
            first = False
            on_start = (lambda t=turn: t.mark("first_audio")) if turn is not None else None
            self.player.play(audio, sr, token, on_start=on_start)

    async def _wait_playback(self, token: CancelToken | None) -> None:
        while self.player.busy and not (token is not None and token.cancelled):
            await asyncio.sleep(0.03)
