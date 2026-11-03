"""Ollama, the model on this computer: Jarvis starts it when it isn't running.

It is the last model on every route (config/settings.toml), the one with no daily limit and no internet,
so it has to be there when the free cloud models are out. On 3 Nov they all were (both Groq models at their
daily tokens, OpenRouter at its 50 requests, Gemini overloaded) and Ollama wasn't running, so every turn
said "I can't reach any language model".

    ensure("http://localhost:11434/v1", path="", models_dir="", log_dir=Path("logs"))
        -> "running" (it already was), "started", "not_installed", "failed", or "remote" (not this computer)

`ollama serve` runs in the background with no window; its output goes to logs/ollama.log. It is left
running when Jarvis quits, as Ollama's own app leaves it: idle, it holds no graphics memory (a model is
unloaded five minutes after its last answer).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def server_root(base_url: str) -> str | None:
    """'http://localhost:11434/v1' -> 'http://127.0.0.1:11434'; None for a model on another computer."""
    u = urlparse(base_url)
    if u.hostname not in LOCAL_HOSTS:
        return None
    return f"http://127.0.0.1:{u.port or 11434}"


def running(root: str, timeout_s: float = 0.7) -> bool:
    try:
        with urllib.request.urlopen(f"{root}/api/version", timeout=timeout_s) as answer:
            return answer.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def find(path: str = "") -> str | None:
    """ollama.exe: the configured path, else on PATH, else where Ollama's installer puts it by default."""
    if path:
        return path if Path(path).is_file() else None
    found = shutil.which("ollama")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    candidates = [Path(local) / "Programs" / "Ollama" / "ollama.exe"] if local else []
    return next((str(c) for c in candidates if c.is_file()), None)


def start(exe: str, models_dir: str = "", log_dir: Path | None = None) -> subprocess.Popen:
    env = dict(os.environ)
    if models_dir and not env.get("OLLAMA_MODELS"):
        env["OLLAMA_MODELS"] = models_dir
    out = subprocess.DEVNULL
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        out = open(log_dir / "ollama.log", "ab")  # noqa: SIM115 - the server keeps writing to it
    # No window, and not ended with Jarvis's console (DETACHED_PROCESS | CREATE_NO_WINDOW on Windows).
    extra: dict = ({"creationflags": 0x00000008 | 0x08000000} if sys.platform == "win32"
                   else {"start_new_session": True})
    return subprocess.Popen([exe, "serve"], env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=out, **extra)


def ensure(base_url: str, path: str = "", models_dir: str = "", log_dir: Path | None = None,
           wait_s: float = 15.0, *, is_running=running, finder=find, starter=start, sleep=time.sleep) -> str:
    """Start Ollama if it's installed and not running; wait until it answers (at most `wait_s`)."""
    root = server_root(base_url)
    if root is None:
        return "remote"
    if is_running(root):
        return "running"
    exe = finder(path)
    if exe is None:
        return "not_installed"
    try:
        starter(exe, models_dir, log_dir)
    except OSError:
        return "failed"
    waited = 0.0
    while waited < wait_s:
        sleep(0.5)
        waited += 0.5
        if is_running(root):
            return "started"
    return "failed"


__all__ = ["ensure", "find", "running", "server_root", "start"]
