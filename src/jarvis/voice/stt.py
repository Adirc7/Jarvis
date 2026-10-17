"""Speech-to-text with faster-whisper, aware of the active language.

For every utterance:
  1. (optional) detect the spoken language with the default multilingual model;
  2. if Whisper confidently heard a *different* Jarvis language, transcribe in
     that one (so "switch to English" works while in Sinhala mode);
  3. otherwise transcribe in the active language, with that language's model
     (a fine-tuned Sinhala model, for example).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ..config import PROJECT_ROOT, Language, Settings
from ..gpu import cuda_device_count
from ..language import LanguageManager
from ..telemetry import Telemetry


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str                 # Jarvis language code the text was transcribed in
    detected: str | None          # Whisper's guess (Whisper code)
    detected_probability: float | None
    retranscribed: bool           # True if step 2 above kicked in
    ms: float


def load_whisper(name: str, device: str = "cuda", compute_type: str = "int8_float16"):
    """Load a model on the GPU if possible, else fall back to CPU int8."""
    from faster_whisper import WhisperModel

    if device == "cuda" and cuda_device_count() > 0:
        try:
            return WhisperModel(name, device="cuda", compute_type=compute_type)
        except Exception as exc:   # missing cuDNN, out of VRAM, ...
            print(f"[stt] CUDA load failed ({exc}); using CPU")
    return WhisperModel(name, device="cpu", compute_type="int8")


class Transcriber:
    def __init__(
        self,
        settings: Settings,
        languages: LanguageManager,
        telemetry: Telemetry | None = None,
        loader: Callable[[str], Any] | None = None,
    ):
        self._settings = settings
        self._lm = languages
        self._tel = telemetry or Telemetry.disabled()
        device = settings.get("stt.device", "cuda")
        compute = settings.get("stt.compute_type", "int8_float16")
        self._loader = loader or (lambda name: load_whisper(name, device, compute))
        self._models: dict[str, Any] = {}

    def _model_name(self, lang: Language | None) -> str:
        default = self._settings.get("stt.model", "small")
        if lang is None or lang.stt_model in ("", "default"):
            return default
        # A local folder (converted fine-tune) or a model name faster-whisper knows.
        path = Path(lang.stt_model)
        path = path if path.is_absolute() else PROJECT_ROOT / path
        return str(path) if path.exists() else lang.stt_model

    def model(self, lang: Language | None = None):
        name = self._model_name(lang)
        if name not in self._models:
            with self._tel.span("stt_load", model=name):
                self._models[name] = self._loader(name)
        return self._models[name]

    def warm_up(self) -> None:
        """Load the default and active-language models before the first request."""
        self.model(None)
        self.model(self._lm.current)

    def transcribe(self, audio: np.ndarray) -> TranscriptResult:
        start = time.perf_counter()
        detected, prob = None, None
        if self._settings.get("stt.detect_language", True) and len(self._lm.languages) > 1:
            detected, prob, _ = self.model(None).detect_language(audio)
        target_code = self._lm.needs_retranscribe(detected, prob) or self._lm.current.code
        target = self._lm.languages[target_code]
        segments, _info = self.model(target).transcribe(
            audio,
            language=target.whisper_code,
            beam_size=int(self._settings.get("stt.beam_size", 1)),
            vad_filter=bool(self._settings.get("stt.vad_filter", True)),
            initial_prompt=self._settings.get("stt.initial_prompt") or None,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        ms = (time.perf_counter() - start) * 1000
        result = TranscriptResult(
            text=text, language=target_code, detected=detected,
            detected_probability=None if prob is None else round(float(prob), 3),
            retranscribed=target_code != self._lm.current.code, ms=round(ms, 1),
        )
        self._tel.log("stt", ms=result.ms, language=target_code, detected=detected,
                      probability=result.detected_probability, retranscribed=result.retranscribed,
                      audio_s=round(len(audio) / 16000, 2), chars=len(text))
        return result
