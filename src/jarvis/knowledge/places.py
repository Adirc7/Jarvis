"""Countries a headline is about: names, people and places that point to them, and a point to map them.

Matching is on whole words in the headline (lower case), so "Colombo" isn't
"Colombia" and "us" (the word) isn't the USA. The points are rough centres,
good enough for a world map.
"""

from __future__ import annotations

import re

# name: (latitude, longitude, words in a headline that point to it)
COUNTRIES: dict[str, tuple[float, float, tuple[str, ...]]] = {
    "Sri Lanka": (7.9, 80.8, ("sri lanka", "sri lankan", "lankan", "colombo", "kandy", "jaffna", "galle")),
    "India": (21.0, 78.0, ("india", "indian", "new delhi", "delhi", "mumbai", "modi", "isro", "bengaluru")),
    "Pakistan": (30.0, 70.0, ("pakistan", "pakistani", "islamabad", "karachi", "lahore")),
    "Bangladesh": (23.7, 90.4, ("bangladesh", "bangladeshi", "dhaka")),
    "Nepal": (28.2, 84.0, ("nepal", "nepali", "nepalese", "kathmandu")),
    "Maldives": (3.2, 73.2, ("maldives", "maldivian")),
    "Afghanistan": (33.9, 67.7, ("afghanistan", "afghan", "kabul", "taliban")),
    "China": (35.0, 103.0, ("china", "chinese", "beijing", "shanghai", "xi jinping")),
    "Taiwan": (23.7, 121.0, ("taiwan", "taiwanese", "taipei")),
    "Japan": (36.2, 138.3, ("japan", "japanese", "tokyo", "jaxa")),
    "South Korea": (36.5, 127.9, ("south korea", "south korean", "seoul")),
    "North Korea": (40.3, 127.4, ("north korea", "north korean", "pyongyang", "kim jong un")),
    "Myanmar": (21.9, 95.9, ("myanmar", "burma", "burmese")),
    "Thailand": (15.9, 101.0, ("thailand", "thai", "bangkok")),
    "Vietnam": (14.1, 108.3, ("vietnam", "vietnamese", "hanoi")),
    "Philippines": (12.9, 121.8, ("philippines", "philippine", "filipino", "manila")),
    "Indonesia": (-0.8, 113.9, ("indonesia", "indonesian", "jakarta")),
    "Malaysia": (4.2, 102.0, ("malaysia", "malaysian", "kuala lumpur")),
    "Singapore": (1.35, 103.8, ("singapore", "singaporean")),
    "Australia": (-25.3, 133.8, ("australia", "australian", "canberra", "sydney", "melbourne")),
    "New Zealand": (-40.9, 174.9, ("new zealand", "wellington", "auckland")),
    "Russia": (61.5, 105.3, ("russia", "russian", "moscow", "kremlin", "putin", "roscosmos")),
    "Ukraine": (48.4, 31.2, ("ukraine", "ukrainian", "kyiv", "kiev", "zelensky", "zelenskyy")),
    "Belarus": (53.7, 27.9, ("belarus", "belarusian", "minsk")),
    "Kazakhstan": (48.0, 66.9, ("kazakhstan", "kazakh", "baikonur")),
    "Turkey": (39.0, 35.2, ("turkey", "turkish", "türkiye", "ankara", "istanbul", "erdogan")),
    "Iran": (32.4, 53.7, ("iran", "iranian", "tehran")),
    "Iraq": (33.2, 43.7, ("iraq", "iraqi", "baghdad")),
    "Syria": (34.8, 39.0, ("syria", "syrian", "damascus")),
    "Lebanon": (33.9, 35.9, ("lebanon", "lebanese", "beirut", "hezbollah")),
    "Israel": (31.0, 34.9, ("israel", "israeli", "jerusalem", "tel aviv", "netanyahu")),
    "Palestine": (31.9, 35.2, ("palestine", "palestinian", "palestinians", "gaza", "west bank", "hamas")),
    "Jordan": (31.2, 36.5, ("jordan", "jordanian", "amman")),
    "Saudi Arabia": (23.9, 45.1, ("saudi", "saudi arabia", "riyadh")),
    "United Arab Emirates": (23.4, 53.8, ("uae", "united arab emirates", "emirati", "dubai", "abu dhabi")),
    "Qatar": (25.4, 51.2, ("qatar", "qatari", "doha")),
    "Yemen": (15.6, 48.5, ("yemen", "yemeni", "houthi", "houthis")),
    "Egypt": (26.8, 30.8, ("egypt", "egyptian", "cairo")),
    "Libya": (26.3, 17.2, ("libya", "libyan", "tripoli")),
    "Sudan": (12.9, 30.2, ("sudan", "sudanese", "khartoum")),
    "Ethiopia": (9.1, 40.5, ("ethiopia", "ethiopian", "addis ababa")),
    "Somalia": (5.2, 46.2, ("somalia", "somali", "mogadishu")),
    "Kenya": (-0.02, 37.9, ("kenya", "kenyan", "nairobi")),
    "Nigeria": (9.1, 8.7, ("nigeria", "nigerian", "lagos", "abuja")),
    "Ghana": (7.9, -1.0, ("ghana", "ghanaian", "accra")),
    "DR Congo": (-4.0, 21.8, ("congo", "congolese", "kinshasa")),
    "South Africa": (-30.6, 22.9, ("south africa", "south african", "johannesburg", "cape town", "pretoria")),
    "Morocco": (31.8, -7.1, ("morocco", "moroccan", "rabat")),
    "Algeria": (28.0, 1.7, ("algeria", "algerian", "algiers")),
    "United Kingdom": (54.0, -2.5, ("united kingdom", "uk", "u.k.", "britain", "british", "london", "england",
                                    "scotland", "downing street")),
    "Ireland": (53.4, -8.2, ("ireland", "irish", "dublin")),
    "France": (46.2, 2.2, ("france", "french", "paris", "macron")),
    "Germany": (51.2, 10.5, ("germany", "german", "berlin")),
    "Italy": (41.9, 12.6, ("italy", "italian", "rome")),
    "Spain": (40.5, -3.7, ("spain", "spanish", "madrid")),
    "Portugal": (39.4, -8.2, ("portugal", "portuguese", "lisbon")),
    "Netherlands": (52.1, 5.3, ("netherlands", "dutch", "amsterdam", "the hague")),
    "Belgium": (50.5, 4.5, ("belgium", "belgian", "brussels")),
    "Switzerland": (46.8, 8.2, ("switzerland", "swiss", "geneva", "zurich")),
    "Austria": (47.5, 14.6, ("austria", "austrian", "vienna")),
    "Poland": (51.9, 19.1, ("poland", "polish", "warsaw")),
    "Sweden": (60.1, 18.6, ("sweden", "swedish", "stockholm")),
    "Norway": (60.5, 8.5, ("norway", "norwegian", "oslo")),
    "Finland": (61.9, 25.7, ("finland", "finnish", "helsinki")),
    "Denmark": (56.3, 9.5, ("denmark", "danish", "copenhagen", "greenland")),
    "Greece": (39.1, 21.8, ("greece", "greek", "athens")),
    "Hungary": (47.2, 19.5, ("hungary", "hungarian", "budapest")),
    "Romania": (45.9, 24.9, ("romania", "romanian", "bucharest")),
    "Serbia": (44.0, 21.0, ("serbia", "serbian", "belgrade")),
    "United States": (39.8, -98.6, ("united states", "u.s.", "usa", "america", "american", "americans",
                                    "washington", "white house", "pentagon", "nasa", "spacex", "silicon valley")),
    "Canada": (56.1, -106.3, ("canada", "canadian", "ottawa", "toronto")),
    "Mexico": (23.6, -102.6, ("mexico", "mexican")),
    "Cuba": (21.5, -77.8, ("cuba", "cuban", "havana")),
    "Venezuela": (6.4, -66.6, ("venezuela", "venezuelan", "caracas")),
    "Colombia": (4.6, -74.3, ("colombia", "colombian", "bogota")),
    "Brazil": (-14.2, -51.9, ("brazil", "brazilian", "brasilia", "sao paulo")),
    "Argentina": (-38.4, -63.6, ("argentina", "argentine", "buenos aires")),
    "Chile": (-35.7, -71.5, ("chile", "chilean", "santiago")),
    "Peru": (-9.2, -75.0, ("peru", "peruvian", "lima")),
}

_PATTERNS = [(name, re.compile(r"(?<![\w.])(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
                               + r")(?![\w])"))
             for name, (_, _, words) in COUNTRIES.items()]


def countries_in(text: str) -> list[str]:
    """The countries a headline points to, in the order they appear."""
    low = text.lower()
    found = []
    for name, pattern in _PATTERNS:
        m = pattern.search(low)
        if m:
            found.append((m.start(), name))
    return [name for _, name in sorted(found)]


def where(name: str) -> tuple[float, float] | None:
    entry = COUNTRIES.get(name)
    return (entry[0], entry[1]) if entry else None
