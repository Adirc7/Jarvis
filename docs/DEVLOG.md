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
