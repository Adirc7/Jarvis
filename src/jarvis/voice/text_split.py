"""Turn a streamed LLM reply into speakable chunks.

Speaking starts after the first short sentence instead of after the whole reply,
which is most of the latency saving in plan section 10.1. Later chunks are
longer so the voice doesn't sound choppy.
"""

from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"[.!?…।](?:[\"')\]]*)(?=\s)|\n+")
_CLAUSE_END = re.compile(r"[,;:](?=\s)")
_ABBREVIATIONS = {"mr.", "mrs.", "ms.", "dr.", "e.g.", "i.e.", "etc.", "vs.", "st.", "no."}

_MARKDOWN = [
    (re.compile(r"```.*?```", re.S), " "),          # code blocks aren't speakable
    # Tables: the |---|---| line goes (30 Oct it reached the voice: "no phonemes"),
    # and the cells are read with a pause between them.
    (re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$", re.M), " "),
    (re.compile(r"^\s*\|\s*", re.M), ""),
    (re.compile(r"\s*\|\s*$", re.M), ". "),
    (re.compile(r"\s*\|\s*"), ", "),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),     # images
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),  # links: keep the text
    (re.compile(r"https?://\S+"), "a link"),
    (re.compile(r"[*_]{1,3}([^*_\n]+)[*_]{1,3}"), r"\1"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""),
    (re.compile(r"^\s*[-*•]\s+", re.M), ""),
    (re.compile(r"^\s*\d+[.)]\s+", re.M), ""),
]


# LaTeX maths, said in words. Models write maths like \(E = mc^2\) even when
# told not to; the voice would read the backslashes and braces aloud.
# Single $...$ counts as maths only with maths inside, so "$5 and $10" stays money.
_MATH_SPANS = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]|\$\$(.+?)\$\$|\$([^$\n]*[\\^_=][^$\n]*?)\$", re.S)
_LATEX_WORDS = {
    "alpha": "alpha", "beta": "beta", "gamma": "gamma", "Gamma": "Gamma", "delta": "delta",
    "Delta": "Delta", "epsilon": "epsilon", "theta": "theta", "lambda": "lambda", "Lambda": "Lambda",
    "mu": "mu", "nu": "nu", "pi": "pi", "rho": "rho", "sigma": "sigma", "Sigma": "sum of",
    "tau": "tau", "phi": "phi", "Phi": "Phi", "omega": "omega", "Omega": "Omega", "psi": "psi",
    "nabla": "del", "partial": "partial", "infty": "infinity", "sum": "the sum of",
    "int": "the integral of", "cdot": "times", "times": "times", "approx": "approximately",
    "neq": "is not equal to", "leq": "is at most", "geq": "is at least", "to": "to",
    "rightarrow": "goes to", "Rightarrow": "so", "implies": "so", "pm": "plus or minus",
    "hbar": "h bar", "ln": "log", "log": "log", "sin": "sine", "cos": "cosine", "tan": "tangent",
}


def latex_to_speech(math: str) -> str:
    r"""'\frac{8\pi G}{c^{4}}' -> '8 pi G over c to the power 4'. Good enough to hear, not exact."""
    m = math
    m = re.sub(r"\\(?:left|right|displaystyle|,|;|!|quad|qquad)", " ", m)
    m = re.sub(r"\\text\{([^{}]*)\}", r" \1 ", m)
    for _ in range(4):   # innermost first: powers and subscripts, then fractions and roots
        m = re.sub(r"\^\{2\}|\^2(?!\d)", " squared ", m)
        m = re.sub(r"\^\{3\}|\^3(?!\d)", " cubed ", m)
        m = re.sub(r"\^\{([^{}]*)\}", r" to the power \1 ", m)
        m = re.sub(r"\^(\w)", r" to the power \1 ", m)
        m = re.sub(r"_\{([^{}]*)\}", r" \1 ", m)
        m = re.sub(r"_(\w)", r" \1 ", m)
        m = re.sub(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", r" \1 over \2 ", m)
        m = re.sub(r"\\sqrt\{([^{}]*)\}", r" the square root of \1 ", m)
    m = re.sub(r"\\([A-Za-z]+)", lambda x: f" {_LATEX_WORDS.get(x.group(1), x.group(1))} ", m)
    m = m.replace("=", " equals ").replace("+", " plus ").replace("\u2212", " minus ")
    m = re.sub(r"(?<=\s)-(?=\s)", " minus ", m)
    m = re.sub(r"[{}\\]", " ", m)
    return " ".join(m.split())


def clean_for_speech(text: str) -> str:
    """Strip markdown and symbols that a TTS voice would read out literally."""
    text = _MATH_SPANS.sub(lambda m: " " + latex_to_speech(next(g for g in m.groups() if g)) + " ", text)
    for pattern, repl in _MARKDOWN:
        text = pattern.sub(repl, text)
    return " ".join(text.split())


class SentenceChunker:
    """Splits a streamed reply into pieces the voice can say one after another.

    The first piece is kept short, because the listener hears nothing until it
    has been synthesized: a first sentence longer than `first_max_chars` is
    cut at its first comma (or semicolon, colon) instead.
    """

    def __init__(self, first_min_chars: int = 12, min_chars: int = 40, max_chars: int = 220,
                 first_max_chars: int = 60):
        self.first_min = first_min_chars
        self.first_max = first_max_chars
        self.min = min_chars
        self.max = max_chars
        self._buf = ""
        self._emitted = 0

    def feed(self, text: str) -> list[str]:
        """Add streamed text; return any chunks that are ready to speak."""
        self._buf += text
        out = []
        while True:
            chunk = self._take()
            if chunk is None:
                break
            out.append(chunk)
        return out

    def flush(self) -> list[str]:
        """Return whatever is left at the end of the reply."""
        rest = clean_for_speech(self._buf)
        self._buf = ""
        return [rest] if rest else []

    # ------------------------------------------------------------------
    def _take(self) -> str | None:
        first = self._emitted == 0
        minimum = self.first_min if first else self.min
        cut = self._sentence_cut(minimum)
        long_first = (cut is None and len(self._buf) >= self.first_max) or (cut is not None and cut > self.first_max)
        if first and long_first:
            clause = self._clause_cut(minimum)    # long first sentence: start at a comma
            if clause is not None and (cut is None or clause < cut):
                cut = clause
        if cut is None and len(self._buf) > self.max:
            cut = self._buf.rfind(" ", 0, self.max)
            cut = cut if cut > 0 else self.max
        if cut is None:
            return None
        chunk, self._buf = self._buf[:cut], self._buf[cut:].lstrip()
        chunk = clean_for_speech(chunk)
        if not chunk:
            return None if not self._buf else self._take()
        self._emitted += 1
        return chunk

    def _sentence_cut(self, minimum: int) -> int | None:
        for m in _SENTENCE_END.finditer(self._buf):
            end = m.end()
            if end < minimum:
                continue
            words = self._buf[:end].split()
            last_word = words[-1].lower() if words else ""
            if last_word in _ABBREVIATIONS:
                continue
            return end
        return None

    def _clause_cut(self, minimum: int) -> int | None:
        for m in _CLAUSE_END.finditer(self._buf):
            if m.end() >= minimum:
                return m.end()
        return None
