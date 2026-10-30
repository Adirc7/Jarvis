"""Jarvis's window: the local read-only server and what the app sends it (ui/server.py, app.py)."""

import http.client
import json
import time
from types import SimpleNamespace

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
    # On the laptop, Edge was found and opened for real (30 Oct): the app window is a stand-in here.
    opened = []
    monkeypatch.setattr("jarvis.ui.server.open_page", lambda url, browser="edge": opened.append(url))
    monkeypatch.setattr("jarvis.ui.app_window.open_app_window", lambda url, size=None: opened.append(("app", url)) or True)
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None)
    app._open_map("file:///tmp/news-map.html")                    # no window: the file itself
    app.view = LiveView(port=0)
    app._open_map("file:///tmp/news-map.html")                    # the window isn't open: a window of its own
    app.view = SimpleNamespace(viewers=1, url="http://127.0.0.1:8765/")
    app.view.publish = lambda kind, **data: opened.append((kind, data["url"][:5]))
    app._open_map("file:///tmp/news-map.html")                    # the window is open: inside it
    assert opened == ["file:///tmp/news-map.html", ("app", "http://127.0.0.1:0/map"), ("map", "/map?")]


async def test_a_spoken_turn_reaches_the_window(settings):
    # 30 Oct: in voice mode the window's conversation stayed "Nothing yet".
    from test_voice_pipeline import AUDIO, FakeWhisper, make_voice_app
    app, *_ = make_voice_app(settings, ["Hello, sir."], FakeWhisper(texts={"en": "tell me something nice"}))
    app.view = FakeView()
    assert await app.voice_turn(AUDIO, 1.0) == "Hello, sir."
    assert app.view.events == [("you", {"text": "tell me something nice", "source": "voice"}),
                               ("jarvis", {"text": "Hello, sir.", "speaker": "Jarvis"})]


def test_the_orb_shows_speaking_while_the_voice_plays(settings):
    # 30 Oct: the orb said "thinking" while Jarvis spoke; nothing ever set "speaking".
    from types import SimpleNamespace

    from jarvis.state import Mode
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None)
    app.sink = SimpleNamespace(busy=False)                          # the player: is audio playing?
    for mode, busy, shown in [(Mode.LISTENING, False, "listening"), (Mode.THINKING, False, "thinking"),
                              (Mode.THINKING, True, "speaking"), (Mode.IDLE, True, "speaking"),
                              (Mode.IDLE, False, "idle"), (Mode.LISTENING, True, "listening"),
                              (Mode.PAUSED, True, "paused")]:
        app.state.mode, app.sink.busy = mode, busy
        assert app._snapshot()["mode"] == shown, (mode, busy)


# ---- the window as an app: typing in it, its own window, one Jarvis at a time ----------------
def post(view, body, origin=None, token=None, kind="application/json", host=None):
    conn = http.client.HTTPConnection("127.0.0.1", view.port, timeout=5)
    headers = {"Host": host or f"127.0.0.1:{view.port}", "Content-Type": kind}
    if origin is not False:
        headers["Origin"] = origin or f"http://127.0.0.1:{view.port}"
    if token is not False:
        headers["X-Jarvis-Token"] = token or view.token
    conn.request("POST", "/say", body=body, headers=headers)
    status = conn.getresponse().status
    conn.close()
    return status


def test_a_line_typed_in_the_window_reaches_jarvis_and_only_from_it():
    typed = []
    v = LiveView(port=0, on_text=typed.append)
    v.start()
    try:
        page = get(v, "/")[1].decode()
        assert v.token in page and "__JARVIS_TOKEN__" not in page
        assert post(v, json.dumps({"text": "  what's the weather?  "})) == 202 and typed == ["what's the weather?"]
        # a web page elsewhere: wrong origin, no token, or a plain form
        assert post(v, json.dumps({"text": "delete"}), origin="https://evil.example") == 403
        assert post(v, json.dumps({"text": "delete"}), token=False) == 403
        assert post(v, json.dumps({"text": "delete"}), token="guess") == 403
        assert post(v, "text=delete", kind="application/x-www-form-urlencoded") == 403
        assert post(v, json.dumps({"text": "delete"}), host="evil.example") == 403
        assert post(v, "not json") == 400 and typed == ["what's the weather?"]
        assert get(v, "/favicon.ico")[0] == 200
    finally:
        v.stop()
    assert LiveView(port=0).on_text is None                         # without a handler: read-only


def test_jarvis_opens_as_an_app_window_on_his_own_address():
    from jarvis.ui.app_window import find_browser, open_app_window, window_command
    cmd = window_command("msedge.exe", "http://127.0.0.1:8765/", (1280, 820), profile=None)
    assert cmd[1] == "--app=http://127.0.0.1:8765/" and "--window-size=1280,820" in cmd
    assert any(c.startswith("--user-data-dir=") and c.endswith("window") for c in cmd)
    with pytest.raises(ValueError):
        window_command("msedge.exe", "https://example.com/")
    started = []
    assert open_app_window("http://127.0.0.1:8765/", browser="edge", popen=lambda c, **k: started.append(c))
    assert started[0][:2] == ["edge", "--app=http://127.0.0.1:8765/"]
    assert find_browser("linux", which=lambda n: "/usr/bin/chromium" if n == "chromium" else None) == "/usr/bin/chromium"
    assert find_browser("linux", which=lambda n: None) is None
    env = {"ProgramFiles(x86)": "C:/PF86", "ProgramFiles": "C:/PF"}
    found = find_browser("win32", env=env, exists=lambda p: "Edge" in str(p) and "PF86" in str(p))
    assert found is not None and found.replace("\\", "/").endswith("Microsoft/Edge/Application/msedge.exe")


def test_a_second_start_opens_the_running_jarvis_window(settings, monkeypatch):
    from jarvis.__main__ import open_running_window
    from jarvis.ui.server import running_jarvis
    v = LiveView(lambda: {"mode": "idle"}, port=0)
    v.start()
    opened = []
    monkeypatch.setattr("jarvis.ui.app_window.open_app_window", lambda url, size=None, **k: opened.append(url) or True)
    try:
        settings.raw["window"].update(enabled=True, port=v.port, style="app")
        assert running_jarvis(v.port) and open_running_window(settings) and opened == [v.url]
    finally:
        v.stop()
    assert not running_jarvis(v.port) and not open_running_window(settings)


async def test_typing_quit_in_the_window_or_closing_it_stops_jarvis(settings):
    import asyncio

    from conftest import FakeClient

    from jarvis.agent.llm import FallbackLLM, Provider
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", FakeClient(["Fine, sir."]))]),
              out=lambda *a, **k: None)
    app._input = lambda prompt: time.sleep(30)                      # nobody types in the console
    app._loop = asyncio.get_running_loop()
    app.view = FakeView()
    await app._window_line("how are you")
    assert app.history[-1]["content"] == "Fine, sir." and app.view.events[0] == ("you", {"text": "how are you",
                                                                                         "source": "window"})
    loop_task = asyncio.create_task(app._keyboard_loop(asyncio.get_running_loop()))
    await asyncio.sleep(0.05)
    await app._window_line("/quit")                                 # the console read is still waiting
    await asyncio.wait_for(loop_task, 2)
    # closing the window: it was open, then nobody is watching for the grace period
    app._quit.clear()
    app.view = SimpleNamespace(viewers=1)
    watcher = asyncio.create_task(app._watch_window_closed(grace_s=0.1, poll_s=0.02))
    await asyncio.sleep(0.06)
    app.view.viewers = 0
    await asyncio.wait_for(watcher, 2)
    assert app._quit.is_set()


async def test_console_lines_still_work(settings):
    import asyncio

    from conftest import FakeClient

    from jarvis.agent.llm import FallbackLLM, Provider
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", FakeClient(["Hi."]))]),
              out=lambda *a, **k: None)
    lines = iter(["hello there", "", "/quit"])
    app._input = lambda prompt: next(lines)
    await asyncio.wait_for(app._keyboard_loop(asyncio.get_running_loop()), 3)
    assert app.history[-1]["content"] == "Hi."
