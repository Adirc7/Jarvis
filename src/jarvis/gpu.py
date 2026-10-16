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
    dirs: list[Path] = []
    for entry in sys.path:
        base = Path(entry) / "nvidia"
        if not base.is_dir():
            continue
        for sub in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            for folder in ("bin", "lib"):
                d = base / sub / folder
                if d.is_dir():
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


def cuda_device_count() -> int:
    """Number of CUDA devices CTranslate2 can see (0 if none or not installed)."""
    prepare_cuda()
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count()
    except Exception:
        return 0
