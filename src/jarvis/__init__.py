"""Jarvis: a context-aware multimodal desktop assistant (self-study build)."""

import os as _os

# Quieter model downloads. Windows can't make the cache's symlinks without
# Developer Mode, so the Hugging Face library warns on every download (it
# just stores normal copies instead), and it warns about downloading without
# an account, which is fine for free public models. Neither is an error.
_os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
_os.environ.setdefault("HF_HUB_VERBOSITY", "error")

__version__ = "0.0.1"
