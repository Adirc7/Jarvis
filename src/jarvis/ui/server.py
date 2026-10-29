"""The window's server: a small read-only web server on 127.0.0.1, pushing live events to the page.

    view = LiveView(snapshot=app_snapshot)      # snapshot() -> dict: mode, language, timers, news...
    view.start()                                # http://127.0.0.1:8765
    view.publish("you", text="open notepad")    # the page shows it at once (Server-Sent Events)

Only this computer can reach it (127.0.0.1), it only answers GET, and it
checks the Host header so a web page elsewhere can't read it through a DNS
trick. The page shows what you said and what Jarvis answered, so it stays on
the laptop. The latest news map is served at /map.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections import deque
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PAGE = Path(__file__).with_name("index.html")


class LiveView:
    def __init__(self, snapshot: Callable[[], dict[str, Any]] = dict, port: int = 8765,
                 map_file: Callable[[], Path | None] = lambda: None, poll_s: float = 0.25):
        self.snapshot, self.port, self.map_file, self.poll_s = snapshot, port, map_file, poll_s
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
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if not self._host_ok():
                    self._send(403, b"forbidden", "text/plain")
                    return
                path = self.path.split("?", 1)[0]
                if path == "/":
                    self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
                elif path == "/state":
                    body = {"state": view.snapshot(), "history": list(view.history)}
                    self._send(200, json.dumps(body, default=str).encode(), "application/json")
                elif path == "/map":
                    found = view.map_file()
                    if found and found.exists():
                        self._send(200, found.read_bytes(), "text/html; charset=utf-8")
                    else:
                        self._send(404, b"No news map yet: ask Jarvis to show the news map.", "text/plain")
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
                self._send(405, b"read only", "text/plain")

            do_PUT = do_DELETE = do_PATCH = do_POST

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
