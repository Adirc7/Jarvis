"""Your files: where one is, and what's in it ("where's my DWBI report?", "what's in it?").

Only in the folders you allow ([tools] search_folders: Desktop, Documents, Downloads by default, plus
[tools] allowed_folders and Jarvis's own folder), read-only, and never secrets: .env files, keys,
certificates, password databases and the like are neither listed nor read. A file's text goes to the
model as data to answer from, never as instructions (a file that says "delete everything" is only text).

    FileFinder([Path.home() / "Documents"]).find("dwbi report")   -> [Found(path, size, modified), ...]
    read_text(path)                                               -> the text of a .txt, .pdf, .docx, .pptx,
                                                                     .xlsx, .csv, .md, code...
"""

from __future__ import annotations

import html
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "appdata", "$recycle.bin", ".cache",
             "site-packages", ".idea", ".vscode", "windows", "program files", "program files (x86)", ".ssh",
             ".aws", ".gnupg", ".azure", ".kube", ".docker", "models"}
SECRET = re.compile(r"(^\.env(\..*)?$|\.(pem|key|pfx|p12|kdbx|keystore|jks|ppk|asc|gpg)$|^id_(rsa|dsa|ecdsa|ed25519)|"
                    r"credential|secret|password|passwd|token|api[_-]?key|\.netrc$|\.npmrc$|\.pypirc$)", re.IGNORECASE)
TEXT = {".txt", ".md", ".csv", ".tsv", ".json", ".py", ".m", ".r", ".rmd", ".ipynb", ".java", ".js", ".ts", ".tsx",
        ".jsx", ".html", ".css", ".sql", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".tex", ".bib", ".yaml", ".yml",
        ".toml", ".ini", ".log", ".xml", ".srt", ".kt", ".php", ".sh", ".bat"}
MAX_BYTES = 50_000_000


@dataclass(frozen=True)
class Found:
    path: Path
    size: int
    modified: datetime

    def line(self, n: int) -> str:
        size = f"{self.size / 1e6:.1f} MB" if self.size >= 1e6 else f"{max(1, self.size // 1000)} KB"
        return f"{n}. {self.path} ({size}, changed {self.modified:%d %b %Y})"


def secret(path: Path) -> bool:
    return any(SECRET.search(part) for part in path.parts[-3:])


def inside(path: Path, folders: list[Path]) -> bool:
    real = path.resolve()
    return any(real == f or real.is_relative_to(f) for f in folders)


class FileFinder:
    def __init__(self, folders: list[Path | str], max_depth: int = 7, budget_s: float = 6.0,
                 max_entries: int = 200_000):
        self.folders = []
        for f in folders:
            p = Path(str(f)).expanduser()
            if p.is_dir() and p.resolve() not in self.folders:
                self.folders.append(p.resolve())
        self.max_depth, self.budget_s, self.max_entries = max_depth, budget_s, max_entries

    def allowed(self, path: Path) -> bool:
        return inside(path, self.folders) and not secret(path)

    def find(self, query: str, limit: int = 8) -> list[Found]:
        """Files whose names have every word of `query` ("dwbi report" finds "DWBI_Final_Report_v3.pdf"),
        newest first; an exact name first of all."""
        words = [w for w in re.split(r"[\s_\-.]+", query.lower()) if w and w not in {"file", "the", "my", "a"}]
        if not words:
            return []
        ext = next((w for w in words if f".{w}" in TEXT | {".pdf", ".docx", ".pptx", ".xlsx"}), None)
        hits: list[tuple[int, float, Found]] = []
        start, seen = time.monotonic(), 0
        stack = [(f, 0) for f in self.folders]
        while stack and time.monotonic() - start < self.budget_s and seen < self.max_entries:
            folder, depth = stack.pop()
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            for e in entries:
                seen += 1
                name = e.name.lower()
                try:
                    if e.is_dir(follow_symlinks=False):
                        if depth < self.max_depth and name not in SKIP_DIRS and not name.startswith("."):
                            stack.append((Path(e.path), depth + 1))
                        continue
                    if not e.is_file(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                flat = re.sub(r"[\s_\-.]+", " ", name)
                if not all(w in flat for w in words if w != ext) or (ext and not name.endswith(f".{ext}")):
                    continue
                path = Path(e.path)
                if secret(path):
                    continue
                st = e.stat()
                exact = 0 if Path(name).stem == " ".join(words) or name == query.lower() else 1
                when = datetime.fromtimestamp(st.st_mtime)  # noqa: DTZ006 - local time, as Explorer shows it
                hits.append((exact, -st.st_mtime, Found(path, st.st_size, when)))
        hits.sort(key=lambda h: (h[0], h[1]))
        return [h[2] for h in hits[:limit]]


def read_text(path: Path, max_chars: int = 12_000) -> str:
    """The file's text, as far as it can be read here: plain text and code, PDF (pypdf), and the text inside
    Word, PowerPoint and Excel files. Long files are cut, and the cut is said."""
    suffix = path.suffix.lower()
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("it's over 50 MB")
    if suffix in TEXT:
        text = path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".ipynb":
            import json
            cells = json.loads(text).get("cells", [])
            text = "\n\n".join("".join(c.get("source", [])) for c in cells)
    elif suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        parts, total = [], 0
        for page in reader.pages:
            parts.append(page.extract_text() or "")
            total += len(parts[-1])
            if total > max_chars:
                break
        text = "\n".join(parts)
        if not text.strip():
            raise ValueError("it's a scanned PDF (pictures, no text)")
    elif suffix in (".docx", ".pptx", ".xlsx"):
        text = _office_text(path, suffix)
    else:
        raise ValueError(f"Jarvis can't read {suffix or 'that kind of'} files")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n[... cut: the file has about {len(text):,} characters; this is the start]"
    return text


def _office_text(path: Path, suffix: str) -> str:
    """The words inside a .docx, .pptx or .xlsx (they're zip files of XML)."""
    with zipfile.ZipFile(path) as z:
        if suffix == ".docx":
            names = ["word/document.xml"]
        elif suffix == ".pptx":
            names = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                           key=lambda n: int(re.search(r"\d+", n.rsplit("/", 1)[1]).group()))
        else:
            names = ["xl/sharedStrings.xml"] if "xl/sharedStrings.xml" in z.namelist() else []
        out = []
        for i, name in enumerate(names, 1):
            xml = z.read(name).decode("utf-8", errors="replace")
            xml = re.sub(r"</w:p>|</a:p>|</si>", "\n", xml)
            words = html.unescape(re.sub(r"<[^>]+>", "", xml))
            out.append((f"[slide {i}]\n" if suffix == ".pptx" else "") + words)
        return "\n".join(out)


__all__ = ["FileFinder", "Found", "read_text", "secret"]
