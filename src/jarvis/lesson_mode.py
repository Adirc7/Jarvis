"""Lesson mode: Jarvis teaches step by step while his window shows each step.

    "explain entropy"   Jarvis answers, and offers when a picture would help: "Want me to show it?"
    "yes"               one model call plans the lesson (JSON, knowledge/lessons.py); SymPy works out the
                        graphs and Wikipedia gives the pictures; then each step is spoken while the window
                        shows its visual (ui/lesson.js)
    "show me", "visualise it", or any request to see something: the same, on what you asked
    "next", "back", "again", "pause", "continue", "from the start", or the window's buttons

The lesson plays beside the one-request-at-a-time lock, with its own stop: a question
asked in the middle pauses it (Jarvis answers; "continue" carries on), a button press
stops the step being spoken at once, and push-to-talk or the kill switch stop it like
any speech.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from .agent.llm import LLMUnavailable
from .knowledge.lessons import (
    Lesson,
    PlanError,
    lesson_for_the_model,
    parse_plan,
    plan_prompt,
    resolve,
    sketch_html,
    sketch_prompt,
)
from .language import normalize
from .state import Mode

OFFER_NOTE = ("Jarvis's window can show a visual lesson: he explains step by step while it shows simulations, 3D "
              "graphs, diagrams and pictures. If seeing it would make this clearer, end your answer with one short "
              "question offering it, in the reply's language (\"Want me to show it?\"), and don't describe the "
              "visual. If the user asks to see, visualise, simulate, animate or draw something, call show_lesson.")
GROUP_NOTE = ("show_lesson to teach it visually in Jarvis's window (he explains step by step while it shows "
              "simulations, 3D graphs, diagrams or pictures) when the user wants to see something")
LESSON_SPEC = {"type": "function", "function": {
    "name": "show_lesson",
    "description": ("Teach something visually in Jarvis's window: Jarvis explains it step by step while the window "
                    "shows simulations, 3D graphs, diagrams or pictures. Use it when the user asks to see, "
                    "visualise, simulate, animate or draw something, or says yes to your offer to show it."),
    "parameters": {"type": "object", "properties": {
        "topic": {"type": "string", "maxLength": 160,
                  "description": "what to teach, as the user means it (e.g. 'entropy in a gas', 'how a lens works')"},
        "focus": {"type": "string", "maxLength": 200,
                  "description": "optional: the part to show, or what the user found hard"}},
        "required": ["topic"]}}}
VISUAL_WORDS = re.compile(
    r"\bshow\b|visuali[sz]|picture|diagram|simulat|animat|\b3d\b|three d|\bdraw|illustrat|demonstrat|"
    r"pennanna|penanna|පෙන්නන්න|පෙන්වන්න", re.IGNORECASE)
# "show me", "visualise it", "can you show that in 3D": a short request to see what was just explained
SHOW_IT = re.compile(
    r"^(?:(?:ok|okay|yes|sure|now|so|please|jarvis|friday|can you|could you|will you|would you)\s+)*"
    r"(?:show|visuali[sz]e|animate|simulate|draw|demonstrate|picture)\s+(?:it|that|this|me|us)"
    r"(?:\s+(?:it|that|this|please|visually|in 3d|in three d|on (?:the )?(?:screen|window)|to me|for me|now|then))*$")
SHOW_IT_SI = {"pennanna", "penanna", "eka pennanna", "meka pennanna", "පෙන්නන්න", "ඒක පෙන්නන්න", "මේක පෙන්නන්න",
              "පෙන්වන්න", "ඒක පෙන්වන්න"}
OFFERED = re.compile(
    r"(?:want|shall|should|would you like|like|may)\b[^?.!]{0,40}?\b(?:show|visuali[sz]e|draw|animate|simulate|"
    r"demonstrate|see it|see this|see that)\b[^?]{0,80}\?\s*$|(?:පෙන්නන්න|පෙන්වන්න)[^?]{0,30}\?\s*$",
    re.IGNORECASE)
YES_WORDS = {"yes", "yeah", "yep", "yup", "ya", "yah", "sure", "ok", "okay", "alright", "please", "definitely",
             "absolutely", "course", "ow", "ou", "ov", "hari", "ha", "හා", "ඔව්", "හරි", "ඔව", "pennanna",
             "පෙන්නන්න"}
YES_PHRASES = ("go ahead", "do it", "show me", "show it", "let s see", "let s do it", "why not", "of course",
               "i d like that", "that would help")
NO_WORDS = {"no", "nah", "nope", "don", "dont", "later", "skip", "epa", "එපා", "නෑ", "naa", "na", "not"}
FILLER = {"jarvis", "friday", "please", "ok", "okay", "so", "now", "um", "uh", "hey"}
CONTROLS = {
    "next": {"next", "next step", "next one", "next please", "and then", "what next", "what s next", "move on",
             "ilanga", "ilangata", "ilanga eka", "ඊළඟ", "ඊළඟට", "ඊළඟ එක", "ඉස්සරහට", "issarahata"},
    "prev": {"back", "go back", "previous", "previous step", "previous one", "step back", "the step before",
             "aapahu", "apahu", "kalin eka", "ආපහු", "කලින් එක"},
    "again": {"again", "repeat", "repeat that", "say that again", "say it again", "once more", "one more time",
              "aye", "aaye", "ayeth", "aye kiyanna", "ආයේ", "ආයෙත්", "ආයේ කියන්න"},
    "restart": {"start again", "from the start", "from the beginning", "start over", "restart", "mula indan",
                "මුල ඉඳන්"},
    "pause": {"pause", "stop", "wait", "hold on", "hang on", "one moment", "nawaththanna", "poddak inna", "inna",
              "නවත්තන්න", "පොඩ්ඩක් ඉන්න", "ඉන්න"},
    "play": {"continue", "resume", "play", "go on", "carry on", "keep going", "go ahead", "digatama", "දිගටම"},
}
WORDS = {
    "planning": {"en": "Let me draw that for you.", "si": "මම ඒක ඔයාට පෙන්නන්නම්.",
                 "ta": "நான் அதை வரைந்து காட்டுகிறேன்."},
    "failed": {"en": "Sorry, I couldn't put that lesson together. Ask me again, or ask about one part of it.",
               "si": "සමාවෙන්න, මට ඒ පාඩම හදන්න බැරි වුණා. ආයෙත් අහන්න, නැත්නම් එක කොටසක් ගැන අහන්න.",
               "ta": "மன்னிக்கவும், அந்தப் பாடத்தை உருவாக்க முடியவில்லை. மீண்டும் கேளுங்கள்."},
    "no_window": {"en": "My window isn't running, so I can't show it here.",
                  "si": "මගේ window එක වැඩ කරන්නේ නෑ, ඒ නිසා පෙන්නන්න බෑ.",
                  "ta": "என் சாளரம் இயங்கவில்லை, அதனால் காட்ட முடியாது."},
    "done": {"en": "That's the whole picture. Ask me about any part of it, or say again.",
             "si": "ඔන්න ඒ තමයි මුළු කතාව. ඕනම කොටසක් ගැන අහන්න.",
             "ta": "அவ்வளவுதான். எந்தப் பகுதியைப் பற்றியும் கேளுங்கள்."},
    "end": {"en": "That was the last step.", "si": "ඒ තමයි අන්තිම පියවර.", "ta": "அதுதான் கடைசி படி."},
}


class LessonToken:
    """Stops a lesson: by its own stop (a button, a new question) or the turn's (push-to-talk, the kill switch)."""

    def __init__(self, base):
        self.base, self.stopped = base, False

    @property
    def cancelled(self) -> bool:
        return self.stopped or self.base.cancelled


def lesson_action(text: str) -> str | None:
    """'next', 'again', 'pause'... if the words are only a lesson control."""
    words = normalize(text).split()
    while words and words[0] in FILLER:
        words = words[1:]
    while words and words[-1] in FILLER:
        words = words[:-1]
    said = " ".join(words)
    return next((action for action, phrases in CONTROLS.items() if said in phrases), None)


def said_yes(text: str) -> bool:
    said = " ".join(normalize(text).split())
    words = said.split()
    if not words or len(words) > 6 or any(w in NO_WORDS for w in words):
        return False
    return words[0] in YES_WORDS or any(said.startswith(p) for p in YES_PHRASES)


def asks_to_see_it(text: str) -> bool:
    said = " ".join(normalize(text).split())
    return bool(SHOW_IT.match(said)) or said in SHOW_IT_SI


class LessonMode:
    """Part of App (app.py): the lesson's state, planning, playing and controls."""

    def _init_lessons(self) -> None:
        self.lesson: Lesson | None = None
        self.lesson_id = 0
        self.lesson_index = 0                 # the step shown now
        self._lesson_spoken = -1              # the last step said all the way through
        self.lesson_playing = False
        self._lesson_task: asyncio.Task | None = None
        self._lesson_token: LessonToken | None = None
        self._offer: tuple[str, str] | None = None      # (question, reply) when Jarvis offered to show it
        self._teachable: tuple[str, str] | None = None  # the last explanation, for "show me"
        self._last_route = ""
        self._sketch_fixes: set[int] = set()

    def _lesson_words(self, key: str) -> str:
        options = WORDS[key]
        return options.get(self.lang.current.code, options["en"])

    # ---- deciding -------------------------------------------------------------------------
    def _lesson_noted(self, question: str, reply: str) -> None:
        """After every reply: did Jarvis offer to show it? Was it an explanation worth showing?"""
        self._offer = (question, reply) if OFFERED.search(reply[-240:]) else None
        if self._last_route in ("teach", "maths") or self._offer:
            self._teachable = (question, reply)

    async def _lesson_turn(self, text: str, turn, token) -> str | None:
        """A lesson control, a yes to the offer, or a request to see it; None for anything else
        (a question in the middle of a lesson pauses it, and Jarvis answers it)."""
        offer, self._offer = self._offer, None
        if self.lesson is not None and self.panel == "lesson" and (action := lesson_action(text)):
            return await self._lesson_control(action, turn)
        if offer is not None and said_yes(text) and self.view is not None:
            return await self._lesson(offer[0], offer[1], text, turn, token, how="offer")
        if self._teachable is not None and self.view is not None and asks_to_see_it(text):
            question, reply = self._teachable
            return await self._lesson(question, reply, text, turn, token, how="asked")
        self._pause_lesson("question")
        return None

    def _visual_offered(self, text: str, route: str) -> bool:
        """Offer show_lesson to the model this turn? Only with a window to show it in."""
        return self.view is not None and (route in ("teach", "maths") or bool(VISUAL_WORDS.search(text))
                                          or self.panel == "lesson")

    async def _lesson_from_tool(self, arguments: str, text: str, turn, token) -> str:
        """The model called show_lesson."""
        try:
            args = json.loads(arguments or "{}")
        except ValueError:
            args = {}
        topic = str(args.get("topic") or text).strip()[:160]
        focus = str(args.get("focus") or "").strip()[:200]
        question = topic + (f" (focus: {focus})" if focus else "")
        context = self.history[-1]["content"] if self.history and self.history[-1]["role"] == "assistant" else ""
        return await self._lesson(question, context, text, turn, token, how="tool")

    # ---- planning -----------------------------------------------------------------------------
    async def _lesson(self, question: str, context: str, text: str, turn, token, how: str) -> str:
        from .app import ToolSaid
        lang = self.lang.current
        if self.view is None:
            return await self._tool_reply(text, ToolSaid("lesson_no_window", self._lesson_words("no_window")),
                                          turn, token)
        self._stop_lesson_task()
        if not self.view.viewers:                   # open the window now: it's ready by the time the plan is
            try:
                self._open_window(self.view.url)
            except Exception as exc:  # noqa: BLE001 - no browser: the plan still goes to /lesson
                self.out(f"[window] couldn't open it ({type(exc).__name__})")
        self.state.mode = Mode.THINKING
        started = time.perf_counter()
        intro = asyncio.create_task(self.sink.say(self._lesson_words("planning"), lang, token))
        try:
            lesson = await self._plan_lesson(question, context, lang, token)
        except (PlanError, LLMUnavailable) as exc:
            await intro
            self.telemetry.log("lesson_error", how=how, error=f"{type(exc).__name__}: {exc}"[:300])
            return await self._tool_reply(text, ToolSaid("lesson_failed", self._lesson_words("failed")), turn, token)
        finally:
            if self.state.mode == Mode.THINKING:
                self.state.mode = Mode.IDLE
        await intro
        if token.cancelled:
            self._cancelled(turn, "lesson_plan")
            return ""
        self.lesson, self.lesson_id = lesson, self.lesson_id + 1
        self.lesson_index, self._lesson_spoken, self._sketch_fixes = 0, -1, set()
        self.panel = "lesson"
        self._show("lesson", id=self.lesson_id, **lesson.as_data())
        summary = lesson_for_the_model(lesson)
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": summary}]
        if self.memory.enabled and self.settings.get("memory.keep_conversation", True):
            self.memory.set_recent(self.history[-24:])           # HISTORY_TURNS * 2, as app.py keeps
            self.memory.save()
        kinds = [s.visual["kind"] + (f":{s.visual['name']}" if s.visual.get("name") else "")
                 for s in lesson.steps if s.visual]
        turn.finish(kind="lesson", how=how, steps=len(lesson.steps), visuals=kinds, notes=lesson.notes[:6],
                    provider=self.llm.last_provider, ms=round((time.perf_counter() - started) * 1000),
                    language=lang.code)
        self._start_lesson_task(0)
        return f"{lesson.title}: a lesson in {len(lesson.steps)} steps, in the window."

    async def _plan_lesson(self, question: str, context: str, lang, token) -> Lesson:
        messages = [{"role": "system", "content": plan_prompt(question, context, lang.name)},
                    {"role": "user", "content": "Plan the lesson. JSON only."}]
        # Another model than the one that just answered, when there is one (its minute's allowance is
        # spent); not for Sinhala, where the best Sinhala writer stays first.
        avoid = self.llm.last_provider if lang.code != "si" else None
        text = await self._collect(messages, "teach", lang.code, token, avoid)
        try:
            lesson = parse_plan(text)
        except PlanError as exc:
            self.telemetry.log("lesson_retry", error=str(exc)[:200])
            messages += [{"role": "assistant", "content": text[:3000]},
                         {"role": "user", "content": f"That isn't a usable plan ({exc}). Reply with the JSON only."}]
            lesson = parse_plan(await self._collect(messages, "teach", lang.code, token, None))
        sketches = [s for s in lesson.steps if s.visual and s.visual["kind"] == "sketch"]
        for extra in sketches[1:]:
            extra.visual = None
            lesson.notes.append("one sketch a lesson: a later one dropped")
        loop = asyncio.get_running_loop()
        jobs = [loop.run_in_executor(None, resolve, lesson, getattr(self.info, "research", None))]
        if sketches:
            jobs.append(self._write_sketch(sketches[0].visual, lesson.title, token))
        await asyncio.gather(*jobs)
        return lesson

    async def _collect(self, messages: list[dict], route: str, lang: str, token, avoid: str | None) -> str:
        parts = []
        async for piece in self.llm.stream_text(messages, token=token, route=route, lang=lang, avoid=avoid):
            if isinstance(piece, str):
                parts.append(piece)
        return "".join(parts)

    async def _write_sketch(self, visual: dict, title: str, token, error: str = "") -> None:
        """The model writes the drawing (route "code"); it runs in the window's sandbox."""
        messages = [{"role": "system", "content": sketch_prompt(visual["description"], title)},
                    {"role": "user", "content": "Write it."}]
        if error and visual.get("code"):
            messages += [{"role": "assistant", "content": visual["code"][:12000]},
                         {"role": "user", "content": f"It failed in the browser with: {error[:300]}. "
                                                     "Reply with the fixed HTML only."}]
        try:
            visual["code"] = sketch_html(await self._collect(messages, "code", "en", token, None))
        except LLMUnavailable as exc:
            self.telemetry.log("lesson_sketch_error", error=str(exc)[:200])
            visual["code"] = visual.get("code", "") if error else ""

    # ---- playing ------------------------------------------------------------------------------
    def _start_lesson_task(self, start: int) -> None:
        self._stop_lesson_task()
        token = LessonToken(self.state.token())
        self._lesson_token = token
        self._lesson_task = asyncio.create_task(self._play_lesson(start, token))

    def _stop_lesson_task(self) -> None:
        speaking = self.lesson_playing and self.sink.busy
        if self._lesson_token is not None:
            self._lesson_token.stopped = True
        if speaking:
            self.sink.stop()                         # cut the step off now, not at its end
        self.lesson_playing = False

    def _pause_lesson(self, why: str) -> None:
        if self.lesson is None or not self.lesson_playing:
            return
        self._stop_lesson_task()
        self.telemetry.log("lesson_pause", why=why, step=self.lesson_index)
        self._show("lesson_step", id=self.lesson_id, i=self.lesson_index, playing=False)

    async def _play_lesson(self, start: int, token: LessonToken) -> None:
        lesson, lang = self.lesson, self.lang.current
        if lesson is None:
            return
        self.lesson_playing = True
        finished = False
        try:
            for i in range(start, len(lesson.steps)):
                if token.cancelled or lesson is not self.lesson:
                    return
                self.lesson_index = i
                self._show("lesson_step", id=self.lesson_id, i=i, playing=True)
                self.telemetry.log("lesson_step", step=i, lesson=self.lesson_id)
                await self.sink.say(lesson.steps[i].say, lang, token)
                if not self.sink.spoken:              # text mode: time to read it
                    await self._reading_pause(lesson.steps[i].say, token)
                if token.cancelled:
                    return
                self._lesson_spoken = i
            finished = True
            self._show("lesson_step", id=self.lesson_id, i=len(lesson.steps) - 1, playing=False, done=True)
            await self.sink.say(self._lesson_words("done"), lang, token)
        except Exception as exc:  # noqa: BLE001 - a broken voice mustn't leave the lesson "playing"
            self.telemetry.log("lesson_error", error=f"{type(exc).__name__}: {exc}"[:300])
        finally:
            if self._lesson_token is token:
                self.lesson_playing = False
                if not finished and lesson is self.lesson:
                    self._show("lesson_step", id=self.lesson_id, i=self.lesson_index, playing=False)

    async def _reading_pause(self, words: str, token) -> None:
        end = time.monotonic() + min(20.0, max(3.0, len(words) / 16))
        while time.monotonic() < end and not token.cancelled:
            await asyncio.sleep(0.1)

    # ---- controls (voice, typed, or the window's buttons) -------------------------------------
    def _lesson_go(self, action: str, step: int | None = None) -> str | None:
        """Do a control; returns the words to say when there's nowhere to go ("end"), else None."""
        if self.lesson is None:
            return None
        n, i = len(self.lesson.steps), self.lesson_index
        if action == "pause":
            self._pause_lesson("asked")
            return None
        if action == "play":
            if self.lesson_playing:
                return None
            target = i + 1 if self._lesson_spoken >= i else i       # carry on where it stopped
        else:
            target = {"next": i + 1, "prev": i - 1, "again": i, "restart": 0,
                      "goto": step if step is not None else i}.get(action, i)
        if target >= n:
            self._pause_lesson("end")
            self._show("lesson_step", id=self.lesson_id, i=n - 1, playing=False, done=True)
            return "end"
        self._start_lesson_task(max(0, target))
        return None

    async def _lesson_control(self, action: str, turn) -> str:
        said = self._lesson_go(action)
        self.telemetry.log("lesson_control", action=action, step=self.lesson_index)
        turn.finish(kind="lesson_control", action=action)
        if not said:
            return ""                        # the window and the voice already show it
        words = self._lesson_words(said)
        await self.sink.say(words, self.lang.current, self.state.token())
        return words

    def _lesson_button(self, event: dict) -> None:
        """From the window (on the loop): a lesson button, or a sketch that failed to run."""
        if "lesson" in event:
            said = self._lesson_go(event["lesson"], event.get("step"))
            self.telemetry.log("lesson_control", action=event["lesson"], source="window", step=self.lesson_index)
            if said:
                asyncio.ensure_future(self.sink.say(self._lesson_words(said), self.lang.current, self.state.token()))
        elif "sketch_error" in event:
            asyncio.ensure_future(self._fix_sketch(int(event.get("step", 0)), str(event["sketch_error"])))

    async def _fix_sketch(self, step: int, error: str) -> None:
        """One repair a sketch: the model sees the error and writes it again."""
        lesson = self.lesson
        if lesson is None or step in self._sketch_fixes or not 0 <= step < len(lesson.steps):
            return
        visual = lesson.steps[step].visual
        if not visual or visual.get("kind") != "sketch":
            return
        self._sketch_fixes.add(step)
        self.telemetry.log("lesson_sketch_fix", step=step, error=error[:200])
        await self._write_sketch(visual, lesson.title, self.state.token(), error=error)
        if lesson is self.lesson and visual.get("code"):
            self._show("lesson_patch", id=self.lesson_id, step=step, code=visual["code"])

    # ---- for the window -----------------------------------------------------------------------
    def _lesson_snapshot(self) -> dict[str, Any] | None:
        if self.lesson is None:
            return None
        return {"id": self.lesson_id, "title": self.lesson.title, "step": self.lesson_index,
                "steps": len(self.lesson.steps), "playing": self.lesson_playing}

    def _lesson_data(self) -> dict[str, Any] | None:
        if self.lesson is None:
            return None
        return {"id": self.lesson_id, "step": self.lesson_index, "playing": self.lesson_playing,
                **self.lesson.as_data()}
