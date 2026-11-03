"""Worked problems: a question in parts, each part solved step by step, every number worked out by SymPy,
and each step shown in a tested animation (problem_views.py).

    plan = parse_problem(model_reply)          # the model's plan: the given values, the parts, their steps, the views
    work(plan)                                 # SymPy runs every step's calculation in order: these are the numbers shown
    again = practice(plan, seed=3)             # the same problem with new numbers; the answers worked out again
    ok, said = check_answer(plan, "b", "25")   # the student's answer against the worked one

The model plans; the computer computes (like PAL, Gao et al. 2022): the model writes each step as
`name = expression` over the given symbols, and SymPy evaluates it, so a slip in the model's arithmetic
can't reach the screen. A step whose calculation SymPy can't run is shown as "not checked".
Tutoring follows the research on step-based tutors and worked examples: a hint first, then one step at
a time with its goal named, the full solution on request, and practice with new numbers to try alone.
"""

from __future__ import annotations

import json
import math
import random
import re
from concurrent.futures import TimeoutError as Slow
from dataclasses import dataclass, field
from typing import Any

from .mathcheck import FUNCTIONS, GREEK, MathError, _pool

SUBJECTS = ("mechanics", "electricity", "waves", "thermodynamics", "modern physics", "maths", "statistics",
            "chemistry", "other")
MAX_PARTS, MAX_STEPS, MAX_GIVEN = 8, 8, 24
# names SymPy may use in a step besides the problem's own symbols
EXTRA = {"solve", "Eq", "diff", "integrate", "limit", "summation", "nsolve", "Rational", "Min", "Max", "log10",
         "rad", "deg", "simplify", "expand", "factor", "Matrix", "det"}
# SymPy's constants that are also everyday symbols (I a current, E an energy or emf, e the electron's charge):
# a problem may name its own values so, and then they mean the problem's value
OWNABLE = {"I", "E", "e"}
RESERVED = (FUNCTIONS - OWNABLE) | EXTRA
_CHARS = re.compile(r"^[A-Za-z0-9_+\-*/^().,=\s<>]+$")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SYMBOL = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,15}$")
_FREE = re.compile(r"^[A-Za-z][0-9]?$")                 # x, t, n, x1: a free variable in a step
PICKS = ("positive", "negative", "smallest", "largest", "first")


class ProblemError(ValueError):
    """The model's plan wasn't a usable problem, or a step couldn't be worked out."""


@dataclass
class Given:
    symbol: str
    name: str
    value: float
    unit: str = ""
    const: bool = False                  # a constant of nature (g, R, h): kept in practice questions


@dataclass
class Step:
    say: str                             # what Jarvis says (spoken words)
    goal: str = ""                       # the step's goal, named ("Find the time to stop"): subgoal labels
    latex: str = ""                      # the step's equation, shown with KaTeX
    calc: str = ""                       # "name = expression": SymPy works it out
    unit: str = ""
    pick: str = ""                       # which root of a solve(): positive, negative, smallest, largest, first
    view: str = ""                       # which of the problem's views to show
    highlight: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)   # filled by work(): symbol, value, shown, latex, ok, note


@dataclass
class Part:
    id: str
    ask: str
    hint: str = ""
    steps: list[Step] = field(default_factory=list)
    answer: str = ""                     # the symbol that is this part's answer
    unit: str = ""


@dataclass
class Problem:
    title: str
    subject: str
    statement: str                       # with {symbol} where a given value goes
    given: list[Given] = field(default_factory=list)
    views: dict[str, dict] = field(default_factory=dict)
    parts: list[Part] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)        # what was dropped or couldn't be checked
    values: dict[str, Any] = field(default_factory=dict)  # symbol -> SymPy value, filled by work()
    shown_views: dict[str, dict] = field(default_factory=dict)   # the views' data for the window
    seed: int = 0                                         # 0: as asked; otherwise a practice version
    lang: str = "en"                                      # the language it was asked in: the marks and the card

    def statement_text(self) -> str:
        values = {g.symbol: g for g in self.given}

        def put(m):
            g = values.get(m.group(1))
            return show_number(g.value) if g else m.group(0)
        return re.sub(r"\{([A-Za-z][A-Za-z0-9_]{0,15})\}", put, self.statement)

    def part(self, pid: str) -> Part | None:
        pid = str(pid).strip().lower().strip("()")
        return next((p for p in self.parts if p.id.lower() == pid), None)

    def answer_of(self, part: Part) -> dict:
        """The part's worked answer: the step that computed its symbol (else its last step)."""
        for step in reversed(part.steps):
            if step.result.get("symbol") == part.answer and step.result.get("ok"):
                return step.result
        return next((s.result for s in reversed(part.steps) if s.result.get("ok")), {})

    def as_data(self) -> dict:
        return {
            "title": self.title, "subject": self.subject, "statement": self.statement_text(), "seed": self.seed,
            "given": [{"symbol": g.symbol, "name": g.name, "shown": show_number(g.value), "unit": g.unit}
                      for g in self.given],
            "parts": [{"id": p.id, "ask": p.ask, "hint": p.hint, "unit": p.unit,
                       "answer": self.answer_of(p).get("shown", ""),
                       "view_check": self.answer_of(p).get("view_check"),
                       "steps": [{"say": s.say, "goal": s.goal, "latex": s.latex, "view": s.view,
                                  "highlight": s.highlight, "result": s.result} for s in p.steps]}
                      for p in self.parts],
            "views": self.shown_views, "summary": self.summary, "concepts": self.concepts, "lang": self.lang,
        }


# ---- numbers as people write them -------------------------------------------------------------
def show_number(value: Any, digits: int = 4) -> str:
    """3 significant figures and a bit: 25, 0.0123, 1.23e+05 -> 1.23 x 10^5 (as text)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(v):
        return str(v)
    if v == 0:
        return "0"
    if 1e-3 <= abs(v) < 1e6:
        text = f"{v:.{digits}g}"
        return text if "e" not in text else f"{v:.{max(0, digits - 1 - math.floor(math.log10(abs(v))))}f}"
    mant, exp = f"{v:.{digits - 1}e}".split("e")
    return f"{mant.rstrip('0').rstrip('.')} × 10^{int(exp)}"


# ---- the model's plan ---------------------------------------------------------------------------
def problem_prompt(question: str, language: str, context: str = "") -> str:
    from .problem_views import view_catalog
    return f"""You are Jarvis's problem solver. Turn this problem into a plan for a step-by-step tutor that will
show it in animations. The problem: {question[:3000]!r}
Earlier conversation (for context): {context[:800]!r}

Reply with JSON only (no prose, no code fences):
{{"title": "...", "subject": "{'|'.join(SUBJECTS)}",
 "statement": "the problem in full, with {{symbol}} where each given number goes, e.g. 'accelerates at {{a1}} m/s^2'",
 "given": [{{"symbol": "a1", "name": "acceleration", "value": 2.5, "unit": "m/s^2", "const": false}}],
 "views": {{"<name>": <a view from the list below>}},
 "parts": [{{"id": "a", "ask": "the question of this part, short", "hint": "a nudge, not the answer",
   "answer": "v1", "unit": "m/s",
   "steps": [{{"goal": "Find the speed after the first phase", "say": "spoken words",
     "latex": "v_1 = u + a_1 t_1", "calc": "v1 = u + a1*t1", "unit": "m/s", "view": "<name>",
     "highlight": {{...}}}}]}}],
 "summary": ["the method in 2 to 4 short points"], "concepts": ["the key ideas"]}}

Rules:
- Keep the problem's own parts (a), (b), (c)...; if it has none, make 1 to 3 natural parts. At most {MAX_PARTS} parts,
  {MAX_STEPS} steps each.
- "given": every number in the problem, in SI units (convert km/h to m/s, g to kg, mL stays mL only in titration),
  plus constants you use (g = 9.81, R = 8.314, Kw = 1e-14...) with "const": true. Symbols: letters, digits, _.
- "calc": exactly `name = expression` in SymPy syntax with explicit * (2*a*s, not 2as), ** or ^ for powers, over
  the given symbols and names computed in earlier steps (any part). Functions: sqrt, exp, log, sin, cos, tan,
  asin, acos, atan, rad(deg) and deg(rad) to convert angles, solve(Eq(lhs, rhs), x), diff(f, x),
  integrate(f, (x, a, b)), limit, summation, nsolve. With solve() also give "pick": positive|negative|smallest|
  largest|first. Leave "calc" empty only for a step that computes nothing. Never put a number you worked out
  yourself in a calc: the computer works it out.
- "say": 1 to 3 short spoken sentences in {language}, words only (no symbols or LaTeX): "v equals u plus a t".
  Don't say the numeric result in "say": the screen shows the worked number.
- "goal": the step's purpose in a few words. "hint": a question or nudge that helps without giving it away.
- Write "title", "ask", "hint", "goal", "say" and "summary" in {language} (spoken style, as students say it;
  English words for units and technical terms are fine). Symbols, "calc" and "latex" stay as maths.
- "views": one to three views of the problem, chosen by what it is about; each step names the view it uses and
  what to highlight. Numbers in views may be symbols or expressions of the given and computed names.
{view_catalog()}
- Everything must be correct physics, chemistry and maths. Use the problem's own numbers.
"""


def _json_in(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ProblemError("no JSON object in the reply")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise ProblemError(f"the JSON doesn't parse: {exc}") from None
    if not isinstance(data, dict):
        raise ProblemError("the plan isn't a JSON object")
    return data


def _text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def parse_problem(text: str) -> Problem:
    data = _json_in(text)
    subject = _text(data.get("subject"), 30).lower()
    problem = Problem(_text(data.get("title"), 120) or "Problem", subject if subject in SUBJECTS else "other",
                      str(data.get("statement") or "").strip()[:3000])
    seen: set[str] = set()
    for g in (data.get("given") or [])[:MAX_GIVEN]:
        if not isinstance(g, dict):
            continue
        sym = _text(g.get("symbol"), 16)
        try:
            value = float(g.get("value"))
        except (TypeError, ValueError):
            problem.notes.append(f"given {sym!r} has no number")
            continue
        if not _SYMBOL.match(sym) or sym in seen or sym in RESERVED or not math.isfinite(value):
            problem.notes.append(f"given {sym!r} isn't usable")
            continue
        seen.add(sym)
        problem.given.append(Given(sym, _text(g.get("name"), 60), value, _text(g.get("unit"), 20),
                                   bool(g.get("const"))))
    views = data.get("views") if isinstance(data.get("views"), dict) else {}
    for name, spec in list(views.items())[:4]:
        if _SYMBOL.match(str(name)) and isinstance(spec, dict) and spec:
            problem.views[str(name)] = spec
    for i, p in enumerate((data.get("parts") or [])[:MAX_PARTS]):
        if not isinstance(p, dict):
            continue
        part = Part(_text(p.get("id"), 6).strip("()").lower() or "abcdefgh"[i], _text(p.get("ask"), 400),
                    _text(p.get("hint"), 400), answer=_text(p.get("answer"), 16), unit=_text(p.get("unit"), 20))
        for s in (p.get("steps") or [])[:MAX_STEPS]:
            if not isinstance(s, dict) or not (_text(s.get("say"), 10) or _text(s.get("calc"), 10)):
                continue
            view = _text(s.get("view"), 16)
            pick = _text(s.get("pick"), 10).lower()
            part.steps.append(Step(_text(s.get("say"), 500), _text(s.get("goal"), 100), str(s.get("latex") or "")[:400],
                                   _text(s.get("calc"), 400), _text(s.get("unit"), 20), pick if pick in PICKS else "",
                                   view if view in problem.views else "",
                                   s.get("highlight") if isinstance(s.get("highlight"), dict) else {}))
        if part.ask and part.steps:
            problem.parts.append(part)
    if not problem.parts:
        raise ProblemError("the plan has no parts with steps")
    problem.summary = [_text(x, 200) for x in (data.get("summary") or []) if _text(x, 200)][:6]
    problem.concepts = [_text(x, 60) for x in (data.get("concepts") or []) if _text(x, 60)][:8]
    return problem


# ---- SymPy works out each step -------------------------------------------------------------------
def _split_args(text: str) -> list[str]:
    """The arguments of a call, split at its top-level commas."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def _equations(text: str) -> str:
    """solve(v**2 = u**2 + 2*a*s, s) -> solve(Eq(v**2, u**2 + 2*a*s), s): models often write it so."""
    for fn in ("solve", "nsolve"):
        start = 0
        while (i := text.find(fn + "(", start)) >= 0:
            j, depth = i + len(fn) + 1, 1
            while j < len(text) and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            args = _split_args(text[i + len(fn) + 1:j - 1])
            first = args[0]
            if re.search(r"(?<![<>=!])=(?!=)", first) and "Eq(" not in first:
                lhs, rhs = re.split(r"(?<![<>=!])=(?!=)", first, maxsplit=1)
                args[0] = f"Eq({lhs.strip()}, {rhs.strip()})"
            text = text[:i] + fn + "(" + ",".join(args) + ")" + text[j:]
            start = i + len(fn) + 1
    return text


def _vet(text: str, known: set[str]) -> str:
    text = (text or "").strip()
    if not text or len(text) > 400:
        raise ProblemError("the calculation is empty or too long")
    if not _CHARS.match(text) or "__" in text:
        raise ProblemError("the calculation has characters that aren't maths")
    if re.search(r"\.(?!\d)|(?<!\d)\.", text):
        raise ProblemError("a dot that isn't a decimal point")
    for name in _NAME.findall(text):
        if name not in known and name not in FUNCTIONS and name not in GREEK and name not in EXTRA \
                and not _FREE.match(name):
            raise ProblemError(f"unknown name {name!r}")
    return text


def _parse(text: str, values: dict[str, Any]):
    import sympy
    from sympy.parsing.sympy_parser import (
        convert_xor,
        parse_expr,
        standard_transformations,
    )
    text = _equations(_vet(text, set(values)))
    local: dict[str, Any] = {"ln": sympy.log, "e": sympy.E, "abs": sympy.Abs,
                             "log10": lambda x: sympy.log(x, 10), "rad": lambda d: d * sympy.pi / 180,
                             "deg": lambda r: r * 180 / sympy.pi}
    local.update({g: sympy.Symbol(g) for g in GREEK})
    for name in set(_NAME.findall(text)):
        if name in values:                          # the problem's own value, even if SymPy has the name (I, E)
            local[name] = values[name]
        elif name not in FUNCTIONS and name not in EXTRA and name not in local:
            local[name] = sympy.Symbol(name)
    safe = {name: getattr(sympy, name) for name in sympy.__all__}
    safe["__builtins__"] = {}
    try:
        return parse_expr(text, local_dict=local, global_dict=safe,
                          transformations=(*standard_transformations, convert_xor))
    except Exception as exc:  # noqa: BLE001 - any parse failure: "not maths I can read"
        raise ProblemError(f"couldn't read it: {type(exc).__name__}") from None


def _pick(roots: list, how: str):
    import sympy
    reals = []
    for r in roots:
        r = r if not isinstance(r, dict) else next(iter(r.values()), None)
        if r is None:
            continue
        try:
            n = complex(sympy.N(r))
            if abs(n.imag) < 1e-9:
                reals.append((n.real, r))
        except (TypeError, ValueError):
            reals.append((None, r))                       # a symbolic root
    if not reals:
        raise ProblemError("no real solution")
    numeric = [x for x in reals if x[0] is not None]
    how = how or ("positive" if any(v > 0 for v, _ in numeric) else "first")
    if how == "positive" and any(v > 0 for v, _ in numeric):
        return min((x for x in numeric if x[0] > 0), key=lambda x: x[0])[1]
    if how == "negative" and any(v < 0 for v, _ in numeric):
        return max((x for x in numeric if x[0] < 0), key=lambda x: x[0])[1]
    if how == "smallest" and numeric:
        return min(numeric, key=lambda x: x[0])[1]
    if how == "largest" and numeric:
        return max(numeric, key=lambda x: x[0])[1]
    return reals[0][1]


def evaluate(calc: str, values: dict[str, Any], pick: str = "") -> tuple[str, Any]:
    """`name = expression` worked out with the values so far: (name, SymPy value)."""
    import sympy
    m = re.match(r"^\s*([A-Za-z][A-Za-z0-9_]{0,15})\s*=(?!=)\s*(.+)$", calc or "", re.DOTALL)
    if not m:
        raise ProblemError("not `name = expression`")
    name, expr = m.group(1), m.group(2)
    if name in RESERVED:
        raise ProblemError(f"{name!r} is a function's name")
    value = _parse(expr, values)
    if isinstance(value, list | tuple | sympy.sets.sets.Set):
        value = _pick(list(value), pick)
    if isinstance(value, sympy.Basic):
        if value.free_symbols:
            value = sympy.simplify(value)
        elif value.is_number:
            value = sympy.N(value, 15)
            if abs(complex(value).imag) > 1e-12 * max(1.0, abs(complex(value))):
                raise ProblemError("the result is complex")
            value = sympy.Float(complex(value).real, 15) if not value.is_Integer else value
    return name, value


def _result(name: str, value: Any, unit: str) -> dict:
    import sympy
    if isinstance(value, sympy.Basic) and value.is_number:
        v = float(value)
        number = re.sub(r"10\^(-?\d+)", r"10^{\1}", show_number(v).replace("×", r"\times"))
        unit_tex = r"\ \mathrm{" + _tex_unit(unit) + "}" if unit else ""
        return {"symbol": name, "value": v, "shown": show_number(v), "unit": unit, "ok": True,
                "latex": f"{_tex_name(name)} = {number}{unit_tex}"}
    text = sympy.sstr(value).replace("**", "^")
    return {"symbol": name, "value": None, "shown": text, "unit": unit, "ok": True,
            "latex": f"{_tex_name(name)} = {sympy.latex(value)}"}


def _tex_name(name: str) -> str:
    m = re.match(r"^([A-Za-z]+)_?([0-9A-Za-z]*)$", name)
    if not m:
        return name.replace("_", r"\_")
    base, sub = m.groups()
    base = "\\" + base if base in GREEK else base
    return f"{base}_{{{sub}}}" if sub else base


def _tex_unit(unit: str) -> str:
    return re.sub(r"\^(-?\d+)", r"^{\1}", unit.replace(" ", r"\,"))


def _work(problem: Problem) -> None:
    import sympy
    values: dict[str, Any] = {g.symbol: sympy.Float(g.value, 15) if not float(g.value).is_integer()
                              else sympy.Integer(int(g.value)) for g in problem.given}
    for part in problem.parts:
        for step in part.steps:
            if not step.calc:
                step.result = {}
                continue
            try:
                name, value = evaluate(step.calc, values, step.pick)
                values[name] = value
                step.result = _result(name, value, step.unit or (part.unit if name == part.answer else ""))
            except (ProblemError, MathError) as exc:
                step.result = {"ok": False, "note": str(exc)[:120]}
                problem.notes.append(f"({part.id}) {step.calc[:60]}: {exc}")
            except Exception as exc:  # noqa: BLE001 - SymPy's own errors
                step.result = {"ok": False, "note": f"SymPy couldn't do it ({type(exc).__name__})"}
                problem.notes.append(f"({part.id}) {step.calc[:60]}: {type(exc).__name__}")
    problem.values = values
    from .dimensions import check_units
    try:
        check_units(problem)                          # a set-up error usually shows up as wrong units
    except Exception as exc:  # noqa: BLE001 - the check is a help; the worked numbers stand without it
        problem.notes.append(f"view units: couldn't check them ({type(exc).__name__})")


def work(problem: Problem, timeout_s: float = 20.0) -> Problem:
    """Every step's calculation, in order, then the views' data."""
    from .problem_views import build_views
    job = _pool.submit(_work, problem)
    try:
        job.result(timeout=timeout_s)
    except Slow:
        raise ProblemError(f"working it out took longer than {timeout_s:g} s") from None
    problem.shown_views = build_views(problem)
    return problem


# ---- practice: the same problem, new numbers --------------------------------------------------------
PRACTICE_SPREAD = (0.6, 1.5)        # a practice version's numbers: 0.6 to 1.5 times the asked ones ([problems])


def _nice(v: float, rng: random.Random, spread: tuple[float, float] = PRACTICE_SPREAD) -> float:
    if v == 0:
        return 0.0
    new = v * rng.uniform(*spread)
    digits = 2 if abs(v) >= 10 or float(v).is_integer() else 3
    return float(f"{new:.{digits}g}")


def practice(problem: Problem, seed: int | None = None, tries: int = 12,
             spread: tuple[float, float] = PRACTICE_SPREAD) -> Problem:
    """A new version: every given that isn't a constant is multiplied by a number in `spread` (-40% to +50%
    by default), rounded nicely; the answers are worked out again. A version whose answers aren't all real
    (a car that never stops) is thrown away and another tried."""
    import copy
    rng = random.Random(seed)
    for _ in range(tries):
        fresh = copy.deepcopy(problem)
        fresh.seed = rng.randint(1, 10_000)
        fresh.notes = []
        for g in fresh.given:
            if not g.const:
                g.value = _nice(g.value, rng, spread)
        try:
            work(fresh)
        except ProblemError:
            continue
        signs_kept = all(
            (not a.get("ok")) or (b.get("ok") and (a.get("value") is None or b.get("value") is None
                                                   or (a["value"] > 0) == (b["value"] > 0)))
            for p0, p1 in zip(problem.parts, fresh.parts, strict=False)
            for a, b in [(problem.answer_of(p0), fresh.answer_of(p1))])
        steps_ok = all(b.result.get("ok") or not a.result.get("ok")
                       for p0, p1 in zip(problem.parts, fresh.parts, strict=False)
                       for a, b in zip(p0.steps, p1.steps, strict=False))
        if signs_kept and steps_ok:
            return fresh
    raise ProblemError("couldn't make a practice version that works out")


# ---- the student's answer ------------------------------------------------------------------------
_NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?(?:\s*(?:e|E|x\s*10\s*\^|×\s*10\s*\^|\*\s*10\s*\*\*)\s*[-+]?\d+)?")


def _number_in(text: str) -> float | None:
    m = _NUMBER.search(text.replace("−", "-"))
    if not m:
        return None
    t = m.group(0).replace(",", ".")
    t = re.sub(r"\s*(?:x|×|\*)\s*10\s*(?:\^|\*\*)\s*", "e", t)
    try:
        return float(t.replace(" ", ""))
    except ValueError:
        return None


# What the marks say, in the language the problem was asked in (Problem.lang). Spoken Sinhala, as Friday talks.
MARKS = {
    "no_part": {"en": "There's no part {id}.", "si": "{id} කියලා කොටසක් නෑ.", "ta": "பகுதி {id} இல்லை."},
    "unchecked": {"en": "I couldn't check that part's answer myself, so I can't mark yours.",
                  "si": "ඒ කොටසේ උත්තරය මටම චෙක් කරගන්න බැරි වුණා, ඒ නිසා ඔයාගේ උත්තරේ හරිද කියන්න බෑ.",
                  "ta": "அந்தப் பகுதியின் விடையை என்னால் சரிபார்க்க முடியவில்லை, அதனால் உங்கள் விடையை மதிப்பிட முடியாது."},
    "no_number": {"en": "I didn't catch a number in your answer.", "si": "ඔයාගේ උත්තරේ ඉලක්කමක් අහුවුණේ නෑ.",
                  "ta": "உங்கள் விடையில் எண் எதுவும் இல்லை."},
    "right": {"en": "Right: {shown}{unit}.", "si": "හරි: {shown}{unit}.", "ta": "சரி: {shown}{unit}."},
    "sign": {"en": "The size is right but the sign isn't: think about the direction.",
             "si": "අගය හරි, ඒත් ලකුණ වැරදියි: දිශාව ගැන හිතන්න.",
             "ta": "அளவு சரி, ஆனால் குறி தவறு: திசையைப் பற்றி யோசியுங்கள்."},
    "conversion": {"en": "Close: the number is off by a unit conversion. Check your units.",
                   "si": "ළඟයි: ඒකක පරිවර්තනයක් වැරදිලා. ඔයාගේ ඒකක බලන්න.",
                   "ta": "நெருக்கம்: அலகு மாற்றத்தில் தவறு. உங்கள் அலகுகளைச் சரிபாருங்கள்."},
    "wrong": {"en": "Not quite. Try the hint, or the next step.", "si": "තාම හරි නෑ. ඉඟිය හරි ඊළඟ පියවර හරි බලන්න.",
              "ta": "இன்னும் சரியில்லை. குறிப்பையோ அடுத்த படியையோ பாருங்கள்."},
    "wrong_maths": {"en": "Not quite. Try the next step.", "si": "තාම හරි නෑ. ඊළඟ පියවර බලන්න.",
                    "ta": "இன்னும் சரியில்லை. அடுத்த படியைப் பாருங்கள்."},
    "unreadable": {"en": "I couldn't read your answer as maths.", "si": "ඔයාගේ උත්තරේ ගණිතයක් විදියට කියවගන්න බැරි වුණා.",
                   "ta": "உங்கள் விடையைக் கணிதமாகப் படிக்க முடியவில்லை."},
    # the animation's own numbers against the answer (problem_views.cross_check); {label} is the view's
    "view_agrees": {"en": "the animation agrees: {label}", "si": "ඇනිමේෂන් එකත් එකඟයි: {label}",
                    "ta": "அனிமேஷனும் ஒப்புக்கொள்கிறது: {label}"},
    "view_differs": {"en": "the animation shows {value} {unit} for {label}, not {answer}",
                     "si": "ඇනිමේෂන් එකේ {label} එකට {value} {unit} එනවා, {answer} නෙවෙයි",
                     "ta": "அனிமேஷன் {label} க்கு {value} {unit} காட்டுகிறது, {answer} அல்ல"},
}


def marks(key: str, lang: str, **values: Any) -> str:
    """A line of MARKS in `lang`, English when that language has none."""
    options = MARKS[key]
    return (options.get(lang) or options["en"]).format(**values)


ANSWER_TOLERANCE = 0.02             # an answer within 2% is right ([problems] answer_tolerance)


def check_answer(problem: Problem, part_id: str, text: str, rel: float = ANSWER_TOLERANCE) -> tuple[bool | None, str]:
    """(right?, what to say, in the problem's language). None: there's nothing to check it against."""
    lang = problem.lang
    part = problem.part(part_id)
    if part is None:
        return None, marks("no_part", lang, id=part_id)
    worked = problem.answer_of(part)
    if not worked:
        return None, marks("unchecked", lang)
    unit = f" {worked.get('unit')}" if worked.get("unit") else ""
    if worked.get("value") is not None:
        mine = _number_in(text or "")
        if mine is None:
            return None, marks("no_number", lang)
        right = worked["value"]
        ok = abs(mine - right) <= max(abs(right) * rel, 1e-12)
        if ok:
            return True, marks("right", lang, shown=worked["shown"], unit=unit)
        if right and abs(abs(mine) - abs(right)) <= abs(right) * rel:
            return False, marks("sign", lang)
        if right and any(abs(mine * f - right) <= abs(right) * rel for f in (1e3, 1e-3, 3.6, 1 / 3.6, 60, 1 / 60)):
            return False, marks("conversion", lang)
        return False, marks("wrong", lang)
    try:
        import sympy
        mine_expr = _parse(text, problem.values)
        ok = sympy.simplify(mine_expr - _parse(worked["shown"].replace("^", "**"), problem.values)) == 0
    except (ProblemError, TypeError, ValueError):
        return None, marks("unreadable", lang)
    return (True, marks("right", lang, shown=worked["shown"], unit="")) if ok else (False, marks("wrong_maths", lang))


def problem_for_the_model(problem: Problem) -> str:
    """What goes in the conversation afterwards, so follow-up questions know the problem and its answers."""
    lines = [f"(Jarvis opened a worked problem in his window: {problem.title})", problem.statement_text()[:600]]
    for p in problem.parts:
        ans = problem.answer_of(p)
        lines.append(f"({p.id}) {p.ask}: " + (f"{ans.get('shown')} {ans.get('unit', '')}".strip() if ans
                                             else "not checked"))
    return "\n".join(lines)


__all__ = ["ANSWER_TOLERANCE", "MARKS", "PRACTICE_SPREAD", "Given", "Part", "Problem", "ProblemError", "Step",
           "check_answer", "evaluate", "marks", "parse_problem", "practice", "problem_for_the_model", "problem_prompt",
           "show_number", "work"]
