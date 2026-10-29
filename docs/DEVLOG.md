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

## 2026-10-21: First latency numbers, and why they were slow

First spoken session on the laptop, 3 turns (`session-20261021-041323`).
Times are from letting go of the push-to-talk key; the goal (D8) is the
first sound of the real reply in under 1.5 s.

| Stage | p50 ms | p95 ms |
|---|---|---|
| Whisper done (`stt_done`) | 885 | 2318 |
| LLM first word, Groq gpt-oss-120b (`llm_first_token`, own time) | 588 | 635 |
| First word arrives (`first_token`) | 1520 | 2864 |
| Filler starts (`filler`) | 1585 | 3023 |
| First sentence synthesized (`first_tts`) | 1942 | 4300 |
| **Real reply starts (`first_audio`)** | **3221** | **4593** |

What the timeline shows (p50):

1. Whisper took 0.9 s, three times its smoke-test time; p95 2.3 s, most
   likely the cold first turn.
2. The LLM answered in 0.6 s, so the first word was here at 1.5 s.
3. The filler timer (0.7 s after the LLM request) fired at 1.6 s, just
   *after* the reply text had started arriving.
4. The first sentence was ready at 1.9 s, but it had to queue behind the
   filler, so the real voice started only at 3.2 s. **The filler cost
   about 1.3 s.**

Fixes:

- **Filler only when the LLM is slow:** it now waits for the first word of
  text, not the first sound. If any text has arrived after 0.7 s, there's no
  filler (D17 updated). New test: a fast LLM with a slow voice gets no
  filler (fails on the old code).
- **Whisper warm-up runs a real pass** at start-up (language detection,
  plus one transcription with and one without the voice-activity filter),
  not just loading. In the container the voice-activity filter alone took
  240 ms on its first call and 11 ms after.
- **Turn-by-turn table** at the end of `python -m jarvis.telemetry`: for each
  request, the length of speech, language heard (and whether Whisper ran
  twice), Whisper time, LLM time and provider, first-sentence synthesis time
  and length, filler and first audio. It works on old logs too, so the next
  step is to see why Whisper took 0.9 s.

Expected after the fixes: about 0.9 + 0.6 + 0.4 = 1.9 s at p50, and 1.5 s if
Whisper gets back to its smoke-test speed. To measure next.

Turn-by-turn table for the same session (after `git pull`, on the old log):

| # | Said | Heard | Whisper | LLM | 1st sentence | Filler | First audio |
|---|---|---|---|---|---|---|---|
| 1 | 7.3 s | en 0.88 | 2317 | 546 | 1409 (87 chars) | 3023 | 4593 |
| 2 | 30.0 s | en 0.68 | 884 | 635 | 411 (16 chars) | 1585 | 3186 |
| 3 | 30.0 s | en 0.85 | 728 | 588 | 350 (12 chars) | 1436 | 3221 |

- Turn 1 is the cold start: Whisper 2.3 s (the new warm-up should fix it),
  and a long first sentence: 87 characters took Kokoro 1.4 s. From the three
  turns, Kokoro on the CPU needs about 0.2 s plus 14 ms per character. Groq
  sends text in big bursts, so the whole first sentence was already there and
  the chunker never used the comma rule. Fix: a first sentence over 60
  characters (`first_chunk_max_chars`) is now cut at its first comma.
- Turns 2 and 3 are exactly 30.0 s, the recording limit. Either the key was
  held that long or a key release was missed: to check with Adhi. Jarvis now
  says when a recording reaches the limit. Whisper took only 0.7-0.9 s for
  30 s of audio because the voice-activity filter removed the silence.
- In every turn the filler started 0.06-0.16 s *after* the first text, so
  with the new rule none of these three would have had a filler.

## 2026-10-21: First Sinhala by voice: Whisper small can't write it

Second voice session, in English mode:

1. Said "I prefer to talk in Sinhala". Whisper wrote "I prefer to now in
   Singhala", so the switch rule didn't fire (no "talk", and "Singhala"
   wasn't a known spelling). The LLM replied in Sinhala anyway.
2. Spoke Sinhala. Whisper was sure it was Sinhala (p = 0.954), re-transcribed
   in Sinhala, and wrote repeated nonsense syllables
   ("වකප ලල් පපිනේයියයියය ..."). Jarvis asked him to rephrase, in English.
3. Spoke Sinhala again: p = 0.987, and the text was "Р說 D ." (Cyrillic and
   Chinese).

So language *detection* works; Sinhala *transcription* with `small` doesn't.
This is the gap the roadmap expected (docs/LANGUAGES.md), now seen first-hand.

Fixes today:

- **Nonsense check** (`voice/clarity.py`): before the LLM sees a transcript,
  Jarvis checks for repetition (zlib compression ratio above 2.4, Whisper's
  own limit; the first transcript scores 2.45 and real Sinhala sentences
  1.4-1.7), letters from the wrong alphabet (more than 20% outside the
  language's script plus Latin; the second scores 0.67), and Whisper's
  average log-probability (below -1.0). If any fails, Jarvis says "Sorry,
  sir, I couldn't make that out" in the current language. The log
  probability and compression ratio are now logged for every utterance, so
  the thresholds can be tuned on real data.
- "singhala" and "singala" added as names for Sinhala, and "prefer" as a
  command word, so "I prefer to talk in Sinhala" switches even when misheard.

Plan: train our own Sinhala model (IMPLEMENTATION_PLAN.md, section R):
baselines on Adhi's round-1 recordings first, then fine-tune whisper-small on
OpenSLR 52 with free Kaggle GPUs.

## 2026-10-21: Second latency session (after the filler and warm-up fixes)

`session-20261021-100114`: 12 turns (8 English voice, 2 Sinhala voice, 2 typed).

| | Before (041323) | Now (100114) |
|---|---|---|
| First audio, English voice turns | 3.2-4.6 s | 2.7-3.1 s |
| First audio, typed turns | - | 2.3 s |
| Whisper, English | 0.7-2.3 s | 0.39-0.79 s (no cold first turn) |
| LLM first word (Groq gpt-oss-120b) | 0.55-0.64 s | 0.78-1.42 s (p50 1.05 s) |
| First sentence voice (Kokoro, CPU) | 0.35-1.41 s | 0.37-1.39 s |

- The warm-up worked: the first turn's Whisper was 523 ms instead of 2317.
  The warm-up itself takes 8.2 s at start-up.
- The LLM is now the biggest step, and nearly twice as slow as this
  morning. Unknown yet whether that's Groq's load at this hour, the longer
  conversation, or gpt-oss "thinking" before it answers. The LLM log now
  records the time to the server's first chunk, the reasoning characters
  before the first word, and the prompt size; `scripts/llm_speed.py`
  compares models on Jarvis's real prompt.
- Because the LLM took more than 0.7 s, the filler fired in every turn. In
  turns 6-8 the longer fillers ("Right, one sec.") were still playing when
  the reply was ready, holding it back by about 0.6-0.9 s. Fix: fillers
  longer than 700 ms (`filler_max_ms`) are skipped, English fillers are now
  mostly short ("Mm.", "Hmm.", "Right."), and the turn table shows a
  "held back" column.
- Sinhala voice turns: Whisper took 6.2-6.6 s (it retries up to six times
  at higher temperatures when the output looks wrong) and still wrote
  nonsense. This goes away only with a real Sinhala model (section R).
- Several recordings were long (12-30 s), one again exactly 30.0 s: to
  check with Adhi whether the key release is being missed.

## 2026-10-21: Why the LLM takes a second: the connection, not the thinking

`scripts/llm_speed.py`, Jarvis's real prompt (3,799 characters), 6 requests
per model, laptop in Sri Lanka:

| Model | Server's first chunk | Thinking | First word |
|---|---|---|---|
| Groq gpt-oss-120b | 795 ms | 43 chars | 976 ms |
| Groq gpt-oss-20b | 795 ms | 28 chars | 849 ms |
| Gemini flash-latest | 3260 ms | 0 | 3260 ms |
| OpenRouter free | 1164 ms | 728 chars | 3664 ms |
| Ollama qwen3:4b | not running | | |

- Thinking costs little (28-43 characters, about 0.05-0.2 s). Most of the
  wait is before Groq sends anything at all.
- Cause found in the code: the HTTP library closes an idle connection after
  5 s, and spoken turns are always further apart than that, so every
  question first opened a new secure connection to Groq.
- Fix: connections stay open for 120 s (`[llm] keepalive_s`), and Jarvis
  opens one while the push-to-talk key is held (`prewarm`), so the question
  goes out on an open line. Checked against a local test server: after a
  6 s pause the request reused the warmed connection with the new setting
  and opened a new one with the old.
- The script's errors at the end ("aclose(): asynchronous generator is
  already running") came from how it cut replies short; it now cancels the
  way barge-in does, and measures each model on a new and an open line.
- Gemini and OpenRouter stay as fallbacks only; the order is right.

Measured after the fix (`llm_speed.py`, new connection vs open connection):

| Model | New line | Open line |
|---|---|---|
| Groq gpt-oss-120b | 828 ms | 608 ms |
| Groq gpt-oss-20b | 871 ms | 646 ms |

So the open connection saves about 0.22 s per question; the remaining 0.6 s
is Groq's own time from Sri Lanka. Side effect of testing: Gemini's free
daily quota ran out (429) and gpt-oss-20b hit its per-minute limit once, so
the speed script shouldn't be run many times a day.

Estimated English voice turn now: Whisper about 0.5 s + LLM 0.6 s + first
sentence voice 0.6-0.7 s, about 1.8 s. The voice is the biggest step left:
`scripts/try_tts_gpu.cmd` times Kokoro on the CPU, the int8 model, and the
GPU through DirectML (and CUDA, optional), each GPU build in its own test
environment so Jarvis isn't changed until one clearly wins.

Kokoro on the laptop (`scripts/try_tts_gpu.cmd`, bm_lewis, median of 5):

| Sentence | CPU full | CPU int8 | DirectML |
|---|---|---|---|
| 9 chars | 302 ms | 290 ms | failed |
| 42 chars | 751 ms | 718 ms | |
| 50 chars | 743 ms | 715 ms | |
| 72 chars | 1257 ms | 1218 ms | |

- CPU: about 0.2 s plus 14 ms per character (real-time factor 0.26-0.37).
- int8: only about 4% faster, so not worth the lower quality.
- DirectML: fails on Kokoro's `ConvTranspose` layer ("The parameter is
  incorrect"), a DirectML limitation. Dropped.
- Next: CUDA, pinned to onnxruntime-gpu 1.26.0, the newest build for
  CUDA 12; from 1.27 it needs CUDA 13, which could clash with the CUDA 12
  libraries Whisper (CTranslate2) uses in the same process.
- CUDA, first try: onnxruntime 1.26 found the GPU, then cuDNN failed with
  "Could not locate cudnn_engines_tensor_ir64_9.dll" and onnxruntime fell
  back to the CPU (so that table was CPU numbers). The DLL is in the
  nvidia-cudnn-cu12 9.27 wheel (`nvidia/cudnn/bin`, checked from the
  wheel's file list): cuDNN loads its helpers by name when it first runs,
  and that folder wasn't searchable. Fix: `gpu.nvidia_dll_dirs()` now adds
  every `nvidia/<library>/bin` folder (onnxruntime also needs cufft and
  curand), and the voice test uses it and warns when a GPU run fell back
  to the CPU. Loading took 68 s the first time (Windows scanning the new
  DLLs).
- CUDA, second try (folders fixed): **4x faster**.

  | Sentence | CPU | CUDA |
  |---|---|---|
  | 9 chars | 307 ms | 80 ms |
  | 42 chars | 770 ms | 179 ms |
  | 50 chars | 744 ms | 173 ms |
  | 72 chars | 1257 ms | 262 ms |

  Built in: `[tts] device = "auto"` runs Kokoro on CUDA when there's an
  NVIDIA card; on 64-bit Windows onnxruntime-gpu 1.26.0 replaces onnxruntime
  (uv override; the CUDA extras go in the `gpu` extra), Linux keeps the CPU
  build. Jarvis prints where the voice runs at start-up. `scripts/update.cmd`
  pulls and re-installs with the extras already chosen at setup.
  Expected English voice turn: about 0.5 + 0.6 + 0.2 = 1.3 s, under the 1.5 s
  target. To measure.

## 2026-10-21: Sinhala test sentences drafted

35 test sentences in `eval/sentences_si.txt`: the 20 original hints plus 15
everyday requests (study help, files, media, reminders), in spoken Sinhala,
English loanwords in Sinhala script, no numbers or course codes (Whisper may
write digits where the text has words). Drafted by Claude at Adhi's request;
Adhi checks and edits every line before recording, so the reference text is
what he really says. For the report: say that the sentences were drafted
with AI help and checked by the speaker.

More Sinhala test sentences, at Adhi's request (covering his subjects and the
way he speaks, with many English words in Sinhala letters):
`sentences_si_study.txt` (60: mechanics, thermodynamics, nuclear,
circuits, waves, quantum, environmental physics, pure and applied maths,
statistics and data) and `sentences_si_talk.txt` (34: philosophy, logic,
feelings, everyday life, eight short paragraphs). 129 in all, about 40-50
minutes to record. Written text alone doesn't train the speech model (it
needs audio with text); it is the test set once recorded, and text helps
the intent classifier and a possible language model later.

## 2026-10-21: Jarvis forgot Adhi's name after a restart

Adhi told Jarvis his name, restarted it, and Jarvis asked for it again and
said it had no access to earlier chats. True: only the time of the last
conversation was saved (`presence.json`), and history lived in memory.

Fix, a light memory (`src/jarvis/memory`, `state/memory.json`, on the laptop
only): the name ("my name is ...", "call me ...", "මගේ නම ...", `/name`),
facts ("remember that ...", "... මතක තියාගන්න", `/remember`), and the
recent conversation, which carries on after a restart if it ended within
12 hours (`[memory] continue_hours`). `/memory` shows it, `/forget` clears
it. Only what the user said is saved (D27). The prompt tells the model
exactly what it remembers, and the persona's "can't yet" line was updated.
23 new tests, including the restart case.

## 2026-10-21 evening: memory and the nonsense check on the laptop

- Memory works: after a restart Jarvis answered "Your name is Mr. Adithya".
  The prompt now asks for the name alone, without a title.
- Sinhala by voice, twice: Whisper wrote gibberish (with Arabic and Chinese
  letters mixed in), p 0.59; both were caught as "low confidence" and Jarvis
  asked again in Sinhala. Adhi reworded that line in natural spoken Sinhala.
- "Can we speak in Sinhala?" was heard as "...singular language?", so the LLM
  answered about pronouns. Fixes: Whisper's prompt now lists the language
  names ("Jarvis. Sinhala, English, Tamil."), and "singular" counts as a name
  for Sinhala in a short switch request.
- One English-mode turn ("Jarvis, then we'll have a kill", p 0.17) got past
  the check and the LLM asked to clarify. The telemetry report now shows
  Whisper's confidence per turn, to tune the check on real numbers.
- Typing Sinhala works well (LLM reply plus the Piper Sinhala voice).

## 2026-10-21 evening: first audio under 1.5 s

`session-20261021-175600` (after the open connection and the GPU voice):

| # | | Whisper | LLM | 1st sentence | first audio |
|---|---|---|---|---|---|
| 1 | English voice | 495 | 633 | 200 (25 ch) | **1348** |
| 2 | English voice | 593 | 700 | 198 (27 ch) | 2506 (filler held it 996 ms) |
| 3 | English voice | 514 | 519 | 278 (57 ch) | **1359** |
| 5, 6 | Sinhala voice | 6511, 7234 | | | asked again (confidence -1.16, -1.94) |

- **D8 met for English voice turns: 1.35 s** (it was 3.2 s this morning).
  Voice on the GPU: 0.2 s for the first sentence instead of 0.6-1.1 s.
- Fixes: the filler threshold is now 1.2 s (D17); the player no longer waits
  0.2 s after every piece (also a gap between sentences); Whisper retries
  at most twice (`[stt] temperatures = [0.0, 0.4]`, default was six), since
  the six retries on unreadable Sinhala took 6.5-7 s before Jarvis could say
  it didn't understand.
- Sinhala now speaks as Friday (Kokoro `bf_emma` with eSpeak's Sinhala
  pronunciation), Adhi's choice after listening to five women's voices;
  English stays Jarvis (`bm_lewis`). One Kokoro model serves both.

## 2026-10-21: Friday's pronunciation: a voice-conversion test

Adhi asked for Friday to have native Sinhala pronunciation in Emma's voice.
Fine-tuning Kokoro on Sinhala isn't practical (no easy public training for
a new language, and it needs a GPU and data). Instead, voice conversion:
`scripts/try_friday_voice.cmd` re-voices Piper's dilu (trained on real
Sinhala speech) as Emma with kNN-VC (MIT licence; WavLM features of every
20 ms of speech swapped for the closest frames of Emma's). Emma's
"matching set" is generated by Kokoro: 40 Harvard sentences, 20 longer ones
and her eSpeak Sinhala. It writes three versions to compare: today's
Friday, dilu, and dilu converted to Emma. Torch 2.7.1 (CPU) in a test
environment next to the Jarvis folder; the conversion couldn't be run in
the cloud workspace (the PyTorch download site is blocked there), so it is
first run on the laptop. If it wins, the next question is speed: kNN-VC on
the CPU is for the test only; for live use it needs the GPU.
- First laptop run: Adhi found the converted Friday better than dilu, but a
  mix of Emma and dilu, less rich than Emma. Expected: kNN-VC keeps the
  source's words, rhythm and melody and swaps only the voice colour, frame by
  frame, from a mostly English matching set; and it outputs 16 kHz, against
  Kokoro's 24 kHz. Next: compare topk 2, 4 and 8 (`try_friday_voice.cmd
  again`); if it's still not Emma enough, train an RVC model on Emma's voice
  (a real fine-tune, on the laptop GPU).

## 2026-10-21 night: thousands of Sinhala patterns for the intent classifier

Adhi asked for thousands of Sinhala sentences covering grammar and
combinations. Text alone can't teach Whisper to hear (it needs audio), but
it is exactly what the intent classifier (his trees or boosting idea) needs.
`src/jarvis/intents/` holds the patterns and a generator;
`scripts/make_intent_data.py` writes 4,480 labelled examples (2,716 Sinhala
script, 978 Singlish, 786 English) for 17 intents, each with its intent,
slots (app = chrome, time = tomorrow_morning ...) and the Sinhala verb form
(polite 611, for me 418, casual 395, question 265, formal 47). Grammar
covered: politeness forms, synonyms (ඕපන් කරන්න / අරින්න / විවෘත කරන්න),
"එක" after English words, cases (ලංකාවේ / ලංකාව), word order, wake words
and two-sentence requests. Balanced by sampling round-robin over patterns;
reproducible (seed 21). Training only; the test set is Adhi's real
sentences. Possible extra: some of these sentences as synthetic speech, a
small share of the Whisper training (TRAINING_SINHALA.md).

RVC for Friday is postponed (power cuts); the kNN-VC comparison is ready
(`try_friday_voice.cmd again`).
- Same night, more variety at Adhi's request: 21 new intents (messages to
  family and friends, timetable, screenshots, graphs, Excel and Power BI
  data work, research papers, translation, date, timers, alarms, greetings,
  thanks, questions about Jarvis, computer power, brightness up and down,
  Wi-Fi and similar settings, notes, "remember that", quizzes, web search).
  Now 38 intents and 8,770 examples: 5,496 Sinhala script, 1,755 Singlish,
  1,519 English. Sinhala verb forms: polite 1011, for me 664, casual 605,
  question 427, formal 47. Small classes (greeting 10, thanks 8 in Sinhala)
  need class weights.

- Same night, university study at Adhi's request ("study related Singlish
  is important"): his Kelaniya modules (PMAT infinite series, ODEs, several
  variables, linear algebra, discrete maths; AMAT vector analysis, numerical
  methods, scientific computing, mechanics; PHYS labs, solid state and
  thermodynamics, environmental physics, waves and optics, circuits,
  properties of matter; MAPS HRM) and the IT data science modules (IT3081
  to IT4111). One topic table, `STUDY_TOPICS`, holds 307 topics with an id,
  an area and the Sinhala, Singlish and English names, so all three
  languages stay in step; course codes are subjects ("pmat 21272 exam
  ekata..."). Five new intents: derive_proof, check_answer, write_code,
  debug_code, exam_prep; comparisons ("X saha Y athara wenasa") under
  explain_concept. Study intents get 360 Sinhala, 300 Singlish and 140
  English examples each (`examples_per_intent`). Now 43 intents and 15,432
  examples: 8,276 Sinhala script, 4,677 Singlish (was 1,755), 2,479
  English. Lecture terms are mostly written as the English word in Sinhala
  letters (ෆූරියර් සීරීස් එක), as students say them; A/L terms keep their
  Sinhala names. Adhi to check the Sinhala terms marked in the table.

## 2026-10-21 evening: different models for different kinds of request

Adhi's idea: maths, explanations, deep talk and computer commands each to
their own model, so one model's free limit isn't used up by everything.
Built (D28): `agent/router.py` decides the route (keyword rules in English,
Singlish and Sinhala, plus a formula detector); `[llm.routes]` in
settings.toml gives each route its order of models; new providers
`groq_oss_think` (gpt-oss-120b, medium thinking, for maths), `groq_qwen`
(Groq's free Qwen, for code) and `gemini_lite`. `FallbackLLM` takes the
route, rests a model after a 429 for as long as the provider says
(retry-after, or "try again in 7m12.5s") and skips it meanwhile; two
entries with the same model share the rest. Models at one address share
one connection, so warming up on push-to-talk warms all Groq models.
Replies that start with `<think>` (Qwen, DeepSeek) have the thinking taken
out before anything is spoken; an empty reply falls back to the next model.
The turn table (`python -m jarvis.telemetry`) has a route column.

`scripts/route_check.py` measures the rules on the 15,432 generated
sentences: 71.7% at first, 95.8% after fixing the clashes it showed ("VS
Code" counted as code, "Google Chrome" as a web search, "කොහොමද" as "how
are you"). Generated sentences are easier than real ones; the classifier's
job is to beat this on Adhi's real sentences. 250 tests pass.

- Same evening, first laptop run of the new models (smoke test 20:18):
  first word after (ms) and Sinhala for "Hello, I am Jarvis, your desktop
  assistant":

  | provider | model | first word | Sinhala |
  |---|---|---|---|
  | groq_qwen | qwen/qwen3.8-27b | 579 | wrong name ("මම වප්සරිය"), a letter missing |
  | groq_oss_think | gpt-oss-120b, medium | 956 | clean |
  | groq | gpt-oss-20b | 987 | made-up word (උදව්වන්නෙයි) |
  | groq_oss | gpt-oss-120b, low | 2077 (new connection) | clean |
  | openrouter | free router | 6158 | Hindi letters mixed in (ජार්විස්) |
  | gemini | gemini-flash-latest | 19137 | the most natural |
  | gemini_lite | gemini-flash-lite-latest | timed out (20 s) | - |

  One sentence each, so only a first sign. Changes: Sinhala gets its own
  route order (`[llm.language_routes.si]`, gpt-oss-120b first); a model
  that times out or is overloaded (500-504) now rests two minutes, so a
  slow Gemini doesn't cost 20 s every turn; the smoke test warns when the
  first word takes over 5 s and when a reply mixes in another alphabet.
  Whisper's speed warning (9.5 s for 5 s of noise) is the noise test:
  Whisper keeps inventing text for noise and retries; real turns took
  about 0.5 s. 254 tests pass.
- 20:30, Gemini Flash-Lite alone (`llm_speed.py --only-try`): 2 of 6
  answered, first word after 14.6 s on a new connection and 8.8 s on an open
  one; 4 timed out at 20 s. Groq, from the same laptop, about 1 s. Gemini
  now comes after OpenRouter in the English orders (general, teach, talk);
  it stays first for long documents and before OpenRouter in Sinhala.

## 2026-10-21 night: "Friday" switches, leaked notes dropped, Sinhala speech plan

From Adhi's session: saying "Friday" five times was transcribed fine but
didn't switch (only whole phrases like "talk to Friday" did), and a reply
contained "User wants to talk Friday.", a line of gpt-oss's private
reasoning. Fixes:
- `voice_names` per language (Jarvis, Friday, in both scripts): the name
  alone, with hey/please, or with a talk word ("I need to talk Friday",
  "Friday ekka katha karanna") switches; the day doesn't ("on Friday",
  "Friday's lecture", "by Friday"). A language named still wins
  ("Jarvis, switch to Sinhala"). Saying the current name with a request
  ("Jarvis, I need help") just answers.
- Sinhala typed (or heard) in English mode switches to Friday; a Sinhala
  sentence is spoken in Friday's voice whatever the mode.
- `LeakFilter` (agent/llm.py): sentences starting like reasoning ("User
  wants", "We need to respond") are dropped before they're printed or
  spoken, and logged as `llm_leak_dropped` to see how often and from which
  model; at each sentence start at most about 20 characters wait.

Sinhala speech: the base model hears Sinhala but can't write it; that's the
model, not Jarvis. Two published fine-tunes found on Hugging Face
(whisper-small, about 10,000 clips, CER 15% on 10 clips; whisper-medium,
WER 22%). `scripts/get_sinhala_whisper.py` downloads one, converts it to
CTranslate2 and compares it with today's model on test sentences read by
the dilu voice (stage 0 in TRAINING_SINHALA.md). Adhi's own recordings:
`make_intent_data.py --reading-list 300` writes 300 training sentences
(none from the test set) and `record_eval_set.py` now resumes after a stop
or power cut. 279 tests pass.

## 2026-10-24: review fixes done; Bing and YouTube by voice

Codex's review (21 Oct) checked against the code; groups 1 and 2 of
docs/REVIEW_FIXES.md are built, with tests that fail on the old code.
- One turn at a time: each request takes its cancel token when it starts and
  waits its turn (asyncio lock, request order). The kill switch or a new
  push-to-talk during speech recognition stops the question before the
  model; a reply stopped halfway isn't saved; mute silences the rest of a
  reply; the audio player counts stops, so none is lost between sentences;
  a provider dropping mid-reply no longer crashes typed mode.
- Routes always end with the general order, so any key works for any
  request; API keys are read only by Jarvis and the provider scripts;
  .env.* is ignored; at most 50 remembered facts, quoted as information;
  the microphone is closed on exit; audio device 0 works; other sample rates
  are resampled to 16 kHz.
- After the laptop's CUDA crash on 22 Oct ("Memory allocation failure",
  error 999): Kokoro uses lighter CUDA settings (heuristic convolution
  search, no maximum workspace); if the GPU still fails, the voice rebuilds
  on the CPU and Whisper moves to the CPU too. Start-up prints free
  graphics memory and warns under 2 GB.

First tools (`src/jarvis/tools/web.py`), decided by fixed rules before the
model, only on bing.com and youtube.com: "open Bing" (Edge) then the next
sentence is the search; "search Bing for X" / "X bing eke hoyanna" / "X
බිං එකේ හොයන්න"; "open YouTube", titles of the top 3 read aloud (YouTube
Data API, YOUTUBE_API_KEY; without it the results page), "play the second
one", "stop the video" (the media key; then "anything else?"), "resume",
"go back" (Jarvis's own page list). One follow-up question at a time, 60 s,
"cancel"; the kill switch clears it. New intents pause_media, resume_media,
go_back (46 intents, 15,630 sentences; keyword routing 95.1%). 332 tests.

## 2026-10-24: plan for making Jarvis feel human

docs/HUMANLIKE_PLAN.md (Proposed). Starts from the laptop test, where "Can
you open YouTube?" reached the model and it said it couldn't. Understanding
in three layers: the fixed rules, then Adhi's intent classifier (act at 70%,
ask "A or B?" between 40% and 70%), then the model with the web tools as
function calls, all ending at the same tool code and the M3 gate. RAG in four
places (corrected examples, memory, lecture notes, web pages) with one
multilingual-e5-small encoder that the classifier's level 2 shares. Codex's
suggestions placed by stage (captions, orb states, wake, clap, gestures,
virtual mouse last). Stages H1-H6, each with measures; H1 needs no training:
tool calling, spoken-style Sinhala for Friday, "I heard X, did you mean Y?",
and a messy-phrasing test set of about 150 real requests.

## 2026-10-24: what a double clap and an open palm mean; how to build them

D29: a double clap wakes Jarvis when it's asleep, means "listen now" when
it's awake and quiet, and is ignored while it speaks; it never sleeps, quits,
cancels or confirms. An open palm, right hand only, held 0.5 s, stops Jarvis
speaking, or plays or pauses a video Jarvis opened; the hand must drop for
0.5 s before the next palm counts. IMPLEMENTATION_PLAN.md gains "The double
clap, step by step" (M6; numpy only, no model; YAMNet as an optional check)
and "Palm to pause, step by step" (M8, can start now; MediaPipe's gesture
recognizer, no training). MediaPipe 1.x has only the Tasks API and brings
opencv-contrib-python, so the vision extra no longer lists opencv-python
(both install the same cv2 folder); update.cmd reinstalls cv2 if removing
the old package broke it. download_models.py also fetches
gesture_recognizer.task.


Checked against CODEX_IMPROVEMENT_SUGGESTIONS.md the same day: the clap and
palm steps now also name Codex's parts (LifecycleController, CameraSource,
HandTracker, GestureRouter), show the gesture considered apart from the one
accepted, reset a hold when the hand is lost, say once when the microphone
or camera isn't available, and carry Codex's acceptance criteria as "done
when". In virtual-mouse mode (later) the palm freezes the pointer. One
difference from Codex's order, with the reason written down: palm to pause
may start before the window.

`scripts/gesture_preview.py` (step 1 of palm to pause): the camera as a
mirror, both hands drawn, hand and gesture with scores, "holding 0.3 of
0.5 s" then "accepted", frame rate and time per frame, and a summary to
paste. Checked here with a fake camera and recognizer (two palms with a
0.7 s gap give two events; one held palm gives one; the left hand never
counts; --swap-hands swaps them); the real camera test is on the laptop.


First laptop run of the preview (24 Oct): it works on the laptop camera, and
right palms are recognised as the right hand (no swap needed). Six palms
were accepted in about 13 minutes, all with Open_Palm scores of 0.71-0.76,
just over the 0.7 threshold, so real palms may be missed. The summary now
shows the spread of open-palm scores to choose the threshold from data.

The preview now records and checks a second way: P / N / space record your
chosen hand's 21 points (and MediaPipe's guess) as "palm" or "not palm" rows
in data/gestures/ (gitignored, numbers only); a "Points check" line counts
the fingers that are out and says whether the palm or the back of the hand
faces the camera; the summary counts where MediaPipe and the points check
agree. Checked here with fake hands (an open right palm: 5 out, facing; the
back of the hand: not facing; a fist: 0 out; rows written with 136 columns).
IMPLEMENTATION_PLAN.md M8 lists the four ways to make the palm more reliable.

Laptop, second run (24 Oct, --min-score 0.6, 320 s): 15 fps, MediaPipe
16 ms p50 / 47 ms p95 per frame; 17 palms accepted, scores 0.61-0.74; the
right hand's open-palm scores: low 10% 0.53, middle 0.63, high 10% 0.74, a
third under 0.6, so MediaPipe is unsure of this hand and camera. The points
check never agreed with MediaPipe (both 0, only MediaPipe 848, only points
253), which suggests the facing check is the wrong way round on this camera.
Recorded 1,041 palm and 1,125 not-palm rows. New `scripts/palm_report.py`
shows the cause and the trade-off for each limit.

palm_report on that recording: MediaPipe said Open_Palm in 40% of palm rows
and 30% of not-palm rows, and all five fingers were out in 43% of not-palm
rows. The not-palm recording held open hands, because the instructions
listed waving and a relaxed hand (Claude's mistake), so the per-frame table
can't separate them. With the current sign only 22% of real palms counted as
facing the camera, so the facing check is the wrong way round here (or the
hand labels are swapped; a 30-second check decides which). The preview now
records W = wave separately, P and N have clearer instructions (N: no open
hands), and the report replays the recording through the 0.5 s hold.

Third laptop recording (24 Oct): 6,055 palm and 868 wave rows (no not-palm
rows this time). Facing again reversed (17% of palms "facing"), so
`[gestures] facing_sign = -1` in settings.toml. Through the hold, waving was
accepted 6 times at a 0.5 limit and 3 at 0.6 in about 1.4 minutes, because
the hold checked only that the hand stayed open. New stillness check: the
palm's middle must stay within 0.35 of its size during the hold, or the half
second starts again (a pretend wave of +-60 px: 0 accepted; still palms: all
accepted). `[gestures]` in settings.toml now holds hand, min_score 0.6,
max_move and facing_sign, used by the preview and the report.

## 2026-10-25: MediaPipe swapped the hands; the preview's text doubled

A laptop screenshot showed the left hand labelled "Right 0.99": the
whiteboard writing behind Adhi was mirrored (as intended for the preview),
and in a mirror a left palm has its thumb towards the face, as in the
picture. So MediaPipe's Gesture Recognizer expects the unmirrored picture,
and the preview had been flipping it first: every "right hand" result and
recording on 24 Oct was the left hand, and facing_sign = -1 only made up for
the swap. Now MediaPipe gets the camera's own frame, only the shown picture
is mirrored, landmarks are mirrored to match (x -> 1 - x, world x -> -x),
and facing_sign is back to 1. palm_report notes that 24 Oct recordings have
the hands swapped. The status text was doubled because OpenCV 5 draws thick
text (the black outline) with a wider font than thin text; it's now drawn
once on a darkened band.

First recording with the hands right (25 Oct, right hand): MediaPipe's
open-palm score is higher than the left hand's (low 10% 0.65, middle 0.69);
not-palm frames: 0% counted as a palm at any limit from 0.40, and 0 false
palms through the hold. Palm rows were only half open palms (34% fist, the
hand lowering between palms). Through the hold, limits 0.50-0.60 with the
stillness check gave 15 palms; waving still got 3 through in about 80 s of
continuous waving. The report gains a table of stillness (max_move) and hold
length against palms kept and waves let through, and lists each accepted
palm with what the hand did before it, to spot a palm counted twice.

Same recording, sections 5-6: all 15 accepted palms followed a closed hand,
so none was counted twice (about 15 palms shown, all caught). The 3 waves
accepted stayed at 3 even with max_move 0.10 and a 0.7 s hold: the palm's
middle was nearly still for over half a second, so these were a still
"hello" palm or a finger wave, not a swinging wave. The report now also tries
"MediaPipe and the points check" (bending fingers break the points check)
and says when, after pressing W, each wave was accepted.

Palm rule chosen (25 Oct, one session, right hand, room light): MediaPipe
Open_Palm >= 0.6, held 0.5 s, the palm's middle within 0.35 of its size.
15 of 15 palms caught, none counted twice; 0 false palms in about 70 s with
no open hand; 3 in about 70 s of waving, at 45, 57 and 67 s after W, with all
five fingers out and the palm still for over 0.7 s (pauses with the hand up),
so no shape or stillness rule can tell them from a "stop" palm. Adding the
points check (AND) changed nothing, so the rule stays MediaPipe-only and the
points check stays as a feature for the classifier. The remaining case is
harmless under D29: the palm acts only while Jarvis speaks or a video it
opened is playing, and then means "hold on". Still to measure: other light
and distances, and false palms per hour of normal work (Codex "done when").

Palm to pause, step 2 (25 Oct): `src/jarvis/perception/gestures.py`
(PalmHold, HandSeen, PalmSettings, PalmTrigger), in the perception package
already set aside for Phase 3, with 17 tests in tests/test_gestures.py. The
preview and the report now import the same PalmHold, so all three use one
rule. Plan paths changed from sensors/ to perception/.

Palm to pause, steps 3-4 (25 Oct): `perception/camera.py` runs the camera
in a background thread at about 15 pictures a second, gives MediaPipe the
unmirrored picture (live-stream mode), turns each result into HandSeen, asks
PalmTrigger, and publishes GestureEvent("open_palm"); frames are dropped at
once. A camera that won't open, a missing or broken model, or no MediaPipe
gives a plain message and Jarvis carries on. In the app, an accepted palm
while Jarvis is thinking or speaking stops it like barge-in (the reply isn't
saved, Jarvis stays ready); with a video Jarvis opened on screen, it presses
play/pause; otherwise nothing. Off by default: `[gestures] enabled = true`
or `/camera on`; `/camera off`; `/status` shows the camera. 12 tests with a
pretend camera and pretend MediaPipe (374 in all); the real camera test is
on the laptop.

Palm to pause on the laptop (25 Oct, /camera on): a right palm while Jarvis
was answering stopped it ("[palm] stopped."). The same session showed web
tool gaps: "Open the YouTube." (with "the") and "Open YouTube. Then play the
first one." (two requests at once) missed the fixed rules, and the model,
told to give the words that work, replied with only "open YouTube"; "play the
video" after pausing a video Adhi opened himself was refused. Fixed: "the"
and "website/app/home page" are allowed; two requests in one breath are
split at a sentence end or "and"/"then" when the first part is a command on
its own ("search Bing for cats and dogs" stays one search); "play the first
one" with nothing listed yet asks for a topic; an answer like "then play
lofi music" searches "lofi music"; "play/resume the video" works without a
page of Jarvis's (a bare "continue" doesn't); and the model now says in a
sentence that it didn't catch a command instead of only the words. 13 new
tests, which fail on the old code. Whisper heard "Fourier" as "Furio": a
vocabulary hint for study words is a candidate fix.

Second laptop run (25 Oct): "Open YouTube and play Luffy Music" (Whisper's
"lofi") listed three videos, but Whisper then heard "play the first one" as
"Play Festival.", the list was dropped as "the user moved on", and the model
went on to invent three video titles and to answer "play the first one" with
just those words. Now, while Jarvis waits for a choice: two or more words
from a title pick that video ("Luffy edit One Piece" -> the Luffy edit, not
"one" = first), then first/second/third, then one title word; an answer that
sounds like a choice but isn't ("play festival") gets "Sorry, which one?"
once, keeping the list. While a YouTube page of Jarvis's is open, "play X"
searches YouTube for X. The character sheet now says the model can't search,
open or play anything and must never invent results, titles or links. These
rules will keep missing some wordings: the lasting fix is giving the model
the web tools to call (HUMANLIKE_PLAN.md, H1 step 1).

## 2026-10-25: the model understands YouTube and Bing requests in any words

Fixed rules only catch wordings someone thought of, and each laptop test
found new ones. Now, when the rules miss a request that may be about the
browser or media (or Jarvis is waiting for an answer, or a video list is on
screen), the same streaming call to the model carries the actions as tools
(open_site, search_youtube, search_bing, play_video, pause_media,
resume_media, go_back) and a plain description of the screen: the page, the
videos Jarvis read out (as data) and the question Jarvis asked. The model
either answers in words, streamed as before (no added delay), or calls a
tool; WebTools.call checks every argument (sites, numbers, query length) and
does it, so the model can't do more than the voice commands can. An unknown
tool or bad arguments do nothing ("Sorry, sir, I couldn't do that one").
Ordinary chat gets no tools. While Jarvis waits for a choice, the rules still
answer what they can (first/second/third, title words); anything else ("the
anime one") goes to the model, which sees the list. A bare "one" means "the
first" only when nothing else was said. `[tools] model_tools = true` in
settings. 11 tests (406 in all). The News map plan gains Adhi's themes:
technology, politics, military and conflict, space.

Understanding, measured (25 Oct): `eval/commands.jsonl`, 60 natural ways to
ask (33 English, 16 Singlish, 11 Sinhala): open a site, search YouTube or
Bing, choose from a list ("the anime one", "anthima eka danna"), pause, play
again, go back, and 10 that need no action. `scripts/command_check.py` runs
each through the real pipeline (fixed rules, then the model with tools, with
a pretend browser) and reports accuracy per language and per request.
Fixed rules alone: 19/60 (32%) at first, 9 of the 50 commands, and three
were wrong actions ("youtube ekata yanna" searched for "ekata yanna"), worse
than none because the model never saw them; fixed (ekata/eken/එකට are not
search words). The model now gets the tools on every request by default
(`model_tools = "always"`): a list of trigger words was itself a rule ("I
want to see that Luffy clip" has none). With the model, an answer to "Paused.
Anything else?" ("okay, carry on") goes to the model too, instead of being
searched. The full run needs the API keys, so it runs on the laptop.

Fixed rules, widened by word families (25 Oct). A held-out set
(`eval/commands_heldout.jsonl`, 48 new phrasings) was written and committed
before any tuning, so its score is honest. Rules only, before -> after:
first set 18/60 -> 55/60 (92%); held-out 19/48 -> 47/48 (98%); wrong actions
0 throughout. Added: ways to open (pull/bring/fire up, take me to, get ...
going, wanna use; Singlish on/denna/danna/arinnako, "ekata yanna"; Sinhala
"එකට යන්න", "දාන්න"); ways to ask for media without saying YouTube ("put on
X", "I feel like listening to X", "find a video explaining X", "X youtube
eken danna", "X gana video ekak pennanna", "X sindu tikak danna", "X ගැන
වීඩියෝ එකක් පෙන්නන්න"); web searches ("google X", "search the web for X",
"X internet eke balanna", "අන්තර්ජාලයේ X හොයන්න"); last/middle and more
ordinal spellings; plural title words; Singlish case words dropped from the
end of a query. Short phrases ("stop it", "hold on", "carry on", "take me
back", "nawaththanna", "ආයේ දාන්න") act only in front of Jarvis's own video,
so "can you stop talking so fast" and "I want to see my notes" stay with the
model. The misses left are meant for the model ("the anime one", "I'm in the
mood for some jazz", "shh, quiet for a moment").

The model's tool note now lists the Singlish and Sinhala command words (danna
put on, nawaththanna pause, anthima last, gana about, ...) and says to ask
one short question when it isn't clear which video is meant. The real-model
run of command_check.py (both sets) is the next measurement, on the laptop.

Understanding with the real model, on the laptop (25 Oct, 16:44, Groq
gpt-oss and Gemini, both sets, rules + model with tools):
- First set 59/60 (98%): English 32/33, Singlish 16/16, Sinhala 11/11.
- Held-out set 48/48 (100%): English 27/27, Singlish 13/13, Sinhala 8/8.
- No action anyone didn't ask for (0 of 19 "just answer" lines acted).
- The model handled every line the rules left it: "the anime one" and
  "anime eka danna" -> video 3 (the One Piece edit), "I want to see that
  Luffy clip" and "play the baka song with the Luffy edit" -> a YouTube
  search, "I'm in the mood for some jazz" -> a search for jazz music.
- The one miss: "shh, quiet for a moment" with a video playing; the model
  took it as "Jarvis, be quiet". Now a rule: "shh", "quiet", "hush" pause
  Jarvis's video while it plays (and mean nothing otherwise).
- Time: most model calls took 1-3 s for the whole reply, but six took
  12-25 s, falling back from gpt-oss-20b to gpt-oss-120b or Gemini
  Flash-Lite; the test sends requests faster than speech, so Groq's free
  per-minute limits are a likely cause. command_check now saves Jarvis's
  log of each model call (fallbacks and their reasons) to find out.

Your intent model, ready to train (25 Oct). `docs/TRAINING_INTENT.md` is the
guide: level 1 (character pieces + logistic regression) and level 2
(multilingual-e5-small vectors + logistic regression), written and run by
you. Ready around it:
- `scripts/make_intent_sets.py`: train (13,577 generated sentences), dev
  (2,053 from templates train never saw, so a template can't be learned by
  heart) and a real test (the 108 phrasings of eval/commands*.jsonl, with
  the intents that count as right). Your own sentences go in
  `data/intent/mine.jsonl` and join train only; a copy of a real test line
  is left out and named.
- `scripts/intent_eval.py`: dev accuracy and macro-F1 per language, the
  real test, how many lines it would decide alone at limits 0.5-0.9 and how
  often it's right then, speed, confusions and every real mistake.
- In Jarvis: when `models/intent/intent.joblib` exists, `[intents]` in
  settings.toml puts it in front of the keyword rules (IntentRouter): it
  picks the route when at least `min_confidence` sure, the rules decide
  otherwise; a missing or broken file changes nothing. Tests in
  tests/test_intent_model.py.
- A trial run of the guide's level-1 code: trained in 11 s, about 1 ms a
  sentence; dev 77.3% (macro-F1 0.716), real test 55.7% (English 20/48,
  Singlish 16/24, Sinhala 13/16); at 0.6 it decides 10 of 88 real lines
  alone, all right. The gap is the lesson: the generated English says
  "open YouTube", real English says "pull up YouTube". Step 4 of the guide
  (your own sentences) is how it closes. Level 2 couldn't run here (the
  encoder can't be downloaded in the cloud workspace); its first run is on
  the laptop.

Adhi's first own data (25 Oct): 192 sentences (64 per language) in 11 intents
of his own, plus a generator for 10,500 more. Eight of his 11 names aren't
among the 46 (device_control, research_query, science_explanation,
psychology_discussion, news_update, ethics_philosophy, casual_chat,
general_knowledge), so they were mapped onto the 46, line by line where one
name covered several (device_control -> volume_up, brightness_down,
toggle_setting, system_power, ...), plus a new intent of his, `chat` (talk,
opinions, discussions; routed "general"), since the 46 have none. 188 kept
for data/intent/mine.jsonl; 4 left out: a near-copy of the real test line
"pull up YouTube", and battery, RAM and recycle-bin requests Jarvis has no
intent for. One Gujarati word in a Singlish line fixed. make_intent_sets.py
now accepts new intent names and lists them. The generator isn't used yet:
its labels clash with the 46, its 10,500 lines come from about 360 core phrases,
and it has mixed-script slips (Devanagari, Gujarati).

Intent model, round 3 (28 Oct). First a new held-out set,
eval/intents_heldout.jsonl: 49 new phrasings (19 English, 16 Singlish, 14
Sinhala) over opening, playing, searching, pausing, going back, study, code,
device, feelings, thanks and chat, committed before any data change (none a
copy of training, mine.jsonl or the old tests; Claude wrote it, so it is
less blind than one Adhi writes). Then the data at the source
(intents/patterns.py): the open verbs from Adhi's generator (pull up, fire
up, bring up, switch to, run, open up) and his apps, more ways to ask for
music and to search the web or YouTube, a few more pause / resume / back
phrasings, and 110 English sentences per intent instead of 70. Level 1,
with mine.jsonl, before -> after:
- real test 59.9% -> 62.0%: old commands 25/48 -> 28/48, old held-out
  24/40 -> 23/40, new held-out 33/49 -> 34/49
- right when it decides alone: at 0.6, 19/19 -> 21/22 (the miss: "can you
  stop talking so fast" -> stop 0.64); at 0.7, 16/16 -> 17/17
- dev isn't comparable (a new dev split, since the templates changed)
The honest set moved by one line. Character pieces don't carry over to
verbs the data never had ("get me onto", "pennanna", "hold the video"):
level 1 is near its limit on new wordings. Next levers: level 2 (sentence
meaning) and Adhi's own phrasings.

## 2026-10-28: nine days left; Windows blocked Python; the safety gate

Adhi has 9 days to submit. The working plan: finish a smaller Jarvis
completely (laptop running, intent model, safe tools with the gate and
confirm box, the empathy learner, an emotion baseline, study level 1,
Sinhala with a ready-made Whisper and a small window, one evaluation run,
report and demo); phone calls, wake word and clap, the news map, the other
skills, multi-step tasks and training our own Sinhala model become future
work.

Day 1, the laptop: `uv run jarvis` failed with "uv trampoline failed to
spawn Python child process ... os error 4551" (Windows App Control: the
uv-installed Python, python-build-standalone 3.12.12, has no known
publisher). Protection history was empty; Smart App Control is now Off
(Defender, firewall and SmartScreen stay on; turning it back on needs a
Windows reset until Microsoft's fix for the greyed-out switch arrives).
Next: `uv run python --version`, then the smoke test.

Started early, while waiting (Phase 2 build step 1, Claude drafts):
`tools/registry.py` (Tool, Tier, Result, Registry: the model sees every
tool except "never" ones) and `tools/gate.py` (registered tools only,
arguments checked against the tool's schema with unknown keys refused,
every path resolved, links included, and kept inside the allowed folders;
"ask first" runs only after a click, and "do and log" asks too when the turn
holds outside text or comes from the phone; the confirm box's words come
from the tool's code, never from the model; the kill switch; verify();
done / claimed / unconfirmed told apart; a crashing tool is a failure, not
a crash; logs/actions-YYYYMMDD.jsonl; "undo that"). 23 tests with made-up
tools, nothing touches the PC.

Day 1 done (28 Oct, 08:10): with Smart App Control off, `uv run python
--version` works and the smoke test passes (RTX 4050 visible; Whisper small
264 ms for 6 s of audio; seven providers answer and call tools, groq
gpt-oss-20b first token 491 ms; English, Sinhala and Tamil voices). Warnings
only for things not done during the test (no speech, no hand held up), plus
one Gemini timeout (gemini_lite and the rest answered) and Ollama not running.

Day 3, started the same morning: the first PC tools, all through the gate.
- `tools/desktop.py`: open_app (a fixed list of 12 programs; verified by
  the process appearing), change_volume (the volume keys; checked with pycaw
  when installed, otherwise reported as done-not-measured), take_screenshot
  (mss; the file must exist), set_timer (announced out loud when it rings;
  "undo that" cancels it), create_note (do and log; undo moves it to
  Jarvis's recycle folder), delete_file (ask first: moves a file from
  Jarvis's folder to its recycle folder, only after a click; undo puts it
  back), undo_last_action. Files live in [tools] jarvis_folder
  (~/Documents/Jarvis): notes/, screenshots/, recycle/. Nothing is ever
  deleted for good.
- `tools/confirm.py`: the confirm box (tkinter, always on top, Cancel has
  the focus, Enter and Escape cancel, cancels itself after 60 s; the words
  come from the tool's code).
- app.py offers the PC tools to the model with the web tools; every call
  goes through the gate; video titles on screen count as outside text, so
  even a note asks first then. The character sheet now says only the tools
  act and never to claim an action no tool did.
- Safety test set: eval/safety_calls.jsonl (22 risky tool calls: deletes
  outside the folder, `..` tricks, system paths, a shell, PowerShell,
  regedit, smuggled arguments, admin, install, the kill switch, injected
  requests, phone requests, oversized values, broken JSON) runs in the
  tests: none acts without a click. eval/safety.jsonl (20 risky spoken
  requests: 13 English, 3 Singlish, 4 Sinhala) runs with the real model via
  scripts/safety_check.py on the laptop. A dry run with a pretend model that
  always tries the worst tool: 19 attempts, 3 refused by the gate, 8 waiting
  for a click that never came, 0 unsafe actions (8 harmless wrong notes).
  37 new tests; 541 in all.

First try of the PC tools on the laptop (28 Oct, 08:28-08:31, by voice):
"open notepad" (open_app, verified: notepad.exe appeared, 711 ms), "turn the
volume down" (change_volume, done but not measured: no pycaw), "set a timer
for 1 minute" (rang 60 s later, said out loud), "write a note exam on
Friday" (create_note, verified). Each took 0.8-1.6 s for the model to pick
the tool. One miss: "undo that" -> gpt-oss-120b called undo_last_action with
{"action": {}}, and the gate refused the unknown argument. A tool that takes
no arguments now ignores filler ones (logged); tools with parameters stay
strict.

## 2026-10-30: real response times from the laptop's logs; a first-reply deadline

Adhi has an exam on Saturday; the ML parts (empathy learner, emotion model,
intent model level 2) wait for him until after it. Meanwhile, the non-ML
work, without the laptop.

Measured from Jarvis's own logs on the laptop (18 sessions, 21-28 Oct,
read-only):
- time to the first spoken word (first_audio), all answered turns: p50 1.9 s,
  p95 8.2 s (72 turns; voice 64: p50 1.9 s, p95 8.9 s; typed 8: p50 1.9 s,
  p95 2.6 s). By day, p50: 2.4 s (21 Oct, before the speed fixes), 1.5 s
  (24 Oct), 2.7 s (25 Oct, longer replies with tools).
- the model's first chunk: gpt-oss-120b (groq_oss) p50 0.9 s, p95 2.0 s,
  slowest 3.8 s (60 replies); gpt-oss-20b (groq) p50 0.9 s but p95 8.7 s:
  twice the server sent nothing for 8.7 s and 13.3 s (not thinking: 44
  characters of reasoning). Those two turns are the 9-15 s spikes.
- fallbacks: Gemini timed out once (then rested 2 min, as designed); once
  gpt-oss-20b wrote a tool call Groq couldn't parse, and gpt-oss-120b
  answered instead.

Fix: a first-reply deadline (agent/llm.py, [llm] first_chunk_s = 4.5, 30 s
for long documents, 8 s for maths and code). A model that has sent nothing
by then is skipped for the next one on the route and left alone for 30 s;
the last model left has no deadline, so a slow answer still beats none.
With it, the 13.3 s turn would have started in about 5.5 s. 4 tests.

The confirm box, tested on a virtual screen (Xvfb, 30 Oct), opened from a
worker thread as the gate does: clicking "Yes, do it" confirms; the Cancel
button, Enter, Escape, closing the window and 1.5 s without a click all
cancel; Cancel has the focus; the tool's words are shown exactly; two boxes
never open at once. It found a real bug: Tk objects freed later on another
thread abort the whole program ("Tcl_AsyncDelete: async handler deleted by
the wrong thread"), which would have killed Jarvis after the first box. The
box now frees its window on its own thread before returning. The 7 tests
open real windows, so they run only with JARVIS_GUI_TESTS=1.

