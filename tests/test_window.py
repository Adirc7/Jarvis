"""Jarvis's window: the local read-only server and what the app sends it (ui/server.py, app.py)."""

import http.client
import json
import time

import pytest

from jarvis.app import App
from jarvis.telemetry import Telemetry
from jarvis.ui.server import LiveView


@pytest.fixture
def view(tmp_path):
    state = {"mode": "idle", "speaker": "Jarvis"}
    maps = {"file": None}
    v = LiveView(lambda: dict(state), port=0, map_file=lambda: maps["file"], poll_s=0.05)
    v.start()
    yield v, state, maps, tmp_path
    v.stop()


def get(view, path, host=None, method="GET"):
    conn = http.client.HTTPConnection("127.0.0.1", view.port, timeout=5)
    conn.request(method, path, headers={"Host": host or f"127.0.0.1:{view.port}"})
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, body


def test_the_page_and_the_state(view):
    v, _, _, _ = view
    status, body = get(v, "/")
    assert status == 200 and b"<canvas id=\"orb\"" in body
    v.publish("you", text="open notepad")
    status, body = get(v, "/state")
    data = json.loads(body)
    assert data["state"]["mode"] == "idle" and data["history"][-1]["text"] == "open notepad"


def test_only_this_computer_and_only_reading(view):
    v, _, _, _ = view
    assert get(v, "/", host="evil.example.com")[0] == 403          # a DNS-rebinding page gets nothing
    assert get(v, "/state", host=f"localhost:{v.port}")[0] == 200
    assert get(v, "/", method="POST")[0] == 405
    assert v._server.server_address[0] == "127.0.0.1"


def test_the_news_map_is_served_once_there_is_one(view):
    v, _, maps, tmp = view
    assert get(v, "/map")[0] == 404
    (tmp / "map.html").write_text("<h1>map</h1>")
    maps["file"] = tmp / "map.html"
    assert get(v, "/map") == (200, b"<h1>map</h1>")


def test_live_events_reach_the_page(view):
    v, state, _, _ = view
    conn = http.client.HTTPConnection("127.0.0.1", v.port, timeout=5)
    conn.request("GET", "/events", headers={"Host": f"127.0.0.1:{v.port}"})
    r = conn.getresponse()
    assert r.getheader("Content-Type") == "text/event-stream"
    time.sleep(0.2)
    state["mode"] = "speaking"                                      # the orb follows the mode
    v.publish("jarvis", text="Opening notepad.", speaker="Jarvis")
    seen, deadline = [], time.time() + 5
    def done():
        return any(e["kind"] == "jarvis" for e in seen) and any(
            e.get("state", {}).get("mode") == "speaking" for e in seen)

    while time.time() < deadline and not done():
        line = r.fp.readline().decode().strip()
        if line.startswith("data: "):
            seen.append(json.loads(line[6:]))
    conn.close()
    kinds = {e["kind"] for e in seen}
    assert "jarvis" in kinds and any(e.get("state", {}).get("mode") == "speaking" for e in seen)


class FakeView:
    def __init__(self):
        self.events = []

    def publish(self, kind, **data):
        self.events.append((kind, data))


async def test_the_app_sends_what_was_said(settings, monkeypatch):
    from conftest import FakeClient

    from jarvis.agent.llm import FallbackLLM, Provider
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", FakeClient(["Hello, sir."]))]),
              out=lambda *a, **k: None)
    app.view = FakeView()
    await app.handle_text("hi there")
    assert app.view.events == [("you", {"text": "hi there", "source": "keyboard"}),
                               ("jarvis", {"text": "Hello, sir.", "speaker": "Jarvis"})]
    snap = app._snapshot()
    assert snap["speaker"] == "Jarvis" and snap["mode"] == "idle" and snap["timers"] == [] and snap["news"] == []


def test_jarvis_opens_only_its_own_pages(monkeypatch):
    # The web tools' opener takes only YouTube and Bing, so it refused the window (ValueError on the laptop).
    import webbrowser

    from jarvis.ui.server import open_page
    opened = []
    monkeypatch.setattr(webbrowser, "open", opened.append)
    monkeypatch.setattr("sys.platform", "linux")
    open_page("http://127.0.0.1:8765/")
    open_page("file:///C:/Users/me/Documents/Jarvis/news/news-map.html")
    assert opened == ["http://127.0.0.1:8765/", "file:///C:/Users/me/Documents/Jarvis/news/news-map.html"]
    for other in ("https://example.com/", "https://www.youtube.com/", "http://192.168.1.5:8765/", "javascript:alert(1)"):
        with pytest.raises(ValueError):
            open_page(other)


def test_the_news_map_opens_from_the_window_when_it_runs(settings, monkeypatch):
    opened = []
    monkeypatch.setattr("jarvis.ui.server.open_page", lambda url, browser="edge": opened.append(url))
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None)
    app._open_map("file:///tmp/news-map.html")                    # no window: the file itself
    app.view = LiveView(port=0)
    app._open_map("file:///tmp/news-map.html")                    # the window's /map is the newest map
    assert opened == ["file:///tmp/news-map.html", app.view.url + "map"]
