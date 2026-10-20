# Roadmap

Phases follow the implementation plan, plus Phase 1.5 (emotion awareness
and human-like conversation) and Phase 2.5 (light memory), added on
2026-10-17, and Phase 1.6 (calling Jarvis from the phone), added on
2026-10-20. Each phase is done when its evidence exists, not when its code
exists.

| Phase | What | Status | Done when |
|---|---|---|---|
| 0 | Foundations: event bus, telemetry, kill switch, free LLMs, languages | Built, not yet run on the laptop | Smoke test passes on the laptop |
| 1 | Spoken conversation | Built, not yet run on the laptop | Recorded dialogue tests, WER/CER per language, working mute and barge-in, p50/p95 latency |
| **1.5** | **Emotion-aware, human-like replies** (the research contribution) | Character sheet, empathy modes and fillers built; feedback bandit next; emotion detection planned | See below |
| 1.6 | Call Jarvis from your phone (free internet call, no phone number) | Planned: starts once Phase 1 works on the laptop | A hold-to-talk call works on home Wi-Fi and away through Tailscale, private only, with first-audio p50/p95 logged per channel |
| 2 | Windows and browser tools, verified; allow-list first | Next to build | 20–30 fixed tasks passed or failed by real state checks, with **verified and claimed completion reported side by side** |
| **2.5** | **Light memory** (an early slice of Phase 6) | Planned | Jarvis recalls facts and recent sessions you allowed it to keep; "forget that" verifiably deletes |
| 3 | Hand tracking | Later | Gesture accuracy and false activations measured |
| 4 | Voice and gesture together | Later | "This/that" resolves to the right object in controlled tasks |
| 5 | Speaking up on its own | Later | Relevant announcements, duplicates suppressed, quiet mode |
| 6 | Memory | Later | Source-linked answers, verified deletion |
| 7 | Multi-step tasks | Later | Multi-step tasks verified, clean recovery from induced failures |
| 8 | Evaluation and demo | Later | Reproducible evaluation run and written report, using the study measures below |

## Research priorities

From the literature review of 23 papers (2026-10-18; the full review with
tables and references is the Claude doc "Jarvis: Research Background and
Gaps"). No reviewed work combines an acting desktop agent, voice and gesture,
emotion-aware replies and per-user personalisation, and none studies Sinhala
or Tamil speakers using an assistant.

**Quick wins (do first):**

1. **Verified vs claimed completion** (Phase 2). Every tool reports what it
   observed; every evaluation reports both rates. AnovaX, a recent voice
   desktop agent, acts without checking results
   ([arXiv:2607.15367](https://www.alphaxiv.org/abs/2607.15367)).
2. **Study measures** (all user studies). Godspeed
   ([Bartneck et al. 2009](https://www.bartneck.de/publications/2009/measurementInstrumentsRobots/))
   and the System Usability Scale in every study; in trials longer than a
   week, also daily use and a short loneliness questionnaire, because heavier
   chatbot use went with more loneliness and dependence in a 981-person
   randomised study ([Fang et al. 2025](https://arxiv.org/html/2503.17473v1)).
3. **Feedback-only empathy bandit** (Phase 1.5, next). Starts learning your
   preferred mode from what you say ("too much", "be more direct", "thanks")
   before the emotion model exists. See "Empathy modes" below.

**Big bets (the contribution):**

4. **Emotion context in the desktop agent** (Phase 1.5, steps 1–2 below).
   Voice desktop agents don't report adapting to mood, and emotion-aware
   agents don't act on a computer
   ([Abbasian et al.](https://arxiv.org/abs/2405.04777)).
5. **A Sri Lankan emotional speech set** (Phase 1.5, "Dataset" below). No
   public Sinhala emotional-speech corpus was found; Tamil has one read-speech
   set ([EmoTa](https://aclanthology.org/2025.chipsal-1.19)); and emotion
   models lose much of their accuracy on languages they weren't trained on
   ([Mi, Ma, Toda 2026](https://arxiv.org/pdf/2606.06200)).

**Later:** code-switching test set (Sinhala–English, Tamil–English
commands), EmoTa as a Tamil baseline if its licence allows, adaptive voice
vs gesture (Phase 4), full-duplex turn-taking.

## Phase 1.5: Emotion-aware replies

**Goal:** Jarvis notices *how* you said something (stressed, frustrated,
confused, calm), not only *what* you said, and adapts its reply. It also
notices when a reply wasn't what you expected.

**Key idea:** the LLM already knows how to respond to a frustrated person; it
just can't hear your voice, because it only receives Whisper's text. So the
work is in perception. The LLM is not fine-tuned; it gets the emotion as
context.

### Steps

1. **Off-the-shelf speech emotion model (no training).** Runs on the same
   push-to-talk audio as Whisper, in parallel. Output: a label and a
   confidence, e.g. `frustrated 0.72`. Candidates to compare: emotion2vec,
   and wav2vec2 models trained on IEMOCAP. Check each one's licence and
   language coverage first.
2. **Give it to the LLM as context**, with a rule: below a confidence
   threshold, say nothing about emotion; above it, adapt tone and *ask*
   rather than assume ("You sound a bit rushed. Want the short version?").
3. **Reaction signals** for "that's not what I expected": a quick "what?",
   "no, I meant…", or the same question asked again right after a reply.
   Later, facial expressions from MediaPipe's face landmarker (the same
   camera as hand tracking).
4. **Corrections become labels.** "I'm not stressed" or a `/mood` command
   stores the model's feature vector (numbers, not audio) with your label,
   locally.
5. **Tune on your voice (level 2).** Keep the pretrained model frozen and
   train a small classifier on the stored features. This is where training
   happens, because those models learned mostly from acted American English
   and may misread Sri Lankan English, Sinhala and Tamil.
6. **Measure.** Macro-F1 per emotion against the off-the-shelf baseline,
   split by session (never random frames from one recording), plus how often
   Jarvis says "you sound upset" when you weren't.

### Rules

- **Privacy:** runs fully on the laptop. No audio is stored; only feature
  vectors and labels, in a gitignored folder. One setting turns the whole
  feature off. Anyone else taking part in tests must agree first.
- **Honesty:** Jarvis never states your emotion as fact; it hedges or asks.
- **Not doing:** fine-tuning the LLM (level 3). Free hosted models can't be
  fine-tuned, and prompting with good context should be enough. Revisit only
  if measured reply quality says otherwise.

### Empathy modes (the "empathy dial")

Three styles, defined in `config/persona.toml`: **logical** (brief, facts,
feelings not mentioned), **balanced** (acknowledge stress briefly, then
help) and **supportive** (acknowledge first, reassure honestly, slower
voice, offer a choice).

1. **Manual (built).** `/empathy supportive`, or say "be more direct", "be
   gentler", "back to normal". The LLM receives the mode's instruction; the
   voice speed follows the mode.
2. **Feedback-only bandit (next).** Before any emotion detection, Jarvis
   learns which mode you prefer from direct feedback ("too much", "be more
   direct", "thanks") and stores the scores in a small JSON file. One
   Beta(good + 1, bad + 1) score per mode; Thompson sampling picks the mode.
3. **Adaptive with emotion (planned).** Once the emotion model exists, the
   scores are kept per emotional state (a **contextual bandit**), and signals
   you give anyway count too (interrupting, repeating yourself). It trains on
   the laptop in milliseconds; the LLM itself is never retrained.
4. **Limits.** You set the allowed range; the learned policy can't leave it.
   Real distress always gets a supportive, safe reply, whatever the setting.
   Jarvis adapts *its own* style; it never tries to change your emotions.

### Dataset: Sri Lankan emotional speech

The second big bet. Small, consented, and labelled for what an assistant
needs.

1. **Ethics first.** Ask the supervisor whether a formal study needs ethics
   approval; written consent from every speaker; recordings stay local, and
   each speaker can withdraw.
2. **Labels that fit an assistant:** calm, rushed, frustrated, confused
   (plus neutral). Public sets use basic emotions (anger, happiness, sadness,
   fear, neutral) and miss these.
3. **Languages:** Sinhala, Tamil, Sri Lankan English; aim for at least 10
   speakers per language, balanced by gender.
4. **Speech that sounds real:** short role-play scenarios ("the build failed
   again", "you're late for a lecture") rather than neutral sentences read
   aloud, plus your own consented corrections from daily use.
5. **Two annotators per clip;** report agreement with Fleiss' kappa, as EmoTa
   did, and keep only clips they agree on for testing.
6. **Use:** train and test the improvement ladder below, always
   leave-one-speaker-out. Publish features or the dataset only if every
   speaker agreed to that.

### Evaluation: the improvement ladder

Each step is measured against the one before, on speakers the model never
trained on (leave-one-speaker-out):

1. **Baseline:** the pretrained emotion model as-is.
2. **Assistant labels:** calm, rushed, frustrated, confused (the pretrained
   models don't even have "confused").
3. **Adapted to Sri Lankan voices:** a small classifier on frozen features.
4. **Fused with words and reactions:** "what?", repeated questions,
   corrections.
5. **Confidence gate** from the report's decision theory: mention emotion only
   when p > C_FA / (C_FA + C_FN).

Report macro-F1 per step and the false "you sound upset" rate, honestly,
including the steps that don't help. Data from other people needs their
consent; ask the supervisor whether a formal study needs ethics approval.

### Human-like conversation

What makes talking to Jarvis feel like talking to a person, and where each
part is built:

| Part | What it means | Where |
|---|---|---|
| Personality | A consistent character: traits, humour, how it disagrees, natural spoken sentences | **Built**: `config/persona.toml` |
| Timing | Starts replying fast; a short filler ("Mm, one moment") only when the real reply is slow | **Built**: fillers; hands-free turn-taking later |
| Voice | Pace and pauses that fit the moment | Partly built (speed follows the empathy mode) |
| Emotional attunement | Notices how you feel and adapts, within your limits | Phase 1.5 |
| Memory | Remembers your projects, preferences and recent conversations | Phase 2.5 (light), Phase 6 (full) |
| Initiative | Speaks up only when it's useful | Phase 5 |
| Presence | Understands gestures and what's on screen | Phases 3–4 |

**The line Jarvis doesn't cross:** it should feel human but never claim to
be human or to have feelings it doesn't have. Asked "are you human?", it
says it's an AI.

**Measuring it:** the Godspeed questionnaire (anthropomorphism, likeability,
perceived intelligence) and the System Usability Scale, compared across
versions with the same tasks: plain, persona only, persona + empathy modes,
persona + adaptive empathy.

### Research question it adds

*Do emotion-aware replies improve how helpful and comfortable the assistant
feels, compared with the same replies without emotion context?* Compare with
the same tasks and the same LLM, with only the emotion context switched on
or off, in counterbalanced order.

## Phase 1.6: Call Jarvis from your phone

**Goal:** talk to Jarvis from the phone, anywhere, as if calling it. The
laptop does all the work (Whisper, LLM, Lewis's voice); the phone is only a
remote microphone and speaker.

**Not a phone number.** A real number costs money after short trials
(Twilio's trial: 75 minutes, verified numbers only), free temporary numbers
are probably foreign (international rates from a Sri Lankan SIM), and phone
lines carry low-quality audio that hurts Whisper, most of all for Sinhala and
Tamil. See decision D20.

**Design:** an internet call. Jarvis serves a small "Call Jarvis" page; the
phone's browser sends and receives audio over WebRTC. On the event bus the
phone is just another audio source and sink beside the laptop's mic and
speakers, so the rest of the pipeline doesn't change. Away from home,
Tailscale (free personal plan) links phone and laptop privately, and
Tailscale Serve gives the page the HTTPS address phone browsers require
before they allow the microphone. Library to choose when building: FastRTC
(voice detection and turn-taking built in, but brings Gradio) or aiortc
(lower level, lighter).

### Steps

1. **Hold-to-talk call (version 1).** A big button on the page works like
   Right Ctrl; barge-in by pressing it while Jarvis speaks. Home Wi-Fi first,
   then through Tailscale.
2. **Hands-free (version 2).** Voice activity detection decides when you've
   finished (e.g. Silero VAD); the browser's echo cancellation keeps Jarvis
   from hearing itself. Shared with hands-free mode on the laptop.
3. **Home-screen app.** Add the page to the home screen so it opens like an
   app, with a pairing code entered once.
4. **Optional, later:** Telegram voice notes as a walkie-talkie fallback that
   needs no tunnel.

### Rules

- **Private only:** reachable through Tailscale, never a public link; a
  pairing code on top.
- **Phone requests are remote control:** once Phase 2 tools exist, anything
  beyond read-only asked from the phone needs confirmation on the phone.
- **Same privacy as the laptop:** audio is processed and dropped, never
  stored.

### Measure

First-audio latency p50/p95 for phone calls next to the laptop numbers
(telemetry tags each turn with its channel), and whether WER changes with the
phone's microphone.
