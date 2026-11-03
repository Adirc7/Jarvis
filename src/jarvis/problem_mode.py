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
    ANSWER_TOLERANCE,
    PRACTICE_SPREAD,
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

def _rx(pattern: str) -> re.Pattern:
    """A rule over normalised text: no zero-width joiners (normalize drops them), any case."""
    return re.compile(pattern.replace("‍", ""), re.IGNORECASE)


# In a problem, by voice: English, Singlish and Sinhala. Sinhala words are matched without \b (its vowel
# signs aren't word characters to the regex engine).
_LEAD = r"^(?:(?:ok|okay|now|so|and|then|jarvis|friday|please|hari|ithin|ane|let's do|lets do|go to|show me|open)\s+)*"
_ID = r"([a-h]|iv|v?i{1,3}|v)"
PART = _rx(_LEAD + rf"(?:(?:part|question|kotasa|කොටස)\s*\(?{_ID}\)?\b|\(?{_ID}\)?\s*(?:part|kotasa|kotase|kotasata|කොටස))")
HINT = _rx(r"\b(hint|clue|nudge|help me start|iggiya|iggiyak|podi udawwak)\b|ඉඟිය|පොඩි උදව්වක්")
STEP = _rx(_LEAD + r"(next(?: step)?|continue|go on|carry on|keep going|then what|what next|ilaga|ilagata|"
           r"issarahata|ඊළඟ|ඉස්සරහට)")
BACK = _rx(_LEAD + r"(back|previous(?: step)?|go back|step back|one back|kalin eka|kalin piyawara|aapahu|ආපහු|කලින්)")
SOLUTION = _rx(r"\b((?:full|whole|complete|all the|mulu) (?:solution|working|answer|steps|uththaraya)|solve it|"
               r"show (?:me )?(?:the )?(?:answer|solution)|just tell me|sampurna wisaduma|"
               r"(?:uththaraya|answer eka|solution eka) (?:pennanna|kiyanna|denna))\b|සම්පූර්ණ විසඳුම|මුළු විසඳුම|"
               r"උත්තරය (?:පෙන්නන්න|කියන්න)")
CHECK = re.compile(r"(?:\b(?:check (?:my )?(?:answer|this)|my answer is|i got|i get|is it|is the answer|"
                   r"the answer is|mage (?:uththaraya|answer eka)|mata (?:aawe|awa|aawa|aave)|check karanna)\b|"
                   r"මගේ උත්තරය|මට ආවේ|මට ආවා)[:\s]*(.+)$", re.IGNORECASE)
PRACTICE = _rx(r"\b(practi[cs]e|new numbers|another one|similar (?:question|problem)|try (?:one )?myself|"
               r"different numbers|aluth numbers|aluth ganan|thawa ekak|wena numbers)\b|පුහුණු|ප්‍රැක්ටිස්|"
               r"අලුත් ගණන්|තව එකක්")
SUMMARY = _rx(r"\b(summary|summari[sz]e|sum (?:it )?up|recap|the method|saaraamsaya|saramsaya)\b|සාරාංශ")

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
# The same units in Sinhala (as Sinhala-medium science says them) and Tamil. A unit not here is said as written.
UNIT_WORDS = {
    "si": {"m/s": "මීටර් තත්පරයට", "m/s^2": "මීටර් තත්පර වර්ගයට", "m/s²": "මීටර් තත්පර වර්ගයට", "m": "මීටර්",
           "km": "කිලෝමීටර්", "cm": "සෙන්ටිමීටර්", "mm": "මිලිමීටර්", "s": "තත්පර", "km/h": "පැයට කිලෝමීටර්",
           "kg": "කිලෝග්‍රෑම්", "g": "ග්‍රෑම්", "N": "නිව්ටන්", "J": "ජූල්", "kJ": "කිලෝජූල්",
           "kJ/mol": "මවුලයට කිලෝජූල්", "W": "වොට්", "V": "වෝල්ට්", "A": "ඇම්පියර්", "ohm": "ඕම්", "Ω": "ඕම්",
           "Pa": "පැස්කල්", "kPa": "කිලෝපැස්කල්", "K": "කෙල්වින්", "Hz": "හර්ට්ස්", "mol": "මවුල",
           "mol/L": "ලීටරයට මවුල", "M": "මවුලික", "mL": "මිලිලීටර්", "L": "ලීටර්", "rad": "රේඩියන්",
           "rad/s": "තත්පරයට රේඩියන්", "°": "අංශක", "deg": "අංශක", "C": "කූලෝම්", "F": "ෆැරඩ්", "T": "ටෙස්ලා",
           "eV": "ඉලෙක්ට්‍රෝන වෝල්ට්", "m^2": "වර්ග මීටර්", "m^3": "ඝන මීටර්"},
    "ta": {"m/s": "மீட்டர் ஒரு வினாடிக்கு", "m/s^2": "மீட்டர் ஒரு வினாடி வர்க்கத்துக்கு",
           "m/s²": "மீட்டர் ஒரு வினாடி வர்க்கத்துக்கு", "m": "மீட்டர்", "km": "கிலோமீட்டர்", "cm": "சென்டிமீட்டர்",
           "mm": "மில்லிமீட்டர்", "s": "வினாடி", "km/h": "மணிக்கு கிலோமீட்டர்", "kg": "கிலோகிராம்", "g": "கிராம்",
           "N": "நியூட்டன்", "J": "ஜூல்", "kJ": "கிலோஜூல்", "kJ/mol": "மோலுக்கு கிலோஜூல்", "W": "வாட்",
           "V": "வோல்ட்", "A": "ஆம்பியர்", "ohm": "ஓம்", "Ω": "ஓம்", "Pa": "பாஸ்கல்", "kPa": "கிலோபாஸ்கல்",
           "K": "கெல்வின்", "Hz": "ஹெர்ட்ஸ்", "mol": "மோல்", "mol/L": "லிட்டருக்கு மோல்", "M": "மோலார்",
           "mL": "மில்லிலிட்டர்", "L": "லிட்டர்", "rad": "ரேடியன்", "rad/s": "வினாடிக்கு ரேடியன்", "°": "டிகிரி",
           "deg": "டிகிரி", "C": "கூலூம்", "F": "ஃபாரட்", "T": "டெஸ்லா", "eV": "எலக்ட்ரான் வோல்ட்",
           "m^2": "சதுர மீட்டர்", "m^3": "கன மீட்டர்"},
}
# "5.27 × 10^-6": how "times ten to the (minus) 6" is said in each language
POWERS = {"en": (" times ten to the {minus}{e}", "minus "), "si": (" ගුණ කිරීම දහයේ බලය {minus}{e}", "සෘණ "),
          "ta": (" பெருக்கல் பத்தின் அடுக்கு {minus}{e}", "மைனஸ் ")}
WORDS = {
    "planning": {"en": "Let me work that out, step by step.", "si": "මම ඒක පියවරෙන් පියවර විසඳන්නම්.",
                 "ta": "நான் அதைப் படிப்படியாகத் தீர்க்கிறேன்."},
    "failed": {"en": "Sorry, I couldn't set that problem up. Ask me again with all its numbers, or one part of it.",
               "si": "සමාවෙන්න, ඒ ප්‍රශ්නය හදන්න බැරි වුණා. ඉලක්කම් ඔක්කොම එක්ක ආයෙත් අහන්න.",
               "ta": "மன்னிக்கவும், அந்தக் கணக்கை அமைக்க முடியவில்லை. மீண்டும் கேளுங்கள்."},
    "reading": {"en": "Let me read that.", "si": "මම ඒක කියවන්නම්.", "ta": "நான் அதைப் படிக்கிறேன்."},
    "unreadable": {"en": "I couldn't read a problem in that. A clearer photo, or a screenshot of the page, would help.",
                   "si": "ඒකෙන් ප්‍රශ්නයක් කියවගන්න බැරි වුණා. පැහැදිලි ෆොටෝ එකක් එවන්න.",
                   "ta": "அதிலிருந்து கணக்கைப் படிக்க முடியவில்லை. தெளிவான படத்தை அனுப்புங்கள்."},
    "opened": {"en": "{title}. {n} parts. Pick a part, or say part a, then ask for a hint or the next step.",
               "si": "{title}. කොටස් {n}ක් තියෙනවා. කොටසක් තෝරන්න, නැත්නම් a කොටස කියන්න, ඊට පස්සේ ඉඟියක් හරි ඊළඟ පියවර හරි අහන්න.",
               "ta": "{title}. {n} பகுதிகள். ஒரு பகுதியைத் தேர்ந்தெடுங்கள், பிறகு குறிப்பு அல்லது அடுத்த படி கேளுங்கள்."},
    "part": {"en": "Part {id}: {ask}. Want a hint, or the first step?",
             "si": "{id} කොටස: {ask}. ඉඟියක් ඕනෙද, නැත්නම් පළවෙනි පියවර?",
             "ta": "பகுதி {id}: {ask}. குறிப்பு வேண்டுமா, அல்லது முதல் படியா?"},
    "no_hint": {"en": "Think about which equation links what you know to what you want.",
                "si": "ඔයා දන්න දේවල් සහ හොයන දේ සම්බන්ධ කරන සමීකරණය මොකක්ද කියලා හිතන්න.",
                "ta": "தெரிந்ததையும் தேடுவதையும் இணைக்கும் சமன்பாடு எது என்று யோசியுங்கள்."},
    "gives": {"en": "That gives {value} {unit}.", "si": "ඒකෙන් {value} {unit} එනවා.", "ta": "அது {value} {unit} தருகிறது."},
    "answer": {"en": "So part {id} is {value} {unit}.", "si": "ඉතින් {id} කොටසේ උත්තරය {value} {unit}.",
               "ta": "எனவே பகுதி {id} இன் விடை {value} {unit}."},
    "units": {"en": "Careful: the units of this step don't come out as {unit}, so the set-up may be wrong.",
              "si": "පරිස්සමෙන්: මේ පියවරේ ඒකක {unit} විදියට එන්නේ නෑ, ඒ නිසා ගණන සකස් කරපු විදිය වැරදි වෙන්න පුළුවන්.",
              "ta": "கவனம்: இந்தப் படியின் அலகுகள் {unit} ஆக வரவில்லை, அமைப்பு தவறாக இருக்கலாம்."},
    "disagree": {"en": "Careful: {said}, so the steps or the animation are set up wrong.",
                 "si": "පරිස්සමෙන්: {said}. ඒ නිසා පියවර හරි ඇනිමේෂන් එක හරි වැරදියි.",
                 "ta": "கவனம்: {said}. படிகளோ அனிமேஷனோ தவறாக அமைக்கப்பட்டுள்ளன."},
    "last": {"en": "That was the last step.", "si": "ඒ තමයි අන්තිම පියවර.", "ta": "அதுதான் கடைசி படி."},
    "start": {"en": "Back to the start.", "si": "ආයෙත් මුලට.", "ta": "மீண்டும் தொடக்கத்திற்கு."},
    "unchecked": {"en": "I couldn't check this part's answer myself, so take it with care.",
                  "si": "මේ කොටසේ උත්තරය මට චෙක් කරගන්න බැරි වුණා, ඒ නිසා පරිස්සමෙන් බලන්න.",
                  "ta": "இந்தப் பகுதியின் விடையை என்னால் சரிபார்க்க முடியவில்லை."},
    "practice": {"en": "Here's the same problem with new numbers. Try it yourself, then check your answers; ask for a hint "
                       "if you're stuck.",
                 "si": "ඔන්න අලුත් ඉලක්කම් එක්ක එකම ප්‍රශ්නය. තනියම හදලා බලන්න, ඊට පස්සේ උත්තර චෙක් කරන්න. හිර වුණොත් ඉඟියක් අහන්න.",
                 "ta": "புதிய எண்களுடன் அதே கணக்கு. நீங்களே முயன்று, பிறகு விடைகளைச் சரிபார்க்கவும்."},
    "no_practice": {"en": "I couldn't make a version with new numbers that works out, sorry.",
                    "si": "සමාවෙන්න, අලුත් ඉලක්කම් එක්ක හරියන ප්‍රශ්නයක් හදන්න බැරි වුණා.",
                    "ta": "மன்னிக்கவும், புதிய எண்களுடன் கணக்கை உருவாக்க முடியவில்லை."},
    "method": {"en": "That's the method.", "si": "ඔන්න ඒ තමයි ක්‍රමය.", "ta": "அதுதான் முறை."},
    "pick": {"en": "There are {n} questions on that sheet. Pick one in my window.",
             "si": "ඒකේ ප්‍රශ්න {n}ක් තියෙනවා. වින්ඩෝ එකේ එකක් තෝරන්න.",
             "ta": "அதில் {n} கேள்விகள் உள்ளன. ஒன்றைத் தேர்ந்தெடுங்கள்."},
}


def spoken_number(text: str, lang: str = "en") -> str:
    """'5.27 × 10^-6' -> '5.27 times ten to the minus 6' (in `lang`)."""
    words, minus = POWERS.get(lang, POWERS["en"])
    return re.sub(r"\s*×\s*10\^(-?)(\d+)",
                  lambda m: words.format(minus=minus if m.group(1) else "", e=m.group(2)), text or "")


def spoken_unit(unit: str, lang: str = "en") -> str:
    unit = (unit or "").strip()
    if lang in UNIT_WORDS:
        return UNIT_WORDS[lang].get(unit, unit)
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
                    return await self._problem_do("part", (m.group(1) or m.group(2)).lower(), turn=turn,
                                                  token=token)
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
        line = self._problem_words("opened", title=problem.title, n=n)
        if n == 1 and lang.code == "en":
            line = line.replace("1 parts", "1 part")
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
        from pathlib import Path

        from .knowledge import problem_views_more
        if problem_views_more.MOLECULE_DIR is None:      # molecules from PubChem are kept here, fetched once
            problem_views_more.MOLECULE_DIR = Path(str(self.settings.get("general.state_dir", "state"))) / "molecules"
        context = "\n".join(m["content"][:300] for m in self.history[-4:])
        messages = [{"role": "system", "content": problem_prompt(question, lang.name, context)},
                    {"role": "user", "content": "Plan it. JSON only."}]
        loop = asyncio.get_running_loop()
        problem = None
        for attempt in range(2):
            text = await self._collect(messages, "problem", lang.code, token, None)
            try:
                problem = parse_problem(text)
                problem.lang = lang.code                 # the marks, the animation's check and the card in it
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
                         {"role": "user", "content": "These steps have problems: " + "; ".join(failed)[:900]
                          + ". Fix them (SymPy syntax, explicit *, only defined names; every given value in SI with "
                            "its unit, each step's unit right for what it computes; if the units are wrong, the "
                            "physics set-up is) and reply with the whole JSON."}]
        if problem is None:
            raise ProblemError("no usable plan")
        self._problem_keep(question, text, problem)
        return problem

    def _problem_keep(self, question: str, reply: str, problem: Problem) -> None:
        """The question, the model's plan as it wrote it, and what SymPy and the checks found: one file a
        problem in state/problems (the newest [problems] keep_plans kept), to see what the model did when one looks wrong."""
        import time
        from pathlib import Path
        folder = Path(str(self.settings.get("general.state_dir", "state"))) / "problems"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", problem.title.lower()).strip("-")[:40] or "problem"
            path = folder / f"{time.strftime('%Y-%m-%d %H%M%S')} {slug}.json"
            answers = {p.id: {k: problem.answer_of(p).get(k) for k in ("shown", "unit", "units", "view_check")}
                       for p in problem.parts}
            path.write_text(json.dumps({"question": question, "provider": self.llm.last_provider, "plan": reply,
                                        "notes": problem.notes, "answers": answers}, indent=1, ensure_ascii=False),
                            encoding="utf-8")
            keep = max(1, int(self.settings.get("problems.keep_plans", 100)))
            for old in sorted(folder.glob("*.json"))[:-keep]:
                old.unlink()
        except OSError as exc:
            self.out(f"[problem] couldn't keep the plan ({type(exc).__name__})")

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
            line = self._problem_words("part", id=part.id, ask=part.ask.rstrip("?."))
        elif action == "hint" and part is not None:
            ex["hint"] = True
            line = part.hint or self._problem_words("no_hint")
        elif action == "step" and part is not None:
            if ex["shown"] >= len(part.steps):
                line = self._problem_answer_line(problem, part, last=True)
            else:
                ex["shown"] += 1
                line = self._problem_step_line(problem, part, ex["shown"] - 1)
        elif action == "back" and part is not None:
            ex["shown"] = max(0, ex["shown"] - 1)
            line = self._problem_step_line(problem, part, ex["shown"] - 1) if ex["shown"] else self._problem_words("start")
        elif action == "solution" and part is not None:
            ex["shown"] = len(part.steps)
            line = " ".join(s.say for s in part.steps if s.say) + " " + self._problem_answer_line(problem, part)
        elif action == "check" and part is not None:
            ok, said = check_answer(problem, part.id, answer,
                                    float(self.settings.get("problems.answer_tolerance", ANSWER_TOLERANCE)))
            ex["check"] = {"ok": bool(ok), "said": said}
            line = said
        elif action == "practice":
            try:
                spread = tuple(float(x) for x in self.settings.get("problems.practice_spread", PRACTICE_SPREAD))
                fresh = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: practice(ex["original"], spread=spread))
            except ProblemError:
                line = self._problem_words("no_practice")
            else:
                ex.update(plan=fresh, part="", shown=0, hint=False, check=None, summary=False)
                self._show("problem", data=fresh.as_data(), state=self._problem_state())
                self.history.append({"role": "assistant", "content": problem_for_the_model(fresh)})
                line = self._problem_words("practice")
                self.telemetry.log("problem_practice", seed=fresh.seed)
                await self.sink.say(line, lang, token)
                if turn is not None:
                    turn.finish(kind="problem", action=action)
                return line
        elif action == "summary":
            ex["summary"] = True
            line = ". ".join(problem.summary) or self._problem_words("method")
        elif action == "close":
            self._problem_close()
            return ""
        self._show("problem_state", state=self._problem_state())
        self.telemetry.log("problem_action", action=action, part=ex.get("part"), shown=ex.get("shown"))
        if line:
            await self.sink.say(spoken_number(line, lang.code), lang, token)
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
            line += " " + self._problem_words("gives", value=r["shown"], unit=self._said_unit(r.get("unit", ""))).replace(
                "  ", " ").replace(" .", ".")
        if r.get("units") == "wrong":
            line += " " + self._problem_words("units", unit=self._said_unit(r.get("unit", "") or part.unit))
        if i == len(part.steps) - 1:
            line += " " + self._problem_answer_line(problem, part)
        return line.strip()

    def _said_unit(self, unit: str) -> str:
        return spoken_unit(unit, self.lang.current.code)

    def _problem_answer_line(self, problem: Problem, part: Any, last: bool = False) -> str:
        ans = problem.answer_of(part)
        if not ans:
            return self._problem_words("unchecked")
        unit = self._said_unit(ans.get("unit", "") or part.unit)
        lead = self._problem_words("last") + " " if last else ""
        line = lead + self._problem_words("answer", id=part.id, value=ans["shown"], unit=unit)
        vc = ans.get("view_check") or {}
        if vc.get("ok") is False:
            line += " " + self._problem_words("disagree", said=vc["said"])
        return line.replace("  ", " ").replace(" .", ".")

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
