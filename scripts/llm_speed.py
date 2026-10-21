"""How fast does each brain start answering a spoken question?

Sends Jarvis's real system prompt and a few everyday questions to every
configured provider and prints, per model (median of all requests):

  new line    time to the first word on a brand-new connection: how Jarvis
              worked until 21 Oct, when the connection closed after 5 s idle
  open line   the same with the connection already open, as Jarvis now does
              by connecting while you hold the push-to-talk key
  thinking    reasoning text before the first word (gpt-oss "thinks" first)

The voice can only start after the first word. Only that is waited for; the
rest of each reply is cancelled, so a run costs little of the free quota.

    uv run python scripts/llm_speed.py
    uv run python scripts/llm_speed.py --runs 3
    uv run python scripts/llm_speed.py --try groq=qwen/qwen3-32b,reasoning_effort=none

--try reuses a configured provider's address and key with another model;
anything after a comma is sent as an extra request field. Check the
provider's model list for what's available today.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.agent.llm import FallbackLLM, Provider  # noqa: E402
from jarvis.config import ProviderConfig, load_settings  # noqa: E402
from jarvis.language import LanguageManager  # noqa: E402
from jarvis.persona import Persona  # noqa: E402
from jarvis.state import SharedState  # noqa: E402
from jarvis.telemetry import Telemetry  # noqa: E402

QUESTIONS = [
    "Jarvis, give me one quick tip for revising thermodynamics tonight.",
    "What's the difference between a series and a parallel circuit, in one sentence?",
    "Remind me why the sky looks blue.",
]


class Capture(Telemetry):
    """Keeps events in memory instead of writing a log file."""

    def __init__(self) -> None:
        super().__init__(None)
        self.events: list[dict[str, Any]] = []

    def log(self, event: str, **fields: Any) -> None:
        self.events.append({"event": event, **fields})


def parse_try(spec: str, configs: dict[str, ProviderConfig]) -> ProviderConfig:
    """'groq=qwen/qwen3-32b,reasoning_effort=none' -> a copy of groq's config."""
    head, *extras = spec.split(",")
    name, _, model = head.partition("=")
    if name not in configs or not model:
        raise SystemExit(f"--try {spec}: use <provider>=<model>; providers: {', '.join(configs)}")
    options: dict[str, Any] = {}
    for extra in extras:
        key, _, value = extra.partition("=")
        options[key.strip()] = value.strip()
    return dataclasses.replace(configs[name], name=f"{name}:{model}", model=model, options=options)


async def first_word(llm: FallbackLLM, messages: list[dict[str, str]]) -> None:
    """Wait for the first word, then cancel the rest the way Jarvis does on barge-in."""
    state = SharedState(language="en")
    async for _ in llm.stream_text(messages, token=state.token(), max_tokens=1024):
        state.cancel_all()          # stream_text closes the stream at the next chunk


async def measure(cfg: ProviderConfig, system: str, runs: int, timeout_s: float,
                  keepalive_s: float) -> dict[str, Any]:
    tels = {"new": Capture(), "open": Capture()}
    errors: list[str] = []
    for _ in range(runs):
        for q in QUESTIONS:
            messages = [{"role": "system", "content": system}, {"role": "user", "content": q}]
            for line, tel in tels.items():
                provider = Provider.from_config(cfg, timeout_s, keepalive_s)   # a fresh connection pool
                llm = FallbackLLM([provider], tel)
                try:
                    if line == "open":
                        await llm.warm()
                    await first_word(llm, messages)
                except Exception as exc:
                    failures = getattr(exc, "failures", None)
                    errors.append(failures[0][1] if failures else f"{type(exc).__name__}: {exc}")
                finally:
                    await provider.client.close()

    def med(tel: Capture, key: str) -> float | None:
        values = [float(e[key]) for e in tel.events if e["event"] == "llm_first_token" and e.get(key) is not None]
        return statistics.median(values) if values else None

    return {"name": cfg.name, "model": cfg.model,
            "n": sum(e["event"] == "llm_first_token" for t in tels.values() for e in t.events),
            "new": med(tels["new"], "ms"), "open": med(tels["open"], "ms"),
            "thinking": med(tels["open"], "thinking_chars"), "errors": errors}


def fmt(v: float | None, unit: str = " ms") -> str:
    return "-" if v is None else f"{v:.0f}{unit}"


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=2, help="times to ask each question (default 2)")
    ap.add_argument("--try", dest="tries", action="append", default=[], metavar="PROVIDER=MODEL[,KEY=VALUE]")
    ap.add_argument("--only-try", action="store_true", help="skip the configured models")
    args = ap.parse_args()

    settings = load_settings()
    configs = {c.name: c for c in settings.providers() if c.is_configured}
    if not configs:
        print("No LLM keys in .env yet.")
        return 1
    targets = [] if args.only_try else list(configs.values())
    targets += [parse_try(spec, configs) for spec in args.tries]

    lm = LanguageManager(settings.languages, settings.get("general.default_language", "en"))
    system = Persona.load().system_prompt(language_instruction=lm.llm_instruction(), spoken=True,
                                          mode="balanced")
    n = len(QUESTIONS) * args.runs
    print(f"System prompt: {len(system)} characters. {n} requests per model on each kind of line.\n")
    print(f"{'model':<44} {'n':>3} {'new line':>9} {'open line':>10} {'thinking':>9}")
    for cfg in targets:
        r = await measure(cfg, system, args.runs, float(settings.get("llm.timeout_s", 20)),
                          float(settings.get("llm.keepalive_s", 120)))
        label = f"{r['name']} ({r['model']})" if ":" not in r["name"] else r["name"]
        print(f"{label[:44]:<44} {r['n']:>3} {fmt(r['new']):>9} {fmt(r['open']):>10} "
              f"{fmt(r['thinking'], ' ch'):>9}")
        if r["errors"]:
            print(f"{'':<4}{len(r['errors'])} failed, e.g. {r['errors'][0][:110]}")
    print("\nBoth columns are the time to the first word, which the voice waits for.")
    print("'new line' connects first (how every spoken turn worked before); 'open line'")
    print("is already connected, as Jarvis now is while you hold the key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
