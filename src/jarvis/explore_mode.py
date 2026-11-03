"""The 3D explorer: take a car, a motorcycle or an engine apart with your hand, and Jarvis explains the parts.

    "show me a car taken apart", "explode the engine", "/explore motorcycle"   opens it in Jarvis's window
    open your hand / make a fist / point and pinch / two hands / peace sign    (perception/hand_controls.py)
    "take it apart", "put it back together", "next model", "close the 3D view"
    "what's the gearbox?", "show me the radiator"                              Jarvis pulls it out and explains

The models are knowledge/explore_models.py; the window draws them (ui/explore.js). While the explorer is
open it owns your hand: an open palm takes the model apart instead of stopping Jarvis (one mode owns the
hand at a time, D29). The camera turns on for it if it was off, and off again when it closes. Nothing is
recorded: only the 21 points of each hand go to the window.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from .knowledge.explore_models import GROUPS, MODELS, ORDER, find_part, model_for
from .language import normalize

OPEN_WORDS = re.compile(
    r"\b(apart|explod\w*|disassembl\w*|dismantl\w*|inside (?:of )?(?:a|an|the)\b|parts of|parts in|3d (?:model|view)|"
    r"exploded view|break \w+ down|explore|how \w+ (?:is|are) built|built inside|in 3d)\b|ගලව|කෑලි", re.IGNORECASE)
EXPLODE = re.compile(r"\b(take (?:it|them) apart|explode|open it up|apart|show (?:me )?(?:the )?inside)\b|ගලවන්න",
                     re.IGNORECASE)
ASSEMBLE = re.compile(r"\b(put (?:it )?(?:back )?together|assemble|reassemble|put it back|close it up|"
                      r"back together)\b|එකතු කරන්න", re.IGNORECASE)
NEXT = re.compile(r"\b(next (?:model|one)|another (?:model|one)|something else)\b", re.IGNORECASE)
CLOSE = re.compile(r"\b(close|leave|exit|stop|hide)\b.*\b(3d|explorer|model|view|car|bike|motorcycle|engine)\b|"
                   r"\bback to jarvis\b", re.IGNORECASE)
ABOUT = re.compile(r"\b(what|explain|show|tell|pull|pick|which|where|how does|how do|describe)\b", re.IGNORECASE)


class ExploreMode:
    """Mixed into App (app.py), like LessonMode."""

    _explore: dict | None = None

    # ---- requests ---------------------------------------------------------------------------------
    async def _explore_turn(self, text: str, source: str, turn: Any, token: Any) -> str | None:
        """A request for the explorer, or None for everything else."""
        if source == "explorer":                         # Jarvis's own question about a part
            return None
        t = normalize(text)
        ex = self._explore
        if ex is None:
            key = model_for(t)
            if key is None or not OPEN_WORDS.search(t):
                return None
            return await self._explore_say(self._explore_open(key), turn, token, "open")
        model = MODELS[ex["model"]]
        if CLOSE.search(t):
            self._explore_close()
            return await self._explore_say("Closed the 3D view.", turn, token, "close")
        if NEXT.search(t):
            return await self._explore_say(self._explore_open(_next(ex["model"])), turn, token, "next")
        named = model_for(t)
        if named is not None and named != ex["model"]:
            if OPEN_WORDS.search(t) or not ABOUT.search(t):
                return await self._explore_say(self._explore_open(named), turn, token, "open")
            # "how does Toyota's hybrid work?": the hybrid comes up on screen, and the model answers
            self._explore_open(named)
            return None
        part = find_part(model, t)
        if part is not None and (ABOUT.search(t) or len(t.split()) <= 6):
            asyncio.create_task(self._explain_part(part["id"]))
            turn.finish(kind="explore", action="part", part=part["id"])
            return ""
        if ASSEMBLE.search(t):
            self._show("explore_cmd", action="assemble")
            return await self._explore_say("Putting it back together.", turn, token, "assemble")
        if EXPLODE.search(t):
            self._show("explore_cmd", action="explode")
            return await self._explore_say("Taking it apart.", turn, token, "explode")
        return None

    def _explore_note(self) -> str:
        """For the language model: what's on screen, so "what does this do?" means the picked part."""
        ex = self._explore
        if ex is None:
            return ""
        model = MODELS[ex["model"]]
        part = next((p for p in model["parts"] if p["id"] == ex.get("part")), None)
        if part is None:
            return (f"\n\nJarvis's window shows a 3D model of a {model['title'].lower()} that the user can take "
                    "apart with their hand.")
        name = part["name"].lower()
        return (f"\n\nJarvis's window shows a 3D model of a {model['title'].lower()}, with the {name} picked "
                f"out: when the user says 'this' or 'it', they mean the {name} ({part['desc']})")

    async def _explore_say(self, line: str, turn: Any, token: Any, action: str) -> str:
        await self.sink.say(line, self.lang.current, token)
        turn.finish(kind="explore", action=action, model=(self._explore or {}).get("model"))
        return line

    # ---- opening and closing ----------------------------------------------------------------------
    def _explore_open(self, key: str) -> str:
        from .perception.hand_controls import ExploreHands
        model = MODELS[key]
        started = (self._explore or {}).get("started_camera", False)
        if self._explore is None:
            was_on = self.camera is not None and self.camera.running
            started = (not was_on) and self._start_camera()
        self._explore = {"model": key, "part": None, "started_camera": started}
        self._explore_hands = ExploreHands(
            str(self.settings.get("gestures.hand", "right")),
            open_fist=float(self.settings.get("explore.open_fist", 1.15)),
            open_flat=float(self.settings.get("explore.open_flat", 1.9)),
            pinch=float(self.settings.get("explore.pinch", 0.33)))
        camera_on = self.camera is not None and self.camera.running
        if camera_on:
            self.camera.on_hands = self._explore_on_hands
        self.panel = "explore"
        self._show("explore", model=model, groups=GROUPS, models=[[k, MODELS[k]["title"]] for k in ORDER])
        self.telemetry.log("explore", model=key, camera=camera_on)
        how = ("Open your hand slowly to take it apart, make a fist to put it back, and point and pinch to pick "
               "a part." if camera_on else
               "The camera isn't on, so drag to turn it, use Take apart, and click a part.")
        like = model.get("like", "").split(",")[0].strip()
        inside = f", built inside like a {like}" if like and not like.startswith(("a ", "most ")) else ""
        return f"Here's the {model['title'].lower()}{inside}. {how}"

    def _explore_close(self) -> None:
        ex, self._explore = self._explore, None
        if ex is None:
            return
        if self.camera is not None:
            self.camera.on_hands = None
            if ex.get("started_camera"):
                self._stop_camera()
        if self.panel == "explore":
            self.panel = ""
        self._show("explore_close")
        self.telemetry.log("explore_closed", model=ex["model"])

    # ---- the hand (MediaPipe's thread) and the window (the server's thread) ----------------------
    def _explore_on_hands(self, hands, timestamp_ms: int, width: int, height: int) -> None:
        if self._explore is None:
            return
        msg = self._explore_hands.update(timestamp_ms / 1000, hands)
        self._show("explore_hand", **msg)
        if "next" in msg["events"]:
            self._on_loop(self._explore_next_from_hand)

    def _explore_next_from_hand(self) -> None:
        if self._explore is not None:
            line = self._explore_open(_next(self._explore["model"]))
            self._speak_soon(line.split(".")[0] + ".")

    def _explore_ui(self, event: dict) -> None:
        """From the window (on the loop): a part picked, a model chosen, or the view closed."""
        action = event.get("explore")
        if action == "close" or self._explore is None:
            self._explore_close()
        elif action == "pick" and event.get("part"):
            asyncio.ensure_future(self._explain_part(str(event["part"])))
        elif action == "model" and event.get("model") in MODELS:
            self._speak_soon(self._explore_open(str(event["model"])).split(".")[0] + ".")
        elif action == "next":
            self._explore_next_from_hand()

    def _speak_soon(self, line: str) -> None:
        if self._loop is not None:
            asyncio.ensure_future(self.sink.say(line, self.lang.current))

    # ---- explaining a part ------------------------------------------------------------------------
    async def _explain_part(self, part_id: str) -> str | None:
        ex = self._explore
        if ex is None:
            return None
        model = MODELS[ex["model"]]
        part = next((p for p in model["parts"] if p["id"] == part_id), None)
        if part is None:
            return None
        ex["part"] = part_id
        self._show("explore_cmd", action="select", part=part_id)
        self.telemetry.log("explore_part", model=ex["model"], part=part_id)
        question = (f"The user is looking at the {part['name'].lower()} of a {model['title'].lower()}, pulled out "
                    f"of the model in Jarvis's window. Explain it in two or three short spoken sentences: what it "
                    f"does and how it works with the parts around it. Background: {part['desc']}")
        token = self.state.token()
        turn = self.telemetry.turn(source="explorer")
        async with self._turn_lock:
            reply = await self._handle_text(question, "explorer", turn, token)
        if not reply or reply.startswith("I can't reach"):
            reply = part["desc"]                         # no model to ask: the part's own description
            await self.sink.say(reply, self.lang.current, token)
        if not token.cancelled:
            self._after_reply(f"(the {part['name'].lower()})", reply)
        return reply


def _next(key: str) -> str:
    return ORDER[(ORDER.index(key) + 1) % len(ORDER)] if key in ORDER else ORDER[0]


__all__ = ["ExploreMode"]
