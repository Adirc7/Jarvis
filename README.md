# Jarvis
Ai assistant how deal with emotions of the users'

A context-aware multimodal desktop assistant: voice, hand gestures and app
context, with verified actions. Self-study build, free tools only.

Status: **Phase 1** (spoken conversation). Next: emotion-aware replies
(Phase 1.5) and Windows tools (Phase 2). See `docs/ROADMAP.md` for the plan,
`docs/DEVLOG.md` for progress and `docs/DECISIONS.md` for the reasoning.

## What works now

- **Talk to it**: hold Right Ctrl, speak, let go. Whisper transcribes, a free
  LLM answers, and Jarvis speaks the reply sentence by sentence while the rest
  is still being written.
- **Its own voice**: a British Kokoro voice with a light studio effects chain
  (the "Jarvis feel"). No cloned voices.
- **Three languages**: English, Sinhala, Tamil. "Switch to Tamil",
  "සිංහලෙන් කතා කරන්න", or `/lang si`. Each language has its own speech
  model and voice.
- **Interrupt it**: press push-to-talk while it's speaking (barge-in),
  `Ctrl+Alt+M` to mute replies, `Ctrl+Alt+K` to stop everything.
- **Free LLMs with fallback**: Gemini, Groq, OpenRouter, local Ollama.
- **Measured from day one**: every stage is timed in `logs/`; scripts to
  record test sentences and score Whisper models (WER/CER).

## Setup on Windows

1. Install **uv**. In PowerShell:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   Close and reopen PowerShell afterwards.
2. Get the code and install everything (uv fetches Python 3.12 itself):
   ```powershell
   git clone https://github.com/Adirc7/Jarvis
   cd Jarvis
   uv sync --all-extras
   ```
   `--all-extras` includes the Tamil voice (torch, about 1 GB more). To skip
   it: `uv sync --extra voice --extra vision --extra desktop --extra gpu --extra dev`.
3. Download the voices and hand-tracking model:
   ```powershell
   uv run python scripts/download_models.py
   ```
4. Add at least one free LLM key:
   ```powershell
   copy .env.example .env
   notepad .env
   ```
   Easiest: Gemini (https://aistudio.google.com/apikey) and Groq
   (https://console.groq.com/keys).
5. Optional, for offline use: install Ollama from https://ollama.com, then
   `ollama pull qwen3:4b`.

To update later: `git pull`, then `uv sync --all-extras`.

## Run

```powershell
uv run jarvis --voice                           # talk to Jarvis (hold Right Ctrl)
uv run jarvis                                   # text chat
uv run python scripts/smoke_test.py --show      # check mic, camera, GPU, models, voices
uv run python scripts/voice_preview.py --play   # hear the candidate voices
uv run pytest                                   # unit tests (no hardware needed)
uv run python -m jarvis.telemetry logs\session-XXXX.jsonl   # latency summary
```

Measuring speech recognition (see `eval/README.md`):

```powershell
uv run python scripts/record_eval_set.py eval/sentences_en.txt --lang en
uv run python scripts/eval_stt.py --lang en --model small --model large-v3-turbo
```

Use **Windows Terminal** for Sinhala and Tamil text; the old console can't draw
these scripts properly.

## Settings worth knowing

| File | Setting | What it does |
|---|---|---|
| `config/settings.toml` | `[hotkeys] push_to_talk` | key to hold while speaking (`ctrl_r`, `f9`, ...) |
| | `[stt] model` | Whisper model: `small`, `large-v3-turbo`, ... |
| | `[tts] speed` | `0.9` = slower, calmer voice |
| | `[voice_style]` | the effects chain; `enabled = false` for the raw voice |
| `config/languages.toml` | `tts_voice` | which voice each language uses |

## Project layout

```
config/            settings.toml, languages.toml
src/jarvis/
  app.py           request pipeline, voice loop, hotkeys
  bus.py           event bus (threads -> asyncio queues)
  state.py         shared state + cancel tokens
  language.py      language switching rules
  telemetry.py     JSONL logging, p50/p95 summaries
  agent/llm.py     free providers with fallback
  voice/           capture (push-to-talk), stt (Whisper), tts (Kokoro/Piper/MMS),
                   effects, player, sink (streams replies to speech), text_split
  evaluation/      WER/CER scoring
  perception/ tools/ proactive/ memory/   later phases
scripts/           smoke_test, download_models, voice_preview, record_eval_set, eval_stt
eval/              test sentences (recordings stay local)
docs/              ROADMAP.md, DECISIONS.md, LANGUAGES.md, DEVLOG.md
```

## Privacy

Audio is only kept while the push-to-talk key is held, and only in memory;
nothing is saved unless you run the evaluation recorder. Free hosted LLM tiers
may use prompts to improve their products, so don't send passwords or private
files through them. Ollama keeps everything on your laptop.

## Licences

Jarvis's own code has no licence chosen yet. Some libraries it uses are
GPL-3.0 (piper-tts, pedalboard), which matters only if you distribute Jarvis
under a different licence. Model licences: Kokoro Apache-2.0, the Sinhala
Piper voice MIT, MMS-TTS CC-BY-NC 4.0 (non-commercial).
