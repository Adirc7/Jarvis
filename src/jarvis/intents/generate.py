"""Turn sentence patterns into thousands of labelled training sentences.

A pattern is a sentence with gaps: "{w}{app} {open}". Each gap is filled from
a word list; every combination becomes one example, labelled with its
intent, the values it used (app = chrome) and the grammatical form of the
verb (polite, casual, for_me, question, formal). From all combinations, a
balanced sample is taken: round-robin over the patterns, so no single
pattern dominates.

Gap names: a choice with a value is recorded as a slot; "{country__loc}"
records under "country" (two word lists, two grammatical cases, one slot).

Generated sentences are for TRAINING only. The test set stays real: your
own typed and recorded sentences (decision D21, ROADMAP "Understanding what
you ask").
"""

from __future__ import annotations

import itertools
import random
import re
import string
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(frozen=True)
class Choice:
    text: str
    value: str | None = None      # slot value to record (None: not a slot)
    form: str | None = None       # grammatical form, for verb choices


def C(text: str, value: str | None = None) -> Choice:
    return Choice(text, value)


def V(text: str, form: str) -> Choice:
    return Choice(text, None, form)


@dataclass(frozen=True)
class Pattern:
    intent: str
    text: str
    slots: dict[str, str] = field(default_factory=dict)   # fixed slots, e.g. {"language": "si"}


@dataclass(frozen=True)
class Example:
    text: str
    lang: str
    intent: str
    slots: dict[str, str]
    form: str | None
    pattern: str

    def as_dict(self) -> dict:
        d = {"text": self.text, "lang": self.lang, "intent": self.intent, "slots": self.slots,
             "pattern": self.pattern, "source": "generated"}
        if self.form:
            d["form"] = self.form
        return d


def gap_names(text: str) -> list[str]:
    return [name for _, name, _, _ in string.Formatter().parse(text) if name]


def expand(pattern: Pattern, vocab: dict[str, list[Choice]], lang: str) -> Iterator[Example]:
    """Every way of filling the pattern's gaps."""
    names = gap_names(pattern.text)
    missing = [n for n in names if n not in vocab]
    if missing:
        raise KeyError(f"pattern {pattern.text!r} uses unknown word lists: {missing}")
    for combo in itertools.product(*(vocab[n] for n in names)):
        filled = dict(zip(names, combo))
        text = pattern.text.format(**{n: c.text for n, c in filled.items()})
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s+([,?.])", r"\1", text)
        slots = dict(pattern.slots)
        form = None
        for name, choice in filled.items():
            if choice.value is not None:
                slots[name.split("__")[0]] = choice.value
            if choice.form is not None:
                form = choice.form
        yield Example(text, lang, pattern.intent, slots, form, pattern.text)


def generate(languages: dict[str, tuple[dict[str, list[Choice]], list[Pattern]]],
             per_intent: dict[str, int], seed: int = 21) -> list[Example]:
    """A balanced, reproducible sample: at most per_intent[lang] examples per intent."""
    rng = random.Random(seed)
    out: list[Example] = []
    for lang, (vocab, patterns) in languages.items():
        by_intent: dict[str, list[list[Example]]] = {}
        for p in patterns:
            options = list(expand(p, vocab, lang))
            rng.shuffle(options)
            by_intent.setdefault(p.intent, []).append(options)
        for intent, pools in by_intent.items():
            chosen, seen = [], set()
            for round_ in itertools.zip_longest(*pools):           # one from each pattern in turn
                for ex in round_:
                    if ex is not None and ex.text not in seen:
                        seen.add(ex.text)
                        chosen.append(ex)
                if len(chosen) >= per_intent[lang]:
                    break
            out.extend(chosen[:per_intent[lang]])
    return out
