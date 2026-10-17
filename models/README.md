# models/

Downloaded model files live here and are not committed to git.

Run `uv run python scripts/download_models.py` to fetch them:

- `hand_landmarker.task`: MediaPipe hand tracking
- `kokoro-v1.0.onnx`, `voices-v1.0.bin`: English voices
- `piper/<voice>.onnx` + `.onnx.json`: Piper voices (Sinhala)
- Converted Whisper fine-tunes (optional): see `docs/LANGUAGES.md`

faster-whisper and MMS-TTS download their own models into the Hugging Face cache on first use.
