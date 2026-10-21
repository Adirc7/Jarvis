"""Jarvis's character: turns config/persona.toml into the model's instructions.

The persona is what makes Jarvis feel like the same someone in every reply:
its traits, how it speaks, what it will and won't claim, what it can do right
now, the current empathy mode, and the local time of day.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT
from .language import normalize

MAX_MODE_COMMAND_WORDS = 8


@dataclass(frozen=True)
class EmpathyMode:
    name: str
    instruction: str
    speed: float = 1.0
    phrases: tuple[str, ...] = ()


@dataclass
class Persona:
    name: str = "Jarvis"
    user_name: str = ""
    address: str = ""          # how Jarvis addresses the user, e.g. "sir"
    role: str = "a personal desktop assistant"
    traits: list[str] = field(default_factory=list)
    style_rules: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    can: list[str] = field(default_factory=list)
    cannot_yet: list[str] = field(default_factory=list)
    include_time: bool = True
    modes: dict[str, EmpathyMode] = field(default_factory=dict)
    default_mode: str = "balanced"

    @classmethod
    def load(cls, path: Path | None = None) -> "Persona":
        path = path or PROJECT_ROOT / "config" / "persona.toml"
        if not path.is_file():
            return cls(modes={"balanced": EmpathyMode("balanced", "")})
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        modes = {
            name: EmpathyMode(name, m.get("instruction", ""), float(m.get("speed", 1.0)),
                              tuple(m.get("phrases", [])))
            for name, m in raw.get("empathy", {}).get("modes", {}).items()
        } or {"balanced": EmpathyMode("balanced", "")}
        default = raw.get("empathy", {}).get("default", "balanced")
        return cls(
            name=raw.get("identity", {}).get("name", "Jarvis"),
            user_name=raw.get("identity", {}).get("user_name", ""),
            address=raw.get("identity", {}).get("address", ""),
            role=raw.get("identity", {}).get("role", "a personal desktop assistant"),
            traits=raw.get("personality", {}).get("traits", []),
            style_rules=raw.get("speaking_style", {}).get("rules", []),
            boundaries=raw.get("boundaries", {}).get("rules", []),
            can=raw.get("abilities", {}).get("can", []),
            cannot_yet=raw.get("abilities", {}).get("cannot_yet", []),
            include_time=raw.get("context", {}).get("include_time", True),
            modes=modes,
            default_mode=default if default in modes else next(iter(modes)),
        )

    # ------------------------------------------------------------------
    def detect_mode_command(self, text: str) -> str | None:
        """'be more direct' -> 'logical'. Only short utterances count."""
        norm = normalize(text)
        words = norm.split()
        if not words or len(words) > MAX_MODE_COMMAND_WORDS:
            return None
        padded = f" {norm} "
        for mode in self.modes.values():
            if any(f" {normalize(p)} " in padded for p in mode.phrases):
                return mode.name
        return None

    def system_prompt(
        self,
        *,
        language_instruction: str,
        spoken: bool,
        mode: str,
        now: datetime | None = None,
    ) -> str:
        def bullets(items: list[str]) -> str:
            return "\n".join(f"- {i}" for i in items)

        parts = [f"You are {self.name}, {self.role}."]
        if self.user_name:
            parts.append(f"The user's name is {self.user_name}. Use it now and then, not in every reply, "
                         "as the name alone (no Mr. or other title).")
        if self.address:
            parts.append(f'Address the user as "{self.address}" now and then (for example "Of course, '
                         f'{self.address}."), not in every sentence.')
        if self.traits:
            parts.append("Your personality:\n" + bullets(self.traits))
        if self.style_rules:
            parts.append("How you talk:\n" + bullets(self.style_rules))
        if self.boundaries:
            parts.append("Always:\n" + bullets(self.boundaries))
        if self.can or self.cannot_yet:
            ability = []
            if self.can:
                ability.append("You can: " + "; ".join(self.can) + ".")
            if self.cannot_yet:
                ability.append("You can't yet: " + "; ".join(self.cannot_yet)
                               + ". If asked, say so simply and offer what you can do instead.")
            parts.append(" ".join(ability))
        empathy = self.modes.get(mode)
        if empathy and empathy.instruction:
            parts.append(f"Emotional style ({empathy.name}): {empathy.instruction}")
        if spoken:
            parts.append(
                "Your replies are spoken aloud by a voice: no markdown, lists, headings, emojis or code. "
                "Never write maths as symbols or LaTeX; say it in words, like 'E equals m c squared'. "
                "For long equations, explain the idea and say you can show the full equations on screen "
                "once the Jarvis window exists. "
                "Usually one to three sentences unless the user asks for more."
            )
        parts.append(language_instruction)
        if self.include_time:
            parts.append(time_context(now or datetime.now()))
        return "\n\n".join(p for p in parts if p)


def time_context(now: datetime) -> str:
    from .greeting import part_of_day

    part = part_of_day(now.hour)
    clock = now.strftime("%I:%M %p").lstrip("0").lower()
    return f"It's {now.strftime('%A')} {part}, {now.day} {now.strftime('%B %Y')}, {clock} local time."
