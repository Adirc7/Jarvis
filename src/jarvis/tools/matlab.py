"""MATLAB (or GNU Octave) on this laptop: Jarvis writes the code, you approve it, it runs, the figures show.

    "solve y'' + 0.5y' + 4y = 0 numerically in MATLAB and plot it"
    -> the model calls run_matlab {title, code}
    -> the code goes on the board in Jarvis's window, and a box asks you to approve it
    -> MATLAB runs it in Jarvis's folder (Documents/Jarvis/matlab/run-...), without a window
    -> its printed output and figures (PNG) go on the board; the model explains them

Which program ([matlab] engine): "auto" uses MATLAB when it's installed and else
GNU Octave (free, runs most MATLAB code); "matlab" or "octave" picks one; [matlab]
path names the program file when it isn't in the usual place.

Safety, in layers: you approve every run (the gate's "ask first" tier; [matlab]
confirm = false makes it "do and log"); code that could reach outside the run
folder is refused before you're asked (system commands, files, the internet, Java,
Python, .NET, eval: see BLOCKED); it runs in its own folder with a time limit,
and is stopped (with everything it started) when the limit passes. The filter is a
second line, not a sandbox: the click is the real check, so read the code on the board.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .gate import ActionLog, Confirm, Gate, Outcome
from .registry import Args, Registry, Result, Tier, Tool

MAX_FIGURES = 4
OUTPUT_CHARS = 4000
RUN_NAME = re.compile(r"run-\d{8}-\d{6}(?:-\d{1,3})?")
FIGURE_NAME = re.compile(r"figure[1-4]\.png")
# Functions that reach outside the run: the shell, files, the network, other languages, code built from text.
BLOCKED = (
    "system", "dos", "unix", "winopen", "perl", "python", "pyrun", "pyrunfile", "pyenv", "javaObject", "javaMethod",
    "javaaddpath", "actxserver", "actxcontrol", "web", "webread", "webwrite", "websave", "urlread", "urlwrite",
    "ftp", "sftp", "sendmail", "tcpclient", "tcpip", "tcpserver", "udpport", "serialport", "delete", "rmdir",
    "recycle", "movefile", "copyfile", "mkdir", "cd", "chdir", "addpath", "rmpath", "savepath", "setenv", "eval",
    "evalin", "evalc", "assignin", "feval", "str2func", "builtin", "run", "exit", "quit", "loadlibrary", "calllib",
    "mex", "fopen", "fwrite", "save", "load", "dlmwrite", "csvwrite", "writematrix", "writetable", "writecell",
    "imwrite", "audiowrite", "unzip", "untar", "gunzip", "gzip", "zip", "tar", "parpool", "parfeval", "batch",
    "input", "keyboard", "inputdlg", "uigetfile", "uiputfile", "clipboard", "shell_cmd", "popen", "popen2", "fork",
    "exec", "unlink", "rename", "pkg", "dbstop", "diary", "print", "saveas", "exportgraphics",
)
_BLOCKED = re.compile(r"(?<![\w.])(" + "|".join(BLOCKED) + r")\b|(?<![\w.])(py|java|NET|COM|matlab\.io)\s*\."
                      r"|^\s*!", re.IGNORECASE | re.MULTILINE)
# A quote after a name, a number, a closing bracket or another quote is a transpose (a'); otherwise it opens a string.
_STRING = re.compile(r"""(?<![\w)\]}.'"])'(?:[^'\n]|'')*'|"(?:[^"\n]|"")*\"""")
_BLOCK_COMMENT = re.compile(r"^\s*%\{.*?^\s*%\}", re.MULTILINE | re.DOTALL)
_COMMENT = re.compile(r"%.*$|#.*$", re.MULTILINE)

# The wrapper Jarvis runs: your code in jarvis_code.m, then every figure saved as a PNG.
WRAPPER = r"""
try
  set(0, 'DefaultFigureVisible', 'off');
catch
end
if exist('OCTAVE_VERSION', 'builtin')
  jarvis_tk = available_graphics_toolkits();
  if any(strcmp(jarvis_tk, 'gnuplot')) && ~any(strcmp(jarvis_tk, 'qt'))
    graphics_toolkit('gnuplot');
  end
end
try
  jarvis_code
catch jarvis_err
  fprintf(2, 'JARVIS_ERROR: %s\n', jarvis_err.message);
end
jarvis_figs = findall(0, 'Type', 'figure');
if exist('OCTAVE_VERSION', 'builtin')
  jarvis_n = double(jarvis_figs);
else
  jarvis_n = arrayfun(@(h) h.Number, jarvis_figs);
end
[jarvis_s, jarvis_o] = sort(jarvis_n);
jarvis_figs = jarvis_figs(jarvis_o);
for jarvis_k = 1:min(numel(jarvis_figs), MAX_FIGURES)
  try
    print(jarvis_figs(jarvis_k), sprintf('figure%d.png', jarvis_k), '-dpng', '-r110');
  catch
    try
      print(jarvis_figs(jarvis_k), sprintf('figure%d.png', jarvis_k), '-dpngcairo');   % Octave + gnuplot, no Ghostscript
    catch jarvis_err
      fprintf(2, 'JARVIS_ERROR: couldn''t save figure %d: %s\n', jarvis_k, jarvis_err.message);
    end
  end
end
""".replace("MAX_FIGURES", str(MAX_FIGURES))


@dataclass(frozen=True)
class Engine:
    kind: str           # "matlab" or "octave"
    exe: Path
    name: str           # "MATLAB R2024b", "Octave 9.2.0": for the model and the confirm box

    def environment(self, base: dict[str, str] | None = None) -> dict[str, str]:
        """What Octave's own launcher (octave.bat) sets up: its bin folder first on PATH (gnuplot and
        Ghostscript for the figures live there) and the MSYS tools beside it. MATLAB needs nothing."""
        env = dict(os.environ if base is None else base)
        if self.kind != "octave":
            return env
        first = [str(self.exe.parent)]
        usr_bin = self.exe.parent.parent.parent / "usr" / "bin"           # ...\octave-11.3.0-w64\usr\bin
        if usr_bin.is_dir():
            first.append(str(usr_bin))
        env["PATH"] = os.pathsep.join([*first, env.get("PATH", "")])
        if (self.exe.parent / "gs.exe").exists():
            env["GS"] = "gs.exe"
        return env

    def command(self, folder: Path) -> list[str]:
        where = str(folder).replace("'", "''")
        if self.kind == "matlab":
            return [str(self.exe), "-batch", f"cd('{where}'); jarvis_run"]
        return [str(self.exe), "--no-gui", "--quiet", "--norc", "--eval", f"cd('{where}'); jarvis_run"]


def _version(path: Path, pattern: str) -> str:
    found = re.search(pattern, str(path), re.IGNORECASE)
    return found.group(1) if found else ""


def find_engine(choice: str = "auto", path: str = "", platform: str = sys.platform,
                which: Callable[[str], str | None] = shutil.which,
                roots: list[Path] | None = None) -> Engine | None:
    """MATLAB or Octave on this computer, newest first; None if neither is there."""
    choice = (choice or "auto").lower()
    if path:
        exe = Path(path).expanduser()
        if not exe.exists():
            return None
        kind = "octave" if "octave" in exe.name.lower() or choice == "octave" else "matlab"
        return _engine(kind, exe)
    kinds = ["matlab", "octave"] if choice == "auto" else [choice]
    for kind in kinds:
        exe = _find(kind, platform, which, roots)
        if exe is not None:
            return _engine(kind, exe)
    return None


def _engine(kind: str, exe: Path) -> Engine:
    if kind == "matlab":
        return Engine("matlab", exe, ("MATLAB " + _version(exe, r"(R20\d\d[ab])")).strip())
    return Engine("octave", exe, ("Octave " + _version(exe, r"Octave[-_ ]?(\d+\.\d+(?:\.\d+)?)")).strip())


def _find(kind: str, platform: str, which, roots: list[Path] | None) -> Path | None:
    if platform == "win32":
        drives = roots or [Path(f"{d}:/") for d in "CD"]
        patterns = (["Program Files/MATLAB/R20*/bin/matlab.exe", "MATLAB/R20*/bin/matlab.exe"] if kind == "matlab"
                    # mingw64\bin or ucrt64\bin, depending on the Octave release's Windows build
                    # installed (Octave-9.2.0\mingw64\bin) or unzipped (octave-9.2.0-w64\[octave-9.2.0-w64\]...)
                    else ["Program Files/GNU Octave/*/*/bin/octave-cli.exe",
                          "Program Files/GNU Octave/*/*/*/bin/octave-cli.exe",
                          "GNU Octave/*/*/bin/octave-cli.exe", "GNU Octave/*/*/*/bin/octave-cli.exe",
                          "Octave*/*/bin/octave-cli.exe", "Octave*/*/*/bin/octave-cli.exe"])
        found = [p for d in drives for pat in patterns for p in d.glob(pat)]
        if found:
            return max(found, key=_release)                                   # the newest release
    for name in (["matlab"] if kind == "matlab" else ["octave-cli", "octave"]):
        hit = which(name)
        if hit:
            return Path(hit)
    return None


def _release(path: Path) -> tuple:
    """...R2024a\bin -> (2024, 'a'); ...octave-10.1.0-w64\... -> (10, 1, 0): comparable, so the newest wins."""
    for part in path.parts:
        if found := re.fullmatch(r"R(20\d\d)([ab])", part):
            return int(found.group(1)), found.group(2)
        if found := re.search(r"octave[-_ ]?(\d+(?:\.\d+)*)", part, re.IGNORECASE):
            return tuple(int(x) for x in found.group(1).split("."))
    return ()


def blocked(code: str) -> list[str]:
    """The functions in the code that could reach outside the run (strings and comments aside)."""
    text = _BLOCK_COMMENT.sub("", code)
    text = _STRING.sub("''", text)
    text = _COMMENT.sub("", text)
    found = []
    for m in _BLOCKED.finditer(text):
        word = (m.group(1) or m.group(2) or "!").strip()
        if word.lower() not in [w.lower() for w in found]:
            found.append(word)
    return found


def _kill(proc: subprocess.Popen) -> None:
    """Stop the run and everything it started (MATLAB's launcher starts the real MATLAB)."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=15,
                           check=False)
        else:
            os.killpg(proc.pid, 9)
    except (OSError, subprocess.SubprocessError):
        proc.kill()


class MatlabTools:
    def __init__(self, jarvis_folder: Path | str, engine: Engine, log: ActionLog | None = None,
                 confirm: Confirm | None = None, *, ask_first: bool = True, timeout_s: float = 120.0,
                 show_board: Callable[[dict], bool] | None = None,
                 popen: Callable[..., Any] = subprocess.Popen):
        self.folder = Path(jarvis_folder).expanduser() / "matlab"
        self.engine, self.timeout_s, self.popen = engine, timeout_s, popen
        self.show_board = show_board or (lambda board: False)
        self.board_given = show_board is not None         # else Jarvis gives his window's board (app.py)
        tier = Tier.ASK_FIRST if ask_first else Tier.DO_AND_LOG
        self.registry = Registry([Tool(
            "run_matlab",
            (f"Run MATLAB code on this laptop ({engine.name}) and show its printed output and figures on the board "
             "in Jarvis's window; the user approves each run. Write complete, self-contained code that prints the "
             "numbers that matter (disp, fprintf) and plots with labelled axes and a title. No files, internet, "
             "system commands, eval or input."
             + (" It's GNU Octave: stick to core MATLAB, no toolboxes." if engine.kind == "octave" else "")),
            {"type": "object", "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 120,
                          "description": "what the code does, in a few words"},
                "code": {"type": "string", "minLength": 1, "maxLength": 6000, "description": "the MATLAB code"}},
             "required": ["title", "code"]},
            tier, self._run, describe=self._describe)])
        self.gate = Gate(self.registry, [self.folder], log, confirm)

    def names(self) -> set[str]:
        return {"run_matlab"}

    def specs(self) -> list[dict]:
        return self.registry.specs()

    def will_ask(self, arguments: str) -> bool:
        """Will this call show the click box? (Jarvis then says to check the code on the board.)"""
        import json
        try:
            args = json.loads(arguments or "{}")
        except ValueError:
            return False
        tool = self.registry.get("run_matlab")
        return (isinstance(args, dict) and bool(str(args.get("code", "")).strip())
                and not blocked(str(args["code"])) and tool is not None and tool.tier is Tier.ASK_FIRST
                and self.gate.confirm is not None)

    def _describe(self, args: Args) -> str:
        lines = len(str(args["code"]).strip().splitlines())
        return (f"Run {lines} lines of {self.engine.name} code: {str(args['title'])[:80]}. "
                "The code is on the board in Jarvis's window.")

    def call(self, name: str, arguments: str) -> Outcome:
        """Refuse code that reaches outside the run, show the code, then ask (the gate) and run."""
        import json
        try:
            args = json.loads(arguments or "{}")
        except ValueError:
            return self.gate.call(name, arguments)
        code = str(args.get("code", "")) if isinstance(args, dict) else ""
        found = blocked(code)
        if found:
            self.gate.log.write(tool=name, args={"title": args.get("title", "")}, decision="refused",
                                reasons=[f"uses {', '.join(found)}"])
            text = (f"Jarvis refused to run that code: it uses {', '.join(found)}, which could reach outside "
                    "the run (files, the system, the internet). Rewrite it without them: compute, print and plot only.")
            return Outcome("refused", "I won't run that code: it reaches outside its folder.", name,
                           Result(False, "refused", data={"for_model": text, "kind": "matlab"}),
                           reasons=[f"uses {', '.join(found)}"])
        if isinstance(args, dict) and code:
            self.show_board({"title": str(args.get("title", "MATLAB"))[:120], "plots": [], "from": "matlab",
                             "steps": [{"text": f"{self.engine.name} code, waiting for your approval",
                                        "code": code[:6000]}]})
        return self.gate.call(name, arguments)

    # ---- running -------------------------------------------------------------------------
    def _new_run(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 - a folder name, local time
        folder = self.folder / f"run-{stamp}"
        n = 1
        while folder.exists():
            folder = self.folder / f"run-{stamp}-{n}"
            n += 1
        folder.mkdir(parents=True)
        return folder

    def _run(self, args: Args) -> Result:
        code, title = str(args["code"]), str(args["title"])[:120]
        run = self._new_run()
        if self.engine.kind == "octave":
            code = "1;\n" + code                       # Octave: a script may define functions after this
        (run / "jarvis_code.m").write_text(code, encoding="utf-8")
        (run / "jarvis_run.m").write_text(WRAPPER, encoding="utf-8")
        start = time.perf_counter()
        flags: dict[str, Any] = ({"creationflags": 0x00000200 | 0x08000000} if sys.platform == "win32"   # new group, no console
                                 else {"start_new_session": True})
        proc = self.popen(self.engine.command(run), cwd=str(run), env=self.engine.environment(),
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          encoding="utf-8", errors="replace", **flags)
        try:
            out, err = proc.communicate(timeout=self.timeout_s)
            timed_out = False
        except subprocess.TimeoutExpired:
            _kill(proc)
            out, err = proc.communicate()
            timed_out = True
        seconds = time.perf_counter() - start
        errors = [line.split("JARVIS_ERROR:", 1)[1].strip() for line in (err or "").splitlines()
                  if "JARVIS_ERROR:" in line]
        if not errors and proc.returncode not in (0, None) and not timed_out:
            errors = [line for line in (err or "").splitlines() if line.strip()][-3:] or [f"exit code {proc.returncode}"]
        figures = sorted(p.name for p in run.glob("figure*.png") if FIGURE_NAME.fullmatch(p.name))
        output = _clean(out)
        steps = [{"text": f"{self.engine.name} code ({seconds:.0f} s)", "code": code.removeprefix("1;\n")[:6000]}]
        if output:
            steps.append({"text": "Output", "code": output})
        if errors or timed_out:
            steps.append({"text": "Error", "code": "\n".join(errors) if errors else
                          f"Stopped after {self.timeout_s:.0f} seconds."})
        steps += [{"text": f"Figure {i}", "image": f"/figure/{run.name}/{name}"} for i, name in enumerate(figures, 1)]
        shown = self.show_board({"title": title, "plots": [], "from": "matlab", "steps": steps})
        report = [f"{self.engine.name} ran: {title} ({seconds:.0f} s).",
                  f"Printed output:\n{output}" if output else "It printed nothing.",
                  (f"{len(figures)} figure(s) saved and shown on the board in Jarvis's window"
                   if shown else f"{len(figures)} figure(s) saved; the window isn't open")
                  + (" (you can't see them: explain what the code plots, not details you can't know)." if figures
                     else ".")]
        if timed_out:
            report.append(f"It was stopped after {self.timeout_s:.0f} seconds (too slow, or waiting for something).")
        if errors:
            report.append("Errors: " + " | ".join(errors)[:800])
        ok = not timed_out and not (errors and not output and not figures)
        summary = ("Ran it; the output and figures are on the board." if ok
                   else "It didn't run cleanly; the error is on the board.")
        return Result(ok, summary, data={"for_model": "\n".join(report), "kind": "matlab", "run": run.name,
                                         "figures": figures, "say": ("matlab_ran" if ok else "matlab_failed", {})})

    def figure(self, run: str, name: str) -> Path | None:
        """A figure for the window (/figure/<run>/<name>): only Jarvis's own runs and PNGs."""
        if not RUN_NAME.fullmatch(run) or not FIGURE_NAME.fullmatch(name):
            return None
        path = self.folder / run / name
        return path if path.is_file() else None


def _clean(out: str | None) -> str:
    """MATLAB's and Octave's printed output, without blank runs, cut to a readable size."""
    text = re.sub(r"\n{3,}", "\n\n", (out or "").replace("\r\n", "\n")).strip()
    return text if len(text) <= OUTPUT_CHARS else text[:OUTPUT_CHARS] + "\n[... cut]"
