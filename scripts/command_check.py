"""How well does Jarvis understand commands, in different words and languages?

    uv run python scripts/command_check.py                   all of eval/commands.jsonl
    uv run python scripts/command_check.py --only singlish   one language (en, singlish, si)
    uv run python scripts/command_check.py --rules-only      only the fixed rules (no model, no keys)

Each line of eval/commands.jsonl is something you might say, and what Jarvis
should do: open a site, search, play video 1-3 from a list, pause, play
again, go back, or nothing (just answer). Every line goes through the real
pipeline, as in `uv run jarvis`: the fixed rules first, then the model with
the tools, using your settings and API keys. The browser is pretend: no page
opens, no key is pressed, and YouTube searches return the same three videos:

    1. Best of lofi hip hop 2021 [beats to relax/study to]
    2. 1 A.M Study Session [lofi hip hop]
    3. Future king of pirates || Luffy Edit - One Piece || #onepiece

Prints each line (right or wrong, and whether the rules or the model did it),
then accuracy per language and per kind of request, and saves everything to
logs/command_check-<time>.json. Add your own lines to eval/commands.jsonl:
the more of your real phrasings it holds, the better it measures.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.agent.llm import FallbackLLM, configured_providers
from jarvis.app import App
from jarvis.config import load_settings
from jarvis.greeting import Presence
from jarvis.memory import Memory
from jarvis.telemetry import Telemetry
from jarvis.tools.web import WebTools

VIDEOS = [("v1", "Best of lofi hip hop 2021 [beats to relax/study to]"),
          ("v2", "1 A.M Study Session [lofi hip hop]"),
          ("v3", "Future king of pirates || Luffy Edit - One Piece || #onepiece")]

# The rules' names for what they did -> the tool names used in commands.jsonl.
RULE_TOOLS = {
    "youtube_open": "open_site", "bing_open": "open_site",
    "youtube_search": "search_youtube", "youtube_results_page": "search_youtube", "youtube_none": "search_youtube",
    "bing_search": "search_bing", "youtube_play": "play_video",
    "media_pause": "pause_media", "media_pause_none": "pause_media", "media_resume": "resume_media",
    "back": "go_back", "back_none": "go_back",
}


@dataclass
class Seen:
    """What happened to one line."""
    by: str = "-"                      # "rules", "model", or "-" (nothing done: a spoken answer)
    tool: str = "none"
    args: dict = field(default_factory=dict)
    reply: str = ""


class PretendWeb(WebTools):
    """WebTools with a pretend browser that notes what was done, and by whom."""

    def __init__(self):
        super().__init__(opener=lambda url: None, media_key=lambda: None, search_videos=lambda q: list(VIDEOS))
        self.seen = Seen()
        self.recording = False

    def handle(self, text, lang="en", address="sir"):
        result = super().handle(text, lang, address)
        if self.recording and result is not None and self.seen.by == "-":
            self.seen = Seen("rules", RULE_TOOLS.get(result.tool, result.tool), self._args_from_rules(result))
        return result

    def call(self, name, arguments="{}", lang="en", address="sir"):
        if self.recording:
            try:
                args = json.loads(arguments or "{}")
            except ValueError:
                args = {"unreadable": arguments[:100]}
            self.seen = Seen("model", name, args if isinstance(args, dict) else {})
        return super().call(name, arguments, lang, address)

    def _args_from_rules(self, result) -> dict:
        page = self.pages[-1] if self.pages else ""
        if result.tool in ("youtube_open", "bing_open"):
            return {"site": "youtube" if "youtube" in page else "bing"}
        if result.tool == "youtube_play":
            return {"number": next((i for i, (vid, _) in enumerate(VIDEOS, 1) if vid in page), 0)}
        if result.tool in ("youtube_search", "youtube_results_page", "bing_search", "youtube_none"):
            from urllib.parse import parse_qs, urlsplit
            q = parse_qs(urlsplit(page).query)
            return {"query": (q.get("search_query") or q.get("q") or [""])[0]}
        return {}


def set_up(web: PretendWeb, setup: str) -> None:
    """Put the pretend browser where the line needs it."""
    if setup in ("listed", "playing", "paused"):
        web.handle("search YouTube for lofi")
    if setup in ("playing", "paused"):
        web.handle("the first one")
    if setup == "paused":
        web.handle("pause the video")


def judge(case: dict, seen: Seen) -> tuple[bool, str]:
    want = case["expect"]
    if seen.tool != want:
        return False, f"wanted {want}, got {seen.tool}"
    check = case.get("check", {})
    if "site" in check and str(seen.args.get("site", "")).lower() != check["site"]:
        return False, f"wrong site {seen.args.get('site')}"
    if "number" in check and str(seen.args.get("number")) != str(check["number"]):
        return False, f"wrong video {seen.args.get('number')}"
    if "query_any" in check:
        query = str(seen.args.get("query", "")).lower()
        if not any(word.lower() in query for word in check["query_any"]):
            return False, f"query \"{seen.args.get('query')}\""
    return True, ""


async def run(cases: list[dict], rules_only: bool, pause_s: float) -> list[dict]:
    settings = load_settings()                       # your settings and API keys, as Jarvis uses them
    settings.raw.setdefault("tools", {})["model_tools"] = "off" if rules_only else "always"
    settings.raw.setdefault("memory", {})["enabled"] = False
    llm = FallbackLLM(configured_providers(settings.providers(), settings.get("llm.timeout_s", 20),
                                           float(settings.get("llm.keepalive_s", 120))),
                      Telemetry.disabled(), routes=settings.routes())
    if not rules_only and not llm.providers:
        print("No API keys found (.env). Run with --rules-only, or add a key.")
        return []
    results = []
    for i, case in enumerate(cases, 1):
        web = PretendWeb()
        set_up(web, case.get("setup", "none"))
        web.recording = True
        app = App(settings, Telemetry.disabled(), llm=llm, out=lambda *a, **k: None, web=web,
                  memory=Memory(None), presence=Presence(None))
        start = time.perf_counter()
        if rules_only:
            reply = web.handle(case["text"])
            seen = web.seen
            seen.reply = reply.text if reply else ""
        else:
            try:
                seen_reply = await app.handle_text(case["text"])
            except Exception as exc:  # noqa: BLE001 - one bad line mustn't stop the run
                seen_reply = f"[error: {type(exc).__name__}: {exc}]"
            seen = web.seen
            seen.reply = seen_reply
        ms = round((time.perf_counter() - start) * 1000)
        ok, why = judge(case, seen)
        mark = "ok  " if ok else "MISS"
        args = json.dumps(seen.args, ensure_ascii=False) if seen.args else ""
        print(f"{i:3} {mark} {case['lang']:8} {seen.by:5} {case['text'][:44]:44} -> {seen.tool} {args}"
              + (f"   ({why})" if why else ""))
        results.append({**case, "ok": ok, "why": why, "by": seen.by, "tool": seen.tool, "args": seen.args,
                        "reply": seen.reply[:300], "ms": ms, "provider": llm.last_provider if seen.by == "model" else None})
        if not rules_only and pause_s:
            await asyncio.sleep(pause_s)             # stay under the free per-minute limits
    return results


def summary(results: list[dict]) -> None:
    def line(label: str, rows: list[dict]) -> str:
        ok = sum(r["ok"] for r in rows)
        return f"  {label:22} {ok:3}/{len(rows):<3} {ok / len(rows):5.0%}" if rows else ""

    print("\nBy language")
    for lang in ("en", "singlish", "si"):
        print(line(lang, [r for r in results if r["lang"] == lang]))
    print("By what was asked")
    for want in ("open_site", "search_youtube", "search_bing", "play_video", "pause_media", "resume_media",
                 "go_back", "none"):
        rows = [r for r in results if r["expect"] == want]
        if rows:
            print(line("nothing (just answer)" if want == "none" else want, rows))
    acted = [r for r in results if r["expect"] == "none" and r["tool"] != "none"]
    print(f"Done by the rules: {sum(r['by'] == 'rules' for r in results)}, by the model: "
          f"{sum(r['by'] == 'model' for r in results)}; actions nobody asked for: {len(acted)}")
    model_ms = sorted(r["ms"] for r in results if r["by"] == "model")
    if model_ms:
        print(f"Time when the model decided: middle {model_ms[len(model_ms) // 2]} ms, "
              f"slowest {model_ms[-1]} ms")
    print(line("All", results))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", type=Path, default=ROOT / "eval" / "commands.jsonl")
    ap.add_argument("--only", choices=["en", "singlish", "si"], help="one language")
    ap.add_argument("--rules-only", action="store_true", help="only the fixed rules (no model, no API keys)")
    ap.add_argument("--pause", type=float, default=2.0, help="seconds between lines (free rate limits)")
    args = ap.parse_args()
    cases = [json.loads(line) for line in args.file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.only:
        cases = [c for c in cases if c["lang"] == args.only]
    print(f"{len(cases)} lines from {args.file.name}" + (" (rules only)" if args.rules_only else ""))
    results = asyncio.run(run(cases, args.rules_only, args.pause))
    if not results:
        return 1
    summary(results)
    out = ROOT / "logs" / f"command_check-{datetime.now():%Y%m%d-%H%M%S}.json"   # noqa: DTZ005 - local time
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
