"""Units checked through a worked problem's steps (problems.py): a set-up error usually shows up as wrong units.

    dims("m/s^2")            -> (1, 0, -2, 0, 0, 0)       length, mass, time, current, temperature, amount
    dims("J/(mol K)")        -> (2, 1, -2, 0, -1, -1)
    dims("furlong")          -> None                      not known: that step isn't checked

How the check works, without SymPy's unit objects (which don't survive solve() and its roots): every
given value is multiplied by a made-up scale for each base dimension (metres 1.7 times bigger, seconds 0.6
times...), and the whole chain of steps is worked out again. A step whose result has the units it says,
say m/s, comes out scaled by exactly 1.7 / 0.6; one that doesn't (a "speed" that is really m*s) comes out
scaled by something else. Twice, with different scales, so a coincidence can't pass. Steps with log, exp
or trig are left out: chemistry takes the log of a concentration by convention.
"""

from __future__ import annotations

import math
import re
from typing import Any

Dims = tuple[int, int, int, int, int, int]          # L, M, T, I, K (temperature), N (amount)
NONE: Dims = (0, 0, 0, 0, 0, 0)


def _d(L=0, M=0, T=0, I=0, K=0, N=0) -> Dims:
    return (L, M, T, I, K, N)


ENERGY, PRESSURE, POWER = _d(2, 1, -2), _d(-1, 1, -2), _d(2, 1, -3)
UNITS: dict[str, Dims] = {
    # length, mass, time, current, temperature, amount
    **{u: _d(L=1) for u in ("m", "km", "cm", "mm", "nm", "um", "μm", "pm", "ly", "AU", "au", "pc", "ft", "mi", "in")},
    **{u: _d(M=1) for u in ("kg", "g", "mg", "u", "amu", "t", "tonne")},
    **{u: _d(T=1) for u in ("s", "ms", "us", "μs", "ns", "min", "h", "hr", "hrs", "day", "days", "yr", "year", "years")},
    **{u: _d(I=1) for u in ("A", "mA", "kA")},
    **{u: _d(K=1) for u in ("K", "°C", "degC", "°F")},
    **{u: _d(N=1) for u in ("mol", "mmol", "kmol")},
    # derived
    **{u: _d(1, 1, -2) for u in ("N", "kN", "mN")},
    **{u: ENERGY for u in ("J", "kJ", "MJ", "mJ", "eV", "keV", "MeV", "GeV", "cal", "kcal", "Wh", "kWh")},
    **{u: POWER for u in ("W", "kW", "MW", "mW")},
    **{u: PRESSURE for u in ("Pa", "kPa", "MPa", "atm", "bar", "mbar", "mmHg", "torr")},
    **{u: _d(2, 1, -3, -1) for u in ("V", "mV", "kV")},
    **{u: _d(2, 1, -3, -2) for u in ("ohm", "ohms", "Ω", "kΩ", "kohm", "Mohm", "MΩ")},
    **{u: _d(T=1, I=1) for u in ("C", "mC", "μC", "uC", "nC")},
    **{u: _d(-2, -1, 4, 2) for u in ("F", "mF", "μF", "uF", "nF", "pF")},
    **{u: _d(M=1, T=-2, I=-1) for u in ("T", "mT", "μT")},              # tesla (time is "s")
    **{u: _d(2, 1, -2, -1) for u in ("Wb",)},
    **{u: _d(2, 1, -2, -2) for u in ("H", "mH")},                       # henry
    **{u: _d(T=-1) for u in ("Hz", "kHz", "MHz", "GHz", "rpm", "Bq")},
    **{u: _d(L=3) for u in ("L", "mL", "dm3", "cm3", "l", "ml")},
    **{u: _d(L=-3, N=1) for u in ("M", "mM", "molar")},
    **{u: NONE for u in ("rad", "deg", "°", "sr", "%", "dB", "rev", "cycles", "pH", "dimensionless")},
}
# Constants a problem uses under their usual names, when the model gave no unit
CONSTANTS: dict[str, Dims] = {
    "g": _d(1, 0, -2), "G": _d(3, -1, -2), "c": _d(1, 0, -1), "h": _d(2, 1, -1), "hbar": _d(2, 1, -1),
    "k_B": _d(2, 1, -2, 0, -1), "kB": _d(2, 1, -2, 0, -1), "R": _d(2, 1, -2, 0, -1, -1),
    "N_A": _d(N=-1), "NA": _d(N=-1), "e": _d(T=1, I=1), "q_e": _d(T=1, I=1), "m_e": _d(M=1), "me": _d(M=1),
    "epsilon0": _d(-3, -1, 4, 2), "eps0": _d(-3, -1, 4, 2), "mu0": _d(1, 1, -2, -2), "sigma_SB": _d(0, 1, -3, 0, -4),
}
# Equilibrium constants (Ka, Kw, Kc, Ksp, K...) are unitless by chemistry's convention (activities), which
# dimensional analysis disagrees with: steps that use one aren't checked, rather than wrongly flagged.
EQUILIBRIUM = re.compile(r"^(?:p?K(?:[a-z]{1,2}\d?|sp)?|Kw|Kc|Kp|Keq)$")
TRANSCENDENTAL = re.compile(r"\b(log|ln|log10|exp|sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|erf|nsolve)\b")
SCALES = ((1.7, 2.3, 0.6, 1.9, 1.3, 2.9), (0.55, 1.45, 2.2, 0.7, 2.6, 0.8))


def _add(a: Dims, b: Dims, sign: int = 1) -> Dims:
    return tuple(x + sign * y for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def dims(unit: str | None) -> Dims | None:
    """The dimensions of a unit as written ("m/s^2", "kg m s^-2", "J/(mol K)", "m·s⁻¹"); None if any part
    of it isn't known."""
    text = (unit or "").strip()
    if not text:
        return NONE
    for a, b in (("²", "^2"), ("³", "^3"), ("⁻¹", "^-1"), ("⁻²", "^-2"), ("⁻³", "^-3"), ("·", " "), ("⋅", " "),
                 ("*", " "), ("**", "^"), ("per ", "/ ")):
        text = text.replace(a, b)
    tokens = re.findall(r"[A-Za-zΩμ°%]+(?:\d(?![\d.]))?|\^?-?\d+|[/()]", text)
    if not tokens or "".join(tokens).replace("^", "") != re.sub(r"[\s^]", "", text):
        return None
    pos = 0

    def expr() -> Dims | None:
        nonlocal pos
        total, sign = NONE, 1
        while pos < len(tokens) and tokens[pos] != ")":
            tok = tokens[pos]
            pos += 1
            if tok == "/":
                sign = -1                              # everything after a slash divides (J/mol/K, J/(mol K))
                continue
            if tok == "(":
                inner = expr()
                pos += 1                               # the ")"
                part = inner
            elif tok == "1":
                part = NONE                            # 1/s
            elif re.fullmatch(r"\^?-?\d+", tok):
                return None                            # a number where a unit should be
            else:
                part = UNITS.get(tok)
                if part is None and tok.endswith(tuple("23")) and tok[:-1] in UNITS:
                    part = tuple(x * int(tok[-1]) for x in UNITS[tok[:-1]])   # m2, cm3
            if part is None:
                return None
            if pos < len(tokens) and re.fullmatch(r"\^?-?\d+", tokens[pos]):
                power = int(tokens[pos].lstrip("^"))
                pos += 1
                part = tuple(x * power for x in part)
            total = _add(total, part, sign)
        return total
    return expr()


def scale_of(d: Dims, scale: tuple[float, ...]) -> float:
    return math.prod(s ** e for s, e in zip(scale, d, strict=True))


def given_dims(symbol: str, unit: str) -> Dims | None:
    if not unit.strip() and symbol in CONSTANTS:
        return CONSTANTS[symbol]
    return dims(unit)


def check_units(problem: Any) -> None:
    """Mark each step's result "units": "ok" or "wrong" (or leave it unchecked), and note the wrong ones."""
    import sympy

    from .problems import ProblemError, evaluate
    known: dict[str, Dims] = {}
    unknown: set[str] = set()
    for g in problem.given:
        d = given_dims(g.symbol, g.unit)
        if d is None or EQUILIBRIUM.match(g.symbol):
            unknown.add(g.symbol)
        else:
            known[g.symbol] = d
    runs = []
    for scale in SCALES:
        values: dict[str, Any] = {g.symbol: sympy.Float(g.value * (scale_of(known[g.symbol], scale)
                                                                 if g.symbol in known else 1.0), 15)
                                  for g in problem.given}
        results = {}
        for part in problem.parts:
            for i, step in enumerate(part.steps):
                if not step.calc or not step.result.get("ok"):
                    continue
                try:
                    name, value = evaluate(step.calc, values, step.pick)
                except (ProblemError, Exception):  # noqa: BLE001 - a scaled run that fails just isn't checked
                    continue
                values[name] = value
                results[(part.id, i)] = value
        runs.append(results)
    tainted = set(unknown)
    for part in problem.parts:
        for i, step in enumerate(part.steps):
            r = step.result
            if not step.calc or not r.get("ok"):
                continue
            name = r.get("symbol", "")
            names = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", step.calc.split("=", 1)[1]))
            unit = step.unit or (part.unit if name == part.answer else "")
            want = dims(unit) if unit else None
            if names & tainted or TRANSCENDENTAL.search(step.calc) or r.get("value") in (None, 0) or want is None:
                if names & tainted or (unit and want is None):
                    tainted.add(name)                 # what comes from an unknown unit isn't checked either
                continue
            v0 = r["value"]
            ok = True
            for scale, results in zip(SCALES, runs, strict=True):
                got = results.get((part.id, i))
                try:
                    ratio = float(got) / v0 / scale_of(want, scale)
                except (TypeError, ValueError, ZeroDivisionError):
                    ok = None
                    break
                if abs(ratio - 1) > 1e-6:
                    ok = False
            if ok is None:
                continue
            r["units"] = "ok" if ok else "wrong"
            if not ok:
                problem.notes.append(f"({part.id}) {step.calc[:60]}: the units don't come out as {unit}")


__all__ = ["CONSTANTS", "UNITS", "check_units", "dims"]
