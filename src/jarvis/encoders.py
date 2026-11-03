"""One copy of each sentence encoder, shared: the intent model (intents/classifier.py) and the stand-in
(standin/lookup.py) both use multilingual-e5-small, which loaded twice at every start (4 Nov: "Loading
weights 199/199" twice), once of them on the graphics card. On the CPU it takes about 20 ms a sentence."""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_loaded: dict[tuple[str, str], Any] = {}


def sentence_encoder(name: str, device: str = "cpu") -> Any:
    with _lock:
        if (name, device) not in _loaded:
            from sentence_transformers import SentenceTransformer
            _loaded[(name, device)] = SentenceTransformer(name, device=device)
        return _loaded[(name, device)]


__all__ = ["sentence_encoder"]
