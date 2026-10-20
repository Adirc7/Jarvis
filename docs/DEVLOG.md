# Dev log

One entry per work session: what you did, what you measured, what's next.
Future you (and anyone reading the repo) will thank you.

## 2026-10-10: Phase 0 scaffold

- Project structure, config files, event bus, shared state, telemetry,
  kill switch, free LLM fallback, language switching (en/si/ta).
- 43 unit tests passing. Text chat checked end to end against a local
  OpenAI-compatible test server (streaming, tool calls, Sinhala/Tamil replies,
  kill switch, telemetry summary).
- Smoke test written. Its Whisper and MediaPipe parts are checked against the
  library APIs (MediaPipe 1.1, faster-whisper 1.2) but have not run on real
  hardware yet.

## 2026-10-17: Phase 1 voice loop

- Push-to-talk capture, Whisper transcription with the language escape hatch,
  sentence streaming, three TTS engines, effects chain, player with
  barge-in, mute, voice mode (`uv run jarvis --voice`).
- Evaluation tools: WER/CER scoring, test sentence recorder, Whisper
  comparison script, voice preview script.
- 77 unit and pipeline tests passing, including real Kokoro synthesis.
- Measured in the build container (CPU, fake STT/LLM): Kokoro synthesis
  real-time factor about 0.4; first audio 0.66 s after transcription.
- Not yet run on the laptop with a real mic, speakers and GPU.

**Next (on the laptop):**
1. `scripts/smoke_test.py --show` (English, then Sinhala or Tamil).
2. `uv run jarvis --voice` and have a conversation; then
   `python -m jarvis.telemetry` on the session log and note p50/p95 for
   `turn.stt_done`, `turn.first_token`, `turn.first_audio`.
3. Record 20 sentences per language and compare Whisper models with
   `scripts/eval_stt.py`.

## 2026-10-17: Emotion awareness added to the roadmap

- New Phase 1.5: speech emotion model beside Whisper, emotion passed to the
  LLM as context, corrections become labels, small classifier tuned on my
  voice. No LLM fine-tuning. Plan in ROADMAP.md, reasoning in DECISIONS D14.

## 2026-10-17: Character, empathy modes, fillers

- `config/persona.toml`: Jarvis's personality, speaking style, honesty
  limits, current abilities; local date and time added to every prompt.
- Empathy modes (logical, balanced, supportive) via `/empathy` or phrases
  like "be more direct"; supportive mode slows the voice.
- Thinking fillers, pre-rendered per language, only when a reply is slow.
- Roadmap: empathy modes, improvement ladder, human-like goals, light memory
  (Phase 2.5). Decisions D15–D17. 89 tests passing.

## 2026-10-18: Literature review and research priorities

- Reviewed 23 papers: desktop agents, voice and gesture, Sri Lankan speech,
  emotion recognition, empathetic agents, bandit personalisation,
  proactivity, human-likeness, wellbeing and regulation.
- Six gaps found; three are strong enough to be the report's contribution.
- Roadmap updated: quick wins (verified vs claimed completion, study
  measures, feedback-only empathy bandit) and big bets (emotion context in
  the agent, Sri Lankan emotional speech set). Decision D18.

## 2026-10-20: Ready to install on the laptop

- `Setup Jarvis.cmd`: one double-click installs uv, Python 3.12, the
  packages (CUDA only with an NVIDIA GPU), the Visual C++ runtime if
  missing, models, `.env`, the push-to-talk key, tests, desktop and Start menu
  shortcuts, and offers the hardware check. Decision D19.
- `Start Jarvis.cmd` / the desktop shortcut: voice mode, reopened in Windows
  Terminal when available so Sinhala and Tamil display.
- `config/settings.local.toml` for this computer's settings;
  `scripts/choose_key.py` picks the push-to-talk key by pressing it and
  refuses keys you type with, Windows/Copilot keys and media keys.
- Project on a drive other than C: (my C: is nearly full): setup checks free
  space and offers to keep uv's cache, Python, and the Whisper and Ollama
  models in a `.cache` folder next to the project, via user environment
  variables (UV_CACHE_DIR, UV_PYTHON_INSTALL_DIR, HF_HOME, OLLAMA_MODELS).
- Checks done in the build container: Windows-only wheel resolution for
  all 83 packages, no default-encoding file access, the setup script run
  under PowerShell 7 (success, missing key, saved key and failed install
  paths). 123 tests passing.
- Not yet run on real Windows: the `.cmd` launchers, shortcuts, Notepad step
  and GPU detection.

**Next:** install on the laptop, then the Phase 1 checks listed on 2026-10-17.

## 2026-10-20: Calling Jarvis from the phone added to the roadmap

- Phase 1.6: an internet call from a page on the phone (WebRTC, Tailscale
  when away), hold-to-talk first, hands-free later. No phone number: not free,
  likely foreign, and phone-line audio hurts Whisper. Decision D20.
- Starts once voice mode works on the laptop.

## 2026-10-20: Greeting, world news map, and intent

- Next in Phase 1: a short startup greeting (varied, daily, in the last
  language used).
- Phase 1.6 now includes the Jarvis window; Phase 1.7: world news on a map
  from GDELT, opened only when asked, summaries grounded in fetched articles.
- Research priority 6 and decision D21: measure how well the LLM understands
  Sri Lankan and code-mixed commands with a JSON test set, then train a
  small classifier only where it fails. The emotional speech set gets intent
  labels too.
- Translation as a bridge: compare direct Sinhala/Tamil, understand-in-
  English-reply-in-Sinhala, and full translation on the intent test set
  (accuracy, latency, naturalness).
- Reply language follows the speaker with a confidence gate (sure: switch;
  maybe: ask once; unsure: stay). Decision D22. Dataset clips get language
  labels too.
- Grammar baseline for mixed speech: action last plus helper words
  (karanna, pannunga); the trained model must beat it. Dataset plan: text
  first, recorded subset, LLM paraphrases for training only.
