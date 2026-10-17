"""Text-to-speech engines, one per language, behind a single interface.

    engine.synthesize(text) -> mono float32 numpy array at engine.sample_rate

Engines (all free, all local):
  kokoro  Kokoro-82M via kokoro-onnx. Best English quality; British voices
          bm_george, bm_lewis, bm_daniel, bm_fable. Apache-2.0.
  piper   Piper ONNX voices. Fast on CPU, many languages, including the
          community Sinhala voice si_LK-dilu-medium.
  mms     Meta MMS-TTS through transformers (Tamil and 1,000+ other
          languages). Needs the "mms" extra (transformers + torch).

Engines load lazily: a language's model is only read from disk the first time
Jarvis speaks that language.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Protocol

import numpy as np

from ..config import Language, Settings
from .effects import VoiceStyle


class TTSEngine(Protocol):
    sample_rate: int

    def synthesize(self, text: str) -> np.ndarray: ...


class KokoroTTS:
    def __init__(self, model_path: Path, voices_path: Path, voice: str, lang: str = "en-gb", speed: float = 1.0):
        from kokoro_onnx import Kokoro

        if not model_path.is_file() or not voices_path.is_file():
            raise FileNotFoundError(
                f"Kokoro files missing ({model_path.name}, {voices_path.name}). "
                "Run: uv run python scripts/download_models.py"
            )
        self._kokoro = Kokoro(str(model_path), str(voices_path))
        if voice not in self._kokoro.get_voices():
            raise ValueError(f"Kokoro has no voice '{voice}'")
        self.voice, self.lang, self.speed = voice, lang or "en-us", speed
        self.sample_rate = 24000

    def synthesize(self, text: str) -> np.ndarray:
        audio, sr = self._kokoro.create(text, voice=self.voice, speed=self.speed, lang=self.lang)
        self.sample_rate = sr
        return np.asarray(audio, dtype=np.float32)


class PiperTTS:
    def __init__(self, onnx_path: Path, speed: float = 1.0):
        from piper import PiperVoice
        from piper.config import SynthesisConfig

        if not onnx_path.is_file():
            raise FileNotFoundError(
                f"Piper voice missing: {onnx_path}. Run: uv run python scripts/download_models.py"
            )
        self._voice = PiperVoice.load(onnx_path)
        self._config = SynthesisConfig(length_scale=1.0 / speed if speed else None)
        self.sample_rate = self._voice.config.sample_rate

    def synthesize(self, text: str) -> np.ndarray:
        parts = []
        for chunk in self._voice.synthesize(text, syn_config=self._config):
            self.sample_rate = chunk.sample_rate
            parts.append(chunk.audio_float_array)
        return np.concatenate(parts).astype(np.float32) if parts else np.zeros(0, np.float32)


class MmsTTS:
    def __init__(self, model_id: str, speed: float = 1.0):
        try:
            import torch
            from transformers import AutoTokenizer, VitsModel
        except ImportError as exc:
            raise ImportError("MMS voices need the 'mms' extra: uv sync --extra mms") from exc
        self._torch = torch
        self._model = VitsModel.from_pretrained(model_id)
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        if speed and speed != 1.0:
            self._model.speaking_rate = speed
        self.sample_rate = self._model.config.sampling_rate

    def synthesize(self, text: str) -> np.ndarray:
        inputs = self._tokenizer(text, return_tensors="pt")
        with self._torch.no_grad():
            wave = self._model(**inputs).waveform
        return wave.squeeze().cpu().numpy().astype(np.float32)


def build_engine(lang: Language, settings: Settings) -> TTSEngine:
    speed = float(settings.get("tts.speed", 1.0))
    if lang.tts_engine == "kokoro":
        return KokoroTTS(
            settings.path("tts.kokoro_model", "models/kokoro-v1.0.onnx"),
            settings.path("tts.kokoro_voices", "models/voices-v1.0.bin"),
            voice=lang.tts_voice, lang=lang.tts_lang or "en-us", speed=speed,
        )
    if lang.tts_engine == "piper":
        return PiperTTS(settings.path("tts.piper_dir", "models/piper") / f"{lang.tts_voice}.onnx", speed=speed)
    if lang.tts_engine == "mms":
        return MmsTTS(lang.tts_voice, speed=speed)
    raise ValueError(f"unknown tts_engine '{lang.tts_engine}' for {lang.name}")


class TTSRouter:
    """Picks the engine for the active language and applies the voice style.

    `render` is blocking (model inference); call it from a worker thread.
    """

    def __init__(self, settings: Settings, style: VoiceStyle | None = None, factory=build_engine):
        self._settings = settings
        self._factory = factory
        self._engines: dict[str, TTSEngine] = {}
        self._lock = threading.Lock()
        self.style = style or VoiceStyle.from_dict(settings.get("voice_style", {}))

    def engine(self, lang: Language) -> TTSEngine:
        with self._lock:
            if lang.code not in self._engines:
                self._engines[lang.code] = self._factory(lang, self._settings)
            return self._engines[lang.code]

    def render(self, text: str, lang: Language) -> tuple[np.ndarray, int]:
        engine = self.engine(lang)
        audio = engine.synthesize(text)
        sr = engine.sample_rate
        return self.style.process(audio, sr), sr
