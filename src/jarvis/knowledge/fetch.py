"""Getting pages from the web: the standard library only, a timeout, and polite spacing per site."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

USER_AGENT = "Jarvis/0.1 (personal study assistant; +https://github.com/Adirc7/Jarvis)"
# Seconds between two requests to the same site. GDELT asks for one request every 5 s.
SPACING = {"api.gdeltproject.org": 5.0}
# How long to wait for a site. GDELT is often slow and has a fallback (news.py), so it gets less.
TIMEOUTS = {"api.gdeltproject.org": 7.0}

Get = Callable[[str], str]


class FetchError(Exception):
    """The page couldn't be fetched (no internet, a block, a timeout, an error page)."""


_last: dict[str, float] = {}
_lock = threading.Lock()


def url_with(base: str, params: dict[str, object] | None = None) -> str:
    if not params:
        return base
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    return f"{base}?{urllib.parse.urlencode(clean)}"


def get_text(url: str, timeout: float | None = None, max_bytes: int = 2_000_000) -> str:
    """The page's text. Waits if the same site was asked too recently."""
    host = urllib.parse.urlsplit(url).hostname or ""
    timeout = timeout or TIMEOUTS.get(host, 10.0)
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise FetchError(f"not a web address: {url[:80]}")
    gap = SPACING.get(host, 0.0)
    with _lock:
        wait = _last.get(host, 0.0) + gap - time.monotonic()
        _last[host] = time.monotonic() + max(0.0, wait)
    if wait > 0:
        time.sleep(wait)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes)
            charset = response.headers.get_content_charset() or "utf-8"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise FetchError(f"{type(exc).__name__}: {exc}"[:200]) from None
    return raw.decode(charset, errors="replace")
