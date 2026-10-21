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
  (karanna, ganna); the trained model must beat it. Dataset plan: text
  first, recorded subset, LLM paraphrases for training only.
- Research scope narrowed to English, Sinhala and Singlish (D23): Tanglish
  dropped, Tamil only with a Tamil-speaking helper. Tamil stays in the app.
- Recording plan: round 1 (me, English/Sinhala/Singlish templates), then
  intents, then consenting friends; Moratuwa text datasets for the text
  side; Whisper LoRA fine-tune once a few hours of speech exist. Recorder
  gained `--set` (Singlish folder) and never overwrites clips. 125 tests.
- Compared with an assembled agent (Hermes Agent, Honcho memory, ElevenLabs
  voice): borrow MCP tools, skill files and Telegram for Phase 2; keep our
  own Windows voice core, free and local.
- Added OpenAI's open gpt-oss-120b (Groq free tier) as a fifth provider,
  with per-provider options (reasoning_effort low for faster speech); Gemma
  4 E2B noted as an Ollama option. Telegram planned as an optional channel
  per user. 127 tests.

## 2026-10-20: Roadmap reorganised as core plus skills; Phase 2 planned

- Roadmap now starts with a build order, then core phases, then skills
  (Study, Visualise, Data, Research, News, Friend), then data collection.
  The news map moved from Phase 1.7 into the News skill; Phase 1.6 now
  includes the Jarvis window. Decision D24.
- Phase 2 planned in detail: threat model, the gate, four risk tiers, allowed
  and private folders, recycle-folder deletes, untrusted content, code
  runner, spoken confirmation, action log and undo, first tools, skills,
  build steps, and a safety test set (zero unsafe actions). Decision D25.
- "Ask first" actions are confirmed only by a click; voice can cancel but
  never confirm, so speech errors can only make Jarvis more careful.
- Confirmation box gains tick boxes per item, up to three alternative
  actions and "Something else..." (typed, sent back through the gate).
  Button labels come from the tool call, not the LLM.
- Topic switching planned (D26): router with confidence per turn, threads
  parked and resumed, focused context, distress override, and answers
  labelled checked, sourced or general knowledge.
- Long-conversation notice: once per thread, with "summarise and start
  fresh", "new chat" or "keep going", and a context gauge in the window.
- Research skill widened to looking things up across the sciences:
  Wikipedia, Tavily (free), OpenAlex and arXiv; PDFs read page by page and
  summarised with page references; references shown in the window.
- Study skill: physics and maths in depth (LaTeX typeset with KaTeX,
  per-skill model choice with gpt-oss-120b for hard problems, SymPy, scipy
  and unit checks); other sciences through Research with references.
- Planned how Jarvis runs: background program with a tray icon, sleeps
  listening for "Hey Jarvis", window pops up with a time-of-day greeting,
  back to sleep after silence, quit from the tray. Window design: an orb
  with the skills around it.

## 2026-10-21: Session continuity and a composed-assistant character

- Character sheet: `address = "sir"` (setting), plus composed, precise,
  one-step-ahead and candid traits, and habits: greet once per session,
  varied short acknowledgements, mention the time only when it matters.
  Our own wording, no film lines. 128 tests passing.
- Greeting plan: no greeting when woken again in the same session; a short
  pick-up after a while; the full greeting only on the first wake of the
  day.
- Same-session window set to about 15 minutes (setting, 10-20); no
  unprompted check-ins after long silences.
- Phase 3 gesture set: open palm (stop), thumbs up/down (feedback), swipe
  (next/previous), point + "this" (Phase 4), double wave (silent wake);
  held half a second, never for risky actions, hand tracking on the CPU.
- Wake options: "Hey/Hi Jarvis", optional double clap (signal processing,
  no model), double wave later. Gestures use MediaPipe's ready-made Gesture
  Recognizer (palm, thumbs up/down) plus simple motion code for swipes.
- Built the startup greeting (`src/jarvis/greeting.py`): full greeting the
  first time each day, a short pick-up after a break, "Yes, sir?" within the
  same session (15 minutes, `[greeting]` in settings.toml); remembered in
  `state/presence.json` (not committed). Lines per language in
  languages.toml (Sinhala lines to be checked by Adhi). The LLM is told it
  already greeted. 140 tests passing.

## 2026-10-21: Everything written down before building

- `docs/ARCHITECTURE.md`: the whole system with diagrams (layers, one
  request step by step, safety gate, camera pipeline, life cycle), how the
  models talk to each other, every model with its input and output, voice,
  camera and gestures, privacy, and the theory behind each part with
  references.
- `docs/IMPLEMENTATION_PLAN.md`: milestones M0-M8 plus recording rounds,
  each with goal, what to learn, files, tests and "done when"; who writes
  what (the ML parts are mine; Claude guides and reviews).
- README rewritten around the idea; the system map page updated.
- Next: M0, the first real run on the laptop.

## 2026-10-21: First run on the laptop (milestone M0, part 1)

Setup finished on Windows 11 (ASUS, RTX 4050 6 GB, driver 591.44), project
on D:. 123 unit tests passed on Windows. Hardware check:

| Check | Result |
|---|---|
| GPU for Whisper | PASS: CUDA visible to CTranslate2 |
| Microphone | PASS: Realtek array, rms 0.0078, peak 0.17 |
| Whisper small load | 66.6 s, first run, including the download |
| Whisper first call | 41.7 s for 6 s of audio: first-run CUDA warm-up, not steady speed |
| Whisper steady | p50 222 ms per run while the camera ran (53 runs) |
| Whisper heard | English, p = 0.71: "Oh my god, Javis is going to be a Javis Twitter" |
| Hand tracking | 7.3 fps alone (dim room at 3 a.m.), 14.8 fps in the second test; hand found in 56% of frames |
| Voices | Lewis RTF 0.28, Sinhala 0.03, Tamil 0.18: all fast enough |
| Gemini | answered, tools work, but 7.2 s to first word and an empty reply |
| Groq, OpenRouter | FAIL: retired / no longer free models |

Fixes: Groq now gpt-oss-20b and gpt-oss-120b, OpenRouter Gemma 4 31B (free),
`reasoning_effort = "low"` for thinking models, the hardware check gives
thinking models room to reply, times Whisper's warm-up separately, and no
longer prints a negative "drop". Two noisy Hugging Face warnings silenced.

**Next:** `git pull`, run the hardware check again, then the first
conversation and the latency table.

## 2026-10-21: Second hardware check, after the fixes

| Check | Result |
|---|---|
| Whisper warm-up | 386 ms (CUDA kernels cached since the first run) |
| Whisper speed | 151 ms for 6 s of audio (real-time factor 0.03) |
| Whisper heard | nothing: the recording was very quiet (rms 0.0016, peak 0.01) |
| Groq gpt-oss-120b | 223 ms to first word; tools, Sinhala and Tamil OK |
| Groq gpt-oss-20b | 323 ms to first word; tools, Sinhala and Tamil OK |
| Gemini | 503: "high demand" (the key works; Google's free servers were busy) |
| OpenRouter | 429: the free Gemma 4 was rate-limited |
| Hand tracking | 14.4 fps, no drop with Whisper running; hand in 12% of frames |
| Voices | all PASS |

Decision: order the brains by measured speed (Groq first), and use
OpenRouter's `openrouter/free` router instead of one fixed free model.

## 2026-10-21: First conversation on the laptop (typed, in voice mode)

- Worked end to end on Groq gpt-oss-120b: the greeting ("Still up, sir?"),
  "sir", and time awareness ("while the world's asleep").
- Problem 1: asked what's happening in Sri Lanka, it answered from the LLM's
  old training memory as if current. Fix: a boundary rule never to present
  anything as current unless a tool fetched it this conversation, and
  "search the web or check current news" added to `cannot_yet`.
- Problem 2: a physics answer came back with LaTeX and bold markers, which
  the voice would read aloud. Fix: the spoken-reply instruction forbids
  symbols and LaTeX, and `clean_for_speech` now says LaTeX in words
  ("8 pi G over c to the power 4"); `$5` stays money.
- Problem 3: holding Right Ctrl did nothing (no "[listening...]" line), so
  the keyboard listener isn't receiving the key. Being diagnosed with
  `scripts/choose_key.py`.
- 143 tests passing.
- Voice mystery solved: Adhi's ASUS has a Copilot key where Right Ctrl used
  to be. It sends Windows + Shift + F23, so Jarvis never saw Right Ctrl. The
  picker now refuses F23 with an explanation (Windows would open Copilot on
  every press) and suggests Right Alt; setup asks about "Ctrl to the right of
  the space bar (not Copilot)".
- 2026-10-21 morning: **first spoken conversation works on the laptop**,
  with Right Alt as the push-to-talk key (saved in settings.local.toml).
  Still to do for M0: the latency table, Sinhala by voice, barge-in, and
  recording round 1.
