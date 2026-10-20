"""Load settings.toml, languages.toml and .env into plain Python objects.

Settings for one computer (push-to-talk key, audio devices, ...) go in
config/settings.local.toml: same format, only the values you change. It isn't
committed, so `git pull` never overwrites it.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SETTINGS = "settings.local.toml"
LOCAL_HEADER = (
    "# Your settings for this computer. Same format as settings.toml; only write\n"
    "# what you change. This file isn't committed, so updates never overwrite it.\n"
)


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
    fillers: tuple[str, ...] = ()
    greetings: dict[str, tuple[str, ...]] = field(default_factory=dict)   # see greeting.py


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str
    model: str
    options: dict[str, Any] = field(default_factory=dict)   # extra request fields, e.g. reasoning_effort

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
            out.append(ProviderConfig(name, p["base_url"], p.get("api_key_env", ""), p["model"],
                                      dict(p.get("options", {}))))
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
            fillers=tuple(v.get("fillers", [])),
            greetings={k: tuple(lines) for k, lines in v.get("greetings", {}).items()},
        )
    return langs


def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Copy of `base` with `override` on top: tables merge, other values replace."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


def set_local_value(path: Path, table: str, key: str, value: str) -> None:
    """Set `[table] key = "value"` in a local settings file, keeping everything else.

    Only handles a plain top-level table and a string value, which is all the
    setup script needs.
    """
    text = path.read_text(encoding="utf-8") if path.is_file() else LOCAL_HEADER
    line = f"{key} = {json.dumps(value, ensure_ascii=False)}"
    header = re.search(rf"^\[{re.escape(table)}\][ \t]*(#.*)?$", text, re.M)
    if header is None:
        text = text.rstrip("\n") + f"\n\n[{table}]\n{line}\n"
    else:
        start = header.end()
        nxt = re.search(r"^[ \t]*\[", text[start:], re.M)
        end = start + nxt.start() if nxt else len(text)
        body = text[start:end]
        existing = re.compile(rf"^[ \t]*{re.escape(key)}[ \t]*=.*$", re.M)
        if existing.search(body):
            body = existing.sub(lambda _: line, body, count=1)
        else:
            body = "\n" + line + body
        text = text[:start] + body + text[end:]
    tomllib.loads(text)   # never write a file Jarvis can't read back
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_settings(config_dir: Path | None = None, local: bool = True) -> Settings:
    """Read the settings. `local=False` ignores settings.local.toml (tests)."""
    config_dir = config_dir or PROJECT_ROOT / "config"
    load_dotenv(PROJECT_ROOT / ".env")
    with open(config_dir / "settings.toml", "rb") as f:
        raw = tomllib.load(f)
    local_path = config_dir / LOCAL_SETTINGS
    if local and local_path.is_file():
        with open(local_path, "rb") as f:
            raw = merge(raw, tomllib.load(f))
    with open(config_dir / "languages.toml", "rb") as f:
        languages = parse_languages(tomllib.load(f))
    settings = Settings(raw=raw, languages=languages)
    default = settings.get("general.default_language", "en")
    if default not in languages:
        raise ValueError(f"default_language '{default}' is not defined in languages.toml")
    return settings
