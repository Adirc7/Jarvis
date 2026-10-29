"""Looking things up with real sources: Wikipedia for background, OpenAlex for research papers.

    r = Research()
    page = r.wikipedia("Fourier series")            # title, summary, link (English or Sinhala Wikipedia)
    papers = r.papers("Sinhala speech recognition", since=2020)

OpenAlex (api.openalex.org) indexes about 250 million scholarly works, free;
without an API key it allows a small daily budget, plenty for a person. Each
paper comes with its authors, year, venue, DOI, citation count and, when
published, its abstract, so Jarvis can cite it and never has to invent one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote

from .fetch import FetchError, Get, get_text, url_with

OPENALEX = "https://api.openalex.org/works"


@dataclass
class Page:
    title: str
    summary: str
    url: str


@dataclass
class Paper:
    title: str
    year: int | None
    authors: list[str]
    venue: str
    doi: str
    cited_by: int
    abstract: str
    open_url: str

    def cite(self) -> str:
        who = self.authors[0].split()[-1] if self.authors else "Unknown"
        if len(self.authors) == 2:
            who += f" and {self.authors[1].split()[-1]}"
        elif len(self.authors) > 2:
            who += " et al."
        return f"{who} ({self.year or 'n.d.'})"


def abstract_from(index: dict | None, limit: int = 700) -> str:
    """OpenAlex keeps abstracts as {word: [positions]}; put the words back in order."""
    if not index:
        return ""
    spots = sorted((pos, word) for word, positions in index.items() for pos in positions)
    text = " ".join(word for _, word in spots)
    return text[:limit] + ("..." if len(text) > limit else "")


class Research:
    def __init__(self, get: Get = get_text):
        self.get = get

    def _json(self, url: str):
        try:
            return json.loads(self.get(url))
        except (FetchError, ValueError):
            return None

    def wikipedia(self, query: str, lang: str = "en") -> Page | None:
        lang = lang if lang in ("en", "si", "ta") else "en"
        base = f"https://{lang}.wikipedia.org"
        found = self._json(url_with(f"{base}/w/api.php", {"action": "opensearch", "search": query[:120],
                                                          "limit": 1, "namespace": 0, "format": "json"}))
        if not (isinstance(found, list) and len(found) > 1 and found[1]):
            return None
        title = found[1][0]
        page = self._json(f"{base}/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}")
        if not isinstance(page, dict) or not page.get("extract"):
            return None
        url = ((page.get("content_urls") or {}).get("desktop") or {}).get("page") or f"{base}/wiki/{quote(title)}"
        return Page(page.get("title", title), page["extract"][:1500], url)

    def papers(self, query: str, since: int | None = None, limit: int = 5) -> list[Paper]:
        params = {"search": query[:160], "per-page": max(1, min(limit, 8)),
                  "select": "display_name,publication_year,doi,cited_by_count,authorships,primary_location,"
                            "abstract_inverted_index,open_access"}
        if since:
            params["filter"] = f"from_publication_date:{since}-01-01"
        data = self._json(url_with(OPENALEX, params))
        out = []
        for w in (data or {}).get("results", []) if isinstance(data, dict) else []:
            authors = [(a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])]
            source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
            out.append(Paper(w.get("display_name") or "(untitled)", w.get("publication_year"),
                             [a for a in authors if a][:6], source, w.get("doi") or "", w.get("cited_by_count") or 0,
                             abstract_from(w.get("abstract_inverted_index")),
                             (w.get("open_access") or {}).get("oa_url") or ""))
        return out


def page_for_the_model(page: Page | None, query: str) -> str:
    if page is None:
        return f"Wikipedia has no article for: {query}. Say so; answer from general knowledge only if you say that's what it is."
    return f"Wikipedia, \"{page.title}\" ({page.url}):\n{page.summary}"


def papers_for_the_model(papers: list[Paper], query: str) -> str:
    if not papers:
        return f"OpenAlex found no papers for: {query}. Say so; never invent a paper or a reference."
    lines = [f"Papers found by OpenAlex for: {query} (cite only these, as given):"]
    for i, p in enumerate(papers, 1):
        lines.append(f"{i}. {p.cite()}: \"{p.title}\". {p.venue or 'venue unknown'}. Cited {p.cited_by} times."
                     + (f" {p.doi}" if p.doi else "") + (f" Free copy: {p.open_url}" if p.open_url else ""))
        if p.abstract:
            lines.append(f"   Abstract: {p.abstract}")
    return "\n".join(lines)
