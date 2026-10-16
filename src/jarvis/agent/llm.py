"""Free LLM access with automatic fallback.

Gemini, Groq, OpenRouter and Ollama all offer an OpenAI-compatible endpoint, so
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

    @classmethod
    def from_config(cls, cfg: ProviderConfig, timeout_s: float = 20) -> "Provider":
        from openai import AsyncOpenAI  # lazy: tests don't need the package

        client = AsyncOpenAI(
            base_url=cfg.base_url,
            api_key=cfg.api_key or "missing",
            timeout=timeout_s,
            max_retries=0,          # we do our own fallback; don't wait on retries
        )
        return cls(cfg.name, cfg.model, client)


def configured_providers(configs: list[ProviderConfig], timeout_s: float = 20) -> list[Provider]:
    return [Provider.from_config(c, timeout_s) for c in configs if c.is_configured]


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
        for p in self.providers:
            start = time.perf_counter()
            started = False
            try:
                stream = await p.client.chat.completions.create(
                    model=p.model, messages=messages, stream=True, **kwargs
                )
                async for chunk in stream:
                    if token is not None and token.cancelled:
                        close = getattr(stream, "close", None)
                        if close is not None:
                            await close()
                        self.telemetry.log("llm_cancelled", provider=p.name)
                        return
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if not delta:
                        continue
                    if not started:
                        started = True
                        self.last_provider = p.name
                        self.telemetry.log(
                            "llm_first_token", provider=p.name, model=p.model,
                            ms=round((time.perf_counter() - start) * 1000, 1),
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
                resp = await p.client.chat.completions.create(model=p.model, messages=messages, **kwargs)
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
