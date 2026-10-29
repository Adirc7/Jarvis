"""Free LLM access with automatic fallback.

Gemini, Groq (Llama and OpenAI's open gpt-oss models), OpenRouter and Ollama all offer an OpenAI-compatible endpoint, so
one client class covers every provider. `FallbackLLM` tries them in order and
moves to the next one when a provider errors, times out or hits a rate limit.

Fallback only happens *before* the first word arrives. Once a reply has started
streaming, switching provider mid-sentence would produce a garbled answer, so
the error is raised instead and the caller speaks an error message.

Routes (agent/router.py decides which): each kind of request has its own
order of providers, e.g. maths to gpt-oss-120b with more thinking, code to
Qwen. Free limits are counted per model, so spreading the work gives more
answers per day. A language can have its own order ("code:si"), since not
every model writes good Sinhala. A model that hits its limit (HTTP 429)
rests until the time the provider gives; one that times out or is
overloaded rests two minutes. Resting models are skipped straight away.
"""

from __future__ import annotations

import asyncio
import importlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from ..config import ProviderConfig
from ..state import CancelToken
from ..telemetry import Telemetry


@dataclass(frozen=True)
class ToolCall:
    """The model asked for an action instead of (or after) answering in words.

    stream_text yields these, as well as text, when it was given `tools`.
    `arguments` is the JSON text the model wrote: untrusted, so the tool
    checks every value before acting.
    """
    name: str
    arguments: str = "{}"


class LLMUnavailable(RuntimeError):
    def __init__(self, failures: list[tuple[str, str]]):
        self.failures = failures
        detail = "; ".join(f"{name}: {err}" for name, err in failures) or "no providers configured"
        super().__init__(f"No LLM provider answered ({detail})")


@dataclass
class Provider:
    name: str
    model: str
    client: Any   # openai.AsyncOpenAI or a test double with the same shape
    options: dict[str, Any] = field(default_factory=dict)   # sent with every request
    base_url: str = ""

    @property
    def quota_key(self) -> str:
        """Free limits belong to the model at a provider: two entries with the
        same model (gpt-oss-120b with low and medium thinking) share them.
        Without an address (test doubles), each entry counts on its own."""
        return f"{self.base_url}|{self.model}" if self.base_url else f"{self.name}|{self.model}"

    def request_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Add this provider's options as extra JSON fields (extra_body), so
        provider-specific settings never trip the client's argument checks."""
        if not self.options:
            return kwargs
        out = dict(kwargs)
        out["extra_body"] = {**self.options, **kwargs.get("extra_body", {})}
        return out

    @classmethod
    def from_config(cls, cfg: ProviderConfig, timeout_s: float = 20, keepalive_s: float = 120,
                    client: Any = None) -> Provider:
        client = client or make_client(cfg, timeout_s, keepalive_s)
        return cls(cfg.name, cfg.model, client, dict(cfg.options), cfg.base_url)


def make_client(cfg: ProviderConfig, timeout_s: float = 20, keepalive_s: float = 120) -> Any:
    from openai import (  # lazy: tests don't need the package
        AsyncOpenAI,
        DefaultAsyncHttpxClient,
    )

    # Keep the connection to the provider open between turns. The default
    # drops it after 5 s idle, so every spoken question (always more than
    # 5 s apart) paid for a new secure connection before the model started.
    # The openai package uses httpx or its successor httpx2, depending on
    # the version: take Limits from whichever its client is built on.
    http_lib = importlib.import_module(DefaultAsyncHttpxClient.__mro__[1].__module__.split(".")[0])
    http_client = DefaultAsyncHttpxClient(
        limits=http_lib.Limits(max_connections=20, max_keepalive_connections=5, keepalive_expiry=keepalive_s),
    )
    return AsyncOpenAI(
        base_url=cfg.base_url,
        api_key=cfg.api_key or "missing",
        timeout=timeout_s,
        max_retries=0,          # we do our own fallback; don't wait on retries
        http_client=http_client,
    )


def configured_providers(configs: list[ProviderConfig], timeout_s: float = 20,
                         keepalive_s: float = 120) -> list[Provider]:
    """One provider per entry with a key; entries at the same address with
    the same key share one client, so one open connection serves all the
    Groq models (and warming it up warms them all)."""
    clients: dict[tuple[str, str | None], Any] = {}
    out = []
    for c in configs:
        if not c.is_configured:
            continue
        key = (c.base_url, c.api_key)
        if key not in clients:
            clients[key] = make_client(c, timeout_s, keepalive_s)
        out.append(Provider.from_config(c, timeout_s, keepalive_s, client=clients[key]))
    return out


def rate_limit_wait(exc: BaseException) -> float | None:
    """Seconds to rest a model after a rate-limit error (HTTP 429), or None.

    Groq sends a retry-after header and says "Please try again in 7m12.5s";
    when neither is there, rest a minute (a per-minute limit) or half an
    hour (a daily one). At most 6 hours: limits reset at least daily.
    """
    if getattr(exc, "status_code", None) != 429:
        return None
    wait: float | None = None
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        wait = float(headers.get("retry-after"))
    except (TypeError, ValueError):
        wait = None
    message = str(exc)
    if wait is None:
        m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", message)
        if m and any(m.groups()):
            h, mins, secs = (float(g) if g else 0.0 for g in m.groups())
            wait = h * 3600 + mins * 60 + secs
    if wait is None:
        daily = re.search(r"per day|daily|\bTPD\b|\bRPD\b|PerDay", message, re.IGNORECASE)
        wait = 1800.0 if daily else 60.0
    return min(max(wait, 5.0), 6 * 3600.0)


SLOW_REST_S = 120.0
# A model that hasn't sent anything by its first-reply deadline rests this long:
# on 24 Oct gpt-oss-20b took 8.7 s and 13.3 s to send its first chunk (laptop
# logs), while the next model in line answers in about 1 s.
FIRST_CHUNK_REST_S = 30.0


class SlowFirstChunk(TimeoutError):
    """Nothing came back by the first-reply deadline; the reply hadn't started, so the next model tries."""


def failure_rest(exc: BaseException) -> float | None:
    """How long to leave a model alone after this error, or None to keep trying it.

    Rate limits: as long as the provider says. Timeouts and overload (500,
    502, 503, 504): two minutes, so a slow provider doesn't cost the full
    timeout on every turn (Gemini took 19-20 s on 21 Oct).
    """
    wait = rate_limit_wait(exc)
    if wait is not None:
        return wait
    if isinstance(exc, SlowFirstChunk):
        return FIRST_CHUNK_REST_S
    if getattr(exc, "status_code", None) in (500, 502, 503, 504):
        return SLOW_REST_S
    if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
        return SLOW_REST_S
    return None


class LeakFilter:
    """Drops sentences where the model talks to itself instead of to you.

    gpt-oss sometimes lets a line of its private reasoning into the reply
    ("Sure, sir. ...?User wants to talk Friday.Do you have..." on 21 Oct).
    Such sentences start in a recognisable way ("User wants", "We need to
    respond"), so at the start of each sentence a few characters are held
    back until it's clear whether it is one. Everything else passes through.
    """

    PREFIXES = tuple(
        p.lower() for group in (
            [f"{who} {verb}" for who in ("user", "the user")
             for verb in ("wants", "asks", "is asking", "said", "says", "requests", "would like", "needs",
                          "just", "mentioned", "greets", "is greeting", "seems", "might")],
            [f"we {modal} {verb}" for modal in ("need to", "should", "must", "can")
             for verb in ("respond", "answer", "reply", "ask", "acknowledge", "comply", "clarify")],
            ["need to respond", "need to answer", "let's respond", "let's answer", "let's craft",
             "i should respond", "i should answer", "the assistant should", "assistant should",
             "so respond", "so answer:", "respond with", "answer in english", "answer in sinhala"],
        ) for p in group)
    LONGEST = max(len(p) for p in PREFIXES)
    ENDS = ".!?\n"

    def __init__(self) -> None:
        self.buf = ""
        self.mode = "start"            # start of a sentence | pass | drop
        self.dropped: list[str] = []
        self.emitted = False           # anything passed on yet
        self.space_due = False         # a sentence was cut out: keep the next one apart

    def _end(self, text: str) -> int:
        return next((i for i, ch in enumerate(text) if ch in self.ENDS), -1)

    def feed(self, text: str) -> str:
        self.buf += text
        out: list[str] = []
        while self.buf:
            if self.mode == "start":
                rest = self.buf.lstrip()
                low = rest.lower()
                if not rest:
                    break                                      # only spaces so far: wait
                if any(low.startswith(p) for p in self.PREFIXES):
                    self.mode = "drop"
                    self.dropped.append("")
                    self.buf = rest
                elif any(p.startswith(low) for p in self.PREFIXES) and len(rest) < self.LONGEST:
                    break                                      # could still become one: wait
                else:
                    self.mode = "pass"
                    if self.space_due and self.emitted and not self.buf[0].isspace():
                        out.append(" ")
                    self.space_due = False
            end = self._end(self.buf)
            piece, self.buf = (self.buf, "") if end < 0 else (self.buf[:end + 1], self.buf[end + 1:])
            if self.mode == "drop":
                self.dropped[-1] += piece
                self.space_due = self.space_due or end >= 0
            else:
                out.append(piece)
                self.emitted = self.emitted or bool(piece.strip())
            if end >= 0:
                self.mode = "start"
        return "".join(out)

    def flush(self) -> str:
        rest, self.buf = ("" if self.mode == "drop" else self.buf), ""
        return rest


class ThinkFilter:
    """Takes out <think>...</think> that some models (Qwen, DeepSeek) write
    into the reply itself, so Jarvis never reads its thinking aloud. Works on
    a stream: a tag split across two pieces is held back until it's whole."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self.inside = False
        self.buf = ""

    def feed(self, text: str) -> tuple[str, int]:
        """(reply text to pass on, characters of thinking taken out)"""
        self.buf += text
        out: list[str] = []
        thought = 0
        while True:
            tag = self.CLOSE if self.inside else self.OPEN
            i = self.buf.find(tag)
            if i >= 0:
                cut, rest = self.buf[:i], self.buf[i + len(tag):]
            else:
                keep = next((k for k in range(min(len(tag) - 1, len(self.buf)), 0, -1)
                             if tag.startswith(self.buf[-k:])), 0)     # maybe the start of a tag
                cut, rest = self.buf[:len(self.buf) - keep], self.buf[len(self.buf) - keep:]
            if self.inside:
                thought += len(cut)
            else:
                out.append(cut)
            self.buf = rest
            if i < 0:
                return "".join(out), thought
            self.inside = not self.inside

    def flush(self) -> str:
        rest, self.buf = ("" if self.inside else self.buf), ""
        return rest


def _reasoning_text(delta: Any) -> str:
    """The model's "thinking" in a stream chunk, if the provider sends it.

    Reasoning models (gpt-oss) think before they answer. Groq and OpenRouter
    send that as `reasoning`, some others as `reasoning_content`; either way
    it isn't part of the reply, but it is time the listener waits.
    """
    for name in ("reasoning", "reasoning_content"):
        value = getattr(delta, name, None)
        if isinstance(value, str):
            return value
    return ""


@dataclass
class FallbackLLM:
    providers: list[Provider]
    telemetry: Telemetry = field(default_factory=Telemetry.disabled)
    last_provider: str | None = None
    # route name -> provider names to try, in order. A route that isn't
    # listed (or no routes at all) uses "general", or every provider in order.
    routes: dict[str, list[str]] = field(default_factory=dict)
    resting: dict[str, float] = field(default_factory=dict)   # quota key -> when it may be tried again
    last_route: str | None = None
    clock: Any = time.monotonic
    # Seconds to wait for a model's first chunk before trying the next one, per
    # route ("default" for the rest). Never applied to the last model available,
    # so a slow answer still beats no answer. Empty: no deadline.
    first_chunk_s: dict[str, float] = field(default_factory=dict)

    def _deadline(self, route: str | None, later: list[Provider]) -> float | None:
        if not self.first_chunk_s or not any(self._resting_for(q) <= 0 for q in later):
            return None
        return self.first_chunk_s.get(route or "general", self.first_chunk_s.get("default"))

    def chain(self, route: str | None = None, lang: str | None = None) -> list[Provider]:
        """The providers to try for this kind of request (in this language), in
        order. Names without a configured provider (no API key) are left out."""
        route = route or "general"
        general = ((lang and self.routes.get(f"general:{lang}")) or self.routes.get("general")
                   or [p.name for p in self.providers])
        names = (lang and self.routes.get(f"{route}:{lang}")) or self.routes.get(route) or general
        by_name = {p.name: p for p in self.providers}
        chosen = [by_name[n] for n in names if n in by_name]
        # Last resort, the general order's other providers: with only some keys
        # (say OpenRouter alone), every kind of request must still get an answer.
        chosen += [by_name[n] for n in general if n in by_name and by_name[n] not in chosen]
        return chosen

    def _resting_for(self, p: Provider) -> float:
        return max(0.0, self.resting.get(p.quota_key, 0.0) - self.clock())

    def _note_failure(self, p: Provider, exc: BaseException) -> str:
        err = f"{type(exc).__name__}: {exc}"[:300]
        wait = failure_rest(exc)
        if wait is not None:
            self.resting[p.quota_key] = self.clock() + wait
            self.telemetry.log("llm_resting", provider=p.name, model=p.model, seconds=round(wait),
                               why=type(exc).__name__)
        return err

    async def stream_text(
        self,
        messages: list[dict[str, Any]],
        token: CancelToken | None = None,
        route: str | None = None,
        lang: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | ToolCall]:
        """Yield reply text as it arrives, from the first provider on the route that answers.

        With `tools=[...]` in kwargs the model may act instead: then ToolCall
        items come (at the end of the stream) instead of, or after, text.
        """
        failures: list[tuple[str, str]] = []
        prompt_chars = sum(len(str(m.get("content") or "")) for m in messages)
        self.last_route = route or "general"
        chain = self.chain(route, lang)
        for index, p in enumerate(chain):
            wait = self._resting_for(p)
            if wait > 0:
                failures.append((p.name, f"resting after a rate limit or timeout ({wait:.0f} s left)"))
                self.telemetry.log("llm_skip_resting", provider=p.name, seconds_left=round(wait))
                continue
            start = time.perf_counter()
            started = False
            first_chunk_ms: float | None = None   # anything back from the server
            thinking_chars = 0                    # reasoning text before the first word
            think = ThinkFilter()
            leak = LeakFilter()
            calls: dict[int, list[str]] = {}     # tool calls arrive in pieces: index -> [name, arguments]
            deadline = self._deadline(route, chain[index + 1:])
            try:
                async def opened(p=p):
                    stream = await p.client.chat.completions.create(
                        model=p.model, messages=messages, stream=True, **p.request_kwargs(kwargs)
                    )
                    it = stream.__aiter__()
                    try:
                        return stream, it, await it.__anext__()
                    except StopAsyncIteration:
                        return stream, it, None

                if deadline:
                    try:
                        stream, it, first = await asyncio.wait_for(opened(), deadline)
                    except TimeoutError:
                        self.telemetry.log("llm_slow_first_chunk", provider=p.name, model=p.model,
                                           deadline_s=deadline)
                        raise SlowFirstChunk(f"nothing back within {deadline:g} s") from None
                else:
                    stream, it, first = await opened()

                async def chunks(first=first, it=it):
                    if first is None:
                        return
                    yield first
                    async for later_chunk in it:
                        yield later_chunk

                async for chunk in chunks():
                    if token is not None and token.cancelled:
                        close = getattr(stream, "close", None)
                        if close is not None:
                            await close()
                        self.telemetry.log("llm_cancelled", provider=p.name)
                        return
                    if first_chunk_ms is None:
                        first_chunk_ms = round((time.perf_counter() - start) * 1000, 1)
                    d = chunk.choices[0].delta if chunk.choices else None
                    for tc in (getattr(d, "tool_calls", None) or []) if d is not None else []:
                        entry = calls.setdefault(getattr(tc, "index", 0) or 0, ["", ""])
                        fn = getattr(tc, "function", None)
                        if fn is not None:
                            entry[0] = getattr(fn, "name", None) or entry[0]
                            entry[1] += getattr(fn, "arguments", None) or ""
                    delta = getattr(d, "content", None) if d is not None else None
                    if delta:
                        delta, thought = think.feed(delta)
                        delta = leak.feed(delta)
                        if not started:
                            thinking_chars += thought
                    if delta and not started:
                        delta = delta.lstrip()             # no stray space before the first word
                    if not delta:
                        if d is not None and not started:
                            thinking_chars += len(_reasoning_text(d))
                        continue
                    if not started:
                        started = True
                        self.last_provider = p.name
                        self.telemetry.log(
                            "llm_first_token", provider=p.name, model=p.model,
                            ms=round((time.perf_counter() - start) * 1000, 1),
                            first_chunk_ms=first_chunk_ms, thinking_chars=thinking_chars,
                            prompt_chars=prompt_chars, messages=len(messages),
                        )
                    yield delta
                tail = leak.feed(think.flush()) + leak.flush()
                if tail and started:
                    yield tail
                if leak.dropped:
                    self.telemetry.log("llm_leak_dropped", provider=p.name, model=p.model,
                                       text=" | ".join(leak.dropped)[:300])
                named = [(name, args or "{}") for name, args in (calls[i] for i in sorted(calls)) if name]
                if named:
                    if not started:
                        started = True
                        self.last_provider = p.name
                    self.telemetry.log("llm_tool_call", provider=p.name, model=p.model,
                                       ms=round((time.perf_counter() - start) * 1000, 1),
                                       tools=[name for name, _ in named])
                    for name, args in named:
                        yield ToolCall(name, args)
                    return
                if not started:
                    raise RuntimeError("empty reply")
                self.telemetry.log(
                    "llm_stream", provider=p.name, model=p.model,
                    ms=round((time.perf_counter() - start) * 1000, 1),
                )
                return
            except Exception as exc:
                if started:
                    raise
                err = self._note_failure(p, exc)
                failures.append((p.name, err))
                self.telemetry.log("llm_fallback", provider=p.name, error=err)
        raise LLMUnavailable(failures)

    async def warm(self, timeout_s: float = 3.0, route: str | None = None) -> None:
        """Open the connection to the first provider before the question is ready.

        Called when push-to-talk is pressed: while you speak, the secure
        connection gets set up, so the question goes out on an open line.
        The route isn't known yet, but all Groq models share one connection.
        A failure here doesn't matter; the real request reports its own.
        """
        chain = self.chain(route)
        if not chain:
            return
        p = chain[0]
        models = getattr(getattr(p.client, "models", None), "list", None)
        if models is None:
            return
        start = time.perf_counter()
        ok = True
        try:
            await asyncio.wait_for(models(), timeout_s)
        except Exception:
            ok = False
        self.telemetry.log("llm_warm", provider=p.name, ok=ok, ms=round((time.perf_counter() - start) * 1000, 1))

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        route: str | None = None,
        lang: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, Any]:
        """Non-streaming call (used for tool calling). Returns (provider, message)."""
        failures: list[tuple[str, str]] = []
        if tools:
            kwargs["tools"] = tools
        for p in self.chain(route, lang):
            if self._resting_for(p) > 0:
                failures.append((p.name, "resting after a rate limit or timeout"))
                continue
            start = time.perf_counter()
            try:
                resp = await p.client.chat.completions.create(
                    model=p.model, messages=messages, **p.request_kwargs(kwargs)
                )
                self.last_provider = p.name
                self.telemetry.log(
                    "llm_complete", provider=p.name, model=p.model,
                    ms=round((time.perf_counter() - start) * 1000, 1),
                )
                return p.name, resp.choices[0].message
            except Exception as exc:
                err = self._note_failure(p, exc)
                failures.append((p.name, err))
                self.telemetry.log("llm_fallback", provider=p.name, error=err)
        raise LLMUnavailable(failures)
