"""Free LLM access with automatic fallback.

Gemini, Groq (Llama and OpenAI's open gpt-oss models), OpenRouter and Ollama all offer an OpenAI-compatible endpoint, so
one client class covers every provider. `FallbackLLM` tries them in order and
moves to the next one when a provider errors, times out or hits a rate limit.

Fallback only happens *before* the first word arrives. Once a reply has started
streaming, switching provider mid-sentence would produce a garbled answer, so
the error is raised instead and the caller speaks an error message.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from ..config import ProviderConfig
from ..state import CancelToken
from ..telemetry import Telemetry


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

    def request_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Add this provider's options as extra JSON fields (extra_body), so
        provider-specific settings never trip the client's argument checks."""
        if not self.options:
            return kwargs
        out = dict(kwargs)
        out["extra_body"] = {**self.options, **kwargs.get("extra_body", {})}
        return out

    @classmethod
    def from_config(cls, cfg: ProviderConfig, timeout_s: float = 20) -> "Provider":
        from openai import AsyncOpenAI  # lazy: tests don't need the package

        client = AsyncOpenAI(
            base_url=cfg.base_url,
            api_key=cfg.api_key or "missing",
            timeout=timeout_s,
            max_retries=0,          # we do our own fallback; don't wait on retries
        )
        return cls(cfg.name, cfg.model, client, dict(cfg.options))


def configured_providers(configs: list[ProviderConfig], timeout_s: float = 20) -> list[Provider]:
    return [Provider.from_config(c, timeout_s) for c in configs if c.is_configured]


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

    async def stream_text(
        self,
        messages: list[dict[str, Any]],
        token: CancelToken | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Yield reply text as it arrives, from the first provider that answers."""
        failures: list[tuple[str, str]] = []
        prompt_chars = sum(len(str(m.get("content") or "")) for m in messages)
        for p in self.providers:
            start = time.perf_counter()
            started = False
            first_chunk_ms: float | None = None   # anything back from the server
            thinking_chars = 0                    # reasoning text before the first word
            try:
                stream = await p.client.chat.completions.create(
                    model=p.model, messages=messages, stream=True, **p.request_kwargs(kwargs)
                )
                async for chunk in stream:
                    if token is not None and token.cancelled:
                        close = getattr(stream, "close", None)
                        if close is not None:
                            await close()
                        self.telemetry.log("llm_cancelled", provider=p.name)
                        return
                    if first_chunk_ms is None:
                        first_chunk_ms = round((time.perf_counter() - start) * 1000, 1)
                    d = chunk.choices[0].delta if chunk.choices else None
                    delta = getattr(d, "content", None) if d is not None else None
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
                self.telemetry.log(
                    "llm_stream", provider=p.name, model=p.model,
                    ms=round((time.perf_counter() - start) * 1000, 1),
                )
                return
            except Exception as exc:
                if started:
                    raise
                err = f"{type(exc).__name__}: {exc}"[:300]
                failures.append((p.name, err))
                self.telemetry.log("llm_fallback", provider=p.name, error=err)
        raise LLMUnavailable(failures)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> tuple[str, Any]:
        """Non-streaming call (used for tool calling). Returns (provider, message)."""
        failures: list[tuple[str, str]] = []
        if tools:
            kwargs["tools"] = tools
        for p in self.providers:
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
                err = f"{type(exc).__name__}: {exc}"[:300]
                failures.append((p.name, err))
                self.telemetry.log("llm_fallback", provider=p.name, error=err)
        raise LLMUnavailable(failures)
