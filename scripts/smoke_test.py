"""Smoke test: does everything Jarvis needs run on this laptop, at the same time?

    python scripts/smoke_test.py                    full test: mic, camera, LLMs
    python scripts/smoke_test.py --no-camera        skip the webcam
    python scripts/smoke_test.py --show             draw hand landmarks in a window
    python scripts/smoke_test.py --whisper-model large-v3-turbo

What it checks:
  1. environment    Python version and the libraries Jarvis needs
  2. gpu            whether faster-whisper can use your RTX 4050
  3. microphone     records a few seconds; tells you if it's silent
  4. whisper        transcribes the recording and reports the language it heard
  5. camera         MediaPipe hand tracking: frames per second and latency
  6. together       camera tracking WHILE Whisper runs: does tracking slow down?
  7. llm            each free provider: speed, tool calling, Sinhala/Tamil replies
  8. voices         each language's voice: loads, speed, and plays it on your speakers

Results print as a table and are saved to logs/smoke-<time>.json.
Tip: run it twice, speaking English the first time and Sinhala or Tamil the second.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import platform
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import Settings, load_settings  # noqa: E402
from jarvis.gpu import cuda_device_count, prepare_cuda  # noqa: E402
from jarvis.telemetry import Telemetry, percentile  # noqa: E402

HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
SAMPLE_RATE = 16_000
SCRIPT_RANGES = {"si": (0x0D80, 0x0DFF), "ta": (0x0B80, 0x0BFF)}


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
@dataclass
class Report:
    rows: list[dict[str, str]] = field(default_factory=list)

    def add(self, check: str, status: str, detail: str) -> None:
        self.rows.append({"check": check, "status": status, "detail": detail})
        print(f"  [{status}] {check}: {detail}", flush=True)

    @property
    def failed(self) -> bool:
        return any(r["status"] == "FAIL" for r in self.rows)

    def print_table(self) -> None:
        print("\n" + "=" * 78)
        print("SUMMARY")
        print("=" * 78)
        for r in self.rows:
            print(f"[{r['status']:4}] {r['check']:28} {r['detail'][:110]}")


def section(title: str) -> None:
    print(f"\n--- {title} " + "-" * (70 - len(title)), flush=True)


# --------------------------------------------------------------------------
# 1-2. Environment and GPU
# --------------------------------------------------------------------------
PACKAGES = [
    ("faster_whisper", "voice"), ("sounddevice", "voice"), ("mediapipe", "vision"),
    ("cv2", "vision"), ("openai", "core"), ("pynput", "desktop"), ("numpy", "core"),
]


def check_environment(r: Report) -> None:
    section("1. Environment")
    v = sys.version_info
    status = "PASS" if (v.major, v.minor) in ((3, 11), (3, 12)) else "WARN"
    r.add("python", status, f"{platform.python_version()} on {platform.system()} {platform.release()}"
          + ("" if status == "PASS" else " (3.11 or 3.12 is the safest choice for these libraries)"))
    for module, extra in PACKAGES:
        try:
            m = importlib.import_module(module)
            r.add(f"import {module}", "PASS", getattr(m, "__version__", "ok"))
        except Exception as exc:
            r.add(f"import {module}", "FAIL",
                  f"{type(exc).__name__}: {exc}. Install with: uv sync --extra {extra}")


def check_gpu(r: Report) -> int:
    section("2. GPU")
    added = prepare_cuda()
    if added:
        r.add("cuda dlls", "PASS", f"added {len(added)} pip NVIDIA folders to the DLL path")
    n = cuda_device_count()
    if n > 0:
        r.add("cuda for whisper", "PASS", f"{n} CUDA device(s) visible to CTranslate2")
    else:
        r.add("cuda for whisper", "WARN",
              "no CUDA device visible; Whisper will run on CPU (slower). "
              "Fix: uv sync --extra gpu, and update the NVIDIA driver")
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version",
             "--format=csv,noheader"], capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            r.add("nvidia-smi", "PASS", out.stdout.strip().splitlines()[0])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return n


# --------------------------------------------------------------------------
# 3-4. Microphone and Whisper
# --------------------------------------------------------------------------
def record_mic(seconds: float, r: Report):
    section("3. Microphone")
    import numpy as np
    try:
        import sounddevice as sd
    except Exception as exc:
        r.add("microphone", "FAIL", f"sounddevice unavailable: {exc}")
        return None
    try:
        dev = sd.query_devices(kind="input")
        print(f"  Using input device: {dev['name']}")
        print(f"  >>> Speak now for {seconds:.0f} seconds (a full sentence works best) <<<", flush=True)
        audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()
    except Exception as exc:
        r.add("microphone", "FAIL", f"{type(exc).__name__}: {exc}")
        return None
    audio = audio.flatten()
    rms = float(np.sqrt(np.mean(audio ** 2)))
    peak = float(np.max(np.abs(audio)))
    if rms < 1e-4:
        r.add("microphone", "WARN", f"almost silent (rms {rms:.5f}). Check Windows privacy settings for the mic")
    elif peak > 0.99:
        r.add("microphone", "WARN", f"clipping (peak {peak:.2f}). Lower the input volume")
    else:
        r.add("microphone", "PASS", f"level ok (rms {rms:.4f}, peak {peak:.2f})")
    return audio


def load_whisper(settings: Settings, model_name: str, cuda_devices: int, r: Report):
    section("4. Whisper")
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        r.add("whisper load", "FAIL", f"faster-whisper unavailable: {exc}")
        return None
    attempts = []
    if cuda_devices > 0 and settings.get("stt.device", "cuda") == "cuda":
        attempts.append(("cuda", settings.get("stt.compute_type", "int8_float16")))
    attempts.append(("cpu", "int8"))
    for device, compute in attempts:
        try:
            t0 = time.perf_counter()
            print(f"  Loading '{model_name}' on {device} ({compute}). First run downloads the model...", flush=True)
            model = WhisperModel(model_name, device=device, compute_type=compute)
            ms = (time.perf_counter() - t0) * 1000
            r.add("whisper load", "PASS" if device == "cuda" else "WARN",
                  f"{model_name} on {device}/{compute} in {ms:.0f} ms")
            return model
        except Exception as exc:
            r.add(f"whisper load ({device})", "WARN" if device == "cuda" else "FAIL",
                  f"{type(exc).__name__}: {str(exc)[:160]}")
    return None


def transcribe(model, audio, use_vad: bool) -> tuple[str, Any, float]:
    t0 = time.perf_counter()
    segments, info = model.transcribe(audio, beam_size=1, vad_filter=use_vad, language=None)
    text = " ".join(s.text.strip() for s in segments)   # the generator does the work
    return text, info, (time.perf_counter() - t0) * 1000


def check_whisper(model, audio, settings: Settings, r: Report, tel: Telemetry):
    import numpy as np
    real_speech = audio is not None
    if not real_speech:
        print("  No recording; using 5 s of noise just to time the model.")
        audio = (np.random.default_rng(0).standard_normal(5 * SAMPLE_RATE) * 0.01).astype("float32")
    # The very first call loads CUDA kernels (can take a long time on the first
    # run ever); Jarvis does this at startup, so time it separately.
    warm_text, _, warm_ms = transcribe(model, np.zeros(SAMPLE_RATE, dtype="float32"), use_vad=False)
    r.add("whisper warm-up", "PASS", f"first call {warm_ms:.0f} ms (Jarvis does this once at startup)")
    text, info, ms = transcribe(model, audio, use_vad=real_speech)
    dur = len(audio) / SAMPLE_RATE
    rtf = (ms / 1000) / dur
    tel.log("smoke_stt", ms=round(ms, 1), audio_s=dur, rtf=round(rtf, 3),
            language=info.language, probability=round(info.language_probability, 3))
    status = "PASS" if rtf < 0.5 else "WARN"
    r.add("whisper speed", status, f"{ms:.0f} ms for {dur:.1f} s of audio (real-time factor {rtf:.2f}; under 0.5 is good)")
    if real_speech:
        known = {lang.whisper_code: lang.name for lang in settings.languages.values()}
        lang_name = known.get(info.language, f"'{info.language}' (not a Jarvis language)")
        r.add("whisper heard", "PASS" if text else "WARN",
              f"{lang_name}, p={info.language_probability:.2f}: \"{text[:80]}\"")
        if info.language == "si":
            r.add("sinhala note", "WARN", "base Whisper is weak at Sinhala; see docs/LANGUAGES.md for a fine-tuned model")
    return audio


# --------------------------------------------------------------------------
# 5-6. Camera + MediaPipe, alone and together with Whisper
# --------------------------------------------------------------------------
def ensure_hand_model(path: Path, r: Report) -> bool:
    if path.is_file():
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading hand model to {path} ...", flush=True)
    try:
        urllib.request.urlretrieve(HAND_MODEL_URL, path)
        return True
    except Exception as exc:
        r.add("hand model", "FAIL", f"download failed ({exc}). Download it manually from {HAND_MODEL_URL}")
        return False


def frame_stats(latencies_ms: list[float], elapsed_s: float, hand_frames: int) -> dict[str, float]:
    n = len(latencies_ms)
    return {
        "frames": n,
        "fps": n / elapsed_s if elapsed_s > 0 else 0.0,
        "p50_ms": percentile(latencies_ms, 50) if n else float("nan"),
        "p95_ms": percentile(latencies_ms, 95) if n else float("nan"),
        "hand_rate": hand_frames / n if n else 0.0,
    }


def camera_loop(settings: Settings, seconds: float, show: bool,
                stop: threading.Event | None = None) -> dict[str, float]:
    """Read frames and run the hand landmarker. Returns timing stats."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(settings.get("vision.camera_index", 0), backend)
    if not cap.isOpened():
        raise RuntimeError("could not open the camera (is another app using it?)")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    options = vision.HandLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(settings.path("vision.hand_model", "models/hand_landmarker.task"))),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=settings.get("vision.num_hands", 1),
    )
    latencies: list[float] = []
    hand_frames = 0
    t_start = time.perf_counter()
    last_ts = -1
    try:
        with vision.HandLandmarker.create_from_options(options) as landmarker:
            while time.perf_counter() - t_start < seconds and not (stop and stop.is_set()):
                ok, frame = cap.read()
                if not ok:
                    continue
                frame = cv2.flip(frame, 1)                      # mirror, like a selfie view
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ts = int((time.perf_counter() - t_start) * 1000)
                ts = max(ts, last_ts + 1)                       # must strictly increase
                last_ts = ts
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                t0 = time.perf_counter()
                result = landmarker.detect_for_video(image, ts)
                latencies.append((time.perf_counter() - t0) * 1000)
                if result.hand_landmarks:
                    hand_frames += 1
                if show:
                    h, w = frame.shape[:2]
                    for hand in result.hand_landmarks:
                        for lm in hand:
                            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 3, (0, 200, 255), -1)
                    cv2.putText(frame, "q = quit", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    cv2.imshow("Jarvis smoke test", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
    finally:
        cap.release()
        if show:
            cv2.destroyAllWindows()
    return frame_stats(latencies, time.perf_counter() - t_start, hand_frames)


def check_camera(settings: Settings, seconds: float, show: bool, r: Report, tel: Telemetry):
    section("5. Camera + hand tracking")
    if not ensure_hand_model(settings.path("vision.hand_model", "models/hand_landmarker.task"), r):
        return None
    print(f"  Hold one hand up in front of the camera for {seconds:.0f} seconds...", flush=True)
    try:
        s = camera_loop(settings, seconds, show)
    except Exception as exc:
        r.add("camera", "FAIL", f"{type(exc).__name__}: {exc}")
        return None
    tel.log("smoke_camera", **s)
    good = s["fps"] >= 20 and s["p95_ms"] < 50
    r.add("hand tracking", "PASS" if good else "WARN",
          f"{s['fps']:.1f} fps, landmarker p50 {s['p50_ms']:.1f} ms / p95 {s['p95_ms']:.1f} ms, "
          f"hand found in {s['hand_rate']:.0%} of frames")
    if s["hand_rate"] < 0.5:
        r.add("hand visibility", "WARN", "hand found in under half the frames: improve lighting or move closer")
    return s


def check_together(settings: Settings, model, audio, seconds: float, baseline: dict[str, float],
                   r: Report, tel: Telemetry) -> None:
    section("6. Camera and Whisper at the same time")
    print(f"  Keep your hand up for another {seconds:.0f} seconds while Whisper runs in parallel...", flush=True)
    stats: dict[str, Any] = {}
    error: list[BaseException] = []

    def run_camera():
        try:
            stats.update(camera_loop(settings, seconds, show=False))
        except BaseException as exc:   # surface thread errors in the report
            error.append(exc)

    t = threading.Thread(target=run_camera, daemon=True)
    t.start()
    stt_ms: list[float] = []
    while t.is_alive():
        _, _, ms = transcribe(model, audio, use_vad=False)
        stt_ms.append(ms)
    t.join()
    if error:
        r.add("together", "FAIL", f"camera thread crashed: {error[0]}")
        return
    drop = 1 - stats["fps"] / baseline["fps"] if baseline["fps"] else 0
    tel.log("smoke_together", fps=stats["fps"], p95_ms=stats["p95_ms"], fps_drop=round(drop, 3),
            whisper_runs=len(stt_ms), whisper_p50_ms=percentile(stt_ms, 50))
    status = "PASS" if drop < 0.25 else "WARN"
    r.add("tracking during whisper", status,
          f"{stats['fps']:.1f} fps (was {baseline['fps']:.1f}, "
          + (f"drop {drop:.0%}); " if drop > 0 else "no drop); ")
          + f"Whisper ran {len(stt_ms)}x, p50 {percentile(stt_ms, 50):.0f} ms")
    if status == "WARN":
        r.add("together note", "WARN",
              "tracking slows down while Whisper runs: move camera capture to its own process in Phase 3")


# --------------------------------------------------------------------------
# 7. Free LLM providers
# --------------------------------------------------------------------------
TIME_TOOL = [{
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current local time on the user's computer.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}]


def has_script(text: str, code: str) -> bool:
    lo, hi = SCRIPT_RANGES[code]
    return any(lo <= ord(ch) <= hi for ch in text)


async def probe_provider(cfg, settings: Settings, r: Report, tel: Telemetry) -> None:
    from jarvis.agent.llm import FallbackLLM, Provider
    llm = FallbackLLM([Provider.from_config(cfg, settings.get("llm.timeout_s", 20))], tel)
    name = cfg.name

    t0 = time.perf_counter()
    first_ms = None
    text = ""
    try:
        # Generous max_tokens: models that think first count thinking against it,
        # and a tight limit leaves an empty reply.
        async for piece in llm.stream_text([{"role": "user", "content": "Reply with exactly one word: OK"}],
                                           max_tokens=1024):
            if first_ms is None:
                first_ms = (time.perf_counter() - t0) * 1000
            text += piece
    except Exception as exc:
        hint = ""
        if name == "ollama":
            hint = f" Start it with 'ollama serve' and run 'ollama pull {cfg.model}'."
        r.add(f"llm {name}", "WARN" if name == "ollama" else "FAIL", f"{str(exc)[:150]}{hint}")
        return
    total = (time.perf_counter() - t0) * 1000
    status = "PASS" if text.strip() else "WARN"
    r.add(f"llm {name}", status, f"{cfg.model}: first token {first_ms or total:.0f} ms, total {total:.0f} ms, "
          + (f"said {text.strip()[:20]!r}" if text.strip() else "empty reply"))

    try:
        _, msg = await llm.complete(
            [{"role": "user", "content": "What time is it right now? Use the tool."}], tools=TIME_TOOL
        )
        called = bool(getattr(msg, "tool_calls", None))
        r.add(f"llm {name} tools", "PASS" if called else "WARN",
              "calls tools correctly" if called else "answered without calling the tool")
    except Exception as exc:
        r.add(f"llm {name} tools", "WARN", f"tool calling failed: {str(exc)[:120]}")

    for code in ("si", "ta"):
        if code not in settings.languages:
            continue
        lang = settings.languages[code]
        try:
            reply = ""
            async for piece in llm.stream_text([
                {"role": "system", "content": f"Reply only in {lang.name}, in {lang.name} script."},
                {"role": "user", "content": "Say: Hello, I am Jarvis, your desktop assistant."},
            ], max_tokens=1024):
                reply += piece
            ok = has_script(reply, code)
            r.add(f"llm {name} {lang.name}", "PASS" if ok else "WARN",
                  reply.strip().replace("\n", " ")[:70] if ok else f"no {lang.name} script in reply")
        except Exception as exc:
            r.add(f"llm {name} {lang.name}", "WARN", str(exc)[:120])


async def check_llms(settings: Settings, r: Report, tel: Telemetry) -> None:
    section("7. Free LLM providers")
    for cfg in settings.providers():
        if not cfg.is_configured:
            r.add(f"llm {cfg.name}", "SKIP", f"no {cfg.api_key_env} in .env")
            continue
        await probe_provider(cfg, settings, r, tel)


# --------------------------------------------------------------------------
# 8. Voices (Phase 1)
# --------------------------------------------------------------------------
def check_voices(settings: Settings, play: bool, r: Report, tel: Telemetry) -> None:
    section("8. Voices")
    try:
        from jarvis.voice.tts import TTSRouter
    except Exception as exc:
        r.add("tts", "FAIL", f"voice libraries missing ({exc}). Install with: uv sync --extra voice")
        return
    router = TTSRouter(settings)
    for lang in settings.languages.values():
        phrase = lang.confirm or "Hello."
        try:
            router.render("Ready.", lang)                     # first call loads and warms up
            t0 = time.perf_counter()
            audio, sr = router.render(phrase, lang)
            ms = (time.perf_counter() - t0) * 1000
        except Exception as exc:
            hint = "" if "download_models" in str(exc) or "missing" not in str(exc).lower() else " Run: uv run python scripts/download_models.py"
            r.add(f"voice {lang.name}", "WARN", f"{lang.tts_engine}/{lang.tts_voice}: {str(exc)[:160]}{hint}")
            continue
        rtf = (ms / 1000) / max(len(audio) / sr, 1e-6)
        tel.log("smoke_tts", language=lang.code, engine=lang.tts_engine, ms=round(ms, 1), rtf=round(rtf, 3))
        r.add(f"voice {lang.name}", "PASS" if rtf < 0.5 else "WARN",
              f"{lang.tts_engine}/{lang.tts_voice}: {ms:.0f} ms for {len(audio) / sr:.1f} s (real-time factor {rtf:.2f})")
        if play:
            try:
                import sounddevice as sd
                print(f"  playing {lang.name}: {phrase}")
                sd.play(audio, sr)
                sd.wait()
            except Exception as exc:
                r.add("speakers", "WARN", f"playback failed: {exc}")
                play = False


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Jarvis smoke test")
    ap.add_argument("--no-mic", action="store_true")
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-voice", action="store_true", help="skip the text-to-speech check")
    ap.add_argument("--no-speaker", action="store_true", help="check voices without playing them")
    ap.add_argument("--record", type=float, default=6, help="seconds of mic audio to record")
    ap.add_argument("--seconds", type=float, default=10, help="seconds per camera test")
    ap.add_argument("--whisper-model", default=None, help="override [stt].model, e.g. large-v3-turbo")
    ap.add_argument("--show", action="store_true", help="show the camera with hand landmarks")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    settings = load_settings()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = settings.path("telemetry.dir", "logs")
    tel = Telemetry(log_dir / f"smoke-{stamp}.jsonl")
    r = Report()

    check_environment(r)
    n_cuda = check_gpu(r)

    audio = None if args.no_mic else record_mic(args.record, r)
    model = load_whisper(settings, args.whisper_model or settings.get("stt.model", "small"), n_cuda, r)
    if model is not None:
        audio = check_whisper(model, audio, settings, r, tel)

    if not args.no_camera:
        baseline = check_camera(settings, args.seconds, args.show, r, tel)
        if baseline and model is not None:
            check_together(settings, model, audio, args.seconds, baseline, r, tel)

    if not args.no_llm:
        asyncio.run(check_llms(settings, r, tel))

    if not args.no_voice:
        check_voices(settings, play=not args.no_speaker, r=r, tel=tel)

    r.print_table()
    out = log_dir / f"smoke-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"time": stamp, "results": r.rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out}")
    return 1 if r.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
