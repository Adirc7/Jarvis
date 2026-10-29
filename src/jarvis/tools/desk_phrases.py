"""What the PC tools say, in each language (tools/desktop.py, gate.py).

The tools write their English replies themselves; for other languages each
reply carries a key and values ("say": ("note_saved", {"title": ...})), and
these phrases are used instead. Spoken Sinhala, as Friday talks, not written
Sinhala. A missing phrase falls back to the English reply.
"""

from __future__ import annotations

from typing import Any

PHRASES: dict[str, dict[str, str]] = {
    "si": {
        "opening": "{name} ඕපන් කරනවා.",
        "volume_up": "සද්දේ වැඩි කළා.",
        "volume_down": "සද්දේ අඩු කළා.",
        "volume_mute": "සද්දේ මියුට් කළා, නැත්නම් ආයේ දැම්මා.",
        "screenshot": "ස්ක්‍රීන්ෂොට් එක සේව් කළා.",
        "timer": "විනාඩි {minutes}කට ටයිමර් එක දැම්මා.",
        "timer_label": "විනාඩි {minutes}කට ටයිමර් එක දැම්මා: {label}.",
        "timer_finished": "ඒ ටයිමර් එක දැනටමත් ඉවරයි.",
        "timer_cancelled": "ටයිමර් එක නැවැත්තුවා.",
        "note_saved": "නෝට් එක සේව් කළා: {title}.",
        "note_gone": "ඒ නෝට් එක දැන් එතන නෑ.",
        "note_removed": "නෝට් එක අයින් කළා. ජාවිස්ගේ රීසයිකල් ෆෝල්ඩර් එකේ තියෙනවා.",
        "not_found": "ජාවිස්ගේ ෆෝල්ඩර් එකේ ඒ ෆයිල් එක හොයාගන්න බැරි වුණා.",
        "already_recycled": "ඒක දැනටමත් රීසයිකල් ෆෝල්ඩර් එකේ තියෙන්නේ.",
        "moved": "{name} ජාවිස්ගේ රීසයිකල් ෆෝල්ඩර් එකට දැම්මා.",
        "cant_restore": "ඒක ආයේ තිබ්බ තැනට දාන්න බැරි වුණා.",
        "restored": "{name} ආයේ තිබ්බ තැනට දැම්මා.",
        "nothing_to_undo": "ආපහු හරවන්න දෙයක් නෑ.",
        "refused": "සමාවෙන්න, ඒක කරන්න මට බෑ.",
        "cancelled": "හරි, මම ඒක කළේ නෑ.",
        "stopped": "නැවැත්තුවා.",
        "failed": "සමාවෙන්න, ඒක හරි ගියේ නෑ.",
        "unconfirmed": "මම උත්සාහ කළා, ඒත් ඒක වුණාද කියලා බලාගන්න බැරි වුණා.",
        "news_none": "දැන් ප්‍රවෘත්ති ගන්න බැරි වුණා. ඉන්ටර්නෙට් එක බලන්න.",
        "map_opened": "ප්‍රවෘත්ති සිතියම ඕපන් කළා: රටවල් {countries}ක ප්‍රවෘත්ති {n}ක්.",
        "weather_none": "දැන් කාලගුණය ගන්න බැරි වුණා. ඉන්ටර්නෙට් එක බලන්න.",
        "weather_map": "කාලගුණ සිතියම ඕපන් කළා: තැන් {n}ක්.",
    },
    "ta": {
        "opening": "{name} திறக்கிறேன்.",
        "volume_up": "ஒலியை அதிகரித்தேன்.",
        "volume_down": "ஒலியைக் குறைத்தேன்.",
        "volume_mute": "ஒலியை அணைத்தேன், அல்லது மீண்டும் இயக்கினேன்.",
        "screenshot": "திரைப்பிடிப்பைச் சேமித்தேன்.",
        "timer": "{minutes} நிமிடத்துக்கு டைமர் வைத்தேன்.",
        "timer_label": "{minutes} நிமிடத்துக்கு டைமர் வைத்தேன்: {label}.",
        "timer_finished": "அந்த டைமர் ஏற்கனவே முடிந்துவிட்டது.",
        "timer_cancelled": "டைமரை ரத்து செய்தேன்.",
        "note_saved": "குறிப்பைச் சேமித்தேன்: {title}.",
        "note_gone": "அந்தக் குறிப்பு இப்போது இல்லை.",
        "note_removed": "குறிப்பை நீக்கினேன். அது ஜார்விஸின் மறுசுழற்சி கோப்புறையில் உள்ளது.",
        "not_found": "ஜார்விஸின் கோப்புறையில் அந்தக் கோப்பைக் காணவில்லை.",
        "already_recycled": "அது ஏற்கனவே மறுசுழற்சி கோப்புறையில் உள்ளது.",
        "moved": "{name} ஐ ஜார்விஸின் மறுசுழற்சி கோப்புறைக்கு நகர்த்தினேன்.",
        "cant_restore": "அதை மீண்டும் வைக்க முடியவில்லை.",
        "restored": "{name} ஐ மீண்டும் அதன் இடத்தில் வைத்தேன்.",
        "nothing_to_undo": "மாற்றியமைக்க எதுவும் இல்லை.",
        "refused": "மன்னிக்கவும், அதை என்னால் செய்ய முடியாது.",
        "cancelled": "சரி, நான் அதைச் செய்யவில்லை.",
        "stopped": "நிறுத்தினேன்.",
        "failed": "மன்னிக்கவும், அது வேலை செய்யவில்லை.",
        "unconfirmed": "முயற்சித்தேன், ஆனால் அது நடந்ததா என்று உறுதிப்படுத்த முடியவில்லை.",
        "news_none": "இப்போது செய்திகளைப் பெற முடியவில்லை. இணைய இணைப்பைச் சரிபாருங்கள்.",
        "map_opened": "செய்தி வரைபடத்தைத் திறந்தேன்: {countries} நாடுகளில் {n} செய்திகள்.",
        "weather_none": "இப்போது வானிலையைப் பெற முடியவில்லை. இணைய இணைப்பைச் சரிபாருங்கள்.",
        "weather_map": "வானிலை வரைபடத்தைத் திறந்தேன்: {n} இடங்கள்.",
    },
}


def words_for(outcome: Any, lang: str) -> str:
    """What to say about a gate Outcome in `lang` (English: the tool's own words)."""
    table = PHRASES.get(lang)
    if not table:
        return outcome.text
    said = outcome.result.data.get("say") if outcome.result is not None else None
    if outcome.status in ("done", "claimed") or (outcome.status == "failed" and said):
        key, values = said or (None, {})
    elif outcome.status == "unconfirmed":
        key, values = "unconfirmed", {}
    elif outcome.status == "cancelled":
        key, values = ("stopped" if outcome.text == "Stopped." else "cancelled"), {}
    elif outcome.status == "refused":
        key, values = ("nothing_to_undo" if "nothing to undo" in outcome.reasons else "refused"), {}
    else:
        key, values = "failed", {}
    phrase = table.get(key or "")
    try:
        return phrase.format(**values) if phrase else outcome.text
    except (KeyError, IndexError):
        return outcome.text
