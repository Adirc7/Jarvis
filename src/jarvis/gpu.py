"""Make faster-whisper find CUDA on Windows without a manual CUDA install.

faster-whisper runs on CTranslate2, which needs the CUDA 12 cuBLAS and
cuDNN 9 DLLs. The easy route is `pip install nvidia-cublas-cu12
"nvidia-cudnn-cu12==9.*"` (the `gpu` extra in pyproject.toml). Those wheels put
the DLLs inside site-packages/nvidia/*/bin, which Windows doesn't search by
default. Call `prepare_cuda()` before importing faster_whisper.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def nvidia_dll_dirs() -> list[Path]:
    """Every site-packages/nvidia/<library>/bin (or lib) folder.

    All of them, not a fixed list: onnxruntime also needs cufft and curand,
    and cuDNN 9 loads helper DLLs (cudnn_engines_tensor_ir64_9.dll ...) by
    name only when it first runs, so their folder must be searchable.
    """
    dirs: list[Path] = []
    for entry in sys.path:
        base = Path(entry) / "nvidia"
        if not base.is_dir():
            continue
        for sub in sorted(base.iterdir()):
            for folder in ("bin", "lib"):
                d = sub / folder
                if d.is_dir() and d not in dirs:
                    dirs.append(d)
    return dirs


def prepare_cuda() -> list[Path]:
    """Add pip-installed NVIDIA DLL folders to the search path (Windows only)."""
    if sys.platform != "win32":
        return []
    added = []
    for d in nvidia_dll_dirs():
        try:
            os.add_dll_directory(str(d))
        except (OSError, AttributeError):
            continue
        os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        added.append(d)
    return added


def gpu_memory_mb() -> tuple[int, int] | None:
    """(used, total) MB on the first NVIDIA card, from nvidia-smi; None without one."""
    import shutil
    import subprocess

    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5, check=True).stdout
        used, total = (int(x) for x in out.splitlines()[0].split(","))
        return used, total
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        return None


def cuda_device_count() -> int:
    """Number of CUDA devices CTranslate2 can see (0 if none or not installed)."""
    prepare_cuda()
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count()
    except Exception:
        return 0
