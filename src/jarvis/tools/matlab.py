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

import json
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

MAX_FIGURES = 8
OUTPUT_CHARS = 4000
# Words that start real MATLAB lines in command form ("hold on", "grid on", "format long"), not prose
COMMAND_WORDS = {"hold", "grid", "axis", "format", "close", "clear", "clc", "legend", "box", "disp", "warning",
                 "more", "figure", "colorbar", "shading", "view", "drawnow", "global", "function", "end", "if",
                 "for", "while", "else", "elseif", "return", "break", "continue", "otherwise", "case", "switch",
                 "try", "catch", "colormap", "subplot", "persistent", "printf", "fprintf", "title", "xlabel",
                 "ylabel", "zlabel", "rotate3d", "camlight", "lighting", "material", "pkg"}
RUN_NAME = re.compile(r"run-\d{8}-\d{6}(?:-\d{1,3})?")
FIGURE_NAME = re.compile(r"figure[1-8]\.(?:png|svg)")
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
# Loading or listing an Octave package that's already installed is fine (2 Nov: "pkg load statistics" for
# ttest2 and tcdf was refused); installing one (pkg install, which downloads) stays blocked.
_PKG_OK = re.compile(r"(?<![\w.])pkg[ \t]+(?:load|list|describe)\b[ \t\w-]*"
                     r"|(?<![\w.])pkg\s*\(\s*(['\"])(?:load|list|describe)\1(?:\s*,\s*(['\"])[\w-]+\2)*\s*\)")
_PKG_LOAD = re.compile(r"(?<![\w.])pkg[ \t]+load((?:[ \t]+[\w-]+)+)|(?<![\w.])pkg\s*\(\s*(['\"])load\2"
                       r"((?:\s*,\s*['\"][\w-]+['\"])+)\s*\)")
# Octave's own words when a function is in a package (2 Nov, Windows: "The 'tcdf' function belongs to the
# statistics package from Octave Forge which you have installed but not loaded.")
_IN_PACKAGE = re.compile(r"belongs to the ([\w-]+) package from Octave Forge which (you have installed but not "
                         r"loaded|seems to not be installed)")
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
  warning('off', 'Octave:gnuplot-graphics');
  jarvis_tk = available_graphics_toolkits();
  % gnuplot draws without a window; Qt and FLTK need one (2 Nov, Windows: "PNGCAIRO output is not
  % available for OpenGL toolkits" with qt chosen)
  if any(strcmp(jarvis_tk, 'gnuplot'))
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
% Each figure as a PNG; if this computer can't make one, as an SVG. Every reason is kept for the report.
jarvis_ways = {{'png', '-dpng', '-r110'}, {'png', '-dpngcairo', '-r110'}, {'svg', '-dsvg', ''}};
for jarvis_k = 1:min(numel(jarvis_figs), MAX_FIGURES)
  jarvis_why = '';
  for jarvis_w = 1:numel(jarvis_ways)
    jarvis_way = jarvis_ways{jarvis_w};
    jarvis_file = sprintf('figure%d.%s', jarvis_k, jarvis_way{1});
    try
      if isempty(jarvis_way{3})
        print(jarvis_figs(jarvis_k), jarvis_file, jarvis_way{2});
      else
        print(jarvis_figs(jarvis_k), jarvis_file, jarvis_way{2}, jarvis_way{3});
      end
      if exist(jarvis_file, 'file')
        jarvis_why = '';
        break;
      end
      jarvis_why = [jarvis_why ' ' jarvis_way{2} ': no file;'];
    catch jarvis_err
      jarvis_why = [jarvis_why ' ' jarvis_way{2} ': ' jarvis_err.message ';'];
    end
  end
  if ~isempty(jarvis_why)
    fprintf(2, 'JARVIS_ERROR: couldn''t save figure %d:%s\n', jarvis_k, jarvis_why);
  end
end
% The figures' data, so Jarvis can draw them himself when no picture could be saved (2 Nov, Windows:
% Octave's printing found no way to make an image without a window). Lines, markers, 3D curves, vector
% fields (quiver), scatter, bars, contour and image colour maps, surfaces; MATLAB and Octave alike.
try
  jarvis_out = {};
  for jarvis_k = 1:min(numel(jarvis_figs), MAX_FIGURES)
    jarvis_axes = findall(jarvis_figs(jarvis_k), 'type', 'axes');
    for jarvis_a = numel(jarvis_axes):-1:max(1, numel(jarvis_axes) - 3)
      jarvis_ax = jarvis_axes(jarvis_a);
      if any(strcmpi(get(jarvis_ax, 'tag'), {'legend', 'colorbar'})), continue; end
      jarvis_lab = {get(get(jarvis_ax, 'title'), 'string'), get(get(jarvis_ax, 'xlabel'), 'string'), ...
                    get(get(jarvis_ax, 'ylabel'), 'string')};
      for jarvis_i = 1:3
        if iscell(jarvis_lab{jarvis_i}), jarvis_lab{jarvis_i} = strjoin(jarvis_lab{jarvis_i}, ' '); end
        if size(jarvis_lab{jarvis_i}, 1) > 1, jarvis_lab{jarvis_i} = strjoin(cellstr(jarvis_lab{jarvis_i})', ' '); end
      end
      jarvis_p = struct('figure', jarvis_k, 'title', jarvis_lab{1}, 'xlabel', jarvis_lab{2}, ...
                        'ylabel', jarvis_lab{3}, 'xscale', get(jarvis_ax, 'xscale'), 'yscale', get(jarvis_ax, 'yscale'));
      jarvis_p.curves = {}; jarvis_p.arrows = {}; jarvis_p.bars = {}; jarvis_p.grids = {}; jarvis_p.surfaces = {};
      % lines drawn straight on the axes (a quiver's or a bar's own lines belong to it, not here)
      jarvis_ls = findall(jarvis_ax, 'type', 'line');
      for jarvis_j = numel(jarvis_ls):-1:1
        jarvis_h = jarvis_ls(jarvis_j);
        if ~isequal(get(jarvis_h, 'parent'), jarvis_ax) || numel(jarvis_p.curves) >= 6, continue; end
        jarvis_x = double(get(jarvis_h, 'xdata')); jarvis_y = double(get(jarvis_h, 'ydata'));
        jarvis_z = double(get(jarvis_h, 'zdata'));
        jarvis_x = jarvis_x(:)'; jarvis_y = jarvis_y(:)'; jarvis_z = jarvis_z(:)';
        if numel(jarvis_x) ~= numel(jarvis_y) || numel(jarvis_y) < 2, continue; end
        jarvis_st = max(1, ceil(numel(jarvis_y) / 600));
        jarvis_c = struct('x', jarvis_x(1:jarvis_st:end), 'y', jarvis_y(1:jarvis_st:end), ...
                          'name', get(jarvis_h, 'displayname'), ...
                          'line', ~strcmpi(get(jarvis_h, 'linestyle'), 'none'), ...
                          'markers', ~strcmpi(get(jarvis_h, 'marker'), 'none'));
        if numel(jarvis_z) == numel(jarvis_y), jarvis_c.z = jarvis_z(1:jarvis_st:end); end
        jarvis_p.curves{end+1} = jarvis_c;
      end
      % scatter (markers only)
      jarvis_hs = findall(jarvis_ax, '-property', 'SizeData');
      for jarvis_j = 1:min(numel(jarvis_hs), 3)
        jarvis_x = double(get(jarvis_hs(jarvis_j), 'xdata')); jarvis_y = double(get(jarvis_hs(jarvis_j), 'ydata'));
        jarvis_st = max(1, ceil(numel(jarvis_y) / 2000));
        if numel(jarvis_x) == numel(jarvis_y) && numel(jarvis_y) >= 1
          jarvis_p.curves{end+1} = struct('x', jarvis_x(1:jarvis_st:end), 'y', jarvis_y(1:jarvis_st:end), ...
                                          'name', get(jarvis_hs(jarvis_j), 'displayname'), 'line', false, 'markers', true);
        end
      end
      % vector fields (quiver): arrows from (x, y) along (u, v)
      jarvis_hs = findall(jarvis_ax, '-property', 'UData');
      for jarvis_j = 1:min(numel(jarvis_hs), 2)
        jarvis_h = jarvis_hs(jarvis_j);
        jarvis_x = double(get(jarvis_h, 'xdata')); jarvis_y = double(get(jarvis_h, 'ydata'));
        jarvis_u = double(get(jarvis_h, 'udata')); jarvis_v = double(get(jarvis_h, 'vdata'));
        if isequal(size(jarvis_x), size(jarvis_u)) && isequal(size(jarvis_y), size(jarvis_v)) && numel(jarvis_u) >= 1
          jarvis_st = max(1, ceil(numel(jarvis_u) / 600));
          jarvis_p.arrows{end+1} = struct('x', jarvis_x(1:jarvis_st:end), 'y', jarvis_y(1:jarvis_st:end), ...
                                          'u', jarvis_u(1:jarvis_st:end), 'v', jarvis_v(1:jarvis_st:end));
        end
      end
      % bars (bar, hist; histogram in MATLAB)
      jarvis_hs = findall(jarvis_ax, '-property', 'BarWidth');
      for jarvis_j = numel(jarvis_hs):-1:max(1, numel(jarvis_hs) - 3)
        jarvis_x = double(get(jarvis_hs(jarvis_j), 'xdata')); jarvis_y = double(get(jarvis_hs(jarvis_j), 'ydata'));
        if numel(jarvis_x) == numel(jarvis_y) && numel(jarvis_y) <= 400
          jarvis_p.bars{end+1} = struct('x', jarvis_x(:)', 'y', jarvis_y(:)', 'name', get(jarvis_hs(jarvis_j), 'displayname'));
        end
      end
      jarvis_hs = findall(jarvis_ax, '-property', 'BinEdges');
      for jarvis_j = 1:min(numel(jarvis_hs), 2)
        jarvis_e = double(get(jarvis_hs(jarvis_j), 'BinEdges')); jarvis_y = double(get(jarvis_hs(jarvis_j), 'Values'));
        if numel(jarvis_e) == numel(jarvis_y) + 1 && numel(jarvis_y) <= 400
          jarvis_p.bars{end+1} = struct('x', (jarvis_e(1:end-1) + jarvis_e(2:end)) / 2, 'y', jarvis_y(:)', 'name', '');
        end
      end
      % contour and image colour maps: a grid of values over an x and y range
      jarvis_hs = [findall(jarvis_ax, '-property', 'LevelList'); findall(jarvis_ax, 'type', 'image')];
      for jarvis_j = 1:min(numel(jarvis_hs), 2)
        jarvis_h = jarvis_hs(jarvis_j);
        if strcmpi(get(jarvis_h, 'type'), 'image')
          jarvis_z = double(get(jarvis_h, 'cdata')); jarvis_kind = 'image';
        else
          jarvis_z = double(get(jarvis_h, 'zdata')); jarvis_kind = 'contour';
        end
        jarvis_X = double(get(jarvis_h, 'xdata')); jarvis_Y = double(get(jarvis_h, 'ydata'));
        if ndims(jarvis_z) == 2 && min(size(jarvis_z)) >= 2
          jarvis_z = jarvis_z(1:max(1, ceil(size(jarvis_z, 1) / 80)):end, 1:max(1, ceil(size(jarvis_z, 2) / 80)):end);
          jarvis_p.grids{end+1} = struct('z', jarvis_z, 'x', [min(jarvis_X(:)) max(jarvis_X(:))], ...
                                         'y', [min(jarvis_Y(:)) max(jarvis_Y(:))], 'kind', jarvis_kind);
        end
      end
      % surfaces (surf, mesh)
      jarvis_ss = findall(jarvis_ax, 'type', 'surface');
      if ~isempty(jarvis_ss)
        jarvis_z = double(get(jarvis_ss(1), 'zdata'));
        jarvis_X = double(get(jarvis_ss(1), 'xdata')); jarvis_Y = double(get(jarvis_ss(1), 'ydata'));
        if size(jarvis_z, 1) >= 2 && size(jarvis_z, 2) >= 2
          jarvis_z = jarvis_z(1:max(1, ceil(size(jarvis_z, 1) / 60)):end, 1:max(1, ceil(size(jarvis_z, 2) / 60)):end);
          jarvis_p.surfaces{end+1} = struct('z', jarvis_z, 'x', [min(jarvis_X(:)) max(jarvis_X(:))], ...
                                            'y', [min(jarvis_Y(:)) max(jarvis_Y(:))]);
        end
      end
      if ~isempty(jarvis_p.curves) || ~isempty(jarvis_p.arrows) || ~isempty(jarvis_p.bars) || ...
         ~isempty(jarvis_p.grids) || ~isempty(jarvis_p.surfaces)
        jarvis_out{end+1} = jarvis_p;
      end
    end
  end
  jarvis_fid = fopen('jarvis_figures.json', 'w');
  fprintf(jarvis_fid, '%s', jsonencode(jarvis_out));
  fclose(jarvis_fid);
catch jarvis_err
  fprintf(2, 'JARVIS_NOTE: the figures'' data wasn''t saved: %s\n', jarvis_err.message);
end
% What each figure shows, measured from its data, for Jarvis to explain it (he can't see the picture).
try
for jarvis_k = 1:min(numel(jarvis_figs), MAX_FIGURES)
  jarvis_axes = findall(jarvis_figs(jarvis_k), 'type', 'axes');
  for jarvis_a = 1:min(numel(jarvis_axes), 4)
    jarvis_ax = jarvis_axes(jarvis_a);
    if any(strcmpi(get(jarvis_ax, 'tag'), {'legend', 'colorbar'}))
      continue;
    end
    jarvis_lab = {get(get(jarvis_ax, 'title'), 'string'), get(get(jarvis_ax, 'xlabel'), 'string'), ...
                  get(get(jarvis_ax, 'ylabel'), 'string')};
    for jarvis_i = 1:3
      if iscell(jarvis_lab{jarvis_i}), jarvis_lab{jarvis_i} = strjoin(jarvis_lab{jarvis_i}, ' '); end
      if size(jarvis_lab{jarvis_i}, 1) > 1, jarvis_lab{jarvis_i} = strjoin(cellstr(jarvis_lab{jarvis_i})', ' '); end
    end
    fprintf('JARVIS_DATA: figure %d: title "%s", x axis "%s", y axis "%s"\n', jarvis_k, jarvis_lab{1}, ...
            jarvis_lab{2}, jarvis_lab{3});
    jarvis_lines = findall(jarvis_ax, 'type', 'line');
    jarvis_cn = 0;
    for jarvis_j = 1:numel(jarvis_lines)
      jarvis_l = jarvis_lines(jarvis_j);
      % only lines drawn straight on the axes: a quiver's arrows or a bar's baseline are measured elsewhere
      if ~isequal(get(jarvis_l, 'parent'), jarvis_ax) || jarvis_cn >= 3, continue; end
      jarvis_x = double(get(jarvis_l, 'xdata')); jarvis_y = double(get(jarvis_l, 'ydata'));
      if numel(jarvis_y) == 2 && all(jarvis_y == 0), continue; end
      jarvis_cn = jarvis_cn + 1;
      jarvis_x = jarvis_x(:)'; jarvis_y = jarvis_y(:)';
      jarvis_ok = isfinite(jarvis_x) & isfinite(jarvis_y);
      jarvis_x = jarvis_x(jarvis_ok); jarvis_y = jarvis_y(jarvis_ok);
      if numel(jarvis_y) < 2, continue; end
      [jarvis_lo, jarvis_ilo] = min(jarvis_y); [jarvis_hi, jarvis_ihi] = max(jarvis_y);
      jarvis_name = get(jarvis_l, 'displayname');
      fprintf(['JARVIS_DATA:   curve %d%s (%d points): x from %.4g to %.4g; y starts at %.4g and ends at %.4g; ' ...
               'lowest %.4g at x = %.4g; highest %.4g at x = %.4g\n'], jarvis_j, ...
              char(repmat([' "' jarvis_name '"'], 1, ~isempty(jarvis_name))), numel(jarvis_y), jarvis_x(1), jarvis_x(end), jarvis_y(1), jarvis_y(end), ...
              jarvis_lo, jarvis_x(jarvis_ilo), jarvis_hi, jarvis_x(jarvis_ihi));
      jarvis_zc = find(jarvis_y(1:end-1) .* jarvis_y(2:end) < 0);
      if ~isempty(jarvis_zc)
        fprintf('JARVIS_DATA:     crosses zero %d times, first near x = %s\n', numel(jarvis_zc), ...
                sprintf('%.3g ', jarvis_x(jarvis_zc(1:min(5, end)))));
      end
      jarvis_pk = find(jarvis_y(2:end-1) > jarvis_y(1:end-2) & jarvis_y(2:end-1) >= jarvis_y(3:end)) + 1;
      if ~isempty(jarvis_pk)
        jarvis_n = min(6, numel(jarvis_pk));
        fprintf('JARVIS_DATA:     %d peaks; the first (x, y): %s\n', numel(jarvis_pk), ...
                sprintf('(%.3g, %.3g) ', [jarvis_x(jarvis_pk(1:jarvis_n)); jarvis_y(jarvis_pk(1:jarvis_n))]));
      end
    end
    jarvis_surfs = findall(jarvis_ax, 'type', 'surface');
    for jarvis_j = 1:min(numel(jarvis_surfs), 2)
      jarvis_z = double(get(jarvis_surfs(jarvis_j), 'zdata'));
      jarvis_z = jarvis_z(isfinite(jarvis_z));
      if ~isempty(jarvis_z)
        fprintf('JARVIS_DATA:   surface %d: z from %.4g to %.4g\n', jarvis_j, min(jarvis_z), max(jarvis_z));
      end
    end
  end
end
catch jarvis_err
  fprintf('JARVIS_DATA: (could not measure the figures: %s)\n', jarvis_err.message);
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
        if exe.exists():
            kind = "octave" if "octave" in exe.name.lower() or choice == "octave" else "matlab"
            return _engine(kind, exe)
        # The named file isn't there (moved, or a typo): look in the usual places instead.
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
                          "Octave*/*/bin/octave-cli.exe", "Octave*/*/*/bin/octave-cli.exe",
                          # unzipped into any folder on the drive: D:\GNU\octave-11.3.0-w64\mingw64\bin
                          "*/octave-*/*/bin/octave-cli.exe", "octave-*/*/bin/octave-cli.exe"])
        found = [p for d in drives for pat in patterns for p in d.glob(pat)]
        if found:
            return max(found, key=_release)                                   # the newest release
    for name in (["matlab"] if kind == "matlab" else ["octave-cli", "octave"]):
        hit = which(name)
        if hit:
            return Path(hit)
    return None


def _release(path: Path) -> tuple:
    r"""...R2024a\bin -> (2024, 'a'); ...octave-10.1.0-w64\... -> (10, 1, 0): comparable, so the newest wins."""
    for part in path.parts:
        if found := re.fullmatch(r"R(20\d\d)([ab])", part):
            return int(found.group(1)), found.group(2)
        if found := re.search(r"octave[-_ ]?(\d+(?:\.\d+)*)", part, re.IGNORECASE):
            return tuple(int(x) for x in found.group(1).split("."))
    return ()


def blocked(code: str) -> list[str]:
    """The functions in the code that could reach outside the run (strings and comments aside)."""
    text = _BLOCK_COMMENT.sub("", code)
    text = _PKG_OK.sub(" ", text)                   # before strings go: pkg('load', 'statistics') is fine too
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
             "numbers that matter (disp, fprintf) and plots with labelled axes and a title. One statement a line; "
             "keep each string on one line (a newline inside fprintf is the two characters \\n). For an ODE "
             "with no initial conditions given, pick ones that show the behaviour (y(0) = 1, y'(0) = 0, never all "
             "zero) and print which. No files, "
             "internet, system commands, eval or input."
             + (" It's GNU Octave: core MATLAB plus the Octave Forge packages installed here. For statistics "
                "(ttest2, tcdf, normpdf, normcdf, histfit) put pkg load statistics on the first line; never pkg "
                "install. Welch's t-test is ttest2(a, b, 'Vartype', 'unequal')." if engine.kind == "octave"
                else "")),
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
                and not blocked(str(args["code"])) and not self.not_runnable(str(args["code"]))
                and tool is not None and tool.tier is Tier.ASK_FIRST
                and self.gate.confirm is not None)

    def not_runnable(self, code: str) -> str:
        """Why this can't run here, before anyone is asked to click: a description instead of code (2 Nov:
        "Second order ODE: y'' + (1/2) y' + 4 y = 0, zero IC" was sent as the code), or symbolic maths
        Octave doesn't have here (syms, dsolve)."""
        if not code.strip():
            return ""
        for line in code.splitlines():
            words = line.split("%", 1)[0].strip()
            first = words.split(" ", 1)[0].lower().rstrip(":,.")
            # three bare words in a row can't start a MATLAB statement, except a command like "axis equal tight"
            if re.match(r"^[A-Za-z]+(?:\s+[A-Za-z']+){2,}\s*[:,.]?(?:\s|$)", words) and first not in COMMAND_WORDS:
                return ("that's a description, not MATLAB code ('" + words[:60] + "'). Write the actual code: "
                        "assignments, ode45, plot, with one statement a line.")
        if self.engine.kind == "octave" and re.search(r"\b(?:syms|dsolve|vpa|sym)\s*[\s(]", code):
            return ("Octave on this laptop has no symbolic maths (syms, dsolve, vpa). Solve it numerically: "
                    "ode45 for differential equations, then print the values that matter and plot.")
        return ""

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
            if "pkg" in found:
                text += (" Loading an installed package (pkg load statistics) is fine; installing one isn't. If a "
                         "package is missing, the user can install it once from Octave's own window.")
            return Outcome("refused", "I won't run that code: it reaches outside its folder.", name,
                           Result(False, "refused", data={"for_model": text, "kind": "matlab"}),
                           reasons=[f"uses {', '.join(found)}"])
        problem = self.not_runnable(code)
        if problem:
            # Not worth a click: no run, and Jarvis has the model write it again (app.py, one repair)
            self.gate.log.write(tool=name, args={"title": args.get("title", "")}, decision="not_code", reasons=[problem])
            return Outcome("failed", "That wasn't code I could run.", name,
                           Result(False, "not runnable", data={"for_model": f"Not run: {problem}", "kind": "matlab",
                                                                "errors": [problem], "timed_out": False, "code": code,
                                                                "title": str(args.get("title", ""))[:120]}),
                           reasons=[problem])
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
        code, title = join_split_strings(str(args["code"])), str(args["title"])[:120]
        run = self._new_run()
        if self.engine.kind == "octave":
            code = "1;\n" + code                       # Octave: a script may define functions after this
        else:                                         # MATLAB has no pkg: its toolboxes are always there
            code = _PKG_LOAD.sub(lambda m: "% (" + m.group(0).strip() + ": Octave only)", code)
        out, err, timed_out, seconds, returncode = self._execute(run, code)
        loaded, missing = [], []
        if self.engine.kind == "octave" and not timed_out:
            for name, state in _IN_PACKAGE.findall(" ".join((err or "").split())):
                (missing if state.startswith("seems") else loaded).append(name)
            missing += re.findall(r"package ([\w-]+) is not installed", err or "")    # pkg load of a missing one
            loaded, missing = list(dict.fromkeys(loaded)), list(dict.fromkeys(missing))
            if loaded:
                # installed, just not loaded: load it and run again (the same approved code, nothing new)
                for old in run.glob("figure*.*"):
                    old.unlink()
                (run / "jarvis_figures.json").unlink(missing_ok=True)
                code = "1;\n" + "".join(f"pkg load {name}\n" for name in loaded) + code.removeprefix("1;\n")
                more, err, timed_out, extra, returncode = self._execute(run, code)
                out, seconds = more, seconds + extra
        errors = _errors(err or "", run, shifted=self.engine.kind == "octave")
        if not errors and returncode not in (0, None) and not timed_out:
            errors = [line for line in (err or "").splitlines() if line.strip()][-3:] or [f"exit code {returncode}"]
        return self._report(run, code, title, out, errors, timed_out, seconds, loaded, missing)

    def _execute(self, run: Path, code: str) -> tuple[str, str, bool, float, int | None]:
        """Run the code once in its folder: what it printed, its errors, whether it was stopped, seconds."""
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
        try:
            with (run / "jarvis_log.txt").open("a", encoding="utf-8") as log:
                log.write(f"--- printed\n{out or ''}\n--- errors and warnings\n{err or ''}\n")
        except OSError:
            pass
        return out or "", err or "", timed_out, seconds, proc.returncode

    def _report(self, run: Path, code: str, title: str, out: str, errors: list[str], timed_out: bool,
                seconds: float, loaded: list[str], missing: list[str]) -> Result:
        """Show the run on the board and tell the model what happened."""
        figures = sorted(p.name for p in run.glob("figure*.*") if FIGURE_NAME.fullmatch(p.name))
        drawn = [a for a in _figure_data(run) if not any(f.startswith(f"figure{a['figure']}.") for f in figures)]
        if drawn:
            # Jarvis draws these himself from their data: an image that couldn't be saved isn't an error
            problems = [e for e in errors if e.startswith("couldn't save figure")]
            errors = [e for e in errors if not e.startswith("couldn't save figure")]
        else:
            problems = []
        measured = [ln.split("JARVIS_DATA:", 1)[1].rstrip() for ln in (out or "").splitlines()
                    if ln.startswith("JARVIS_DATA:")] + _measure_more(_figure_data(run))
        output = _clean("\n".join(ln for ln in (out or "").splitlines() if not ln.startswith("JARVIS_DATA:")))
        steps = [{"text": f"{self.engine.name} code ({seconds:.0f} s)", "code": code.removeprefix("1;\n")[:6000]}]
        if output:
            steps.append({"text": "Output", "code": output})
        if errors or timed_out:
            steps.append({"text": "Error", "code": "\n".join(errors) if errors else
                          f"Stopped after {self.timeout_s:.0f} seconds."})
        steps += [{"text": f"Figure {name[6]}", "image": f"/figure/{run.name}/{name}"} for name in figures]
        steps += [{"text": f"Figure {a['figure']}" + (f": {a['title']}" if a["title"] else ""),
                   **{k: a[k] for k in ("plot", "grid", "surface", "curve3d") if a.get(k)}} for a in drawn]
        n_figures = len(figures) + len({a["figure"] for a in drawn})
        shown = self.show_board({"title": title, "plots": [], "from": "matlab", "steps": steps})
        report = [f"{self.engine.name} ran: {title} ({seconds:.0f} s).",
                  f"Printed output:\n{output}" if output else "It printed nothing.",
                  (f"{n_figures} figure(s) shown on the board in Jarvis's window"
                   if shown else f"{n_figures} figure(s) made; the window isn't open")
                  + (" (you can't see them; what they show, measured from their data, is below)." if n_figures
                     else ".")]
        if measured:
            report.append("What the figures show (measured from the plotted data):\n" + "\n".join(measured)[:1800])
        if timed_out:
            report.append(f"It was stopped after {self.timeout_s:.0f} seconds (too slow, or waiting for something).")
        if errors:
            report.append("Errors: " + " | ".join(errors)[:800])
        if loaded:
            report.append(f"Octave's {', '.join(loaded)} package was installed but not loaded, so Jarvis loaded it "
                          "(pkg load) and ran the code again; that's the run above.")
        if missing:
            report.append(f"The {', '.join(missing)} package isn't installed in Octave on this laptop. Tell the user "
                          "they can install it once from Octave's own window with: pkg install -forge "
                          f"{missing[0]} ; or rewrite the code with core functions only.")
        ok = not timed_out and not (errors and not output and not n_figures)
        summary = ("Ran it; the output and figures are on the board." if ok
                   else "It didn't run cleanly; the error is on the board.")
        return Result(ok, summary, data={"for_model": "\n".join(report), "kind": "matlab", "run": run.name,
                                         "figures": figures, "say": ("matlab_ran" if ok else "matlab_failed", {}),
                                         "errors": errors, "timed_out": timed_out, "code": code.removeprefix("1;\n"),
                                         "title": title, "drawn": len(drawn), "images": len(figures),
                                         "figure_problems": problems[:3]})

    def figure(self, run: str, name: str) -> Path | None:
        """A figure for the window (/figure/<run>/<name>): only Jarvis's own runs and PNGs."""
        if not RUN_NAME.fullmatch(run) or not FIGURE_NAME.fullmatch(name):
            return None
        path = self.folder / run / name
        return path if path.is_file() else None


def _number(v: Any) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) and abs(v) < 1e300 else None


def _numbers(v: Any, limit: int) -> list[float | None]:
    v = v if isinstance(v, list) else [v]
    return [_number(x) for x in v[:limit]]


def _items(v: Any, limit: int) -> list:
    return (v if isinstance(v, list) else [v])[:limit] if v else []


def _grid(z: Any, cells: int) -> list[list[float | None]] | None:
    if isinstance(z, list) and len(z) >= 2 and all(isinstance(r, list) and len(r) >= 2 for r in z[:cells]):
        return [_numbers(r, cells) for r in z[:cells]]
    return None


def _figure_data(run: Path) -> list[dict]:
    """The figures' data the wrapper saved (jarvis_figures.json), checked and ready for the board: curves
    (lines, markers, 3D), arrows (vector fields), bars, colour maps (contour, image) and a surface.
    Only numbers and short labels get through."""
    path = run / "jarvis_figures.json"
    if not path.is_file() or path.stat().st_size > 5_000_000:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    out = []
    for a in _items(data, 12):
        if not isinstance(a, dict):
            continue
        text = {k: str(a.get(k) or "")[:120] for k in ("title", "xlabel", "ylabel")}
        logs = {k: a.get(k) == "log" for k in ("xscale", "yscale")}
        curves, arrows, bars, grid, surface = [], [], [], None, None
        for c in _items(a.get("curves"), 8):
            if not isinstance(c, dict):
                continue
            xs, ys = _numbers(c.get("x"), 2000), _numbers(c.get("y"), 2000)
            zs = _numbers(c.get("z"), 2000) if "z" in c else []
            points = ([[x, y, z] for x, y, z in zip(xs, ys, zs)] if len(zs) == len(xs) and zs
                      else [[x, y] for x, y in zip(xs, ys) if x is not None])
            if len(points) >= 1:
                curves.append({"label": str(c.get("name") or "")[:60] or f"curve {len(curves) + 1}",
                               "points": points, "line": bool(c.get("line", True)),
                               "markers": bool(c.get("markers", False)), "three_d": bool(zs)})
        for q in _items(a.get("arrows"), 2):
            if isinstance(q, dict):
                cols = [_numbers(q.get(k), 600) for k in ("x", "y", "u", "v")]
                arrows += [list(t) for t in zip(*cols) if None not in t]
        for b in _items(a.get("bars"), 4):
            if isinstance(b, dict):
                xs, ys = _numbers(b.get("x"), 400), _numbers(b.get("y"), 400)
                bars.append({"label": str(b.get("name") or "")[:60] or f"bars {len(bars) + 1}",
                             "points": [[x, y] for x, y in zip(xs, ys) if x is not None and y is not None]})
        for g in _items(a.get("grids"), 1):
            z = _grid(g.get("z"), 80) if isinstance(g, dict) else None
            if z:
                grid = {"z": z, "x": _numbers(g.get("x"), 2), "y": _numbers(g.get("y"), 2),
                        "kind": "contour" if g.get("kind") == "contour" else "image"}
        for sf in _items(a.get("surfaces"), 1):
            z = _grid(sf.get("z"), 80) if isinstance(sf, dict) else None
            if z:
                surface = {"z": z, "x": _numbers(sf.get("x"), 2), "y": _numbers(sf.get("y"), 2)}
        flat = [c for c in curves if not c["three_d"]]
        if bars:            # a bar chart's own baseline (a flat line at zero) isn't a curve of its own
            flat = [c for c in flat if not (len(c["points"]) <= 2 and all(p[1] == 0 for p in c["points"]))]
        plot = ({**text, **logs, "curves": flat, "arrows": arrows[:600], "bars": bars}
                if flat or arrows or bars else None)
        curve3d = [c for c in curves if c["three_d"]]
        if plot or grid or surface or curve3d:
            out.append({"figure": int(_number(a.get("figure")) or 1), "title": text["title"], "plot": plot,
                        "grid": {**grid, **text} if grid else None, "surface": surface,
                        "curve3d": {**text, "curves": curve3d} if curve3d else None})
    return out


def _g(v: float | None) -> str:
    return "?" if v is None else f"{v:.4g}"


def _measure_more(figures: list[dict]) -> list[str]:
    """What the wrapper's own measurements leave out, for Jarvis to explain: vector fields, colour maps,
    bars and 3D curves (lines and surfaces are measured in the wrapper)."""
    lines = []
    for a in figures:
        head = f" figure {a['figure']}" + (f" ({a['title']})" if a["title"] else "")
        plot = a.get("plot") or {}
        if plot.get("arrows"):
            arrows = plot["arrows"]
            sizes = [((u * u + v * v) ** 0.5, x, y) for x, y, u, v in arrows]
            big, small = max(sizes), min(sizes)
            lines.append(f"{head}: a vector field of {len(arrows)} arrows; longest {_g(big[0])} at "
                         f"({_g(big[1])}, {_g(big[2])}), shortest {_g(small[0])} at ({_g(small[1])}, {_g(small[2])})")
        for b in plot.get("bars", []):
            values = ", ".join(f"{_g(x)}: {_g(y)}" for x, y in b["points"][:12])
            lines.append(f"{head}: bars ({len(b['points'])}) {values}")
        grid = a.get("grid")
        if grid:
            cells = [(v, r, c) for r, row in enumerate(grid["z"]) for c, v in enumerate(row) if v is not None]
            if cells:
                hi, lo = max(cells), min(cells)
                xr, yr = grid.get("x") or [None, None], grid.get("y") or [None, None]
                lines.append(f"{head}: a {grid['kind']} map over x {_g(xr[0])} to {_g(xr[-1])}, y {_g(yr[0])} to "
                             f"{_g(yr[-1])}; values from {_g(lo[0])} to {_g(hi[0])}")
        for c in (a.get("curve3d") or {}).get("curves", []):
            pts = [p for p in c["points"] if None not in p]
            if pts:
                rng = [(min(p[i] for p in pts), max(p[i] for p in pts)) for i in range(3)]
                lines.append(f"{head}: a 3D curve of {len(pts)} points; x {_g(rng[0][0])} to {_g(rng[0][1])}, "
                             f"y {_g(rng[1][0])} to {_g(rng[1][1])}, z {_g(rng[2][0])} to {_g(rng[2][1])}")
    return lines


def _errors(err: str, run: Path, shifted: bool) -> list[str]:
    """Each error the wrapper reported, with the lines after it (Octave's parse errors run over several),
    the run folder's path left out, and line numbers as the model wrote them (Octave's code starts with "1;")."""
    errors: list[str] = []
    for block in err.split("JARVIS_ERROR:")[1:]:
        lines = [ln.rstrip() for ln in block.strip().splitlines() if ln.strip()]
        text = "\n".join(ln for ln in lines if not ln.startswith("warning:"))[:600]
        text = re.sub(r"\s*(?:of |in )?(?:file )?\S*jarvis_code\.m", "", text.replace(str(run), ""))
        if shifted:
            text = re.sub(r"\bline (\d+)", lambda m: f"line {max(1, int(m.group(1)) - 1)}", text)
        errors.append(text.strip())
    return [e for e in errors if e]


def join_split_strings(code: str) -> str:
    """A string the model broke across lines (it wrote a real newline where it meant \\n): one line again."""
    out: list[str] = []
    pending = ""
    for line in code.split("\n"):
        text = pending + line if pending else line
        if _open_string(text):
            pending = text + "\\n"
            continue
        out.append(text)
        pending = ""
    if pending:
        out.append(pending[:-2])
    return "\n".join(out)


def _open_string(line: str) -> bool:
    """Does this line end inside a quoted string? (a' is a transpose; % and # start comments)"""
    quote, prev = "", ""
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == quote:
                if line[i + 1:i + 2] == quote:       # '' or "" inside a string
                    i += 2
                    continue
                quote = ""
        elif ch in "%#":
            return False
        elif ch == '"' or (ch == "'" and not (prev.isalnum() or prev in "_)]}.'")):
            quote = ch
        prev = ch if quote == "" or ch != quote else prev
        i += 1
    return bool(quote)


def _clean(out: str | None) -> str:
    """MATLAB's and Octave's printed output, without blank runs, cut to a readable size."""
    text = re.sub(r"\n{3,}", "\n\n", (out or "").replace("\r\n", "\n")).strip()
    return text if len(text) <= OUTPUT_CHARS else text[:OUTPUT_CHARS] + "\n[... cut]"
