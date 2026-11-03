"""Jarvis's own fixed lines, in each language Jarvis speaks.

The tools have theirs (tools/desk_phrases.py, tools/web.py), and so do the lessons, the problems and
the 3D explorer's words below; these are the app's: the window, the panels, the models being out of
reach, a new computer. Spoken Sinhala, as Friday talks, not written Sinhala. A language with no line
of its own gets the English one, so adding a language never breaks a reply.

    said("closed_map", "si")                      -> "සිතියම වැහුවා."
    said("standin_slow", "en", source=...)       -> "The connection's slow, so this is from ..."
"""

from __future__ import annotations

LINES: dict[str, dict[str, str]] = {
    # The language models can't be reached, or the reply broke off (app.py).
    "llm_unavailable": {
        "en": "I can't reach any language model right now. Check the internet connection or start Ollama.",
        "si": "දැන් කිසිම ලැන්ග්වේජ් මොඩල් එකකට සම්බන්ධ වෙන්න බෑ. ඉන්ටර්නෙට් එක බලන්න, නැත්නම් ඔලාමා පටන් ගන්න.",
        "ta": "இப்போது எந்த மொழி மாதிரியையும் அணுக முடியவில்லை. இணைய இணைப்பைச் சரிபாருங்கள், "
              "அல்லது Ollama-வைத் தொடங்குங்கள்.",
    },
    # The models answered but couldn't this time: free limits used up, or busy (llm.py's LLMUnavailable.why).
    "llm_limits": {
        "en": "My free models have used up their limits for now. One is free again {when}.",
        "si": "මගේ ෆ්‍රී මොඩල් වල සීමාව දැනට ඉවරයි. {when} එකක් ආයෙත් ලැබෙයි.",
        "ta": "என் இலவச மாதிரிகள் இப்போதைக்கு வரம்பை எட்டிவிட்டன. {when} ஒன்று மீண்டும் கிடைக்கும்.",
    },
    "llm_busy": {
        "en": "The models are busy or slow right now. Ask me again {when}.",
        "si": "මොඩල් දැන් ගොඩක් කාර්යබහුලයි, නැත්නම් හෙමින්. {when} ආයෙත් අහන්න.",
        "ta": "மாதிரிகள் இப்போது பரபரப்பாக அல்லது மெதுவாக உள்ளன. {when} மீண்டும் கேளுங்கள்.",
    },
    "when_minute": {"en": "in about a minute", "si": "විනාඩියකින් විතර", "ta": "சுமார் ஒரு நிமிடத்தில்"},
    "when_minutes": {"en": "in about {n} minutes", "si": "විනාඩි {n}කින් විතර", "ta": "சுமார் {n} நிமிடங்களில்"},
    "when_hours": {"en": "in about {n} hours", "si": "පැය {n}කින් විතර", "ta": "சுமார் {n} மணி நேரத்தில்"},
    "when_soon": {"en": "soon", "si": "ටිකකින්", "ta": "விரைவில்"},
    "ollama_hint": {"en": "If Ollama were running on this computer, it could answer meanwhile.",
                    "si": "මේ පරිගණකයේ ඔලාමා ඕන් කළොත්, ඒ අතරේ ඒකෙන් උත්තර දෙන්න පුළුවන්.",
                    "ta": "இந்தக் கணினியில் Ollama இயங்கினால், அதுவரை அது பதில் சொல்லும்."},
    "reply_broke_off": {
        "en": "Sorry, the connection dropped in the middle of my answer. Please ask again.",
        "si": "සමාවෙන්න, උත්තරේ මැද්දෙදි කනෙක්ෂන් එක කැඩුණා. ආයෙත් අහන්න.",
        "ta": "மன்னிக்கவும், என் பதிலின் நடுவில் இணைப்பு துண்டிக்கப்பட்டது. மீண்டும் கேளுங்கள்.",
    },
    # The stand-in answering instead (standin/): always said, never passed off as the model's answer.
    "standin_slow": {
        "en": "The connection's slow, so this is from {source}.",
        "si": "කනෙක්ෂන් එක හෙමින් නිසා, මේ උත්තරේ {source} ගත්තේ.",
        "ta": "இணைப்பு மெதுவாக உள்ளது, அதனால் இந்தப் பதில் {source} வருகிறது.",
    },
    "standin_limits": {
        "en": "My free models are at their limits for now, so this is from {source}.",
        "si": "මගේ ෆ්‍රී මොඩල් වල සීමාව දැනට ඉවර නිසා, මේ උත්තරේ {source} ගත්තේ.",
        "ta": "என் இலவச மாதிரிகள் இப்போதைக்கு வரம்பை எட்டிவிட்டன, அதனால் இந்தப் பதில் {source} வருகிறது.",
    },
    "standin_unreachable": {
        "en": "I can't reach the language models, so this is from {source}.",
        "si": "ලැන්ග්වේජ් මොඩල් වලට සම්බන්ධ වෙන්න බැරි නිසා, මේ උත්තරේ {source} ගත්තේ.",
        "ta": "மொழி மாதிரிகளை அணுக முடியவில்லை, அதனால் இந்தப் பதில் {source} வருகிறது.",
    },
    "source_student": {"en": "my own small model", "si": "මගේම පොඩි මොඩල් එකෙන්",
                       "ta": "என் சொந்த சிறிய மாதிரியிலிருந்து"},
    "source_saved": {"en": "what I said before", "si": "මම කලින් කියපු දේකින්", "ta": "நான் முன்பு சொன்னதிலிருந்து"},
    # The window (ui/index.html): the conversation column hidden for a bigger map or model, and panels closed.
    "hid_talk": {"en": "Hid the conversation.", "si": "කතාබහ හැංගුවා.", "ta": "உரையாடலை மறைத்தேன்."},
    "show_talk": {"en": "Here's the conversation again.", "si": "ඔන්න කතාබහ ආයෙත් පෙන්නනවා.",
                  "ta": "உரையாடல் மீண்டும் இதோ."},
    "closed_map": {"en": "Closed the map.", "si": "සිතියම වැහුවා.", "ta": "வரைபடத்தை மூடினேன்."},
    "closed_lesson": {"en": "Closed the lesson.", "si": "පාඩම වැහුවා.", "ta": "பாடத்தை மூடினேன்."},
    "closed_board": {"en": "Closed the board.", "si": "බෝඩ් එක වැහුවා.", "ta": "பலகையை மூடினேன்."},
    "closed_it": {"en": "Closed it.", "si": "වැහුවා.", "ta": "மூடினேன்."},
    # The 3D explorer (explore_mode.py). {title} is the model's name, as the window shows it.
    "explore_closed": {"en": "Closed the 3D view.", "si": "ත්‍රීඩී මොඩල් එක වැහුවා.", "ta": "3D காட்சியை மூடினேன்."},
    "explore_assemble": {"en": "Putting it back together.", "si": "ආයෙත් එකතු කරනවා.",
                         "ta": "மீண்டும் ஒன்றாகப் பொருத்துகிறேன்."},
    "explore_explode": {"en": "Taking it apart.", "si": "ගලවලා පෙන්නනවා.", "ta": "பிரித்துக் காட்டுகிறேன்."},
    "explore_here": {"en": "Here's the {title}{inside}.", "si": "ඔන්න {title} එක{inside}.", "ta": "இதோ {title}{inside}."},
    "explore_inside": {"en": ", built inside like a {like}", "si": ", ඇතුළත හදලා තියෙන්නේ {like} වගේ",
                       "ta": ", உள்ளே {like} போல அமைக்கப்பட்டது"},
    "explore_hands": {
        "en": "Open your hand slowly to take it apart, make a fist to put it back, and point and pinch to pick a part.",
        "si": "ගලවන්න අත හෙමින් අරින්න, ආයෙ එකතු කරන්න මිට මොලවන්න, කොටසක් තෝරන්න ඇඟිල්ලෙන් පෙන්නලා ඇඟිලි දෙක ළං කරන්න.",
        "ta": "பிரிக்க கையை மெதுவாகத் திறங்கள், மீண்டும் பொருத்த முஷ்டியை மூடுங்கள், ஒரு பகுதியைத் தேர்ந்தெடுக்க "
              "சுட்டிக்காட்டி கிள்ளுங்கள்.",
    },
    "explore_mouse": {
        "en": "The camera isn't on, so drag to turn it, use Take apart, and click a part.",
        "si": "කැමරාව ඕන් කරලා නෑ, ඒ නිසා කරකවන්න මවුස් එකෙන් අදින්න, ටේක් අපාර්ට් බොත්තම ඔබන්න, කොටසක් ක්ලික් කරන්න.",
        "ta": "கேமரா இயங்கவில்லை, அதனால் சுழற்ற இழுங்கள், Take apart-ஐ அழுத்துங்கள், ஒரு பகுதியைக் கிளிக் செய்யுங்கள்.",
    },
    # Jarvis's folder carried to another computer (carry.py, machines.py).
    "new_computer": {
        "en": "New computer, {address}: {name}, moved from {before}; {where}. {memory}",
        "si": "අලුත් පරිගණකයක්, {address}: {name}, {before} එකෙන් ආවා; {where}. {memory}",
        "ta": "புதிய கணினி, {address}: {name}, {before} இலிருந்து வந்தேன்; {where}. {memory}",
    },
    "new_computer_gpu": {"en": "the {gpu} runs my ears and voice", "si": "{gpu} එකෙන් මගේ කන් සහ කටහඬ වැඩ කරනවා",
                         "ta": "{gpu} என் காதுகளையும் குரலையும் இயக்குகிறது"},
    "new_computer_cpu": {
        "en": "no NVIDIA graphics card here, so I'll listen on the processor, a little slower",
        "si": "මෙතන එන්විඩියා ග්‍රැෆික්ස් කාඩ් එකක් නෑ, ඒ නිසා ප්‍රොසෙසර් එකෙන් අහන්නම්, ටිකක් හෙමින්",
        "ta": "இங்கே NVIDIA கிராபிக்ஸ் அட்டை இல்லை, அதனால் செயலியில் கேட்பேன், சற்று மெதுவாக",
    },
    "new_computer_memory": {"en": "Your memory came along.", "si": "ඔයා ගැන මගේ මතකයත් එක්කම ආවා.",
                            "ta": "உங்களைப் பற்றிய என் நினைவும் கூடவே வந்தது."},
}


def said(key: str, lang: str, **values: object) -> str:
    """The line `key` in language `lang` ("en", "si", "ta"...), English when that language has none."""
    options = LINES[key]
    line = options.get(lang) or options["en"]
    try:
        return line.format(**values).strip()
    except (KeyError, IndexError):
        return options["en"].format(**values).strip()


def when(seconds: float | None, lang: str) -> str:
    """'in about 14 minutes', in `lang`."""
    if seconds is None:
        return said("when_soon", lang)
    if seconds < 90:
        return said("when_minute", lang)
    if seconds < 90 * 60:
        return said("when_minutes", lang, n=round(seconds / 60))
    return said("when_hours", lang, n=round(seconds / 3600))


def unavailable(exc: object, lang: str) -> str:
    """What to say when no model answered (llm.py's LLMUnavailable): why, and when to ask again."""
    why = getattr(exc, "why", "down")
    if why == "down":
        return said("llm_unavailable", lang)
    line = said("llm_limits" if why == "limit" else "llm_busy", lang, when=when(getattr(exc, "back_in", None), lang))
    return f"{line} {said('ollama_hint', lang)}" if getattr(exc, "local_down", False) else line


def is_said(text: str, key: str) -> bool:
    """Whether `text` is the line `key` in any language (its fixed part: lines with values aren't matched)."""
    return text in LINES[key].values()


__all__ = ["LINES", "is_said", "said", "unavailable", "when"]
