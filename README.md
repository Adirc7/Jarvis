# Jarvis
Ai assistant how deal with emotions of the users'

A context-aware multimodal desktop assistant: voice, hand gestures and app
context, with verified actions. Self-study build, free tools only.

Status: **Phase 0** (foundations). See `docs/DEVLOG.md` for progress and
`docs/DECISIONS.md` for the design decisions behind the code.

## What works now

- Text chat with free LLMs (Gemini, Groq, OpenRouter, local Ollama) with
  automatic fallback when one fails or hits its rate limit
- Language switching: English, Sinhala, Tamil ("switch to Tamil",
  "සිංහලෙන් කතා කරන්න", or `/lang si`)
- Global kill switch (`Ctrl+Alt+K`) that stops whatever Jarvis is doing
- Event bus, shared state and telemetry (every stage logged as JSON lines)
- A smoke test that checks your mic, camera, GPU, Whisper, MediaPipe and LLMs,
  including whether hand tracking slows down while Whisper runs

## Setup on Windows

1. Install **uv** (manages Python and packages). In PowerShell:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   Close and reopen PowerShell afterwards.
2. In the project folder, install everything (uv fetches Python 3.12 itself;
   the GPU libraries are about 1 GB):
   ```powershell
   cd jarvis
   uv sync --all-extras
   ```
3. Add at least one free LLM key:
   ```powershell
   copy .env.example .env
   notepad .env
   ```
   Easiest: a Gemini key from https://aistudio.google.com/apikey and a Groq key
   from https://console.groq.com/keys. Two providers means one can fail.
4. Optional, for offline use: install Ollama from https://ollama.com, then
   `ollama pull qwen3:4b`.

## Run

```powershell
uv run pytest                                  # unit tests (no hardware needed)
uv run python scripts/smoke_test.py --show     # hardware + model check
uv run jarvis                                  # Phase 0 text chat
uv run python -m jarvis.telemetry logs\session-XXXX.jsonl   # latency summary
```

For Sinhala and Tamil text, use **Windows Terminal** (the old console can't
draw these scripts properly).

The smoke test records your voice, so run it twice: once speaking English, once
speaking Sinhala or Tamil. It saves its results to `logs/smoke-<time>.json`.

## Project layout

```
config/            settings.toml, languages.toml
src/jarvis/
  bus.py           event bus (threads -> asyncio queues)
  state.py         shared state + cancel tokens
  language.py      language switching rules
  killswitch.py    global hotkey
  telemetry.py     JSONL logging, p50/p95 summaries
  gpu.py           finds pip-installed CUDA DLLs on Windows
  agent/llm.py     free providers with fallback
  voice/ perception/ tools/ proactive/ memory/ evaluation/   later phases
scripts/smoke_test.py
desktop/           Electron UI (Phase 2)
docs/              DECISIONS.md, LANGUAGES.md, DEVLOG.md
```

## Privacy

No audio or video is saved, except that the smoke test keeps your recording in
memory only while it runs. Free hosted LLM tiers may use prompts to improve
their products; don't send passwords or private files through them. Ollama
keeps everything on your laptop.
