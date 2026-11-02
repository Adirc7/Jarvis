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
    for release, build in (("Octave-10.1.0", "ucrt64"), ("Octave-9.2.0", "mingw64")):
        octave = c / "Program Files" / "GNU Octave" / release / build / "bin" / "octave-cli.exe"
        octave.parent.mkdir(parents=True)
        octave.write_text("")
    none = lambda name: None  # noqa: E731
    found = find_engine("auto", platform="win32", which=none, roots=[c])
    assert found.kind == "matlab" and found.name == "MATLAB R2024a" and "R2024a" in str(found.exe)
    assert find_engine("octave", platform="win32", which=none, roots=[c]).name == "Octave 10.1.0"   # not "9" > "1"
    unzipped = (tmp_path / "D" / "Program Files" / "GNU Octave" / "octave-11.1.0-w64" / "octave-11.1.0-w64" / "mingw64"
                / "bin" / "octave-cli.exe")
    unzipped.parent.mkdir(parents=True)
    unzipped.write_text("")
    assert find_engine("octave", platform="win32", which=none, roots=[c, tmp_path / "D"]).name == "Octave 11.1.0"
    assert find_engine("auto", platform="win32", which=none, roots=[tmp_path / "empty"]) is None
    assert find_engine("auto", platform="linux", which=lambda n: "/usr/bin/octave-cli" if n == "octave-cli" else None,
                       roots=[]).kind == "octave"
    assert find_engine("auto", path=str(octave)).kind == "octave"
    assert find_engine("auto", path=str(tmp_path / "nowhere.exe"), platform="win32", which=none,
                       roots=[tmp_path / "empty"]) is None
    # a wrong path falls back to the usual places; Octave unzipped into any folder on a drive is found
    gnu = tmp_path / "E" / "GNU" / "octave-11.3.0-w64" / "mingw64" / "bin" / "octave-cli.exe"
    gnu.parent.mkdir(parents=True)
    gnu.write_text("")
    found_gnu = find_engine("octave", path="D:/moved/octave-cli.exe", platform="win32", which=none,
                            roots=[tmp_path / "E"])
    assert found_gnu.name == "Octave 11.3.0" and found_gnu.exe == gnu
    folder = tmp_path / "it's here"
    assert found.command(folder) == [str(found.exe), "-batch", f"cd('{str(folder).replace(chr(39), chr(39) * 2)}'); jarvis_run"]
    assert OCTAVE.command(folder)[1:5] == ["--no-gui", "--quiet", "--norc", "--eval"]
    # like octave.bat: Octave's bin folder (gnuplot, Ghostscript) and the MSYS tools first on PATH
    root = tmp_path / "GNU" / "octave-11.3.0-w64"
    exe = root / "mingw64" / "bin" / "octave-cli.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    (exe.parent / "gs.exe").write_text("")
    (root / "usr" / "bin").mkdir(parents=True)
    unzipped = find_engine("octave", path=str(exe))
    assert unzipped.name == "Octave 11.3.0"
    env = unzipped.environment({"PATH": "/windows"})
    assert env["PATH"].split(M.os.pathsep) == [str(exe.parent), str(root / "usr" / "bin"), "/windows"]
    assert env["GS"] == "gs.exe" and found.environment({"PATH": "x"}) == {"PATH": "x"}


class FakeRun:
    """Stands in for MATLAB: records the command, prints, and saves figures in the run folder."""

    def __init__(self, out="y(20) = -0.0020\n", err="", figures=1, code=0, hang=False):
        self.out, self.err, self.figures, self.code, self.hang = out, err, figures, code, hang
        self.commands, self.cwd = [], None

    def __call__(self, command, cwd, **kwargs):
        self.commands.append(command)
        self.env = kwargs.get("env")
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
    app.history += [{"role": "user", "content": "thanks"}, {"role": "assistant", "content": "You're welcome."}]
    app._matlab_at -= 11 * 60                                                     # some minutes later
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


def test_asked_for_matlab_by_name_only_run_matlab_is_offered(settings, tmp_path):
    from test_knowledge import make_info
    info, _ = make_info(tmp_path)
    t = MatlabTools(tmp_path / "Jarvis", OCTAVE, confirm=lambda *a: True, popen=FakeRun())
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None, info=info, matlab=t)
    from types import SimpleNamespace as NS
    app.view = NS(publish=lambda *a, **k: None, viewers=1, url="http://127.0.0.1:1/")
    _, specs, groups = app._tools_for("Jarvis, solve y double dash plus half y dash plus 4y equals 0 in Matlab "
                                      "and plot it", "code")
    names = {s["function"]["name"] for s in specs}
    assert "run_matlab" in names and not names & {"show_on_board", "check_maths", "show_lesson"}
    assert "matlab" in groups and "maths" not in groups
    _, specs, _ = app._tools_for("solve this ODE numerically and plot it", "maths")      # not by name: both
    assert {"run_matlab", "show_on_board"} <= {s["function"]["name"] for s in specs}


async def test_a_refused_board_still_gets_an_answer_in_words(settings, tmp_path):
    from test_knowledge import make_info
    info, _ = make_info(tmp_path)
    model = TwoStep("show_on_board", json.dumps({"title": "x", "steps": [{"text": 5}]}),
                    ["The roots are minus a quarter plus or minus about 1.98 i."])
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]),
              out=lambda *a, **k: None, info=info)
    reply = await app.handle_text("solve y'' + 0.5y' + 4y = 0 on the board")
    assert reply == "The roots are minus a quarter plus or minus about 1.98 i."
    assert "couldn't use the arguments" in model.requests[1]["messages"][0]["content"]


async def test_asked_to_do_it_in_matlab_the_model_must_run_it(settings, tmp_path):
    """1 Nov: "One moment, sir.", then "Done, I've plotted it" with nothing run, then the code read aloud."""
    model = TwoStep("run_matlab", json.dumps({"title": "ODE", "code": ODE}), ["It decays to zero."])
    t = MatlabTools(tmp_path / "Jarvis", OCTAVE, confirm=lambda *a: True, popen=FakeRun())
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]),
              out=lambda *a, **k: None, matlab=t)
    from types import SimpleNamespace as NS
    app.view = NS(publish=lambda *a, **k: None, viewers=1, url="http://127.0.0.1:1/")
    await app.handle_text("solve y double dash plus half y dash plus 4y equals 0 in MATLAB and plot it")
    forced = {"type": "function", "function": {"name": "run_matlab"}}
    assert model.requests[0]["tool_choice"] == forced
    assert "Never say you ran or plotted" in model.requests[0]["messages"][0]["content"]
    assert app._wants_matlab_run("can you show the code and run it and show?")       # right after: still MATLAB
    assert not app._wants_matlab_run("what is MATLAB used for?")                       # a question, not a job
    assert not app._wants_matlab_run("can you show me the map?")                       # not a MATLAB job
    assert app._wants_matlab_run("and can you run it by yourself?")                    # 1 Nov, 13:42
    app.history.append({"role": "user", "content": "thanks, what's the weather?"})
    app._matlab_at -= 11 * 60
    assert not app._wants_matlab_run("run it again")                                   # long moved on
    assert not app._wants_matlab_run("why does it oscillate?")


def test_errors_are_read_whole_and_broken_strings_are_joined(tmp_path):
    run = tmp_path / "run-20261101-134223"
    err = ("warning: using the gnuplot graphics toolkit is discouraged\nJARVIS_ERROR: parse error near line 4, column 26 "
           f"in file {run}/jarvis_code.m\n\n  syntax error\n\n>>> ', x);\n         ^\n")
    assert M._errors(err, run, shifted=True) == [
        "parse error near line 3, column 26\n  syntax error\n>>> ', x);\n         ^"]
    # 1 Nov: the model wrote a real newline where it meant \n inside fprintf's quotes
    assert M.join_split_strings("x = 2;\nfprintf('x is %d\n', x);\ndisp('done')") == \
        "x = 2;\nfprintf('x is %d\\n', x);\ndisp('done')"
    fine = ("title('y'''' + 0.5y'' = 0');\nz = A';\n% it's a comment\ny = [a' b'];\n"
            's = "say ""hi""";')
    assert M.join_split_strings(fine) == fine


async def test_an_error_gets_one_repair_and_another_click(settings, tmp_path):
    from types import SimpleNamespace as NS

    from test_lessons import Chunks

    class Runs(FakeRun):
        def __call__(self, command, cwd, **kwargs):
            first = not self.commands
            self.out = "" if first else "y(20) = -0.0020\n"
            self.err = "JARVIS_ERROR: 'helix' undefined\n" if first else ""
            self.figures = 0
            return super().__call__(command, cwd, **kwargs)

    clicks = []
    t = MatlabTools(tmp_path / "Jarvis", OCTAVE, popen=Runs(),
                    confirm=lambda tool, args, words: clicks.append(args["code"]) or True)

    class Model:
        def __init__(self):
            self.requests = []
            self.chat = NS(completions=NS(create=self.create))

        async def create(self, model, messages, stream=False, **kwargs):
            self.requests.append({"messages": messages, **kwargs})
            n = len(self.requests)
            if n in (1, 2):                                   # the run, then the repair: both call run_matlab
                code = "helix()" if n == 1 else ODE
                chunks = [NS(choices=[NS(delta=NS(content=None, tool_calls=[NS(index=0, function=NS(
                    name="run_matlab", arguments=json.dumps({"title": "ODE", "code": code})))]))])]
            else:
                chunks = [NS(choices=[NS(delta=NS(content="It decays to zero.", tool_calls=None))])]
            return Chunks(chunks)

    model = Model()
    said = []
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]),
              out=lambda *a, **k: said.append(" ".join(map(str, a))), matlab=t)
    app.view = NS(publish=lambda *a, **k: None, viewers=1, url="http://127.0.0.1:1/")
    reply = await app.handle_text("solve y'' + 0.5y' + 4y = 0 in MATLAB and plot it")
    assert reply == "It decays to zero." and clicks == ["helix()", ODE]
    assert "'helix' undefined" in model.requests[1]["messages"][1]["content"]
    assert model.requests[1]["tool_choice"]["function"]["name"] == "run_matlab"
    assert "Jarvis: That had an error, so I've fixed the code on the board. Click Run again." in said


def test_an_svg_figure_is_shown_but_can_never_run_anything(tmp_path):
    t, _, _ = tools(tmp_path, FakeRun(figures=0))
    out = t.call("run_matlab", json.dumps({"title": "t", "code": "plot(1:3)"}))
    run = out.result.data["run"]
    (tmp_path / "Jarvis" / "matlab" / run / "figure1.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    assert t.figure(run, "figure1.svg") is not None and t.figure(run, "figure1.svgz") is None
    v = LiveView(port=0, figure=t.figure)
    v.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", v.port, timeout=5)
        conn.request("GET", f"/figure/{run}/figure1.svg", headers={"Host": f"127.0.0.1:{v.port}"})
        r = conn.getresponse()
        r.read()
        assert r.status == 200 and r.getheader("Content-Type") == "image/svg+xml"
        assert "default-src 'none'" in r.getheader("Content-Security-Policy")       # no scripts, even opened alone
        conn.close()
    finally:
        v.stop()
    # 2 Nov, Windows: Qt was chosen and couldn't draw without a window; gnuplot now comes first, then PNG, then SVG
    assert "if any(strcmp(jarvis_tk, 'gnuplot'))\n    graphics_toolkit('gnuplot');" in M.WRAPPER
    assert "{'svg', '-dsvg', ''}" in M.WRAPPER


async def test_jarvis_explains_the_plot_from_its_measured_data_not_the_code(settings, tmp_path):
    """2 Nov, Adhi: explain the background, what's special and the plot itself; don't read the code or values."""
    measured = ("y(10) = 0.0533\nJARVIS_DATA: figure 1: title \"Damped oscillator\", x axis \"t (s)\", y axis \"y\"\n"
                "JARVIS_DATA:   curve 1 (400 points): x from 0 to 10; y starts at 1 and ends at 0.05329\n"
                "JARVIS_DATA:     3 peaks; the first (x, y): (3.16, 0.453) (6.34, 0.205) (9.5, 0.0929)\n")
    boards = []
    t = MatlabTools(tmp_path / "Jarvis", OCTAVE, confirm=lambda *a: True, popen=FakeRun(out=measured),
                    show_board=lambda b: boards.append(b) or True)
    model = TwoStep("run_matlab", json.dumps({"title": "ODE", "code": ODE}), ["It's a damped spring..."])
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([Provider("groq", "m", model)]),
              out=lambda *a, **k: None, matlab=t)
    from types import SimpleNamespace as NS
    app.view = NS(publish=lambda *a, **k: None, viewers=1, url="http://127.0.0.1:1/")
    await app.handle_text("solve y'' + 0.5y' + 4y = 0 in MATLAB and plot it")
    answer = model.requests[1]["messages"][0]["content"]
    assert "3 peaks; the first (x, y): (3.16, 0.453)" in answer                      # the plot, measured
    assert "never read the code" in answer and "what is special about this case" in answer
    assert boards[-1]["steps"][1] == {"text": "Output", "code": "y(10) = 0.0533"}     # measurements stay off the board
    assert app.llm.last_route == "teach"                                              # explained by a teaching model
    assert "for jarvis_k = 1:min(numel(jarvis_figs), 8)\n  jarvis_axes = findall" in M.WRAPPER


def test_without_a_saved_picture_jarvis_draws_the_figure_from_its_data(tmp_path):
    """2 Nov: on the laptop no run left an image (Octave couldn't print without a window), so nothing showed."""
    figures = [{"figure": 1, "title": "Damped oscillator", "xlabel": "t", "ylabel": "y",
                "curves": [{"x": [0, 1, 2], "y": [1, None, -0.5], "name": "y", "color": [0, 0, 1]},
                           {"x": [0, 1], "y": [0, 0.3], "name": "", "color": [1, 0, 0]}], "surfaces": []},
               {"figure": 2, "title": "Gaussian", "xlabel": "", "ylabel": "", "curves": [],
                "surfaces": {"z": [[0, 0.5], [0.5, 1]], "x": [-2, 2], "y": [-2, 2]}},
               {"figure": 3, "title": "<script>alert(1)</script>", "curves": "not a list", "surfaces": []}]

    class SavesData(FakeRun):
        def __call__(self, command, cwd, **kwargs):
            proc = super().__call__(command, cwd, **kwargs)
            (Path(cwd) / "jarvis_figures.json").write_text(json.dumps(figures))
            return proc

    run = SavesData(figures=0, err="JARVIS_ERROR: couldn't save figure 1: -dpng: no toolkit;\n")
    t, _, boards = tools(tmp_path, run)
    out = t.call("run_matlab", json.dumps({"title": "ODE", "code": ODE}))
    steps = boards[-1]["steps"]
    plot = steps[-2]["plot"]
    assert steps[-2]["text"] == "Figure 1: Damped oscillator" and plot["xlabel"] == "t"
    assert plot["curves"][0] == {"label": "y", "points": [[0.0, 1.0], [1.0, None], [2.0, -0.5]], "line": True,
                                 "markers": False, "three_d": False}
    assert plot["curves"][1]["label"] == "curve 2"
    assert steps[-1]["surface"] == {"z": [[0.0, 0.5], [0.5, 1.0]], "x": [-2.0, 2.0], "y": [-2.0, 2.0]}
    assert len(steps) == 4                                       # code, output, two figures; the bad one left out
    assert out.status == "claimed" and out.result.data["errors"] == []      # drawn instead: not an error
    assert out.result.data["figure_problems"] == ["couldn't save figure 1: -dpng: no toolkit;"]
    assert "2 figure(s) shown on the board" in out.result.data["for_model"]
    assert "--- printed" in (run.cwd / "jarvis_log.txt").read_text()     # the run's own record, for checking later
    assert "jsonencode(jarvis_out)" in M.WRAPPER


def test_descriptions_and_symbolic_maths_are_sent_back_without_a_click(tmp_path):
    t, asked, _ = tools(tmp_path, FakeRun())
    for code in ("Second order ODE: y'' + (1/2) y' + 4 y = 0, zero IC",               # 2 Nov, as sent
                 "solve the damped ODE y'' + 0.5 y' + 4 y = 0, y(0)=1, y'(0)=0",
                 "syms t y(t)\nsol = dsolve(diff(y, t, 2) + 4*y == 0);"):
        out = t.call("run_matlab", json.dumps({"title": "t", "code": code}))
        assert out.status == "failed" and out.result.data["errors"] and not t.will_ask(json.dumps({"code": code}))
    assert asked == []
    fine = "hold on\ngrid on\naxis equal tight\nfor k = 1:3\n  disp(k)\nend\nfunction y = f(x)\n  y = x;\nend"
    assert t.not_runnable(fine) == ""


def test_every_kind_of_figure_is_read_and_measured(tmp_path):
    """Vector analysis and numerical methods use more than plot(): quiver, contour, imagesc, bar, scatter,
    plot3, semilogy, subplots. All of them are drawn when no picture could be saved."""
    figures = [
        {"figure": 1, "title": "field", "xlabel": "x", "ylabel": "y", "xscale": "linear", "yscale": "linear",
         "curves": [], "arrows": {"x": [0, 1], "y": [0, 0], "u": [0, 1], "v": [1, 0]}, "bars": [], "grids": [],
         "surfaces": []},
        {"figure": 2, "title": "saddle", "curves": [], "arrows": [], "bars": [],
         "grids": {"z": [[0, 1], [2, 3]], "x": [-2, 2], "y": [-1, 1], "kind": "contour"}, "surfaces": []},
        {"figure": 3, "title": "bars", "curves": {"x": [0, 6], "y": [0, 0], "name": "", "line": True, "markers": False},
         "bars": {"x": [1, 2], "y": [3, 5], "name": ""}, "arrows": [], "grids": [], "surfaces": []},
        {"figure": 4, "title": "helix", "curves": {"x": [1, 0, -1], "y": [0, 1, 0], "z": [0, 0.5, 1], "name": "",
                                                   "line": True, "markers": False}},
        {"figure": 5, "title": "growth", "yscale": "log",
         "curves": [{"x": [1, 2], "y": [10, 100], "name": "", "line": True, "markers": False},
                    {"x": [1, 2], "y": [5, 50], "name": "data", "line": False, "markers": True}]},
    ]
    run = tmp_path / "run-20261102-070000"
    run.mkdir()
    (run / "jarvis_figures.json").write_text(json.dumps(figures))
    got = {a["figure"]: a for a in M._figure_data(run)}
    assert got[1]["plot"]["arrows"] == [[0.0, 0.0, 0.0, 1.0], [1.0, 0.0, 1.0, 0.0]]
    assert got[2]["grid"]["kind"] == "contour" and got[2]["grid"]["z"] == [[0.0, 1.0], [2.0, 3.0]]
    assert got[3]["plot"]["bars"][0]["points"] == [[1.0, 3.0], [2.0, 5.0]] and got[3]["plot"]["curves"] == []
    assert got[4]["curve3d"]["curves"][0]["points"][2] == [-1.0, 0.0, 1.0] and got[4]["plot"] is None
    assert got[5]["plot"]["yscale"] is True and got[5]["plot"]["curves"][1]["markers"] is True
    said = "\n".join(M._measure_more(list(got.values())))
    assert "a vector field of 2 arrows; longest 1" in said and "a contour map over x -2 to 2" in said
    assert "values from 0 to 3" in said and "bars (2) 1: 3, 2: 5" in said and "a 3D curve of 3 points" in said
    for kind in ("UData", "SizeData", "BarWidth", "LevelList", "'image'", "BinEdges", "'zdata'"):
        assert kind in M.WRAPPER, kind

