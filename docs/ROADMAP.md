# Roadmap

Phases follow the implementation plan, plus Phase 1.5 (emotion awareness
and human-like conversation) and Phase 2.5 (light memory), added on
2026-10-17. Each phase is done when its evidence exists, not when its code
exists.

| Phase | What | Status | Done when |
|---|---|---|---|
| 0 | Foundations: event bus, telemetry, kill switch, free LLMs, languages | Built, not yet run on the laptop | Smoke test passes on the laptop |
| 1 | Spoken conversation | Built, not yet run on the laptop | Recorded dialogue tests, WER/CER per language, working mute and barge-in, p50/p95 latency |
| **1.5** | **Emotion-aware, human-like replies** | Character sheet, empathy modes and fillers built; emotion detection planned | See below |
| 2 | Windows and browser tools, verified; allow-list first | Next to build | 20–30 fixed tasks passed or failed by real state checks |
| **2.5** | **Light memory** (an early slice of Phase 6) | Planned | Jarvis recalls facts and recent sessions you allowed it to keep; "forget that" verifiably deletes |
| 3 | Hand tracking | Later | Gesture accuracy and false activations measured |
| 4 | Voice and gesture together | Later | "This/that" resolves to the right object in controlled tasks |
| 5 | Speaking up on its own | Later | Relevant announcements, duplicates suppressed, quiet mode |
| 6 | Memory | Later | Source-linked answers, verified deletion |
| 7 | Multi-step tasks | Later | Multi-step tasks verified, clean recovery from induced failures |
| 8 | Evaluation and demo | Later | Reproducible evaluation run and written report |

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
2. **Adaptive (planned).** The detected emotion picks the starting mode, and
   a **contextual bandit** learns *your* preference per emotional state from
   signals you give anyway (interrupting, repeating, "thanks") and from
   explicit feedback ("too much", a thumbs up or down). It trains on the
   laptop in milliseconds; the LLM itself is never retrained.
3. **Limits.** You set the allowed range; the adaptive policy can't leave it.
   Real distress always gets a supportive, safe reply, whatever the setting.
   Jarvis adapts *its own* style; it never tries to change your emotions.

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
