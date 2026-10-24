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
from .clarity import compression_ratio, unclear_reason


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str                 # Jarvis language code the text was transcribed in
    detected: str | None          # Whisper's guess (Whisper code)
    detected_probability: float | None
    retranscribed: bool           # True if step 2 above kicked in
    ms: float
    avg_logprob: float | None = None   # Whisper's confidence per token (0 = sure, -1 = guessing)
    unclear: str | None = None         # why the text looks like nonsense (voice/clarity.py)


def _mean_logprob(segments: list[Any]) -> float | None:
    """Average log-probability over all segments, weighted by their token counts."""
    pairs = [(s.avg_logprob, len(getattr(s, "tokens", None) or [0])) for s in segments
             if getattr(s, "avg_logprob", None) is not None]
    total = sum(n for _, n in pairs)
    return sum(lp * n for lp, n in pairs) / total if total else None


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
        cpu_loader: Callable[[str], Any] | None = None,
    ):
        self._settings = settings
        self._lm = languages
        self._tel = telemetry or Telemetry.disabled()
        device = settings.get("stt.device", "cuda")
        compute = settings.get("stt.compute_type", "int8_float16")
        self._loader = loader or (lambda name: load_whisper(name, device, compute))
        # If the graphics card fails mid-session (CUDA error 999), Whisper
        # moves to the CPU: slower, but Jarvis keeps hearing you.
        self._cpu_loader = cpu_loader or (None if loader else (lambda name: load_whisper(name, "cpu")))
        self.on_cpu = False
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

    def _detects_language(self) -> bool:
        return bool(self._settings.get("stt.detect_language", True)) and len(self._lm.languages) > 1

    def warm_up(self) -> None:
        """Load the models and run each once, before the first request.

        Loading alone isn't enough: the first pass on the GPU sets up its
        kernels, and the voice-activity filter loads its own small model on
        first use, so a cold first request is much slower than the rest.
        A failure here is only logged; the real request will report it.
        """
        silence = np.zeros(16000, np.float32)                  # one second
        vad_options = (True, False) if self._settings.get("stt.vad_filter", True) else (False,)
        warmed: set[str] = set()
        for lang in (None, self._lm.current):
            name = self._model_name(lang)
            model = self.model(lang)
            if name in warmed:
                continue
            warmed.add(name)
            with self._tel.span("stt_warm", model=name) as info:
                try:
                    if lang is None and self._detects_language():
                        model.detect_language(silence)
                    for vad in vad_options:     # with VAD: loads it; without: runs the encoder and decoder
                        segments, _ = model.transcribe(
                            silence, language=self._lm.current.whisper_code, beam_size=1,
                            vad_filter=vad, max_new_tokens=4, without_timestamps=True,
                        )
                        for _ in segments:                     # transcription is lazy until read
                            pass
                except Exception as exc:
                    info["error"] = f"{type(exc).__name__}: {exc}"[:200]

    def transcribe(self, audio: np.ndarray) -> TranscriptResult:
        try:
            return self._transcribe(audio)
        except Exception as exc:
            if self.on_cpu or self._cpu_loader is None:
                raise
            self._tel.log("stt_fallback_cpu", error=f"{type(exc).__name__}: {exc}"[:300])
            print(f"[stt] Speech recognition failed on the graphics card ({type(exc).__name__}); "
                  "moving Whisper to the CPU.")
            self._models.clear()
            self._loader, self.on_cpu = self._cpu_loader, True
            return self._transcribe(audio)

    def _transcribe(self, audio: np.ndarray) -> TranscriptResult:
        start = time.perf_counter()
        detected, prob = None, None
        if self._detects_language():
            detected, prob, _ = self.model(None).detect_language(audio)
        target_code = self._lm.needs_retranscribe(detected, prob) or self._lm.current.code
        target = self._lm.languages[target_code]
        segments, _info = self.model(target).transcribe(
            audio,
            language=target.whisper_code,
            beam_size=int(self._settings.get("stt.beam_size", 1)),
            vad_filter=bool(self._settings.get("stt.vad_filter", True)),
            initial_prompt=self._settings.get("stt.initial_prompt") or None,
            temperature=tuple(float(t) for t in self._settings.get("stt.temperatures", [0.0, 0.4])),
        )
        segments = list(segments)                          # transcription runs here
        text = " ".join(s.text.strip() for s in segments).strip()
        logprob = _mean_logprob(segments)
        unclear = None
        if text and self._settings.get("stt.reject_unclear", True):
            unclear = unclear_reason(
                text, target.whisper_code, logprob,
                max_compression=float(self._settings.get("stt.unclear_max_compression", 2.4)),
                min_logprob=float(self._settings.get("stt.unclear_min_logprob", -1.0)),
                max_foreign_share=float(self._settings.get("stt.unclear_max_foreign_script", 0.2)),
            )
        ms = (time.perf_counter() - start) * 1000
        result = TranscriptResult(
            text=text, language=target_code, detected=detected,
            detected_probability=None if prob is None else round(float(prob), 3),
            retranscribed=target_code != self._lm.current.code, ms=round(ms, 1),
            avg_logprob=None if logprob is None else round(logprob, 3), unclear=unclear,
        )
        self._tel.log("stt", ms=result.ms, language=target_code, detected=detected,
                      probability=result.detected_probability, retranscribed=result.retranscribed,
                      audio_s=round(len(audio) / 16000, 2), chars=len(text),
                      logprob=result.avg_logprob, compression=round(compression_ratio(text), 2),
                      unclear=unclear)
        return result
