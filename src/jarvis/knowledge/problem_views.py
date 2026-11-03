"""The animations of a worked problem (problems.py): tested drawings that take their numbers from SymPy.

The model chooses a view and writes its numbers as symbols or expressions ("a1", "-mu*g", "v1/2"); they are
worked out here with the problem's values, so the animation and the solution can't disagree. The window
draws them (ui/problem.js). A view that can't be made is dropped, with a note.

  motion          bodies along a road in phases (accelerate, constant speed, brake with ABS or locked
                  wheels), with s-t, v-t and a-t graphs; or a path in 2D (x(t), y(t)): projectiles, circles,
                  oscillations
  graph           curves y = f(x) with points, the area under a curve, a tangent, Newton's method,
                  Euler's method, Riemann sums and the trapezium rule
  forces          a free-body diagram, on the flat or on a slope, with components
  circuit         resistors in series and parallel with a battery: every current and voltage
  kinetics        [A] against time for zero, first and second order, half-lives, particles reacting
  titration       the pH curve of an acid or a base titrated, the equivalence point, an indicator
  energy_profile  reactants, transition state and products, with Ea, delta H and a catalyst's path
  ice             an equilibrium's ICE table (initial, change, equilibrium) and its K
  lesson          any visual of the lessons (a scene, a plot, a formula, a diagram, a picture)
"""

from __future__ import annotations

import math
from typing import Any

from .problems import Problem, ProblemError, _parse, show_number

LOOKS = ("car", "truck", "bike", "train", "ball", "box", "person", "rocket")


def view_catalog() -> str:
    return """  {"motion": {"bodies": [{"name": "car", "look": "car|truck|bike|train|ball|box|person|rocket", "start": 0,
     "u": 0, "t0": 0, "phases": [{"label": "accelerates", "a": "a1", "duration": "t1"},
     {"label": "constant speed", "a": 0, "duration": "t2"},
     {"label": "brakes (ABS)", "a": "-a3", "until": "stop", "abs": true}]}], "graphs": ["v", "s", "a"]}}
     A phase ends after "duration", or "until": "stop", or at speed "v", or after "distance". "abs": true pulses
     the brakes (no skid); "locked": true leaves skid marks. Two bodies show catching up or overtaking.
     highlight: {"t": "t1"} stops the animation at that time; {"phase": 2} lights a phase; {"area": ["t1", "T2"],
     "graph": "v"} shades the area under v-t (the distance); {"point": "t1", "graph": "v"} marks a value.
  {"motion": {"path": {"x": "u*cos(rad(th))*t", "y": "u*sin(rad(th))*t - g*t^2/2", "t1": "T", "look": "ball"},
     "graphs": ["x", "y", "vx", "vy"]}}   a 2D path over time t from 0 to t1 (projectiles, circular motion, SHM)
  {"graph": {"curves": [{"y": "x^2 - 2", "label": "f(x)"}], "x": [-1, 3], "xlabel": "x", "ylabel": "y",
     "points": [["x1", "", "root"]], "area": {"curve": 0, "from": 0, "to": 2},
     "tangent": {"curve": 0, "at": "x0"}, "newton": {"curve": 0, "x0": 1, "steps": 4},
     "euler": {"dy": "x + y", "x0": 0, "y0": 1, "h": 0.2, "steps": 5, "exact": "2*exp(x) - x - 1"},
     "riemann": {"curve": 0, "from": 0, "to": 2, "n": 6, "rule": "left|right|mid|trapezium"}}}
     Use any of points, area, tangent, newton, euler, riemann. highlight: {"show": ["area", "tangent"]} or
     {"newton_step": 2} or {"euler_step": 3} or {"x": "x1"}. Curves may use the problem's symbols.
  {"forces": {"surface": "flat|incline", "angle": "theta", "body": "box|car|person", "forces": [{"name": "weight",
     "symbol": "W", "value": "m*g", "dir": "down"}, {"name": "normal", "symbol": "N", "value": "N1", "dir": "normal"},
     {"name": "friction", "symbol": "f", "value": "f1", "dir": "along_down"}], "components": true}}
     dir: down, up, left, right, normal, along_up, along_down, or an angle in degrees. highlight: {"force": "friction"}
     or {"components": true}.
  {"circuit": {"V": "V", "r": 0, "network": {"series": [{"R": "R1", "name": "R1"}, {"parallel": [{"R": "R2",
     "name": "R2"}, {"R": "R3", "name": "R3"}]}]}}}   highlight: {"element": "R2"}
  {"kinetics": {"order": 1, "k": "k", "A0": "A0", "t1": "T", "species": "A", "plot": "A|lnA|invA"}}
     highlight: {"t": "t_half"} or {"half_lives": true}
  {"titration": {"analyte": "weak_acid|strong_acid|weak_base|strong_base", "C": "Ca", "V": "Va", "K": "Ka",
     "titrant_C": "Cb", "V_max": 50, "indicator": "phenolphthalein|methyl_orange|none"}}   volumes in mL, K is Ka
     (or Kb for a weak base). highlight: {"V": "Veq"} or {"half": true} or {"equivalence": true}
  {"energy_profile": {"Ea": "Ea", "dH": "dH", "Ea_cat": "", "unit": "kJ/mol", "reactants": "A + B",
     "products": "C"}}   highlight: {"show": ["Ea", "dH", "catalyst"]}
  {"ice": {"species": [{"name": "N2", "coef": 1, "side": "reactant", "initial": 1.0}, {"name": "NH3", "coef": 2,
     "side": "product", "initial": 0}], "x": "x1", "unit": "mol/L"}}   highlight: {"row": "change|equilibrium"}
  {"lesson": {"scene": "pendulum", "params": {"length": 2}}} or {"lesson": {"plot": ["sin(x)"], "from": 0, "to": 6}}
     or {"lesson": {"diagram": "flowchart LR ..."}} or {"lesson": {"formula": "..."}}: a visual from the lessons
     (scenes: gas_box, waves_3d, string_wave, pendulum, projectile, rc_circuit, fourier, field_3d, orbit, lens).
""" + MORE_CATALOG


class _Num:
    """Numbers in a view: a number, or an expression of the problem's values."""

    def __init__(self, problem: Problem):
        self.values = problem.values

    def __call__(self, value: Any, default: float | None = None) -> float:
        if value is None or value == "":
            if default is None:
                raise ProblemError("a number is missing")
            return default
        if isinstance(value, bool):
            raise ProblemError("a number is missing")
        if isinstance(value, int | float):
            out = float(value)
        else:
            import sympy
            expr = _parse(str(value), self.values)
            if isinstance(expr, sympy.Basic) and expr.free_symbols:
                raise ProblemError(f"{value!r} isn't a number here")
            out = float(sympy.N(expr))
        if not math.isfinite(out):
            raise ProblemError(f"{value!r} isn't finite")
        return out

    def curve(self, text: str, var: str = "x"):
        """y = f(x) with the problem's values: a function of one number (math, not Python's eval)."""
        import sympy
        expr = _parse(str(text), self.values)
        x = sympy.Symbol(var)
        extra = [s for s in getattr(expr, "free_symbols", set()) if s != x]
        if extra:
            raise ProblemError(f"{text!r} has unknown names: {', '.join(map(str, extra))}")
        f = sympy.lambdify(x, expr, modules=["math"])

        def safe(v: float) -> float | None:
            try:
                y = complex(f(v))
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                return None
            return y.real if abs(y.imag) < 1e-9 and math.isfinite(y.real) else None
        return safe, expr

    def highlight(self, h: dict) -> dict:
        """A step's highlight with its numbers worked out (strings that are names or expressions)."""
        out: dict[str, Any] = {}
        for key, value in list(h.items())[:8]:
            key = str(key)[:20]
            if key in ("t", "x", "V", "point"):
                try:
                    out[key] = self(value)
                except ProblemError:
                    continue
            elif key == "area" and isinstance(value, list) and len(value) == 2:
                try:
                    out[key] = [self(value[0]), self(value[1])]
                except ProblemError:
                    continue
            elif isinstance(value, bool | int | float):
                out[key] = value
            elif isinstance(value, str):
                out[key] = value[:40]
            elif isinstance(value, list):
                out[key] = [str(v)[:20] for v in value[:6]]
        return out


# ---- motion -----------------------------------------------------------------------------------------
def _phase_time(ph: dict, u: float, a: float, n: _Num) -> float:
    if ph.get("duration") not in (None, ""):
        return n(ph["duration"])
    if ph.get("until") == "stop":
        if a == 0 or u == 0 or u * a > 0:
            raise ProblemError("a phase 'until stop' needs a speed and a deceleration against it")
        return -u / a
    if ph.get("v") not in (None, ""):
        v = n(ph["v"])
        if a == 0:
            raise ProblemError("a phase to a speed needs an acceleration")
        return (v - u) / a
    if ph.get("distance") not in (None, ""):
        d = n(ph["distance"])
        if a == 0:
            if u == 0:
                raise ProblemError("never gets there")
            return d / u
        disc = u * u + 2 * a * d
        if disc < 0:
            raise ProblemError("never covers that distance")
        roots = [(-u + s * math.sqrt(disc)) / a for s in (1, -1)]
        good = [r for r in roots if r > 0]
        if not good:
            raise ProblemError("never covers that distance")
        return min(good)
    raise ProblemError("a phase needs a duration, 'until': 'stop', a speed or a distance")


def _motion(spec: dict, n: _Num) -> dict:
    graphs = [g for g in (spec.get("graphs") or []) if g in ("s", "v", "a", "x", "y", "vx", "vy")][:4]
    if isinstance(spec.get("path"), dict):
        return _path(spec["path"], graphs or ["x", "y"], n)
    bodies = []
    for b in (spec.get("bodies") or [])[:3]:
        if not isinstance(b, dict):
            continue
        s, u, t = n(b.get("start"), 0.0), n(b.get("u"), 0.0), n(b.get("t0"), 0.0)
        phases = []
        for ph in (b.get("phases") or [])[:6]:
            if not isinstance(ph, dict):
                continue
            a = n(ph.get("a"), 0.0)
            d = _phase_time(ph, u, a, n)
            if not 0 < d < 1e6:
                raise ProblemError(f"a phase lasts {d:g} s")
            phases.append({"label": str(ph.get("label") or "")[:40], "t0": t, "t1": t + d, "a": a, "u": u, "s0": s,
                           "abs": bool(ph.get("abs")), "locked": bool(ph.get("locked"))})
            s, u, t = s + u * d + a * d * d / 2, u + a * d, t + d
        if phases:
            look = str(b.get("look") or "car")
            bodies.append({"name": str(b.get("name") or look)[:30], "look": look if look in LOOKS else "car",
                           "phases": phases, "end": t, "s_end": s, "v_end": u,
                           "start": phases[0]["s0"], "t0": phases[0]["t0"]})
    if not bodies:
        raise ProblemError("a motion view needs a body with phases, or a path")
    T = max(b["end"] for b in bodies)
    lo = min(min(b["start"], b["s_end"]) for b in bodies)
    hi = max(max(b["start"], b["s_end"], *(p["s0"] for p in b["phases"])) for b in bodies)
    vmax = max(abs(p["u"] + p["a"] * (p["t1"] - p["t0"])) for b in bodies for p in b["phases"])
    vmax = max(vmax, max(abs(p["u"]) for b in bodies for p in b["phases"]))
    return {"kind": "motion", "T": T, "bodies": bodies, "graphs": graphs or ["v", "s"], "s_range": [lo, hi],
            "v_max": vmax, "a_max": max(abs(p["a"]) for b in bodies for p in b["phases"]) or 1.0,
            "units": {"s": "m", "v": "m/s", "a": "m/s²", "t": "s"}}


def _path(p: dict, graphs: list[str], n: _Num) -> dict:
    import sympy
    t = sympy.Symbol("t")
    xs, ys = _parse(str(p.get("x", "0")), n.values), _parse(str(p.get("y", "0")), n.values)
    for e in (xs, ys):
        if isinstance(e, sympy.Basic) and (e.free_symbols - {t}):
            raise ProblemError("a path may only use t and the problem's values")
    T = n(p.get("t1"))
    if not 0 < T < 1e6:
        raise ProblemError("the path's time must be positive")
    fx, fy = (sympy.lambdify(t, sympy.sympify(e), modules=["math"]) for e in (xs, ys))
    dfx, dfy = (sympy.lambdify(t, sympy.diff(sympy.sympify(e), t), modules=["math"]) for e in (xs, ys))
    N = 240
    times = [T * i / (N - 1) for i in range(N)]
    try:
        pts = [[float(fx(ti)), float(fy(ti)), float(dfx(ti)), float(dfy(ti))] for ti in times]
    except (ValueError, ZeroDivisionError, OverflowError, TypeError) as exc:
        raise ProblemError(f"the path can't be drawn: {type(exc).__name__}") from None
    look = str(p.get("look") or "ball")
    return {"kind": "path", "T": T, "times": times, "points": pts, "look": look if look in LOOKS else "ball",
            "graphs": [g for g in graphs if g in ("x", "y", "vx", "vy")] or ["x", "y"],
            "ground": bool(p.get("ground", True)), "units": {"x": "m", "y": "m", "t": "s"}}


# ---- graphs (maths) ------------------------------------------------------------------------------------
def _graph(spec: dict, n: _Num) -> dict:
    import sympy
    x0, x1 = (spec.get("x") or [-5, 5])[:2] if isinstance(spec.get("x"), list) else (-5, 5)
    lo, hi = n(x0), n(x1)
    if not lo < hi:
        raise ProblemError("the graph's range must go from small to large")
    curves, fns = [], []
    for c in (spec.get("curves") or [])[:4]:
        c = c if isinstance(c, dict) else {"y": c}
        f, expr = n.curve(str(c.get("y", "")))
        N = 360
        pts = [[lo + (hi - lo) * i / (N - 1), f(lo + (hi - lo) * i / (N - 1))] for i in range(N)]
        curves.append({"label": str(c.get("label") or c.get("y"))[:40], "points": pts})
        fns.append((f, expr))
    if not curves and not isinstance(spec.get("euler"), dict):
        raise ProblemError("a graph needs a curve")
    out: dict[str, Any] = {"kind": "graph", "x": [lo, hi], "curves": curves, "xlabel": str(spec.get("xlabel") or "x")[:30],
                           "ylabel": str(spec.get("ylabel") or "y")[:30], "annotations": {}}
    ann = out["annotations"]

    def curve_of(d: dict) -> tuple:
        i = int(d.get("curve", 0)) if str(d.get("curve", 0)).isdigit() else 0
        if not 0 <= i < len(fns):
            raise ProblemError("that curve isn't on the graph")
        return i, fns[i]
    pts = []
    for p in (spec.get("points") or [])[:8]:
        if isinstance(p, list) and p:
            try:
                px = n(p[0])
                py = n(p[1]) if len(p) > 1 and p[1] not in (None, "") else (fns[0][0](px) if fns else None)
            except ProblemError:
                continue
            if py is not None:
                py = 0.0 if abs(py) < 1e-9 * max(1.0, abs(px)) else py      # a root's y is 0, not -8.9e-16
                pts.append([px, py, str(p[2])[:30] if len(p) > 2 else ""])
    if pts:
        ann["points"] = pts
    x = sympy.Symbol("x")
    if isinstance(spec.get("area"), dict):
        i, (f, expr) = curve_of(spec["area"])
        a, b = n(spec["area"].get("from")), n(spec["area"].get("to"))
        value = float(sympy.N(sympy.Integral(expr, (x, a, b))))
        ann["area"] = {"curve": i, "from": a, "to": b, "value": value, "shown": show_number(value)}
    if isinstance(spec.get("tangent"), dict):
        i, (f, expr) = curve_of(spec["tangent"])
        at = n(spec["tangent"].get("at"))
        slope = float(sympy.N(sympy.diff(expr, x).subs(x, at)))
        ann["tangent"] = {"curve": i, "at": at, "y": f(at), "slope": slope, "shown": show_number(slope)}
    if isinstance(spec.get("newton"), dict):
        i, (f, expr) = curve_of(spec["newton"])
        df = sympy.lambdify(x, sympy.diff(expr, x), modules=["math"])
        xk, steps = n(spec["newton"].get("x0")), []
        for _ in range(max(1, min(int(n(spec["newton"].get("steps"), 4)), 8))):
            fx, d = f(xk), float(df(xk))
            if fx is None or d == 0:
                break
            nxt = xk - fx / d
            steps.append({"x": xk, "y": fx, "slope": d, "next": nxt, "shown": show_number(nxt)})
            xk = nxt
        ann["newton"] = {"curve": i, "steps": steps}
    if isinstance(spec.get("euler"), dict):
        e = spec["euler"]
        y = sympy.Symbol("y")
        dy = _parse(str(e.get("dy", "")), n.values)
        if not isinstance(dy, sympy.Basic) or dy.free_symbols - {x, y}:
            raise ProblemError("Euler's dy may only use x, y and the problem's values")
        g = sympy.lambdify((x, y), dy, modules=["math"])
        xi, yi, h = n(e.get("x0")), n(e.get("y0")), n(e.get("h"))
        pts_e = [[xi, yi]]
        for _ in range(max(1, min(int(n(e.get("steps"), 5)), 40))):
            yi, xi = yi + h * float(g(xi, yi)), xi + h
            pts_e.append([xi, yi])
        ann["euler"] = {"points": pts_e, "h": h}
        if e.get("exact"):
            fe, _ = n.curve(str(e["exact"]))
            N = 200
            out["curves"].append({"label": "exact", "points": [[lo + (hi - lo) * k / (N - 1),
                                                                fe(lo + (hi - lo) * k / (N - 1))] for k in range(N)]})
    if isinstance(spec.get("riemann"), dict):
        r = spec["riemann"]
        i, (f, expr) = curve_of(r)
        a, b, m = n(r.get("from")), n(r.get("to")), max(1, min(int(n(r.get("n"), 6)), 60))
        rule = str(r.get("rule") or "left")
        rule = rule if rule in ("left", "right", "mid", "trapezium") else "left"
        w, bars, total = (b - a) / m, [], 0.0
        for k in range(m):
            xa, xb = a + k * w, a + (k + 1) * w
            ya, yb = f(xa), f(xb)
            if ya is None or yb is None:
                raise ProblemError("the curve isn't defined over the whole sum")
            if rule == "trapezium":
                area, hgt = (ya + yb) / 2 * w, [ya, yb]
            else:
                xm = {"left": xa, "right": xb, "mid": (xa + xb) / 2}[rule]
                ym = f(xm)
                area, hgt = ym * w, [ym, ym]
            bars.append([xa, xb, *hgt])
            total += area
        exact = float(sympy.N(sympy.Integral(expr, (x, a, b))))
        ann["riemann"] = {"curve": i, "rule": rule, "bars": bars, "value": total, "shown": show_number(total),
                          "exact": exact, "exact_shown": show_number(exact)}
    ys = [p[1] for c in out["curves"] for p in c["points"] if p[1] is not None]
    ys += [p[1] for p in ann.get("euler", {}).get("points", [])]
    if ys:
        ys.sort()
        cut = max(0, len(ys) // 50)                       # leave out the extremes of an asymptote
        y_lo, y_hi = ys[cut], ys[-1 - cut]
        pad = (y_hi - y_lo) * 0.1 or 1.0
        out["y"] = [min(y_lo - pad, 0) if y_lo >= 0 and y_lo < pad * 3 else y_lo - pad, y_hi + pad]
    return out


# ---- forces --------------------------------------------------------------------------------------------
DIRS = {"down": 270, "up": 90, "left": 180, "right": 0}


def _forces(spec: dict, n: _Num) -> dict:
    incline = str(spec.get("surface") or "flat") == "incline"
    angle = n(spec.get("angle"), 0.0) if incline else 0.0
    if not 0 <= angle < 90:
        raise ProblemError("the slope's angle must be 0 to 90 degrees")
    forces = []
    for f in (spec.get("forces") or [])[:7]:
        if not isinstance(f, dict):
            continue
        d = str(f.get("dir") or "down")
        if d in DIRS:
            direction = DIRS[d]
        elif d == "normal":
            direction = 90 + angle
        elif d == "along_up":
            direction = angle
        elif d == "along_down":
            direction = 180 + angle
        else:
            direction = n(d)
        try:
            value: float | None = n(f.get("value"), 0.0)
            shown = show_number(abs(value))
        except ProblemError:                 # "m*g" with no mass given: drawn with its symbol, no number
            value, shown = None, str(f.get("value") or "")[:16]
        forces.append({"name": str(f.get("name") or "")[:24], "symbol": str(f.get("symbol") or "")[:8],
                       "value": value, "shown": shown, "angle": direction % 360})
    if not forces:
        raise ProblemError("a force diagram needs forces")
    look = str(spec.get("body") or "box")
    return {"kind": "forces", "incline": incline, "angle": angle, "forces": forces,
            "body": look if look in LOOKS else "box", "components": bool(spec.get("components")), "unit": "N"}


# ---- circuits --------------------------------------------------------------------------------------------
def _net(node: Any, n: _Num, names: set[str]) -> dict:
    if not isinstance(node, dict):
        raise ProblemError("a circuit element must be an object")
    if "R" in node:
        name = str(node.get("name") or node["R"])[:12]
        if name in names:
            name = f"{name}'"
        names.add(name)
        r = n(node["R"])
        if r < 0:
            raise ProblemError("a negative resistance")
        return {"type": "R", "name": name, "R": r}
    for kind in ("series", "parallel"):
        if isinstance(node.get(kind), list) and node[kind]:
            kids = [_net(k, n, names) for k in node[kind][:6]]
            if kind == "series":
                total = sum(k["R"] for k in kids)
            else:
                if any(k["R"] == 0 for k in kids):
                    total = 0.0
                else:
                    total = 1 / sum(1 / k["R"] for k in kids)
            return {"type": kind, "kids": kids, "R": total}
    raise ProblemError("a circuit element needs R, series or parallel")


def _flow(node: dict, current: float, out: list) -> None:
    node["I"], node["V"] = current, current * node["R"]
    if node["type"] == "R":
        out.append({"name": node["name"], "R": node["R"], "I": current, "V": node["V"],
                    "shown": f"{show_number(current)} A, {show_number(node['V'])} V"})
    elif node["type"] == "series":
        for k in node["kids"]:
            _flow(k, current, out)
    else:
        for k in node["kids"]:
            _flow(k, node["V"] / k["R"] if k["R"] else current, out)


def _circuit(spec: dict, n: _Num) -> dict:
    V, r = n(spec.get("V")), n(spec.get("r"), 0.0)
    tree = _net(spec.get("network"), n, set())
    total = tree["R"] + r
    if total <= 0:
        raise ProblemError("a short circuit")
    current = V / total
    elements: list[dict] = []
    _flow(tree, current, elements)
    return {"kind": "circuit", "V": V, "r": r, "tree": tree, "I": current, "R_total": total,
            "elements": elements, "shown": f"I = {show_number(current)} A, R = {show_number(total)} Ω"}


# ---- chemistry ---------------------------------------------------------------------------------------------
def _kinetics(spec: dict, n: _Num) -> dict:
    order = int(n(spec.get("order"), 1))
    if order not in (0, 1, 2):
        raise ProblemError("order 0, 1 or 2")
    k, A0 = n(spec.get("k")), n(spec.get("A0"))
    if k <= 0 or A0 <= 0:
        raise ProblemError("k and [A]0 must be positive")
    half = {0: A0 / (2 * k), 1: math.log(2) / k, 2: 1 / (k * A0)}[order]
    T = n(spec.get("t1"), 0.0) or ({0: A0 / k, 1: 4 * half, 2: 7 * half}[order])
    plot = str(spec.get("plot") or "A")
    return {"kind": "kinetics", "order": order, "k": k, "A0": A0, "T": T, "half_life": half,
            "half_shown": show_number(half), "species": str(spec.get("species") or "A")[:12],
            "plot": plot if plot in ("A", "lnA", "invA") else "A"}


def _ph(h_total: float, cations: float, anions_of, kw: float = 1e-14) -> float:
    """pH from the charge balance h + cations = Kw/h + anions(h), by bisection on log h."""
    lo, hi = -15.0, 1.5
    for _ in range(80):
        mid = (lo + hi) / 2
        h = 10 ** mid
        if h + cations - kw / h - anions_of(h) > 0:
            hi = mid
        else:
            lo = mid
    return -(lo + hi) / 2


def _titration(spec: dict, n: _Num) -> dict:
    kind = str(spec.get("analyte") or "weak_acid")
    if kind not in ("weak_acid", "strong_acid", "weak_base", "strong_base"):
        raise ProblemError("analyte: weak_acid, strong_acid, weak_base or strong_base")
    C, V, Ct = n(spec.get("C")), n(spec.get("V")), n(spec.get("titrant_C"))
    K = n(spec.get("K"), 0.0) if kind.startswith("weak") else 0.0
    if min(C, V, Ct) <= 0 or (kind.startswith("weak") and K <= 0):
        raise ProblemError("concentrations, the volume and K must be positive")
    v_eq = C * V / Ct
    v_max = n(spec.get("V_max"), 0.0) or 2 * v_eq
    kw = 1e-14
    curve = []
    for i in range(241):
        vt = v_max * i / 240
        total = V + vt
        c_an, c_ti = C * V / total, Ct * vt / total
        if kind == "weak_acid":
            ph = _ph(0, c_ti, lambda h, c=c_an: c * K / (K + h))
        elif kind == "strong_acid":
            ph = _ph(0, c_ti, lambda h, c=c_an: c)
        elif kind == "weak_base":
            ka = kw / K
            ph = _ph(0, 0, lambda h, c_an=c_an, c_ti=c_ti, ka=ka: c_ti - c_an * h / (h + ka))
        else:
            ph = _ph(0, c_an, lambda h, c=c_ti: c)
        curve.append([vt, ph])
    ind = str(spec.get("indicator") or "none")
    out = {"kind": "titration", "analyte": kind, "C": C, "V": V, "titrant_C": Ct, "K": K, "V_eq": v_eq,
           "V_eq_shown": show_number(v_eq), "V_max": v_max, "curve": curve,
           "indicator": ind if ind in ("phenolphthalein", "methyl_orange", "none") else "none"}
    out["pH_eq"] = min(curve, key=lambda p: abs(p[0] - v_eq))[1]
    if kind.startswith("weak"):
        out["pK"] = -math.log10(K)
        out["pH_half"] = out["pK"] if kind == "weak_acid" else 14 + math.log10(K)
    return out


def _energy(spec: dict, n: _Num) -> dict:
    Ea, dH = n(spec.get("Ea")), n(spec.get("dH"))
    if Ea <= 0 or Ea <= dH:
        raise ProblemError("Ea must be positive and above the products")
    cat = n(spec.get("Ea_cat"), 0.0)
    return {"kind": "energy_profile", "Ea": Ea, "dH": dH, "Ea_cat": cat if 0 < cat < Ea else 0.0,
            "unit": str(spec.get("unit") or "kJ/mol")[:12], "reactants": str(spec.get("reactants") or "reactants")[:40],
            "products": str(spec.get("products") or "products")[:40]}


def _ice(spec: dict, n: _Num) -> dict:
    x = n(spec.get("x"))
    rows, kp, kr = [], 1.0, 1.0
    for s in (spec.get("species") or [])[:6]:
        if not isinstance(s, dict):
            continue
        coef = n(s.get("coef"), 1.0)
        side = "product" if str(s.get("side")) == "product" else "reactant"
        initial = n(s.get("initial"), 0.0)
        change = coef * x * (1 if side == "product" else -1)
        eq = initial + change
        if eq < -1e-12:
            raise ProblemError(f"{s.get('name')} would go below zero")
        rows.append({"name": str(s.get("name") or "")[:16], "coef": coef, "side": side, "initial": initial,
                     "change": change, "eq": max(eq, 0.0)})
        if side == "product":
            kp *= max(eq, 0.0) ** coef
        else:
            kr *= max(eq, 0.0) ** coef
    if not rows:
        raise ProblemError("an ICE table needs species")
    K = kp / kr if kr > 0 else None
    return {"kind": "ice", "rows": rows, "x": x, "K": K, "K_shown": show_number(K) if K is not None else "",
            "unit": str(spec.get("unit") or "mol/L")[:12]}


def _lesson(spec: dict, problem: Problem) -> dict:
    from .lessons import Lesson, _visual, resolve
    from .lessons import Step as LessonStep
    notes: list[str] = []
    if "sketch" in spec:
        raise ProblemError("no model-drawn sketches in problems: only tested visuals")
    visual = _visual(spec, notes)
    if visual is None:
        raise ProblemError("; ".join(notes) or "not a lesson visual")
    lesson = resolve(Lesson("view", [LessonStep("", visual)]))
    if lesson.steps[0].visual is None:
        raise ProblemError("; ".join(lesson.notes) or "the visual couldn't be made")
    return {"kind": "lesson", "visual": lesson.steps[0].visual}


BUILDERS = {"motion": _motion, "graph": _graph, "forces": _forces, "circuit": _circuit, "kinetics": _kinetics,
            "titration": _titration, "energy_profile": _energy, "ice": _ice}
from .problem_views_more import MORE_BUILDERS, MORE_CATALOG  # noqa: E402 - after _Num and the builders above

BUILDERS.update(MORE_BUILDERS)


def build_views(problem: Problem) -> dict[str, dict]:
    """Each view's data for the window, and each step's highlight with its numbers worked out."""
    n = _Num(problem)
    shown: dict[str, dict] = {}
    for name, spec in problem.views.items():
        kind = next((k for k in (*BUILDERS, "lesson") if k in spec), None)
        try:
            if kind is None:
                raise ProblemError(f"no known view in {', '.join(list(spec)[:3])}")
            data = _lesson(spec[kind], problem) if kind == "lesson" else BUILDERS[kind](
                spec[kind] if isinstance(spec[kind], dict) else {}, n)
            shown[name] = data
        except (ProblemError, ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            problem.notes.append(f"view {name}: {exc}"[:160])
    for part in problem.parts:
        for step in part.steps:
            if step.view not in shown:
                step.view = ""
            step.highlight = n.highlight(step.highlight) if step.highlight else {}
    problem.shown_views = shown
    cross_check(problem)
    return shown




# ---- the answers against the animations --------------------------------------------------------------------
def view_facts(data: dict) -> list[tuple[float, str, str]]:
    """What a view works out itself, as (value, unit, what it is): the numbers an answer can be checked
    against. A view with nothing of its own to compare (a force diagram of symbols) has none."""
    k, out = data.get("kind"), []
    add = out.append
    if k == "motion":
        for b in data["bodies"]:
            for p in b["phases"]:
                d = p["t1"] - p["t0"]
                add((d, "s", f"{p['label']}: time"))
                add((p["u"] * d + p["a"] * d * d / 2, "m", f"{p['label']}: distance"))
                add((p["u"] + p["a"] * d, "m/s", f"{p['label']}: speed at the end"))
                add((p["u"], "m/s", f"{p['label']}: speed at the start"))
                add((p["s0"] + p["u"] * d + p["a"] * d * d / 2 - b["start"], "m", f"distance up to the end of {p['label']}"))
                add((p["t1"], "s", f"time at the end of {p['label']}"))
                add((p["a"], "m/s^2", f"{p['label']}: acceleration"))
            total_t = b["end"] - b["t0"]
            add((b["s_end"] - b["start"], "m", f"{b['name']}: total distance"))
            add((total_t, "s", f"{b['name']}: total time"))
            if total_t > 0:
                add(((b["s_end"] - b["start"]) / total_t, "m/s", f"{b['name']}: average speed"))
    elif k == "path":
        pts = data["points"]
        add((max(p[1] for p in pts), "m", "greatest height"))
        add((pts[-1][0] - pts[0][0], "m", "distance across"))
        add((data["T"], "s", "time of flight"))
        add((math.hypot(pts[-1][2], pts[-1][3]), "m/s", "speed at the end"))
    elif k == "titration":
        add((data["V_eq"], "mL", "equivalence volume"))
        add((data["pH_eq"], "", "pH at equivalence"))
        add((data["curve"][0][1], "", "pH at the start"))
        if "pH_half" in data:
            add((data["pH_half"], "", "pH half-way"))
    elif k == "circuit":
        add((data["R_total"], "ohm", "total resistance"))
        add((data["I"], "A", "current from the battery"))
        add((data["I"] * data["r"], "V", "voltage lost inside the battery"))
        add((data["V"] - data["I"] * data["r"], "V", "terminal voltage"))
        for e in data["elements"]:
            add((e["I"], "A", f"current in {e['name']}"))
            add((e["V"], "V", f"voltage across {e['name']}"))
        stack = [data["tree"]]
        while stack:
            node = stack.pop()
            if node["type"] != "R":
                add((node["R"], "ohm", f"resistance of a {node['type']} group"))
                add((node["V"], "V", f"voltage across a {node['type']} group"))
                stack.extend(node["kids"])
    elif k == "kinetics":
        add((data["half_life"], "s", "half-life"))
    elif k == "energy_profile":
        add((data["Ea"], "kJ/mol", "activation energy"))
        add((data["dH"], "kJ/mol", "enthalpy change"))
        add((data["Ea"] - data["dH"], "kJ/mol", "activation energy of the reverse reaction"))
    elif k == "ice":
        if data.get("K") is not None:
            add((data["K"], "", "equilibrium constant"))
        for r in data["rows"]:
            add((r["eq"], "mol/L", f"{r['name']} at equilibrium"))
    elif k == "graph":
        a = data.get("annotations", {})
        for key, label in (("area", "area"), ("riemann", "the rule's estimate"), ("tangent", "slope")):
            if key in a:
                add((a[key].get("value", a[key].get("slope")), "", label))
        if a.get("newton", {}).get("steps"):
            add((a["newton"]["steps"][-1]["next"], "", "Newton's root"))
        if "riemann" in a:
            add((a["riemann"]["exact"], "", "the exact area"))
    elif k == "quantum":
        for e in data.get("E_eV", []):
            add((e, "eV", "an energy level"))
        for e in data.get("E", []):
            add((e, "J", "an energy level"))
        if "T" in data:
            add((data["T"], "", "transmission"))
            add((data["R"], "", "reflection"))
        if "transition" in data:
            add((data["transition"]["wavelength"], "m", "the photon's wavelength"))
            add((data["transition"]["dE_eV"], "eV", "the photon's energy"))
    elif k == "minkowski":
        add((data["gamma"], "", "gamma"))
        for e in data["events"]:
            add((e["x2"], data["unit"], f"{e['name']}: x'"))
            add((e["ct2"], data["unit"], f"{e['name']}: ct'"))
        for w in data["worldlines"]:
            add((w["tau"], data["unit"], f"{w['name']}: proper time"))
    elif k == "black_hole":
        add((data["rs"], "m", "Schwarzschild radius"))
        add((data["T_hawking"], "K", "Hawking temperature"))
    elif k == "matrix":
        add((data["det"], "", "determinant"))
        for e in data["eigen"]:
            add((e["value"], "", "an eigenvalue"))
    elif k in ("distribution",):
        add((data["prob"], "", "the probability"))
    elif k == "montecarlo":
        add((data["exact"], "", "the exact value"))
    elif k == "qcircuit":
        for p in data["states"][-1]["probs"]:
            add((p, "", "a measurement probability"))
    for f in data.get("facts", []):                        # a view of the newer kinds lists its own
        add(tuple(f))
    return [f for f in out if isinstance(f[0], int | float) and math.isfinite(f[0])]


def cross_check(problem: Problem, rel: float = 0.01) -> None:
    """Each part's answer against the views its steps show: it agrees when the animation worked out the same
    number itself; it doesn't when the animation has numbers of the same kind and none is this one."""
    from .dimensions import dims
    for part in problem.parts:
        ans = problem.answer_of(part)
        value = ans.get("value") if ans else None
        names = {s.view for s in part.steps if s.view}
        if value is None or not names:
            continue
        unit = ans.get("unit") or part.unit
        want = dims(unit)
        facts = [f for n in names for f in view_facts(problem.shown_views.get(n, {}))]
        same = [f for f in facts if want is not None and dims(f[1]) == want]
        close = [f for f in same if abs(f[0] - value) <= max(abs(value) * rel, 1e-12)]
        hit = min(close, key=lambda f: abs(f[0] - value)) if close else None
        if hit is not None:
            ans["view_check"] = {"ok": True, "said": f"the animation agrees: {hit[2]}"}
        elif same:
            near = min(same, key=lambda f: abs(f[0] - value))
            ans["view_check"] = {"ok": False, "said": f"the animation shows {show_number(near[0])} {near[1]} for "
                                                     f"{near[2]}, not {ans.get('shown')}"}
            problem.notes.append(f"({part.id}) the answer {ans.get('shown')} {unit} isn't what the animation works out "
                                 f"({show_number(near[0])} {near[1]}, {near[2]}): the view or the steps are set up wrong")


__all__ = ["BUILDERS", "LOOKS", "build_views", "cross_check", "view_catalog", "view_facts"]
