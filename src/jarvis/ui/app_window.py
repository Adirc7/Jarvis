"""Jarvis's window as an app: its own window, no tabs or address bar, its own icon in the taskbar.

    open_app_window("http://127.0.0.1:8765/")      # True if it opened

Edge (on every Windows 10 and 11 PC) or Chrome runs the page in "app" mode,
with a profile of its own in Jarvis's local folder, so it's a separate window
that remembers its size, and closing it closes only Jarvis's window. Only
this computer's own address is accepted. If neither browser is found, the
caller falls back to the default browser.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

APP_PATHS = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"


def _registry_path(exe: str) -> str | None:
    import winreg
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, rf"{APP_PATHS}\{exe}") as key:
                value = winreg.QueryValue(key, None)
        except OSError:
            continue
        if value and Path(value.strip('"')).exists():
            return value.strip('"')
    return None


def find_browser(platform: str = sys.platform, env: dict | None = None,
                 which: Callable[[str], str | None] = shutil.which,
                 exists: Callable[[Path], bool] = Path.exists) -> str | None:
    """Edge first (it's on every Windows PC), then Chrome, then Chromium elsewhere."""
    env = os.environ if env is None else env
    if platform == "win32":
        for exe in ("msedge.exe", "chrome.exe"):
            try:
                found = _registry_path(exe)
            except ImportError:
                found = None
            if found:
                return found
        for base, rest in (("ProgramFiles(x86)", r"Microsoft\Edge\Application\msedge.exe"),
                           ("ProgramFiles", r"Microsoft\Edge\Application\msedge.exe"),
                           ("ProgramFiles", r"Google\Chrome\Application\chrome.exe"),
                           ("ProgramFiles(x86)", r"Google\Chrome\Application\chrome.exe"),
                           ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe")):
            if env.get(base) and exists(Path(env[base]) / rest):
                return str(Path(env[base]) / rest)
        return None
    for name in ("microsoft-edge", "microsoft-edge-stable", "google-chrome", "chromium", "chromium-browser"):
        if which(name):
            return which(name)
    mac = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
    return str(mac) if platform == "darwin" and exists(mac) else None


def profile_folder(env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    base = Path(env["LOCALAPPDATA"]) if env.get("LOCALAPPDATA") else Path.home() / ".local" / "share"
    return base / "Jarvis" / "window"


def window_command(browser: str, url: str, size: tuple[int, int] = (1280, 820),
                   profile: Path | None = None) -> list[str]:
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError(f"not Jarvis's own address: {url[:80]}")
    return [browser, f"--app={url}", f"--window-size={size[0]},{size[1]}",
            f"--user-data-dir={profile or profile_folder()}", "--no-first-run", "--no-default-browser-check"]


def open_app_window(url: str, size: tuple[int, int] = (1280, 820), *, browser: str | None = None,
                    popen: Callable[..., object] = subprocess.Popen) -> bool:
    browser = browser or find_browser()
    if not browser:
        return False
    command = window_command(browser, url, size)
    flags = 0
    if sys.platform == "win32":                      # not tied to Jarvis's console
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
          close_fds=True, creationflags=flags)
    return True
