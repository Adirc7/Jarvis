"""Which kind of request is this? Picks the route, and so the models, for each turn.

Free models have limits per model, so Jarvis spreads the work: maths to a
model that thinks longer, code to a coding model, long documents to a model
with a big context, quick chat to the fastest one (config/settings.toml,
[llm.routes]).

Two ways to decide:

- `KeywordRouter` (now): word lists in English, Singlish and Sinhala. Simple,
  instant and good enough to start; `scripts/route_check.py` measures it on
  the generated sentences.
- `IntentRouter` (Adhi's classifier, M3): the classifier names the intent
  ("derive_proof"), `INTENT_ROUTE` turns it into a route ("maths"). When the
  classifier isn't sure, the keyword rules decide.

A wrong route costs little: every route's models can answer anything; the
route only picks the best suited (and spreads the free limits).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

ROUTES = ("command", "quick", "maths", "teach", "code", "long", "talk", "general")

# Every intent in jarvis/intents/patterns.py, and the route it goes to.
INTENT_ROUTE: dict[str, str] = {
    # things to do on the computer (Jarvis will do these itself, M3; until then a fast model answers)
    **dict.fromkeys(["open_app", "close_app", "open_folder", "search_files", "play_music", "volume_up",
                     "volume_down", "take_screenshot", "send_message", "set_timer", "set_alarm", "set_reminder",
                     "system_power", "brightness_up", "brightness_down", "toggle_setting", "create_note",
                     "remember_fact", "switch_language", "stop", "pause_media", "resume_media", "go_back"],
                    "command"),
    **dict.fromkeys(["ask_time", "ask_date", "greeting", "thanks", "ask_capabilities", "ask_schedule"], "quick"),
    **dict.fromkeys(["solve_problem", "derive_proof", "check_answer"], "maths"),
    **dict.fromkeys(["explain_concept", "quiz_me", "exam_prep", "translate"], "teach"),
    **dict.fromkeys(["write_code", "debug_code", "analyze_data", "draw_graph"], "code"),
    "summarize_document": "long",
    "feeling_low": "talk",
    **dict.fromkeys(["news", "ask_weather", "search_research", "search_web"], "general"),
    # Adhi's own intent (data/intent/mine.jsonl): talk, opinions, discussions,
    # advice, anything that isn't one of the others
    "chat": "general",
}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str                  # the rule or intent that decided, for the logs
    intent: str | None = None
    confidence: float | None = None


class Router(Protocol):
    def route(self, text: str, lang: str = "en", prompt_chars: int = 0) -> RouteDecision: ...


def route_for_intent(intent: str) -> str:
    return INTENT_ROUTE.get(intent, "general")


def _words(*items: str) -> list[str]:
    return [w for item in items for w in item.split("|")]


# Order matters: the first rule that matches wins. Latin-letter words match
# whole words ("program" not "programming"); Sinhala-script ones match
# anywhere, since Sinhala adds endings to words (විසඳන්න, විසඳලා). A word
# with a backslash is a regular expression ("this \w+ question").
RULES: list[tuple[str, list[str]]] = [
    ("command", _words("vs code|වීඑස් කෝඩ්|google chrome|ගූගල් ක්‍රෝම්")),    # apps whose names sound like other things
    ("general", _words("google eke|ගූගල් එකේ|ඉන්ටර්නෙට් එකේ|search google|look up|online|bing|බිං")),   # web search
    ("quick", _words(                                  # the time and date, before "what's" means "explain"
        "what time|what's the time|the time|what day|the date|today's date|what's today",
        "welawa keeyada|time eka keeyada|date eka|mona dawasada|keewenida",
        "වෙලාව කීයද|ටයිම් එක කීයද|දැන් කීයද|දිනය මොකක්ද|මොන දවසද|කීවෙනිදා|මොන මාසෙද")),
    ("code", _words(
        r"code|coding|python|java|c\+\+|javascript|sql|query|bug|debug|exception|traceback|compile|script",
        "program|numpy|pandas|sklearn|scikit|matplotlib|matlab|jupyter|notebook|dataframe|csv|pivot|dashboard",
        "index error|syntax error|type error|key error|indentation error|module not found|out of memory",
        "mismatch|null pointer|plot|graph of|draw a graph|graph eka|graph ekak|chart|histogram|run wenne",
        "loss eka|loss isn't|accuracy|t-test|t test|best-fit|best fit|regression to|correlation in|in 3d",
        "data wala|average eka|adinna|adala|plot karanna|අඳින්න|අඳිලා",
        "error analysis|lab readings|dataset|average of|standard deviation of|this sheet|this data",
        "කෝඩ්|පයිතන්|ජාවා|මැට්ලැබ්|ප්ලස් ප්ලස්|ආර් වලින්|එස්කියුඑල්|බග්|ස්ක්‍රිප්ට්|ප්‍රෝග්‍රෑම්|එරර් එක|එරර් එකක්",
        "ප්ලොට්|ග්‍රැෆ්|ප්‍රස්තාර|චාට්|ඩෑෂ්බෝඩ්|පිවට් ටේබල් එකක්|සීඑස්වී|එක්සෙල් ෂීට් එකේ|ඩේටාසෙට්|ඩේටා වල",
        "රීඩිංස් වල|රන් වෙන්නේ|ලොස් එක|ඇක්යුරසි")),
    ("maths", _words(
        "solve|solving|derive|derivation|prove|proof|calculate|compute|evaluate|simplify|factorise|factorize",
        "is that right|is this right|my answer|my working|my method|check my|answer doesn't match|find the value",
        r"this \w+ question|this \w+ problem|this problem|this equation|this integral|this limit|by induction",
        "wisadanna|solve karanna|derive karanna|prove karanna|harida|ganana|answer eka|step by step",
        r"me prashnaya|me \w+ question eka|me equation eka|me integral eka|me limit eka|waradi da",
        r"question \w+ from|help me with question",
        "සොල්ව්|වැරැද්ද කොහෙද|විසඳ|සාධනය|ඩිරයිව්|ව්‍යුත්පන්න|ප්‍රූෆ්|ඩෙරිවේෂන්|ගණනය|ගණන|උත්තරේ|පියවරෙන් පියවර|හරිද",
        "මේ ප්‍රශ්නය|ප්‍රශ්නේ|ආවේ කොහොමද|සත්‍ය බව")),
    ("long", _words(
        "summarize|summarise|summary|main points|this pdf|this chapter|this paper|this document",
        "summary ekak|main points tika|pdf eke|chapter eke|paper eke",
        "සාරාංශ|සමරි|ප්‍රධාන කරුණු|පීඩීඑෆ්|චැප්ටර්|පේපර් එකේ|කෙටියෙන්")),
    ("talk", _words(
        "life|society|philosophy|meaning of|purpose|ethics|moral|religion|politics|believe|opinion",
        "what do you think|lonely|sad|stressed|stress|tired|scared|worried|anxious|happy|feel|feeling",
        "relationship|friendship|future|advice|headache|bad day",
        "jeewithaya|jivithe|samajaya|hithenne|dukai|sathutui|palui|mahansiyi|baya|oya hithanne|hoda na",
        "ජීවිත|සමාජ|දර්ශන|හිතෙන්නේ|හිතන්නේ|දුක|සතුටු|පාළු|මහන්සි|ස්ට්‍රෙස්|බයයි|හැඟීම|අනාගත|යාළු|රිදෙනවා|හොඳ නෑ")),
    ("teach", _words(                                  # exams and revision, before "research methods" means research
        "exam|past papers|short note|formula sheet|study plan|study timetable|revise|mcqs",
        "එක්සෑම්|විභාග|පාස්ට් පේපර්ස්|ෂෝට් නෝට්|ෆෝමියුලා ෂීට්|රිවිෂන්|ස්ටඩි ටයිම්ටේබල්")),
    ("general", _words(                                # needs the internet: weather, news, research, the web
        "weather|rain|raining|forecast|cyclone|storm|monsoon|flood|floods|news|research|google|video",
        "wahiyida|wahinawada|wessa|weather eka|news|research",
        "කාලගුණ|වහියිද|වහිනවද|වැස්ස|වැසි|සුළි කුණාටු|ගංවතුර|මෝසම්|වෙදර්|ප්‍රවෘත්ති|නිව්ස්|මොකද වෙන්නේ|මොකද වෙලා|රිසර්ච්|පර්යේෂණ|ගූගල්|වීඩියෝ|රෙෆරන්ස්")),
    ("command", _words(
        "open|close|launch|start|volume|louder|quieter|mute|screenshot|brightness|brighter|dimmer|timer|alarm",
        "remind|reminder|shut down|shutdown|restart|lock|put to sleep|wifi|wi-fi|bluetooth|dark mode",
        "do not disturb|play|put on|message|text my|tell my|make a note|write a note|remember that|note that",
        "find my|where is my|search for|folder|my documents|the desktop|turn|switch|wake me|count down",
        "too loud|can't hear|capture the screen|stop|cancel|never mind|that's enough|text the|send a message",
        "pause|resume|go back|previous page|video eka|aapahu yanna|වීඩියෝ එක|ආපහු යන්න",
        "speak|switch to|reply in|talk to|talk in|search karala|search karanna|send karanna|yawala|katha karanna",
        "open karanna|close karanna|arinna|wahanna|sound eka|volume eka|danna|yawanna|mathak karanna",
        "sleep karanna|on karanna|off karanna|koheda thiyenne|photo ekak|aharawanna|wadi karanna|adu karanna",
        "mathak karala|up karanna|down karanna|sindu|playlist|note ekak|mathaka thiyaganna|nawaththanna|epa|cancel karanna",
        "ඕපන්|අරින්න|විවෘත|ක්ලෝස්|වහන්න|වහලා|සද්දේ|වොලියුම්|ස්ක්‍රීන්ෂොට්|ස්ක්‍රීන් එක|ෆොටෝ එකක්",
        "බ්‍රයිට්නස්|එළිය|ටයිමර්|ඇලාම්|ඇහැරවන්න|මතක් කරන්න|මතක් කරලා|පස්සේ මට කියන්න|රිමයින්ඩ්|මතක තියාගන්න|ශට් ඩවුන්|රීස්ටාට්",
        "ලොක්|ස්ලීප්|වයිෆයි|බ්ලූටූත්|ඩාක් මෝඩ්|ඩිස්ටර්බ්|නෝටිෆිකේෂන්|ඔන් කරන්න|ඕෆ් කරන්න|ක්‍රියාත්මක කරන්න",
        "ප්ලේ|සින්දු|ප්ලේලිස්ට්|සංගීත|මියුසික්|මැසේජ්|යවන්න|නෝට් එකක් ලියන්න|නෝට් එකක් දාන්න|නෝට් එකක් විදියට",
        "ෆෝල්ඩර්|ඩෙස්ක්ටොප්|කොහෙද තියෙන්නේ|සර්ච් කරන්න|හොයන්න|හොයලා|වැඩි කරන්න|අඩු කරන්න|අප් කරන්න",
        "ඩවුන් කරන්න|දාන්න|නවත්තන්න|එපා|අවලංගු|ඇති|අරලා|කතා කරන්න|කතා කරමු|උත්තර දෙන්න|සෙන්ඩ් කරන්න")),
    ("teach", _words(
        "explain|what is|what are|what's|how does|how do|why does|why is|why do|difference between|compare",
        "teach|quiz|revise|revision|exam|study plan|lecture|notes|mcq|practice|intuitively|example|test me",
        "translate|meaning|how do you say|short notes|formula sheet|important topics",
        "kiyala denna|therum|pahadili|kiyanne mokakda|wenasa|padam|exam eka|exam ekata|short note",
        "prashna|questions|test karanna|help ekak|gana|practically|wada karanne kohomada|translate karanna",
        "පැහැදිලි|කියලා දෙන්න|තේරුම්|කියන්නේ මොකක්ද|වෙනස|ක්විස්|විභාග|එක්සෑම්|පාඩම්|එක්ස්ප්ලේන්",
        "රිවිෂන්|ලෙක්චර්|ප්‍රශ්න|උදාහරණ|පරිවර්තනය|ට්‍රාන්ස්ලේට්|ෂෝට් නෝට්|ෆෝමියුලා ෂීට්|වැදගත්ම|ටයිම්ටේබල් එකක්",
        "ටෙස්ට් කරන්න|උදව්වක්|ප්‍රායෝගිකව|වැඩ කරන්නේ කොහොමද|හැඳින්වීම|සරලව|ගැන|හරවන්න|කියන්නේ කොහොමද")),
    ("quick", _words(
        "hi|hello|thanks|thank you|good morning|good evening|good night|today|day is it",
        "who are you|your name|what can you do|how are you|timetable|lectures|i'm back|understand sinhala",
        "have to do|lab on",
        "sthuthi|ayubowan|oya kohomada|kohomada jarvis|kohomada friday|timetable|lectures|mama awa",
        "monawada karanna puluwan|oya kawda|sinhala therenawada|thanks|good morning",
        "ස්තූතියි|තැන්ක්ස්|ආයුබෝවන්|ඔයා කොහොමද|කොහොමද ජාවිස්|කොහොමද ෆ්‍රයිඩේ|ජාවිස්, කොහොමද|වෙලාව|සුභ|හායි",
        "ටයිම්ටේබල්|ලෙක්චර්ස්|ඔයා කවුද|ඔයාගේ නම|මම ආවා|තේරෙනවද|කරන්න පුළුවන්|දන්නේ|කරගන්න පුළුවන්",
        "ලැබ් එකක් තියෙනවද|කරන්න තියෙන්නේ")),
]

_SINHALA = re.compile(r"[඀-෿]")
_MATHS_EXPR = re.compile(r"\d\s*[+*/^=]\s*[\dx(]|\d\s+-\s+\d|[a-z]\^\d|\bd[xy]\b|\b(?:sin|cos|tan|log|ln|sqrt)\s*\(|∫|√|π")


def _pattern(word: str) -> re.Pattern[str]:
    if _SINHALA.search(word):
        return re.compile(re.escape(word))
    body = word if "\\" in word else re.escape(word)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


_COMPILED = [(route, [_pattern(w) for w in words]) for route, words in RULES]


@dataclass
class KeywordRouter:
    """Word-list rules. Long prompts go to the big-context models whatever they say."""

    long_prompt_chars: int = 12000       # about 3,000 tokens of English; Sinhala counts double (more tokens)

    def route(self, text: str, lang: str = "en", prompt_chars: int = 0) -> RouteDecision:
        weight = 2 if lang == "si" or _SINHALA.search(text) else 1
        if max(prompt_chars, len(text)) * weight > self.long_prompt_chars:
            return RouteDecision("long", f"long prompt ({max(prompt_chars, len(text))} chars)")
        low = text.lower()
        if _MATHS_EXPR.search(low):
            return RouteDecision("maths", "a formula or calculation")
        for route, patterns in _COMPILED:
            for pat in patterns:
                if pat.search(low):
                    return RouteDecision(route, f"word '{pat.pattern}'")
        if len(low.split()) <= 3:
            return RouteDecision("quick", "short")
        return RouteDecision("general", "no rule matched")


@dataclass
class IntentRouter:
    """For Adhi's classifier: classify(text, lang) -> (intent, confidence 0-1).
    Below `min_confidence`, the keyword rules decide instead."""

    classify: Callable[[str, str], tuple[str, float]]
    fallback: Router
    min_confidence: float = 0.6

    def route(self, text: str, lang: str = "en", prompt_chars: int = 0) -> RouteDecision:
        backup = self.fallback.route(text, lang, prompt_chars)
        if backup.route == "long" and backup.reason.startswith("long prompt"):
            return backup                                    # too big for the fast models anyway
        intent, confidence = self.classify(text, lang)
        if confidence < self.min_confidence:
            return RouteDecision(backup.route, f"{backup.reason} (classifier unsure: {intent} {confidence:.2f})",
                                 intent, confidence)
        return RouteDecision(route_for_intent(intent), f"intent {intent}", intent, confidence)
