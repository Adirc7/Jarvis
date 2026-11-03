"""Problem mode: a question solved part by part in Jarvis's window, every number worked out by SymPy.

    "solve this: a car starts from rest ... (a) ... (b) ..."   the model plans (knowledge/problems.py), SymPy
                                works every step out, the window shows the problem and its parts (ui/problem.js)
    click a part, or say "part b"                 its card opens
    "hint", "next step", "back", "full solution"  one step at a time, each with its animation
    "check my answer: 25", "I got 80 metres"      Jarvis marks it against the worked answer
    "practice", "new numbers"                     the same problem with new numbers to try alone
    "summary"                                     the method in a few points
    a photo or a PDF dropped on the window        Gemini reads it; a sheet with several questions: pick one

Hints first and a step at a time, because that's what the research on tutoring finds works (VanLehn 2011;
worked examples and their fading, Renkl and Atkinson): docs/PROBLEMS.md.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any

from .agent.llm import LLMUnavailable
from .knowledge.problems import (
    Problem,
    ProblemError,
    check_answer,
    parse_problem,
    practice,
    problem_for_the_model,
    problem_prompt,
    work,
)
from .language import normalize

SOLVE_SPEC = {"type": "function", "function": {
    "name": "solve_problem",
    "description": ("Work through a problem with numbers or parts in Jarvis's window: physics, chemistry, maths, "
                    "statistics. Every number is worked out by the computer, each part gets a hint, steps and "
                    "an animation (motion and v-t graphs, forces, circuits, titration curves, kinetics, energy "
                    "profiles, equilibria, Newton's and Euler's methods, areas, and more). Use it for any exam or "
                    "textbook style question to solve, or when the user asks to be taken through a problem."),
    "parameters": {"type": "object", "properties": {
        "problem": {"type": "string", "maxLength": 3000,
                    "description": "the whole problem, with all its numbers and its parts (a), (b)..."}},
        "required": ["problem"]}}}
SOLVE_NOTE = ("solve_problem to work through a problem (numbers, parts (a), (b)...) step by step in Jarvis's window, "
              "with hints, SymPy-checked numbers and animations")
# "solve this problem: ...", "take me through this question", or a question with parts (a), (b)
SOLVE_WORDS = re.compile(
    r"\bsolve (?:this|the|that|my|a|these|following)\b|\b(work (?:it |this |that )?out|work through|step by step|"
    r"take me through|walk me through|help me (?:solve|with this (?:question|problem)))\b|"
    r"(?:^|\s)\(?[ab]\)\s|\bpart \(?a\)?\b|විසඳන්න|ගණනය කරන්න|visandanna|wisandanna|"
    r"\bsolve (?:karanna|karala|krnn|krla|kranna)\b", re.IGNORECASE)
PARTS = re.compile(r"(?:^|\s)\(?a\)\s.*(?:^|\s)\(?b\)\s", re.IGNORECASE | re.DOTALL)
HAS_NUMBER = re.compile(r"\d")
NOT_HERE = re.compile(r"\b(matlab|octave|python|code|script|program)\b", re.IGNORECASE)   # those have their own tools

PART = re.compile(r"^(?:(?:ok|okay|now|so|jarvis|please|let's do|lets do|go to|show me|open)\s+)*"
                  r"(?:part|question|කොටස)\s*\(?([a-h])\)?\b", re.IGNORECASE)
HINT = re.compile(r"\b(hint|clue|nudge|help me start|ඉඟිය|ඉඟියක්)\b", re.IGNORECASE)
STEP = re.compile(r"^(?:(?:ok|okay|yes|now|so|and|then|jarvis|please)\s+)*(next(?: step)?|continue|go on|"
                  r"carry on|keep going|then what|what next|ඊළඟ|ඊළඟ පියවර)\b", re.IGNORECASE)
BACK = re.compile(r"^(?:(?:ok|now|jarvis|please)\s+)*(back|previous(?: step)?|go back|step back|one back)\b",
                  re.IGNORECASE)
SOLUTION = re.compile(r"\b((?:full|whole|complete|all the) (?:solution|working|answer|steps)|solve it|"
                      r"show (?:me )?(?:the )?(?:answer|solution)|just tell me)\b", re.IGNORECASE)
CHECK = re.compile(r"\b(?:check (?:my )?(?:answer|this)|my answer is|i got|i get|is it|is the answer|"
                   r"the answer is)\b[:\s]*(.+)$", re.IGNORECASE)
PRACTICE = re.compile(r"\b(practi[cs]e|new numbers|another one|similar (?:question|problem)|try (?:one )?myself|"
                      r"different numbers|පුහුණු)\b", re.IGNORECASE)
SUMMARY = re.compile(r"\b(summary|summari[sz]e|sum (?:it )?up|recap|the method)\b", re.IGNORECASE)

READ_PROMPT = """Read the problem sheet. Reply with JSON only: {"questions": [{"label": "1", "text": "..."}]}
- One entry per separate question (1, 2, 3 or Q1, Q2...), each with its whole text, all its numbers and its parts
  (a), (b)... exactly as written; maths in plain text or LaTeX; describe any figure the question needs in words.
- Keep the question's own words. Don't solve anything."""

UNITS = {"m/s": "metres per second", "m/s^2": "metres per second squared", "m/s²": "metres per second squared",
         "m": "metres", "km": "kilometres", "cm": "centimetres", "mm": "millimetres", "s": "seconds",
         "km/h": "kilometres an hour", "kg": "kilograms", "g": "grams", "N": "newtons", "J": "joules",
         "kJ": "kilojoules", "kJ/mol": "kilojoules per mole", "W": "watts", "V": "volts", "A": "amps",
         "ohm": "ohms", "Ω": "ohms", "Pa": "pascals", "kPa": "kilopascals", "K": "kelvin", "Hz": "hertz",
         "mol": "moles", "mol/L": "moles per litre", "M": "molar", "mL": "millilitres", "L": "litres",
         "rad": "radians", "rad/s": "radians per second", "°": "degrees", "deg": "degrees", "C": "coulombs",
         "F": "farads", "T": "tesla", "eV": "electron volts", "m^2": "square metres", "m^3": "cubic metres"}
WORDS = {
    "planning": {"en": "Let me work that out, step by step.", "si": "මම ඒක පියවරෙන් පියවර විසඳන්නම්.",
                 "ta": "நான் அதைப் படிப்படியாகத் தீர்க்கிறேன்."},
    "failed": {"en": "Sorry, I couldn't set that problem up. Ask me again with all its numbers, or one part of it.",
               "si": "සමාවෙන්න, ඒ ප්‍රශ්නය හදන්න බැරි වුණා. ඉලක්කම් ඔක්කොම එක්ක ආයෙත් අහන්න.",
               "ta": "மன்னிக்கவும், அந்தக் கணக்கை அமைக்க முடியவில்லை. மீண்டும் கேளுங்கள்."},
    "reading": {"en": "Let me read that.", "si": "මම ඒක කියවන්නම්.", "ta": "நான் அதைப் படிக்கிறேன்."},
    "unreadable": {"en": "I couldn't read a problem in that. A clearer photo, or a screenshot of the page, would help.",
                   "si": "ඒකෙන් ප්‍රශ්නයක් කියවගන්න බැරි වුණා. පැහැදිලි photo එකක් එවන්න.",
                   "ta": "அதிலிருந்து கணக்கைப் படிக்க முடியவில்லை. தெளிவான படத்தை அனுப்புங்கள்."},
    "pick": {"en": "There are {n} questions on that sheet. Pick one in my window.",
             "si": "ඒකේ ප්‍රශ්න {n}ක් තියෙනවා. window එකේ එකක් තෝරන්න.",
             "ta": "அதில் {n} கேள்விகள் உள்ளன. ஒன்றைத் தேர்ந்தெடுங்கள்."},
}


def spoken_number(text: str) -> str:
    """'5.27 × 10^-6' -> '5.27 times ten to the minus 6'."""
    return re.sub(r"\s*×\s*10\^(-?)(\d+)", lambda m: f" times ten to the {'minus ' if m.group(1) else ''}{m.group(2)}",
                  text or "")


def spoken_unit(unit: str) -> str:
    unit = (unit or "").strip()
    return UNITS.get(unit, unit.replace("^2", " squared").replace("^3", " cubed").replace("/", " per "))


class ProblemMode:
    """Mixed into App (app.py), like LessonMode and ExploreMode."""

    _problem: dict | None = None

    def _problem_words(self, key: str, **kw: Any) -> str:
        options = WORDS[key]
        return options.get(self.lang.current.code, options["en"]).format(**kw)

    # ---- deciding -----------------------------------------------------------------------------------
    def _wants_problem(self, text: str) -> bool:
        """A problem to work through: asked to solve, with numbers and enough words to be a problem."""
        t = text.strip()
        if NOT_HERE.search(t) or len(t) < 60 or len(HAS_NUMBER.findall(t)) < 2:
            return False
        return bool(SOLVE_WORDS.search(t) or PARTS.search(t))

    async def _problem_turn(self, text: str, source: str, turn: Any, token: Any) -> str | None:
        """While a problem is open: its commands. Otherwise: a problem to solve, or None."""
        if source == "problem":
            return None
        ex = self._problem
        if ex is not None and self.panel == "problem":
            t = normalize(text)
            if len(t.split()) <= 12:
                m = PART.search(t)
                if m:
                    return await self._problem_do("part", m.group(1).lower(), turn=turn, token=token)
                if (c := CHECK.search(text)) and re.search(r"\d", c.group(1)):
                    return await self._problem_do("check", ex["part"], c.group(1), turn=turn, token=token)
                for rx, action in ((SOLUTION, "solution"), (HINT, "hint"), (BACK, "back"), (STEP, "step"),
                                   (PRACTICE, "practice"), (SUMMARY, "summary")):
                    if rx.search(t):
                        return await self._problem_do(action, ex["part"], turn=turn, token=token)
            if len(t.split()) > 12 and self._wants_problem(text):
                return await self._problem_open(text, turn, token)      # another problem
            return None                                  # a question about it: the model answers, with the note
        if self.view is not None and self._wants_problem(text):
            return await self._problem_open(text, turn, token)
        return None

    async def _problem_from_tool(self, arguments: str, text: str, turn: Any, token: Any) -> str:
        try:
            args = json.loads(arguments or "{}")
        except ValueError:
            args = {}
        problem = str(args.get("problem") or "").strip() or text
        return await self._problem_open(problem if len(problem) >= len(text) * 0.6 else text, turn, token)

    # ---- opening --------------------------------------------------------------------------------------
    async def _problem_open(self, question: str, turn: Any, token: Any, said: bool = False) -> str:
        from .app import ToolSaid
        lang = self.lang.current
        if self.view is None:
            return await self._tool_reply(question, ToolSaid("problem_no_window",
                                                             self._lesson_words("no_window")), turn, token)
        if not self.view.viewers:
            try:
                self._open_window(self.view.url)
            except Exception as exc:  # noqa: BLE001 - no browser: the problem still goes to the window
                self.out(f"[window] couldn't open it ({type(exc).__name__})")
        intro = None if said else asyncio.create_task(self.sink.say(self._problem_words("planning"), lang, token))
        try:
            problem = await self._plan_problem(question, lang, token)
        except (ProblemError, LLMUnavailable) as exc:
            if intro:
                await intro
            self.telemetry.log("problem_error", error=f"{type(exc).__name__}: {exc}"[:300])
            return await self._tool_reply(question, ToolSaid("problem_failed", self._problem_words("failed")),
                                          turn, token)
        if intro:
            await intro
        if token.cancelled:
            self._cancelled(turn, "problem_plan")
            return ""
        self._problem = {"plan": problem, "original": problem, "part": "", "shown": 0, "hint": False,
                         "check": None, "summary": False, "question": question}
        self.panel = "problem"
        self._show("problem", data=problem.as_data(), state=self._problem_state())
        n = len(problem.parts)
        line = (f"{problem.title}. {n} part{'s' if n != 1 else ''}. Pick a part, or say part a, then ask for a "
                "hint or the next step.")
        await self.sink.say(line, lang, token)
        summary = problem_for_the_model(problem)
        self.history += [{"role": "user", "content": question[:2000]}, {"role": "assistant", "content": summary}]
        if self.memory.enabled and self.settings.get("memory.keep_conversation", True):
            self.memory.set_recent(self.history[-24:])
            self.memory.save()
        unchecked = sum(1 for p in problem.parts for s in p.steps if s.calc and not s.result.get("ok"))
        turn.finish(kind="problem", parts=n, views=[v["kind"] for v in problem.shown_views.values()],
                    unchecked=unchecked, notes=problem.notes[:6], provider=self.llm.last_provider, language=lang.code)
        return line

    async def _plan_problem(self, question: str, lang: Any, token: Any) -> Problem:
        context = "\n".join(m["content"][:300] for m in self.history[-4:])
        messages = [{"role": "system", "content": problem_prompt(question, lang.name, context)},
                    {"role": "user", "content": "Plan it. JSON only."}]
        loop = asyncio.get_running_loop()
        problem = None
        for attempt in range(2):
            text = await self._collect(messages, "problem", lang.code, token, None)
            try:
                problem = parse_problem(text)
            except ProblemError as exc:
                self.telemetry.log("problem_retry", error=str(exc)[:200])
                messages += [{"role": "assistant", "content": text[:4000]},
                             {"role": "user", "content": f"That isn't a usable plan ({exc}). Reply with the JSON only."}]
                continue
            await loop.run_in_executor(None, work, problem)
            failed = [n for n in problem.notes if not n.startswith("view ")]
            if not failed or attempt == 1:
                break
            # Some calculations wouldn't run: once more, with what went wrong
            self.telemetry.log("problem_retry", error="; ".join(failed)[:300])
            messages += [{"role": "assistant", "content": text[:4000]},
                         {"role": "user", "content": "These calculations couldn't be run: " + "; ".join(failed)[:900]
                          + ". Fix them (SymPy syntax, explicit *, only defined names) and reply with the whole JSON."}]
        if problem is None:
            raise ProblemError("no usable plan")
        return problem

    # ---- doing ---------------------------------------------------------------------------------------
    def _problem_state(self) -> dict:
        ex = self._problem or {}
        return {"part": ex.get("part", ""), "shown": ex.get("shown", 0), "hint": ex.get("hint", False),
                "check": ex.get("check"), "summary": ex.get("summary", False)}

    async def _problem_do(self, action: str, part_id: str = "", answer: str = "", turn: Any = None,
                          token: Any = None) -> str:
        ex = self._problem
        if ex is None:
            return ""
        problem: Problem = ex["plan"]
        lang = self.lang.current
        token = token or self.state.token()
        part = problem.part(part_id or ex["part"]) or (problem.parts[0] if action in ("hint", "step", "solution",
                                                                                       "check") else None)
        if part is not None and part.id != ex["part"]:
            ex.update(part=part.id, shown=0, hint=False, check=None)
        line = ""
        if action == "part" and part is not None:
            line = f"Part {part.id}: {part.ask}. Want a hint, or the first step?"
        elif action == "hint" and part is not None:
            ex["hint"] = True
            line = part.hint or "Think about which equation links what you know to what you want."
        elif action == "step" and part is not None:
            if ex["shown"] >= len(part.steps):
                line = self._problem_answer_line(problem, part, last=True)
            else:
                ex["shown"] += 1
                line = self._problem_step_line(problem, part, ex["shown"] - 1)
        elif action == "back" and part is not None:
            ex["shown"] = max(0, ex["shown"] - 1)
            line = self._problem_step_line(problem, part, ex["shown"] - 1) if ex["shown"] else "Back to the start."
        elif action == "solution" and part is not None:
            ex["shown"] = len(part.steps)
            line = " ".join(s.say for s in part.steps if s.say) + " " + self._problem_answer_line(problem, part)
        elif action == "check" and part is not None:
            ok, said = check_answer(problem, part.id, answer)
            ex["check"] = {"ok": bool(ok), "said": said}
            line = spoken_number(said)
        elif action == "practice":
            try:
                fresh = await asyncio.get_running_loop().run_in_executor(None, practice, ex["original"])
            except ProblemError:
                line = "I couldn't make a version with new numbers that works out, sorry."
            else:
                ex.update(plan=fresh, part="", shown=0, hint=False, check=None, summary=False)
                self._show("problem", data=fresh.as_data(), state=self._problem_state())
                self.history.append({"role": "assistant", "content": problem_for_the_model(fresh)})
                line = ("Here's the same problem with new numbers. Try it yourself, then check your answers; "
                        "ask for a hint if you're stuck.")
                self.telemetry.log("problem_practice", seed=fresh.seed)
                await self.sink.say(line, lang, token)
                if turn is not None:
                    turn.finish(kind="problem", action=action)
                return line
        elif action == "summary":
            ex["summary"] = True
            line = ". ".join(problem.summary) or "That's the method."
        elif action == "close":
            self._problem_close()
            return ""
        self._show("problem_state", state=self._problem_state())
        self.telemetry.log("problem_action", action=action, part=ex.get("part"), shown=ex.get("shown"))
        if line:
            await self.sink.say(spoken_number(line), lang, token)
        if turn is not None:
            turn.finish(kind="problem", action=action, part=ex.get("part"))
        return line

    def _problem_step_line(self, problem: Problem, part: Any, i: int) -> str:
        if not 0 <= i < len(part.steps):
            return ""
        step = part.steps[i]
        line = step.say
        r = step.result
        if r.get("ok") and r.get("value") is not None:
            line += f" That gives {r['shown']} {spoken_unit(r.get('unit', ''))}.".replace("  ", " ")
        if i == len(part.steps) - 1:
            line += " " + self._problem_answer_line(problem, part)
        return line.strip()

    def _problem_answer_line(self, problem: Problem, part: Any, last: bool = False) -> str:
        ans = problem.answer_of(part)
        if not ans:
            return "I couldn't check this part's answer myself, so take it with care."
        unit = spoken_unit(ans.get("unit", "") or part.unit)
        lead = "That was the last step. " if last else ""
        return f"{lead}So part {part.id} is {ans['shown']} {unit}.".replace(" .", ".")

    def _problem_close(self) -> None:
        if self.panel == "problem":
            self.panel = ""
        self._show("problem_close")

    def _problem_ui(self, event: dict) -> None:
        """From the window (on the loop): a part, a button, an answer to check, or a question picked."""
        action = str(event.get("problem") or "")
        if action == "pick":
            picks = (self._problem_picks or [])
            i = int(event.get("index", -1))
            if 0 <= i < len(picks):
                self._problem_picks = None
                asyncio.ensure_future(self._problem_open_untracked(picks[i]["text"]))
            return
        if self._problem is None:
            return
        asyncio.ensure_future(self._problem_do(action, str(event.get("part") or ""), str(event.get("answer") or "")))

    _problem_picks: list | None = None

    async def _problem_open_untracked(self, question: str) -> None:
        token = self.state.token()
        turn = self.telemetry.turn(source="problem")
        async with self._turn_lock:
            await self._problem_open(question, turn, token)

    def _problem_data(self) -> dict | None:
        """For the window (GET /problem): the problem and where the user is in it."""
        ex = self._problem
        return None if ex is None else {"data": ex["plan"].as_data(), "state": self._problem_state()}

    def _problem_note(self) -> str:
        """For the language model: the problem on screen, so 'why do we square it?' is about it."""
        ex = self._problem
        if ex is None or self.panel != "problem":
            return ""
        problem: Problem = ex["plan"]
        note = "\n\n" + problem_for_the_model(problem)[:1500]
        part = problem.part(ex["part"])
        if part is not None and ex["shown"]:
            step = part.steps[min(ex["shown"], len(part.steps)) - 1]
            note += (f"\nThe user is on part ({part.id}), step {ex['shown']}: {step.goal or step.say[:80]} "
                     f"({step.latex[:120]}). 'This' and 'it' mean that step. Answer their question about it in "
                     "two or three spoken sentences; don't redo the whole problem.")
        return note

    # ---- a photo or a PDF ------------------------------------------------------------------------------
    def _window_upload(self, kind: str, data: bytes) -> None:
        """From the window's server thread: a photo or a PDF of a problem."""
        self._on_loop(lambda: asyncio.ensure_future(self._problem_from_file(kind, data)))

    async def _problem_from_file(self, kind: str, data: bytes) -> None:
        lang = self.lang.current
        token = self.state.token()
        turn = self.telemetry.turn(source="upload")
        await self.sink.say(self._problem_words("reading"), lang, token)
        try:
            if kind == "application/pdf":
                text = await asyncio.get_running_loop().run_in_executor(None, pdf_text, data)
                if len(text.strip()) < 40:
                    raise ProblemError("a scanned PDF (no text in it)")
                messages = [{"role": "system", "content": READ_PROMPT}, {"role": "user", "content": text[:20000]}]
                reply = await self._collect(messages, "long", lang.code, token, None)
            else:
                url = f"data:{kind};base64,{base64.b64encode(data).decode()}"
                messages = [{"role": "user", "content": [{"type": "text", "text": READ_PROMPT},
                                                         {"type": "image_url", "image_url": {"url": url}}]}]
                reply = await self._collect(messages, "vision", lang.code, token, None)
            questions = read_questions(reply)
        except (ProblemError, LLMUnavailable) as exc:
            self.telemetry.log("upload_error", kind=kind, error=f"{type(exc).__name__}: {exc}"[:200])
            await self.sink.say(self._problem_words("unreadable"), lang, token)
            turn.finish(kind="upload", ok=False)
            return
        self.telemetry.log("upload_read", kind=kind, questions=len(questions))
        if len(questions) == 1:
            async with self._turn_lock:
                await self._problem_open(questions[0]["text"], turn, token)
            return
        self._problem_picks = questions
        self.panel = "problem"
        self._show("problem_pick", questions=[{"label": q["label"], "text": q["text"][:300]} for q in questions])
        await self.sink.say(self._problem_words("pick", n=len(questions)), lang, token)
        turn.finish(kind="upload", ok=True, questions=len(questions))


def read_questions(reply: str) -> list[dict]:
    text = re.sub(r"```(?:json)?", "", reply or "").strip()
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start:end + 1]) if 0 <= start < end else {}
    except ValueError:
        data = {}
    out = []
    for i, q in enumerate((data.get("questions") or [])[:20] if isinstance(data, dict) else []):
        if isinstance(q, dict) and len(str(q.get("text") or "").strip()) >= 15:
            out.append({"label": str(q.get("label") or i + 1)[:10], "text": str(q["text"]).strip()[:3000]})
    if not out:
        raise ProblemError("no question in it")
    return out


def pdf_text(data: bytes, max_pages: int = 12) -> str:
    """The text of a PDF's first pages (pypdf). Empty for a scanned one."""
    import io

    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages[:max_pages])
    except Exception:  # noqa: BLE001 - a broken PDF is just one with no text
        return ""


__all__ = ["SOLVE_NOTE", "SOLVE_SPEC", "ProblemMode", "pdf_text", "read_questions", "spoken_number", "spoken_unit"]
