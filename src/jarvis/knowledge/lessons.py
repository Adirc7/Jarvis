"""Visual lessons: Jarvis explains step by step while his window shows what he's saying.

    prompt = plan_prompt(question, context, "English")     # one model call returns a JSON plan
    lesson = parse_plan(model_reply)                        # checked: kinds, scenes, ranges, sizes
    resolve(lesson, research)                               # SymPy points and grids, Wikipedia pictures

Each step is one to three spoken sentences and one visual, chosen by what the
step needs, not by the subject:

  scene     a simulation from the library below (tested and accurate; the
            model only picks it and its numbers, never writes its code)
  plot      y = f(x), up to three curves, points worked out by SymPy
  surface   z = f(x, y) in 3D, the grid worked out by SymPy
  formula   LaTeX, drawn by KaTeX (beside any visual, or alone)
  diagram   a Mermaid flowchart or concept map, for processes and ideas
  image     a picture from Wikipedia, for real things worth seeing
  sketch    when nothing else fits: the model writes the drawing code, which
            runs in a locked sandbox in the window (no network, no access to
            Jarvis); labelled as the model's sketch

A step without a visual keeps the one before; a step that names the same
scene with new numbers changes it in place (the wall comes out, the
molecules spread), which is what makes cause and effect visible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .mathcheck import MathError, sample, sample_surface

# name: (what it shows, {param: (type, low, high, default)}); type "choice" keeps its options in `low`
SCENES: dict[str, tuple[str, dict[str, tuple]]] = {
    "gas_box": ("molecules in a box: diffusion, entropy, temperature, pressure, the second law",
                {"molecules": ("int", 10, 300, 80), "temperature": ("num", 0.2, 3.0, 1.0),
                 "wall": ("bool", None, None, True), "colour_by_side": ("bool", None, None, True)}),
    "waves_3d": ("ripples on water from point sources, in 3D: interference, wavelength, superposition",
                 {"sources": ("int", 1, 2, 2), "separation": ("num", 0.0, 10.0, 4.0),
                  "wavelength": ("num", 0.5, 6.0, 2.5), "speed": ("num", 0.0, 3.0, 1.0)}),
    "string_wave": ("a wave on a string: standing waves, harmonics, nodes and antinodes, travelling waves",
                    {"harmonic": ("int", 1, 8, 2), "standing": ("bool", None, None, True),
                     "show_nodes": ("bool", None, None, True)}),
    "pendulum": ("a simple pendulum: period, simple harmonic motion, kinetic and potential energy, damping",
                 {"length": ("num", 0.2, 5.0, 1.0), "gravity": ("num", 1.0, 25.0, 9.81),
                  "amplitude": ("num", 1.0, 80.0, 20.0), "damping": ("num", 0.0, 0.5, 0.0),
                  "show_energy": ("bool", None, None, True)}),
    "projectile": ("a projectile: trajectory, range, maximum height, velocity components, air resistance",
                   {"speed": ("num", 1.0, 60.0, 20.0), "angle": ("num", 5.0, 85.0, 45.0),
                    "gravity": ("num", 1.0, 25.0, 9.81), "drag": ("num", 0.0, 0.1, 0.0),
                    "show_vectors": ("bool", None, None, True)}),
    "rc_circuit": ("an RC circuit charging or discharging: time constant, exponential growth and decay",
                   {"resistance_kohm": ("num", 0.1, 100.0, 10.0), "capacitance_uf": ("num", 1.0, 1000.0, 100.0),
                    "voltage": ("num", 1.0, 24.0, 9.0), "discharge": ("bool", None, None, False)}),
    "fourier": ("a square, sawtooth or triangle wave built from sine waves: Fourier series, harmonics, Gibbs effect",
                {"shape": ("choice", ("square", "sawtooth", "triangle"), None, "square"),
                 "terms": ("int", 1, 50, 5)}),
    "field_3d": ("the electric field of point charges in 3D: field arrows, a single charge, a dipole, like charges",
                 {"arrangement": ("choice", ("single", "dipole", "like_pair"), None, "dipole"),
                  "separation": ("num", 1.0, 8.0, 4.0)}),
    "orbit": ("a planet's elliptical orbit: Kepler's laws, equal areas in equal times, faster near the Sun",
              {"eccentricity": ("num", 0.0, 0.9, 0.5), "show_areas": ("bool", None, None, True)}),
    "lens": ("a thin lens ray diagram: converging and diverging lenses, focal length, real and virtual images",
             {"focal_length": ("num", 2.0, 20.0, 8.0), "object_distance": ("num", 1.0, 40.0, 16.0),
              "converging": ("bool", None, None, True)}),
}
KINDS = ("scene", "plot", "surface", "formula", "diagram", "image", "sketch", "pview")
DIAGRAM_TYPES = ("flowchart", "graph", "mindmap", "timeline", "sequenceDiagram", "stateDiagram", "classDiagram",
                 "pie", "quadrantChart")
MAX_STEPS = 7


class PlanError(ValueError):
    """The model's plan wasn't a usable lesson."""


@dataclass
class Step:
    say: str
    visual: dict[str, Any] | None = None     # {"kind": ..., ...}; None keeps the one before
    formula: str = ""                        # an equation shown with the visual


@dataclass
class Lesson:
    title: str
    steps: list[Step] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)    # what was dropped, and why (for the log)

    def as_data(self) -> dict:
        return {"title": self.title,
                "steps": [{"say": s.say, "visual": s.visual, "formula": s.formula} for s in self.steps]}


def scene_catalog() -> str:
    lines = []
    for name, (about, params) in SCENES.items():
        spec = []
        for p, (kind, low, high, default) in params.items():
            if kind == "bool":
                spec.append(f"{p} true/false (default {str(default).lower()})")
            elif kind == "choice":
                spec.append(f"{p} one of {'/'.join(low)} (default {default})")
            else:
                spec.append(f"{p} {low}-{high} (default {default})")
        lines.append(f"- {name}: {about}. Params: {'; '.join(spec)}")
    return "\n".join(lines)


def plan_prompt(question: str, context: str, language: str) -> str:
    return f"""You plan a short visual lesson for Jarvis, a voice assistant with a window. Jarvis speaks each step
aloud while the window shows that step's visual. The user asked: {question[:400]!r}
What Jarvis said just before (for context): {context[:1500]!r}

Reply with JSON only, no prose and no code fences:
{{"title": "...", "steps": [{{"say": "...", "show": {{...}}, "formula": "..."}}]}}

Rules:
- 3 to 6 steps that build the idea, the way a good teacher would at a whiteboard.
- "say": what Jarvis says for that step: 1 to 3 short spoken sentences in {language}; words only, no symbols,
  no LaTeX, no markdown (say "E equals m c squared"). Refer to the picture ("watch the molecules...").
- "show": the visual for the step, chosen by what this step needs. One of:
  {{"view": {{<a tested animation, below>}}}}   motion, forces, circuits, chemistry, quantum, qubits, relativity,
     matrices, statistics, fields, molecules, Feynman diagrams: accurate and animated; prefer one when it fits
  {{"scene": "<name>", "params": {{...}}}}   a simulation from the library below (accurate; prefer one when it fits)
  {{"plot": ["sin(x)", "x^2"], "from": -5, "to": 5}}   graphs of y = f(x) (maths like x^2 sin(x), exp(-x^2/2), sqrt(2 pi))
  {{"surface": "sin(x) cos(y)", "x": [-3, 3], "y": [-3, 3]}}   a 3D surface z = f(x, y)
  {{"diagram": "flowchart LR\\n A[Sun] --> B[Water evaporates]"}}   Mermaid, at most 12 nodes, for processes and how ideas connect
  {{"image": "search words"}}   a picture from Wikipedia, for real things worth seeing (an organ, a galaxy, an engine)
  {{"sketch": "what to draw and animate"}}   a last resort, only if no view, scene, plot, diagram or picture fits:
     generated drawings often fail, so describe it exactly
  Leave "show" out to keep the previous visual. Use the same scene again with different params to show cause and
  effect (for example wall true, then wall false).
- "formula" (optional): the key equation for the step, in LaTeX (for example S = k_B \\\\ln W).
- Everything must be correct: real laws, real numbers, no invented data.

Library scenes:
{scene_catalog()}

Views (in "view", the numbers are plain numbers here):
{_views()}
"""


def _views() -> str:
    from .problem_views import view_catalog
    return "\n".join(line for line in view_catalog().splitlines() if '"lesson"' not in line
                     and "a visual from the lessons" not in line and "(scenes: gas_box" not in line)


def sketch_prompt(description: str, title: str) -> str:
    return f"""Write a small animated drawing for a lesson on {title[:120]!r}: {description[:400]}

Reply with HTML only (no fences, no explanation): one <canvas> or <div> and one <script>. Rules:
- It runs in a sandbox with no network: no fetch, no external files, no images from the web.
- For 3D you may use the global THREE (three.js r149, already loaded); otherwise use the 2D canvas.
- Fill a 760 x 420 area; dark background #03070d; light colours (#eaf5ff text, #4de1ff, #ffb43b); label things.
- Physically and mathematically correct; animate with requestAnimationFrame; under 150 lines.
"""


def sketch_html(text: str, limit: int = 20000) -> str:
    """The model's sketch, ready for the sandbox: no code fences, no <meta> tags (a refresh
    could send the frame elsewhere), and not too long. Empty if there's no script in it."""
    text = re.sub(r"```(?:html)?", "", text or "").strip()
    text = re.sub(r"<meta\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<!doctype[^>]*>|</?(?:html|head|body)\b[^>]*>", "", text, flags=re.IGNORECASE).strip()
    if "<script" not in text.lower() or len(text) > limit:
        return ""
    return text


def _json_in(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise PlanError("no JSON object in the reply")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise PlanError(f"the JSON doesn't parse: {exc}") from None
    if not isinstance(data, dict):
        raise PlanError("the plan isn't a JSON object")
    return data


def _clamp_params(name: str, given: Any) -> dict:
    out = {}
    params = SCENES[name][1]
    given = given if isinstance(given, dict) else {}
    for p, (kind, low, high, default) in params.items():
        value = given.get(p, default)
        if kind == "bool":
            out[p] = bool(value) if isinstance(value, bool | int) else default
        elif kind == "choice":
            out[p] = value if value in low else default
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = float(default)
            number = min(max(number, low), high)
            out[p] = round(number) if kind == "int" else round(number, 4)
    return out


def _visual(show: Any, notes: list[str]) -> dict | None:
    if not isinstance(show, dict) or not show:
        return None
    if isinstance(show.get("view"), dict) and show["view"]:
        return {"kind": "pview", "spec": show["view"]}
    if "scene" in show:
        name = str(show["scene"])
        if name not in SCENES:
            notes.append(f"unknown scene {name[:40]!r}")
            return None
        return {"kind": "scene", "name": name, "params": _clamp_params(name, show.get("params"))}
    if "plot" in show:
        exprs = show["plot"] if isinstance(show["plot"], list) else [show["plot"]]
        exprs = [str(e)[:200] for e in exprs if isinstance(e, str | int | float)][:3]
        lo, hi = _range(show.get("from", -5), show.get("to", 5), -5, 5)
        return {"kind": "plot", "expressions": exprs, "from": lo, "to": hi} if exprs else None
    if "surface" in show:
        x = show.get("x") if isinstance(show.get("x"), list) and len(show["x"]) == 2 else [-3, 3]
        y = show.get("y") if isinstance(show.get("y"), list) and len(show["y"]) == 2 else [-3, 3]
        return {"kind": "surface", "expression": str(show["surface"])[:200], "x": list(_range(*x, -3, 3)),
                "y": list(_range(*y, -3, 3))}
    if "diagram" in show:
        text = "\n".join(line for line in str(show["diagram"]).splitlines() if not line.strip().startswith("%%"))
        first = text.strip().split(None, 1)[0] if text.strip() else ""
        if first not in DIAGRAM_TYPES or len(text) > 1500:
            notes.append("a diagram that isn't a short Mermaid diagram")
            return None
        return {"kind": "diagram", "mermaid": text.strip()}
    if "image" in show:
        return {"kind": "image", "query": str(show["image"])[:80]}
    if "sketch" in show:
        return {"kind": "sketch", "description": str(show["sketch"])[:400], "code": ""}
    if "formula" in show:
        return {"kind": "formula", "latex": str(show["formula"])[:400]}
    notes.append(f"a visual of no known kind ({', '.join(list(show)[:3])})")
    return None


def _range(lo: Any, hi: Any, d_lo: float, d_hi: float) -> tuple[float, float]:
    try:
        lo, hi = float(lo), float(hi)
    except (TypeError, ValueError):
        return d_lo, d_hi
    if not (-1e6 < lo < hi < 1e6):
        return d_lo, d_hi
    return lo, hi


def parse_plan(text: str) -> Lesson:
    data = _json_in(text)
    raw = data.get("steps")
    if not isinstance(raw, list) or not raw:
        raise PlanError("the plan has no steps")
    lesson = Lesson(str(data.get("title") or "Lesson")[:120])
    for item in raw[:MAX_STEPS]:
        if not isinstance(item, dict) or not str(item.get("say", "")).strip():
            continue
        visual = _visual(item.get("show"), lesson.notes)
        lesson.steps.append(Step(str(item["say"]).strip()[:500], visual, str(item.get("formula") or "")[:400]))
    if not lesson.steps:
        raise PlanError("no step has anything to say")
    if lesson.steps[0].visual is None and not lesson.steps[0].formula:
        lesson.notes.append("the first step shows nothing")
    return lesson


def resolve(lesson: Lesson, research=None) -> Lesson:
    """Work out what the window needs: curve points, surface grids, picture addresses.
    A visual that can't be made is dropped (the step keeps the one before), with a note."""
    for step in lesson.steps:
        v = step.visual
        if v is None:
            continue
        try:
            if v["kind"] == "plot":
                v["curves"] = []
                for expr in v["expressions"]:
                    try:
                        v["curves"].append({"label": expr, "points": sample(expr, "x", v["from"], v["to"], 300)})
                    except MathError as exc:
                        lesson.notes.append(f"couldn't plot {expr}: {exc}")
                if not v["curves"]:
                    step.visual = None
            elif v["kind"] == "pview":
                v["data"] = _problem_view(v.pop("spec"))
            elif v["kind"] == "surface":
                v["z"] = sample_surface(v["expression"], v["x"], v["y"], 48)
            elif v["kind"] == "image":
                page = research.wikipedia(v["query"]) if research is not None else None
                if page is None or not page.image:
                    lesson.notes.append(f"no Wikipedia picture for {v['query']!r}")
                    step.visual = None
                else:
                    v.update(url=page.image, title=page.title, credit=f"Wikipedia: {page.title}", page=page.url)
        except MathError as exc:
            lesson.notes.append(f"couldn't draw {v.get('expression', '?')}: {exc}")
            step.visual = None
    return lesson


def _problem_view(spec: dict) -> dict:
    """A worked problem's tested view (problem_views.py), with the plain numbers a lesson gives it."""
    from .problem_views import BUILDERS, _Num
    from .problems import Problem, ProblemError
    kind = next((k for k in BUILDERS if k in spec), None)
    if kind is None or not isinstance(spec[kind], dict):
        raise MathError(f"no known view in {', '.join(list(spec)[:3])}")
    try:
        return BUILDERS[kind](spec[kind], _Num(Problem("lesson", "other", "")))
    except (ProblemError, ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise MathError(f"the {kind} view: {exc}") from None


def lesson_for_the_model(lesson: Lesson) -> str:
    """What goes in the conversation afterwards, so follow-ups know what was shown."""
    shown = [f"{i}. {s.say}" + (f" [showing {s.visual['kind']}"
                                + (f" {s.visual.get('name', '')}" if s.visual and s.visual.get('name') else "") + "]"
                                if s.visual else "")
             for i, s in enumerate(lesson.steps, 1)]
    return f"(Jarvis showed a visual lesson in his window: {lesson.title})\n" + "\n".join(shown)
