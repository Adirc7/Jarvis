# Jarvis
Ai assistant how deal with emotions of the users'

A context-aware multimodal desktop assistant: voice, hand gestures and app
context, with verified actions. Self-study build, free tools only.

Jarvis is one core (voice, Sinhala and English, emotion, memory, safety)
plus skills (study, visualise, data, research, news).

Status: **Phase 1** (spoken conversation), about to run on the laptop.
Next: a startup greeting, replying in the language you speak, then Phase 2
(tools and safety) and the first skill, Study. See `docs/ROADMAP.md` for the
build order and the research priorities behind it, `docs/DEVLOG.md` for
progress and `docs/DECISIONS.md` for the reasoning.

## What works now

- **Talk to it**: hold Right Ctrl, speak, let go. Whisper transcribes, a free
  LLM answers, and Jarvis speaks the reply sentence by sentence while the rest
  is still being written.
- **Its own voice and character**: a British Kokoro voice (Lewis) with a light
  studio effects chain, and a written personality in `config/persona.toml`.
  No cloned voices; Jarvis says it's an AI if you ask.
- **Empathy modes**: logical, balanced or supportive. Say "be more direct" or
  "be gentler", or type `/empathy supportive`.
- **Natural timing**: a short "mm, one moment" only when a reply is slow.
- **Three languages**: English, Sinhala, Tamil. "Switch to Tamil",
  "සිංහලෙන් කතා කරන්න", or `/lang si`. Each language has its own speech
  model and voice.
- **Interrupt it**: press push-to-talk while it's speaking (barge-in),
  `Ctrl+Alt+M` to mute replies, `Ctrl+Alt+K` to stop everything.
- **Free LLMs with fallback**: Gemini, Groq (Llama and OpenAI's open gpt-oss),
  OpenRouter, local Ollama.
- **Measured from day one**: every stage is timed in `logs/`; scripts to
  record test sentences and score Whisper models (WER/CER).

## Setup on Windows

1. **Get the code** into a folder outside OneDrive, on any drive, e.g.
   `D:\Projects\Jarvis`:
   ```powershell
   D:
   cd \Projects
   git clone https://github.com/Adirc7/Jarvis
   ```
   On a drive other than C:, setup offers to keep the big downloads (package
   cache, Python, Whisper and Ollama models) on that drive too, in
   `D:\Projects\.cache`. Jarvis needs roughly 6 GB, plus 2.5 GB with Ollama.
   No Git? Install it with `winget install Git.Git`, or use Code → Download
   ZIP on GitHub (right-click the ZIP → Properties → Unblock, then extract).
2. **Double-click `Setup Jarvis.cmd`** in the Jarvis folder. It:
   - installs uv, which fetches Python 3.12 and every package (the CUDA
     libraries too if it finds an NVIDIA GPU), plus the Visual C++ runtime if
     it's missing;
   - downloads the voices and the hand-tracking model;
   - opens `.env` in Notepad for your free LLM keys: Gemini
     (https://aistudio.google.com/apikey) and Groq (https://console.groq.com/keys);
   - asks about your push-to-talk key (some new laptops have a Copilot key
     where Right Ctrl used to be; then you press the key you want instead);
   - runs the unit tests, creates the shortcuts, and offers a hardware check
     (mic, speakers, camera, GPU, voices).

   The first run downloads a few GB. If a step fails, fix what it says and run
   it again; finished steps are skipped. Options: `"Setup Jarvis.cmd" -NoTamil`
   skips the Tamil voice (about 1 GB of torch), `-NoGpu` skips CUDA.
3. **Double-click Jarvis** on the desktop (or `Start Jarvis.cmd`). Hold the
   push-to-talk key, speak, let go. "Jarvis (text chat)" in the Start menu is
   the typing version.

Optional, for answers without internet: install Ollama from
https://ollama.com and run setup again; it offers to download `qwen3:4b`.

**Update:** `git pull`, then double-click `Setup Jarvis.cmd` again.

**Settings for this computer** (push-to-talk key, audio devices, Whisper
model) go in `config/settings.local.toml`: same format as
`config/settings.toml`, only the lines you change. It isn't committed, so
updates never overwrite it. Change the push-to-talk key any time with
`uv run python scripts/choose_key.py`.

<details>
<summary>Manual setup (what the script does)</summary>

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv sync --all-extras
uv run python scripts/download_models.py
copy .env.example .env
notepad .env
```
</details>

## Run

```powershell
uv run jarvis --voice                           # talk to Jarvis (hold the push-to-talk key)
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

Put your own values for `settings.toml` in `config/settings.local.toml` (see
Setup); edit the other files directly.

| File | Setting | What it does |
|---|---|---|
| `config/settings.toml` | `[hotkeys] push_to_talk` | key to hold while speaking (`ctrl_r`, `f9`, ...); `scripts/choose_key.py` sets it |
| | `[stt] model` | Whisper model: `small`, `large-v3-turbo`, ... |
| | `[tts] speed` | `0.9` = slower, calmer voice |
| | `[voice_style]` | the effects chain; `enabled = false` for the raw voice |
| `config/languages.toml` | `tts_voice` | which voice each language uses |
| `config/persona.toml` | `user_name` | what Jarvis calls you (empty = no name) |
| | `[personality]`, `[speaking_style]` | Jarvis's character; edit freely |
| | `[empathy] default` | starting empathy mode |

## Project layout

```
Setup Jarvis.cmd   one-click setup (runs scripts/setup_windows.ps1)
Start Jarvis.cmd   starts voice mode (runs scripts/run_jarvis.cmd)
config/            settings.toml, languages.toml, persona.toml
                   (+ settings.local.toml: this computer only, not committed)
src/jarvis/
  app.py           request pipeline, voice loop, hotkeys
  persona.py       character sheet -> instructions for the LLM
  bus.py           event bus (threads -> asyncio queues)
  state.py         shared state + cancel tokens
  language.py      language switching rules
  telemetry.py     JSONL logging, p50/p95 summaries
  agent/llm.py     free providers with fallback
  voice/           capture (push-to-talk), stt (Whisper), tts (Kokoro/Piper/MMS),
                   effects, player, sink (streams replies to speech), text_split
  evaluation/      WER/CER scoring
  perception/ tools/ proactive/ memory/   later phases
scripts/           setup_windows, run_jarvis, choose_key, smoke_test, download_models,
                   voice_preview, record_eval_set, eval_stt
assets/            shortcut icon
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
