"""MATLAB or Octave: finding it, refusing code that reaches outside, asking first, running, the figures."""

import http.client
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import FakeClient  # noqa: F401 - the fixtures live there
from test_knowledge import TwoStep

from jarvis.agent.llm import FallbackLLM, Provider
from jarvis.app import App
from jarvis.telemetry import Telemetry
from jarvis.tools import matlab as M
from jarvis.tools.matlab import Engine, MatlabTools, blocked, find_engine
from jarvis.ui.server import LiveView

OCTAVE = Engine("octave", Path("/usr/bin/octave-cli"), "Octave 9.2.0")
ODE = ("f = @(t, y) [y(2); -0.5*y(2) - 4*y(1)];\n[t, y] = ode45(f, [0 20], [1; 0]);\n"
       "fprintf('y(20) = %.4f\\n', y(end, 1));\nplot(t, y(:, 1)); title('Damped oscillator');")


def test_code_that_reaches_outside_is_refused():
    assert blocked(ODE) == []
    assert blocked("x = A';\ny = [1 2]';\ndisp('it''s fine'); title('a system of equations') % delete later") == []
    assert blocked("%{\nsystem('format c:')\n%}\nx = 1;") == []                 # a block comment
    assert blocked("x = a'; system('dir')") == ["system"]                        # a transpose isn't a string
    assert blocked("!del *.*") == ["!"]
    assert blocked("r = py.os.listdir('.');") == ["py"]
    assert blocked("h = str2func('system'); h('dir')") == ["str2func"]
    assert set(blocked("fid = fopen('x.txt', 'w'); webread('http://x'); EVAL('1')")) == {"fopen", "webread", "EVAL"}
    assert blocked("delete('*.m')") == ["delete"] and blocked("cd ..") == ["cd"]
    assert blocked("x = input('number? ')") == ["input"]                        # it would wait for ever


def test_matlab_or_octave_is_found_newest_first(tmp_path):
    c = tmp_path / "C"
    for release in ("R2023b", "R2024a"):
        exe = c / "Program Files" / "MATLAB" / release / "bin" / "matlab.exe"
        exe.parent.mkdir(parents=True)
        exe.write_text("")
    for release in ("Octave-10.1.0", "Octave-9.2.0"):
        octave = c / "Program Files" / "GNU Octave" / release / "mingw64" / "bin" / "octave-cli.exe"
        octave.parent.mkdir(parents=True)
        octave.write_text("")
    none = lambda name: None  # noqa: E731
    found = find_engine("auto", platform="win32", which=none, roots=[c])
    assert found.kind == "matlab" and found.name == "MATLAB R2024a" and "R2024a" in str(found.exe)
    assert find_engine("octave", platform="win32", which=none, roots=[c]).name == "Octave 10.1.0"   # not "9" > "1"
    assert find_engine("auto", platform="win32", which=none, roots=[tmp_path / "empty"]) is None
    assert find_engine("auto", platform="linux", which=lambda n: "/usr/bin/octave-cli" if n == "octave-cli" else None,
                       roots=[]).kind == "octave"
    assert find_engine("auto", path=str(octave)).kind == "octave"
    assert find_engine("auto", path=str(tmp_path / "nowhere.exe")) is None
    folder = tmp_path / "it's here"
    assert found.command(folder) == [str(found.exe), "-batch", f"cd('{str(folder).replace(chr(39), chr(39) * 2)}'); jarvis_run"]
    assert OCTAVE.command(folder)[1:5] == ["--no-gui", "--quiet", "--norc", "--eval"]


class FakeRun:
    """Stands in for MATLAB: records the command, prints, and saves figures in the run folder."""

    def __init__(self, out="y(20) = -0.0020\n", err="", figures=1, code=0, hang=False):
        self.out, self.err, self.figures, self.code, self.hang = out, err, figures, code, hang
        self.commands, self.cwd = [], None

    def __call__(self, command, cwd, **kwargs):
        self.commands.append(command)
        self.cwd = Path(cwd)
        for i in range(1, self.figures + 1):
            (self.cwd / f"figure{i}.png").write_bytes(b"\x89PNG fake")
        run = self

        class Proc:
            pid, returncode = 4242, run.code

            def communicate(self, timeout=None):
                if run.hang and timeout is not None:
                    raise subprocess.TimeoutExpired(command, timeout)
                return run.out, run.err

            def kill(self):
                pass
        return Proc()


def tools(tmp_path, run=None, confirm=True, **kwargs):
    asked, boards = [], []

    def click(tool, args, words):
        asked.append(words)
        return confirm
    t = MatlabTools(tmp_path / "Jarvis", OCTAVE, confirm=click, show_board=lambda b: boards.append(b) or True,
                    popen=run or FakeRun(), **kwargs)
    return t, asked, boards


def test_a_run_asks_first_then_shows_code_output_and_figures(tmp_path):
    run = FakeRun(figures=2)
    t, asked, boards = tools(tmp_path, run)
    out = t.call("run_matlab", json.dumps({"title": "Damped oscillator", "code": ODE}))
    assert out.status == "claimed" and asked == [
        "Run 4 lines of Octave 9.2.0 code: Damped oscillator. The code is on the board in Jarvis's window."]
    assert boards[0]["steps"][0]["code"] == ODE                          # shown before the click
    folder = run.cwd
    assert (folder / "jarvis_code.m").read_text() == "1;\n" + ODE and "print(" in (folder / "jarvis_run.m").read_text()
    assert folder.parent == tmp_path / "Jarvis" / "matlab" and M.RUN_NAME.fullmatch(folder.name)
    final = boards[-1]["steps"]
    assert final[1] == {"text": "Output", "code": "y(20) = -0.0020"}
    assert [s.get("image") for s in final[2:]] == [f"/figure/{folder.name}/figure1.png", f"/figure/{folder.name}/figure2.png"]
    text = out.result.data["for_model"]
    assert "y(20) = -0.0020" in text and "2 figure(s)" in text and "you can't see them" in text
    assert t.figure(folder.name, "figure1.png") == folder / "figure1.png"
    assert t.figure("../..", "figure1.png") is None and t.figure(folder.name, "jarvis_code.m") is None


def test_no_click_means_no_run_and_blocked_code_isnt_even_asked(tmp_path):
    run = FakeRun()
    t, asked, boards = tools(tmp_path, run, confirm=False)
    assert t.call("run_matlab", json.dumps({"title": "t", "code": "x = 1"})).status == "cancelled"
    assert run.commands == [] and len(asked) == 1
    out = t.call("run_matlab", json.dumps({"title": "t", "code": "system('del /q *')"}))
    assert out.status == "refused" and len(asked) == 1 and "system" in out.result.data["for_model"]
    assert not t.will_ask(json.dumps({"code": "system('x')"})) and t.will_ask(json.dumps({"code": "x = 1"}))
    no_ask, asked2, _ = tools(tmp_path, FakeRun(), ask_first=False)
    assert no_ask.call("run_matlab", json.dumps({"title": "t", "code": "x = 1"})).status == "claimed" and asked2 == []
    assert t.call("run_matlab", json.dumps({"title": "t", "code": "x" * 6001})).status == "refused"


def test_errors_and_a_run_that_never_ends(tmp_path, monkeypatch):
    t, _, boards = tools(tmp_path, FakeRun(out="", err="JARVIS_ERROR: index (5,_): out of bound 3\n", figures=0))
    out = t.call("run_matlab", json.dumps({"title": "t", "code": "x = [1 2 3]; x(5)"}))
    assert out.status == "failed" and "out of bound" in out.result.data["for_model"]
    assert boards[-1]["steps"][-1] == {"text": "Error", "code": "index (5,_): out of bound 3"}
    killed = []
    monkeypatch.setattr(M, "_kill", killed.append)
    t, _, _ = tools(tmp_path, FakeRun(out="", figures=0, hang=True), timeout_s=3)
    out = t.call("run_matlab", json.dumps({"title": "t", "code": "while true, end"}))
    assert out.status == "failed" and len(killed) == 1 and "stopped after 3 seconds" in out.result.data["for_model"]


@pytest.mark.skipif(shutil.which("octave-cli") is None, reason="GNU Octave isn't installed here")
def test_real_octave_solves_and_plots(tmp_path):
    engine = find_engine("octave")
    t = MatlabTools(tmp_path, engine, confirm=lambda *a: True, show_board=lambda b: True, timeout_s=90)
    out = t.call("run_matlab", json.dumps({"title": "ODE", "code": ODE}))
    assert out.status == "claimed", out.result.data["for_model"]
    assert "y(20) = -0.0020" in out.result.data["for_model"] and out.result.data["figures"] == ["figure1.png"]
    assert (tmp_path / "matlab" / out.result.data["run"] / "figure1.png").read_bytes()[:4] == b"\x89PNG"


async def test_ask_for_matlab_and_jarvis_runs_it_and_explains(settings, tmp_path):
    run = FakeRun()
    said = []
    model = TwoStep("run_matlab", json.dumps({"title": "Damped oscillator", "code": ODE}),
                    ["It settles to almost zero by t equals 20."])
    t = MatlabTools(tmp_path / "Jarvis", OCTAVE, confirm=lambda *a: True, popen=run)
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]),
              out=lambda *a, **k: said.append(" ".join(map(str, a))), matlab=t)
    shown = []
    from types import SimpleNamespace as NS
    app.view = NS(publish=lambda kind, **d: shown.append((kind, d)), viewers=1, url="http://127.0.0.1:1/")
    reply = await app.handle_text("solve y'' + 0.5y' + 4y = 0 in MATLAB and plot it")
    assert reply == "It settles to almost zero by t equals 20."
    assert "run_matlab" in {s["function"]["name"] for s in model.requests[0]["tools"]}
    assert "Jarvis: The code's on the board. Click Run if it looks right." in said
    boards = [d for k, d in shown if k == "board"]
    assert boards[0]["steps"][0]["code"] == ODE and boards[-1]["steps"][-1]["image"].endswith("figure1.png")
    assert "y(20) = -0.0020" in model.requests[1]["messages"][0]["content"]       # the answer is from the output
    assert "matlab" in app._tools_for("and with less damping?", "general")[2]       # a follow-up to the run
    app.recent_info = None
    assert "matlab" not in app._tools_for("what's the weather like", "general")[2]   # only when it's about MATLAB


def test_the_window_serves_jarvis_figures_only(tmp_path):
    t, _, _ = tools(tmp_path, FakeRun())
    out = t.call("run_matlab", json.dumps({"title": "t", "code": "plot(1:3)"}))
    run = out.result.data["run"]
    v = LiveView(port=0, figure=t.figure)
    v.start()
    try:
        def get(path):
            conn = http.client.HTTPConnection("127.0.0.1", v.port, timeout=5)
            conn.request("GET", path, headers={"Host": f"127.0.0.1:{v.port}"})
            r = conn.getresponse()
            body, kind = r.read(), r.getheader("Content-Type")
            conn.close()
            return r.status, kind, body
        assert get(f"/figure/{run}/figure1.png") == (200, "image/png", b"\x89PNG fake")
        assert get(f"/figure/{run}/jarvis_code.m")[0] == 404
        assert get("/figure/..%2F..%2Fsecret/figure1.png")[0] == 404
        assert get(f"/figure/{run}/../figure1.png")[0] == 404
    finally:
        v.stop()
