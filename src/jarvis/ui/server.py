"""The window's server: a small web server on 127.0.0.1, pushing live events to the page.

    view = LiveView(snapshot=app_snapshot, on_text=typed)   # snapshot() -> dict: mode, language, timers...
    view.start()                                # http://127.0.0.1:8765
    view.publish("you", text="open notepad")    # the page shows it at once (Server-Sent Events)

Only this computer can reach it (127.0.0.1), and it checks the Host header so
a web page elsewhere can't read it through a DNS trick. The page shows what
you said and what Jarvis answered, so it stays on the laptop. The latest map
(news or weather) is served at /map.

Two things can be sent to it: a line typed in the window (POST /say), which
Jarvis handles like a line typed in his console, and which panel the page
shows (POST /ui: the map, the board, or none). A web page elsewhere can't
send one: the request must come from the window's own address (Origin), carry
the window's secret (a random token in the page, which other sites can't
read), and be JSON (so a plain form can't fake it).
"""

from __future__ import annotations

import hmac
import json
import os
import queue
import secrets
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PAGE = Path(__file__).with_name("index.html")
ICON = Path(__file__).with_name("jarvis.ico")


def open_page(url: str, browser: str = "edge") -> None:
    """Open one of Jarvis's own pages: the window (http://127.0.0.1:port/...) or a file Jarvis wrote (file://).

    Not the web tools' opener, which only takes YouTube and Bing (tools/web.py):
    anything else here is refused too, so a model can't open a site through it.
    """
    parts = urlsplit(url)
    local = parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost")
    if not (local or parts.scheme == "file"):
        raise ValueError(f"not one of Jarvis's own pages: {url[:80]}")
    if local and browser == "edge" and sys.platform == "win32":
        os.startfile(f"microsoft-edge:{url}")       # a fixed scheme and this computer's own address
        return
    import webbrowser
    webbrowser.open(url)


def running_jarvis(port: int = 8765, timeout_s: float = 1.0) -> bool:
    """True if a Jarvis is already running on this computer (its window server answers)."""
    import http.client
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout_s)
        conn.request("GET", "/state", headers={"Host": f"127.0.0.1:{port}"})
        reply = conn.getresponse()
        ok = reply.status == 200 and "state" in json.loads(reply.read(200_000) or b"{}")
        conn.close()
        return ok
    except (OSError, ValueError):
        return False


class LiveView:
    def __init__(self, snapshot: Callable[[], dict[str, Any]] = dict, port: int = 8765,
                 map_file: Callable[[], Path | None] = lambda: None, poll_s: float = 0.25,
                 on_text: Callable[[str], None] | None = None, on_ui: Callable[[dict], None] | None = None,
                 board: Callable[[], dict | None] = lambda: None):
        self.snapshot, self.port, self.map_file, self.poll_s = snapshot, port, map_file, poll_s
        self.on_text, self.on_ui, self.board = on_text, on_ui, board
        self.token = secrets.token_urlsafe(24)           # in the page; proves a POST came from it
        self.history: deque[dict] = deque(maxlen=60)     # a page opened later still sees recent turns
        self._clients: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._stop = threading.Event()

    # ---- events --------------------------------------------------------------------------
    def publish(self, kind: str, **data: Any) -> None:
        event = {"kind": kind, "t": time.time(), **data}
        with self._lock:
            if kind in ("you", "jarvis", "action"):
                self.history.append(event)
            for q in self._clients:
                q.put(event)

    def _watch(self) -> None:
        """Send the snapshot whenever it changes (the orb follows the mode this way)."""
        last = None
        while not self._stop.wait(self.poll_s):
            try:
                snap = self.snapshot()
            except Exception:  # noqa: BLE001, S112 - a snapshot error must not stop the window
                continue
            text = json.dumps(snap, sort_keys=True, default=str)
            if text != last:
                last = text
                self.publish("state", state=json.loads(text))

    # ---- server -----------------------------------------------------------------------------
    @property
    def viewers(self) -> int:
        """How many pages are open on the window right now."""
        with self._lock:
            return len(self._clients)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self) -> str:
        view = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:       # quiet: Jarvis has its own logs
                pass

            def _host_ok(self) -> bool:
                host = (self.headers.get("Host") or "").lower()
                return host in (f"127.0.0.1:{view.port}", f"localhost:{view.port}")

            def _send(self, code: int, body: bytes, kind: str) -> None:
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "frame-ancestors 'self'")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if not self._host_ok():
                    self._send(403, b"forbidden", "text/plain")
                    return
                path = self.path.split("?", 1)[0]
                if path == "/":
                    page = PAGE.read_text(encoding="utf-8").replace("__JARVIS_TOKEN__", view.token)
                    self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
                elif path == "/favicon.ico" and ICON.exists():
                    self._send(200, ICON.read_bytes(), "image/x-icon")
                elif path == "/state":
                    body = {"state": view.snapshot(), "history": list(view.history)}
                    self._send(200, json.dumps(body, default=str).encode(), "application/json")
                elif path == "/map":
                    found = view.map_file()
                    if found and found.exists():
                        self._send(200, found.read_bytes(), "text/html; charset=utf-8")
                    else:
                        self._send(404, b"No map yet: ask Jarvis for the news map or the weather map.",
                                   "text/plain")
                elif path == "/board":
                    self._send(200, json.dumps(view.board() or {}, default=str).encode(), "application/json")
                elif path == "/events":
                    self._events()
                else:
                    self._send(404, b"not found", "text/plain")

            def _events(self) -> None:
                q: queue.Queue = queue.Queue()
                with view._lock:
                    view._clients.append(q)
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(b": hello\n\n")
                    self.wfile.flush()
                    while not view._stop.is_set():
                        try:
                            event = q.get(timeout=10)
                            self.wfile.write(f"data: {json.dumps(event, default=str)}\n\n".encode())
                        except queue.Empty:
                            self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    with view._lock:
                        if q in view._clients:
                            view._clients.remove(q)

            def do_POST(self) -> None:
                path = self.path.split("?", 1)[0]
                handler = {"/say": view.on_text, "/ui": view.on_ui}.get(path)
                if handler is None:
                    self._send(405, b"read only", "text/plain")
                    return
                origin = self.headers.get("Origin") or ""
                token = self.headers.get("X-Jarvis-Token") or ""
                kind = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if (not self._host_ok() or origin not in (f"http://127.0.0.1:{view.port}", f"http://localhost:{view.port}")
                        or not hmac.compare_digest(token, view.token) or kind != "application/json"):
                    self._send(403, b"forbidden", "text/plain")
                    return
                try:
                    size = int(self.headers.get("Content-Length") or 0)
                    body = json.loads(self.rfile.read(min(size, 8000)) if 0 < size <= 8000 else b"")
                    if path == "/ui":
                        event = {"panel": str(body["panel"])[:10]}      # which panel the page shows
                    else:
                        text = str(body["text"]).strip()[:2000]
                except (ValueError, KeyError, TypeError):
                    self._send(400, b"send JSON", "text/plain")
                    return
                if path == "/ui":
                    handler(event)
                elif text:
                    handler(text)
                self._send(202, b"ok", "text/plain")

            def do_PUT(self) -> None:
                self._send(405, b"read only", "text/plain")

            do_DELETE = do_PATCH = do_PUT

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]          # the real port, when 0 was asked for
        threading.Thread(target=self._server.serve_forever, name="window", daemon=True).start()
        threading.Thread(target=self._watch, name="window-watch", daemon=True).start()
        return self.url

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
