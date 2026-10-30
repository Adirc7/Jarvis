"""Moving Jarvis to another PC: what he knows goes in one file; the new PC's hardware stays its own.

    uv run jarvis --carry-out                 # Desktop\\Jarvis-carry-<PC>-<date>.zip
    uv run jarvis --carry-in <that file>      # on the new PC, after "Setup Jarvis.cmd"

What travels: his memory (your name, the facts you asked him to keep, the
recent conversation, which PCs he has run on), your notes, your own training
sentences and the intent model trained on them, and your push-to-talk key.
What doesn't: the code (GitHub has it), the models (setup downloads them for
the new PC's hardware), microphone and speaker choices (another PC's
devices), your voice recordings and hand data (they stay where they were
made), and your API keys unless you ask (--with-keys): then keep the file
private and delete it once it's moved.

Bringing it in never overwrites quietly: anything already there is kept as
"<name>.before-carry" next to it, and memory is merged (the facts of both,
the newer conversation). Bring in only carry files you made yourself: the
intent model in one is a Python pickle, which runs code when it's loaded.
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

FORMAT = 1
# (path inside the file, path from the Jarvis folder)
PROJECT_FILES = (
    ("state/memory.json", "state/memory.json"),
    ("state/presence.json", "state/presence.json"),
    ("state/machines.json", "state/machines.json"),
    ("data/intent/mine.jsonl", "data/intent/mine.jsonl"),
)
PROJECT_GLOBS = (("models/intent", "*.joblib"), ("models/intent", "*.json"))
HOME_FOLDERS = ("notes",)              # inside Jarvis's own folder (~/Documents/Jarvis)
MAX_FILE_BYTES = 50_000_000


class CarryError(Exception):
    """Not a Jarvis carry file, or one that tries to write outside Jarvis's folders."""


def default_name(pc: str, now: datetime) -> str:
    return f"Jarvis-carry-{re.sub(r'[^A-Za-z0-9_-]+', '-', pc).strip('-') or 'pc'}-{now:%Y%m%d-%H%M}.zip"


def hotkeys_block(text: str) -> str:
    """The [hotkeys] table of a settings file, as written (the push-to-talk key and friends)."""
    match = re.search(r"(?ms)^\[hotkeys\]\s*\n.*?(?=^\[|\Z)", text)
    return match.group(0).rstrip() + "\n" if match else ""


def carry_out(root: Path, jarvis_home: Path, out: Path, pc: str = "", with_keys: bool = False,
              now: datetime | None = None) -> tuple[Path, list[str]]:
    """Write the carry file; returns its path and what went in."""
    now = now or datetime.now()  # noqa: DTZ005 - local time, for the file name
    if out.is_dir() or out.suffix.lower() != ".zip":       # a folder: the file gets its own name
        out.mkdir(parents=True, exist_ok=True)
        out = out / default_name(pc, now)
    out.parent.mkdir(parents=True, exist_ok=True)
    files: list[tuple[str, Path]] = []
    for inside, rel in PROJECT_FILES:
        if (root / rel).is_file():
            files.append((f"project/{inside}", root / rel))
    for folder, pattern in PROJECT_GLOBS:
        for f in sorted((root / folder).glob(pattern)):
            files.append((f"project/{folder}/{f.name}", f))
    for folder in HOME_FOLDERS:
        base = jarvis_home / folder
        for f in sorted(base.rglob("*")) if base.is_dir() else []:
            if f.is_file() and not f.is_symlink():
                files.append((f"home/{folder}/{f.relative_to(base).as_posix()}", f))
    local = root / "config" / "settings.local.toml"
    extra: dict[str, str] = {}
    if local.is_file():
        extra["project/config/hotkeys.toml"] = hotkeys_block(local.read_text(encoding="utf-8"))
    if with_keys and (root / ".env").is_file():
        files.append(("keys/.env", root / ".env"))
    files = [(name, path) for name, path in files if path.stat().st_size <= MAX_FILE_BYTES]
    manifest = {"format": FORMAT, "from_pc": pc, "made": now.isoformat(timespec="seconds"),
                "files": [name for name, _ in files] + [k for k, v in extra.items() if v],
                "with_keys": with_keys and any(n == "keys/.env" for n, _ in files)}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("jarvis-carry.json", json.dumps(manifest, indent=1))
        for name, path in files:
            z.write(path, name)
        for name, text in extra.items():
            if text:
                z.writestr(name, text)
    return out, manifest["files"]


def _target(name: str, root: Path, jarvis_home: Path) -> Path | None:
    """Where a file from the carry file goes; None for anything it may not write (no escaping)."""
    parts = PurePosixPath(name).parts
    if not parts or ".." in parts or name.startswith("/") or "\\" in name or ":" in name:
        raise CarryError(f"unsafe name in the carry file: {name[:80]}")
    allowed_project = {inside for inside, _ in PROJECT_FILES} | {f"{folder}/" for folder, _ in PROJECT_GLOBS}
    if parts[0] == "project":
        rel = "/".join(parts[1:])
        in_folder = any(rel.startswith(p) and rel.count("/") == p.count("/") for p in allowed_project
                        if p.endswith("/"))
        if rel in allowed_project or (in_folder and rel.endswith((".joblib", ".json"))):
            return root / rel
        return None
    if parts[0] == "home" and len(parts) > 2 and parts[1] in HOME_FOLDERS:
        return jarvis_home.joinpath(*parts[1:])
    if name == "keys/.env":
        return root / ".env"
    return None


def _merge_memory(old: dict, new: dict) -> dict:
    facts = list(new.get("facts", []))
    for f in old.get("facts", []):
        if not any(f.get("text", "").lower() == g.get("text", "").lower() for g in facts):
            facts.append(f)
    newer = new if (new.get("last") or "") >= (old.get("last") or "") else old
    return {"name": new.get("name") or old.get("name", ""), "facts": facts[:50],
            "recent": newer.get("recent", []), "last": newer.get("last")}


def carry_in(zip_path: Path, root: Path, jarvis_home: Path) -> tuple[dict, list[str]]:
    """Bring a carry file in. Returns its manifest and what was written where."""
    try:
        z = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise CarryError(f"not a carry file: {exc}") from None
    done: list[str] = []
    with z:
        try:
            manifest = json.loads(z.read("jarvis-carry.json"))
        except (KeyError, ValueError):
            raise CarryError("not a Jarvis carry file (no jarvis-carry.json)") from None
        if manifest.get("format") != FORMAT:
            raise CarryError(f"carry file format {manifest.get('format')} (this Jarvis reads {FORMAT})")
        for info in z.infolist():
            name = info.filename
            if name == "jarvis-carry.json" or name.endswith("/"):
                continue
            if info.file_size > MAX_FILE_BYTES:
                raise CarryError(f"{name} is too big")
            if name == "project/config/hotkeys.toml":
                done.append(_bring_hotkeys(z.read(name).decode("utf-8"), root))
                continue
            target = _target(name, root, jarvis_home)
            if target is None:
                continue
            data = z.read(name)
            if name == "keys/.env" and target.exists():
                done.append("API keys: this PC already has its own .env; kept it")
                continue
            if name == "project/state/memory.json" and target.exists():
                try:
                    merged = _merge_memory(json.loads(target.read_text(encoding="utf-8")), json.loads(data))
                    data = json.dumps(merged, ensure_ascii=False, indent=1).encode("utf-8")
                except ValueError:
                    pass
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                target.replace(target.with_name(target.name + ".before-carry"))
            target.write_bytes(data)
            done.append(str(target))
    record = root / "state" / "carried-in.txt"               # setup doesn't offer the same file twice
    record.parent.mkdir(parents=True, exist_ok=True)
    with record.open("a", encoding="utf-8") as f:
        f.write(f"{zip_path.name}\t{manifest.get('from_pc', '')}\t{manifest.get('made', '')}\n")
    return manifest, done


def _bring_hotkeys(block: str, root: Path) -> str:
    local = root / "config" / "settings.local.toml"
    if not block.strip():
        return "push-to-talk key: none was set"
    text = local.read_text(encoding="utf-8") if local.is_file() else ""
    if hotkeys_block(text):
        return "push-to-talk key: this PC has its own; kept it"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text((text.rstrip() + "\n\n" if text.strip() else "") + block, encoding="utf-8")
    return f"push-to-talk key and hotkeys -> {local}"
