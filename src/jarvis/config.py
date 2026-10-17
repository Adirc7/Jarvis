"""Load settings.toml, languages.toml and .env into plain Python objects."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=value lines; existing env vars win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    native_name: str
    whisper_code: str
    stt_model: str
    tts_engine: str
    tts_voice: str
    tts_lang: str = ""
    names: tuple[str, ...] = ()
    command_words: tuple[str, ...] = ()
    switch_phrases: tuple[str, ...] = ()
    confirm: str = ""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str
    model: str

    @property
    def api_key(self) -> str | None:
        if not self.api_key_env:
            return "local"  # Ollama ignores the key but the client needs one
        return os.environ.get(self.api_key_env) or None

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None


@dataclass
class Settings:
    raw: dict[str, Any]
    languages: dict[str, Language] = field(default_factory=dict)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def path(self, dotted: str, default: str) -> Path:
        p = Path(self.get(dotted, default))
        return p if p.is_absolute() else PROJECT_ROOT / p

    def providers(self) -> list[ProviderConfig]:
        table = self.get("llm.providers", {})
        out = []
        for name in self.get("llm.order", []):
            if name not in table:
                raise ValueError(f"llm.order names '{name}' but [llm.providers.{name}] is missing")
            p = table[name]
            out.append(ProviderConfig(name, p["base_url"], p.get("api_key_env", ""), p["model"]))
        return out


def parse_languages(table: dict[str, Any]) -> dict[str, Language]:
    langs = {}
    for code, v in table.items():
        langs[code] = Language(
            code=code,
            name=v["name"],
            native_name=v.get("native_name", v["name"]),
            whisper_code=v.get("whisper_code", code),
            stt_model=v.get("stt_model", "default"),
            tts_engine=v.get("tts_engine", "piper"),
            tts_voice=v.get("tts_voice", ""),
            tts_lang=v.get("tts_lang", ""),
            names=tuple(v.get("names", [v["name"]])),
            command_words=tuple(v.get("command_words", [])),
            switch_phrases=tuple(v.get("switch_phrases", [])),
            confirm=v.get("confirm", ""),
        )
    return langs


def load_settings(config_dir: Path | None = None) -> Settings:
    config_dir = config_dir or PROJECT_ROOT / "config"
    load_dotenv(PROJECT_ROOT / ".env")
    with open(config_dir / "settings.toml", "rb") as f:
        raw = tomllib.load(f)
    with open(config_dir / "languages.toml", "rb") as f:
        languages = parse_languages(tomllib.load(f))
    settings = Settings(raw=raw, languages=languages)
    default = settings.get("general.default_language", "en")
    if default not in languages:
        raise ValueError(f"default_language '{default}' is not defined in languages.toml")
    return settings
