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
