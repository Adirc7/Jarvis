"""How fast can Kokoro say the first sentence? CPU vs GPU, full vs int8 model.

The first sentence is what you wait for before Jarvis starts talking, so
this times sentences of typical first-chunk length (median of 5 after a
warm-up) and prints milliseconds and the real-time factor (RTF: 0.1 means
one second of speech takes 0.1 s to make).

Standalone on purpose: it only needs onnxruntime, kokoro-onnx and numpy, so
it can run in a small test environment with a different onnxruntime build
(scripts/try_tts_gpu.cmd does that for you).

    uv run python scripts/bench_tts.py                                  # CPU, Jarvis's setup
    python scripts/bench_tts.py --provider DmlExecutionProvider         # any DirectX 12 GPU
    python scripts/bench_tts.py --provider CUDAExecutionProvider        # NVIDIA, CUDA
    uv run python scripts/bench_tts.py --model models/kokoro-v1.0.int8.onnx
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENTENCES = [                        # first chunks are 12-60 characters (tts.first_chunk_*)
    "Yes, sir.",
    "Good evening, sir. All systems are normal.",
    "When you open the settings panel on the left side,",
    "Thermodynamics is the study of heat, work and energy, and how they move.",
]


def make_session(model: Path, provider: str):
    import onnxruntime as rt

    if provider == "CUDAExecutionProvider" and hasattr(rt, "preload_dlls"):
        rt.preload_dlls()                       # CUDA and cuDNN DLLs from pip packages
    available = rt.get_available_providers()
    if provider not in available:
        sys.exit(f"{provider} isn't in this onnxruntime build. Available: {', '.join(available)}")
    opts = rt.SessionOptions()
    if provider == "DmlExecutionProvider":      # DirectML's documented requirements
        opts.enable_mem_pattern = False
        opts.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
    providers = [provider] if provider == "CPUExecutionProvider" else [provider, "CPUExecutionProvider"]
    return rt.InferenceSession(str(model), opts, providers=providers)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="CPUExecutionProvider")
    ap.add_argument("--model", type=Path, default=ROOT / "models" / "kokoro-v1.0.onnx")
    ap.add_argument("--voices", type=Path, default=ROOT / "models" / "voices-v1.0.bin")
    ap.add_argument("--voice", default="bm_lewis")
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()
    for f in (args.model, args.voices):
        if not f.is_file():
            sys.exit(f"Missing {f}. Run: uv run python scripts/download_models.py")

    import onnxruntime as rt
    from kokoro_onnx import Kokoro

    t0 = time.perf_counter()
    session = make_session(args.model, args.provider)
    kokoro = Kokoro.from_session(session, str(args.voices))
    load_ms = (time.perf_counter() - t0) * 1000
    print(f"onnxruntime {rt.__version__}, model {args.model.name}, asked for {args.provider}")
    print(f"running on: {', '.join(session.get_providers())}   (load {load_ms:.0f} ms)\n")

    for _ in range(2):                          # the first runs are slow everywhere
        kokoro.create(SENTENCES[1], voice=args.voice, speed=1.0, lang="en-gb")

    print(f"{'chars':>5} {'median ms':>10} {'audio s':>8} {'RTF':>6}   sentence")
    for text in SENTENCES:
        times, seconds = [], 0.0
        for _ in range(args.runs):
            t = time.perf_counter()
            audio, sr = kokoro.create(text, voice=args.voice, speed=1.0, lang="en-gb")
            times.append((time.perf_counter() - t) * 1000)
            seconds = len(audio) / sr
        ms = statistics.median(times)
        print(f"{len(text):>5} {ms:>10.0f} {seconds:>8.2f} {ms / 1000 / seconds:>6.2f}   {text[:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
