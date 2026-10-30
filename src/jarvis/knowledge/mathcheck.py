"""Maths checked by SymPy, so Jarvis never states a result it hasn't worked out (ROADMAP, Study skill).

    check("integrate", "x^2 sin(x)", "x")                 -> "-x^2 cos(x) + 2x sin(x) + 2cos(x)" (and a check)
    check("solve", "x^2 - 5x + 6 = 0", "x")               -> [2, 3]
    check("integrate", "exp(-x^2)", "x", lower="-oo", upper="oo")

The model writes the expression, so it's untrusted: only maths characters and
known function names get through, and SymPy parses it with nothing else in
reach (no dots, quotes, brackets or underscores-names, so no Python). A
calculation that takes too long is given up after a few seconds.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as Slow
from dataclasses import dataclass

FUNCTIONS = {
    "sin", "cos", "tan", "sec", "csc", "cot", "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh",
    "asinh", "acosh", "atanh", "exp", "log", "ln", "sqrt", "cbrt", "Abs", "abs", "factorial", "gamma",
    "binomial", "floor", "ceiling", "sign", "erf", "re", "im", "conjugate", "Heaviside", "DiracDelta",
    "pi", "E", "I", "oo", "e",
}
GREEK = {"alpha", "beta", "theta", "phi", "omega", "mu", "sigma", "tau", "epsilon", "delta", "rho", "nu", "psi",
         "eta", "kappa", "xi", "zeta", "chi"}
TASKS = ("simplify", "expand", "factor", "solve", "differentiate", "integrate", "limit", "series", "evaluate")
_CHARS = re.compile(r"^[A-Za-z0-9+\-*/^().,=\s]+$")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_VAR = re.compile(r"^[A-Za-z][0-9]{0,2}$")


class MathError(ValueError):
    """Not something Jarvis will hand to SymPy, or SymPy couldn't do it."""


@dataclass
class Checked:
    task: str
    expression: str
    result: str
    numeric: str = ""
    note: str = ""
    latex: str = ""                      # the question and its answer, for the board (KaTeX)

    def for_the_model(self) -> str:
        text = f"SymPy checked ({self.task}): {self.expression} -> {self.result}"
        if self.numeric and self.numeric != self.result:
            text += f" (about {self.numeric})"
        return text + (f". {self.note}" if self.note else "")


def _vet(text: str, what: str = "expression") -> str:
    text = (text or "").strip()
    if not text or len(text) > 300:
        raise MathError(f"the {what} is empty or too long")
    if not _CHARS.match(text):
        raise MathError(f"the {what} has characters that aren't maths")
    if re.search(r"\.(?!\d)|(?<!\d)\.", text):
        raise MathError(f"a dot that isn't a decimal point in the {what}")
    for name in _NAME.findall(text):
        if name not in FUNCTIONS and name not in GREEK and not _VAR.match(name):
            raise MathError(f"unknown name {name!r} in the {what}")
    return text


def _parse(text: str, what: str = "expression"):
    import sympy
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )
    text = _vet(text, what)
    names = {"ln": sympy.log, "e": sympy.E, "abs": sympy.Abs}
    names.update({g: sympy.Symbol(g) for g in GREEK})
    for name in set(_NAME.findall(text)) - FUNCTIONS - GREEK:
        names[name] = sympy.Symbol(name)
    safe = {name: getattr(sympy, name) for name in sympy.__all__}    # SymPy's own names, and no Python builtins
    safe["__builtins__"] = {}
    try:
        return parse_expr(text, local_dict=names, global_dict=safe,
                          transformations=(*standard_transformations, implicit_multiplication_application,
                                           convert_xor))
    except Exception as exc:  # noqa: BLE001 - any parse failure means "not maths I can read"
        raise MathError(f"couldn't read the {what}: {type(exc).__name__}") from None


def _show(value) -> str:
    import sympy
    text = sympy.sstr(value)
    return text.replace("**", "^")


def _work(task: str, expression: str, variable: str, lower: str, upper: str, point: str, order: int) -> Checked:
    import sympy
    var = sympy.Symbol(_vet(variable or "x", "variable"))
    if task == "solve" and "=" in expression:
        if expression.count("=") != 1:
            raise MathError("an equation needs exactly one =")
        left, right = expression.split("=")
        target = sympy.Eq(_parse(left), _parse(right))
    else:
        if "=" in expression:
            raise MathError("only 'solve' takes an equation")
        target = _parse(expression)
    note = ""
    if task == "simplify":
        result = sympy.simplify(target)
    elif task == "expand":
        result = sympy.expand(target)
    elif task == "factor":
        result = sympy.factor(target)
    elif task == "solve":
        result = sympy.solve(target, var)
    elif task == "differentiate":
        result = sympy.diff(target, var, max(1, min(order or 1, 10)))
    elif task == "integrate":
        if lower or upper:
            if not (lower and upper):
                raise MathError("a definite integral needs both limits")
            result = sympy.integrate(target, (var, _parse(lower, "lower limit"), _parse(upper, "upper limit")))
        else:
            result = sympy.integrate(target, var)
            if not result.has(sympy.Integral):
                back = sympy.simplify(sympy.diff(result, var) - target) == 0
                note = "Differentiating it gives back the integrand." if back else "Check: its derivative differs."
                note += " Add + C."
    elif task == "limit":
        result = sympy.limit(target, var, _parse(point or "0", "point"))
    elif task == "series":
        result = sympy.series(target, var, _parse(point or "0", "point"), max(2, min(order or 6, 12))).removeO()
    elif task == "evaluate":
        result = sympy.N(target, 12)
    else:
        raise MathError(f"unknown task {task!r}")
    if isinstance(result, sympy.Basic) and result.has(sympy.Integral, sympy.Limit):
        note = (note + " SymPy couldn't find a closed form.").strip()
    numeric = ""
    if isinstance(result, sympy.Basic) and result.is_number and result.is_finite and not result.is_Integer:
        numeric = _show(sympy.N(result, 8))
    return Checked(task, expression, _show(result), numeric, note,
                   _latex(task, target, result, var, lower, upper, point, order))


def _latex(task, target, result, var, lower, upper, point, order) -> str:
    """"\\int x^2 \\sin x\\,dx = ..." for the board; "" if SymPy can't write it."""
    import sympy
    try:
        tex = sympy.latex
        if task == "integrate":
            limits = (var, _parse(lower, "lower limit"), _parse(upper, "upper limit")) if lower and upper else var
            return f"{tex(sympy.Integral(target, limits))} = {tex(result)}" + ("" if lower else " + C")
        if task == "differentiate":
            return f"{tex(sympy.Derivative(target, (var, max(1, min(order or 1, 10)))))} = {tex(result)}"
        if task == "limit":
            return f"{tex(sympy.Limit(target, var, _parse(point or '0', 'point')))} = {tex(result)}"
        if task == "solve":
            answers = ", \\; ".join(tex(r) for r in result) if isinstance(result, list) else tex(result)
            empty = "\\varnothing"
            return f"{tex(target)} \\;\\Rightarrow\\; {tex(var)} = {answers or empty}"
        if task in ("series", "evaluate"):
            return f"{tex(target)} \\approx {tex(result)}"
        return f"{tex(target)} = {tex(result)}"
    except Exception:  # noqa: BLE001 - the board shows the plain answer instead
        return ""


def _sample(expression: str, variable: str, lower: float, upper: float, points: int) -> list[list[float | None]]:
    import numpy as np
    import sympy
    var = sympy.Symbol(_vet(variable or "x", "variable"))
    expr = _parse(expression)
    if expr.free_symbols - {var}:
        raise MathError(f"the graph needs one variable ({var}); it also has "
                        f"{', '.join(sorted(map(str, expr.free_symbols - {var})))}")
    f = sympy.lambdify(var, expr, modules="numpy")
    xs = np.linspace(lower, upper, points)
    with np.errstate(all="ignore"):
        ys = np.broadcast_to(np.asarray(f(xs), dtype=complex), xs.shape)
    out: list[list[float | None]] = []
    for x, y in zip(xs, ys, strict=True):
        ok = abs(y.imag) < 1e-9 and np.isfinite(y.real) and abs(y.real) < 1e8
        out.append([round(float(x), 6), round(float(y.real), 6) if ok else None])
    return out


def sample(expression: str, variable: str = "x", lower: float = -5, upper: float = 5, points: int = 240,
           timeout_s: float = 8.0) -> list[list[float | None]]:
    """Points of y = f(x) for the board's graph; None where it isn't defined (gaps, asymptotes)."""
    if not (-1e6 < lower < upper < 1e6):
        raise MathError("the graph's range must go from a smaller to a larger number")
    job = _pool.submit(_sample, expression, variable, float(lower), float(upper), max(20, min(points, 600)))
    try:
        return job.result(timeout=timeout_s)
    except Slow:
        raise MathError(f"drawing it took longer than {timeout_s:g} s") from None
    except MathError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MathError(f"couldn't draw it: {type(exc).__name__}") from None


_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sympy")


def check(task: str, expression: str, variable: str = "x", lower: str = "", upper: str = "", point: str = "",
          order: int = 0, timeout_s: float = 8.0) -> Checked:
    if task not in TASKS:
        raise MathError(f"unknown task {task!r}")
    job = _pool.submit(_work, task, expression, variable, lower, upper, point, order)
    try:
        return job.result(timeout=timeout_s)
    except Slow:
        raise MathError(f"SymPy took longer than {timeout_s:g} s") from None
    except MathError:
        raise
    except Exception as exc:  # noqa: BLE001 - SymPy's own errors (NotImplementedError, ...)
        raise MathError(f"SymPy couldn't do it: {type(exc).__name__}") from None
