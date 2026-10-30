"""Which computer Jarvis is running on, and the ones he has run on before (state/machines.json).

    pcs = Machines.load(Path("state/machines.json"))
    pc, new = pcs.see(this_machine())       # new: the first time on this computer
    pcs.save()

A computer is known by its name and network card (hashed, so the file holds
no hardware address), with what Jarvis needs to know about it: its graphics
card and memory, which decide where Whisper and the voices run. The file
travels with the rest of Jarvis's memory when you move to a new PC
(carry.py), so on the new laptop he knows it's new, and where he came from.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Machine:
    id: str
    name: str
    os: str = ""
    cpu: str = ""
    cores: int = 0
    ram_gb: float = 0.0
    gpu: str = ""                        # "" = no NVIDIA card: Whisper and the voices on the CPU
    gpu_mb: int = 0
    first_seen: str = ""
    last_seen: str = ""

    def describe(self) -> str:
        parts = [self.name]
        if self.gpu:
            parts.append(f"{self.gpu} ({self.gpu_mb / 1024:.0f} GB)" if self.gpu_mb else self.gpu)
        else:
            parts.append("no NVIDIA graphics card")
        if self.ram_gb:
            parts.append(f"{self.ram_gb:.0f} GB memory")
        return ", ".join(parts)


def _ram_gb() -> float:
    try:
        if sys.platform == "win32":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong), ("page_total", ctypes.c_ulonglong),
                            ("page_avail", ctypes.c_ulonglong), ("virtual_total", ctypes.c_ulonglong),
                            ("virtual_avail", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong)]
            status = Status()
            status.length = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return round(status.total / 2**30, 1)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (OSError, ValueError, AttributeError):
        return 0.0


def _gpu() -> tuple[str, int]:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return "", 0
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5, check=True).stdout
        name, mb = out.splitlines()[0].rsplit(",", 1)
        return name.strip(), int(mb)
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        return "", 0


def machine_id(name: str, node: int | None = None) -> str:
    """Stable for one computer: its name and network card, hashed."""
    node = uuid.getnode() if node is None else node
    return hashlib.sha256(f"{name.lower()}|{node:012x}".encode()).hexdigest()[:16]


def this_machine() -> Machine:
    name = platform.node() or "this computer"
    gpu, gpu_mb = _gpu()
    return Machine(machine_id(name), name, f"{platform.system()} {platform.release()}".strip(),
                   platform.processor() or platform.machine(), os.cpu_count() or 0, _ram_gb(), gpu, gpu_mb)


class Machines:
    def __init__(self, path: Path | None, known: dict[str, Machine] | None = None, current: str = ""):
        self.path, self.known, self.current = path, known or {}, current

    @classmethod
    def load(cls, path: Path | None) -> Machines:
        if path is None or not path.is_file():
            return cls(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            known = {k: Machine(**{f: v for f, v in m.items() if f in Machine.__dataclass_fields__})
                     for k, m in raw.get("machines", {}).items()}
            return cls(path, known, str(raw.get("current", "")))
        except (OSError, ValueError, TypeError):
            return cls(path)

    def see(self, machine: Machine, now: datetime | None = None) -> tuple[Machine, Machine | None]:
        """Note that Jarvis runs on `machine` now. Returns it, and the computer he ran on
        before if that was another one (None on the same computer, or the very first run)."""
        when = (now or datetime.now()).isoformat(timespec="seconds")  # noqa: DTZ005 - local, like the logs
        before = self.known.get(self.current) if self.current and self.current != machine.id else None
        old = self.known.get(machine.id)
        machine.first_seen = old.first_seen if old else when
        machine.last_seen = when
        self.known[machine.id] = machine
        self.current = machine.id
        return machine, before

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"current": self.current, "machines": {k: asdict(m) for k, m in self.known.items()}}
        self.path.write_text(json.dumps(data, indent=1), encoding="utf-8")
