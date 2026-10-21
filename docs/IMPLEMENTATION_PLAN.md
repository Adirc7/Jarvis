# Implementation plan: building Jarvis step by step

This is the build guide: what to build in which order, what to learn first,
which files to touch, how to test it, and what counts as done. The *why* is
in [ROADMAP.md](ROADMAP.md) and [DECISIONS.md](DECISIONS.md); the *how it
fits together* is in [ARCHITECTURE.md](ARCHITECTURE.md).

## How we work together

You build; Claude guides, explains and reviews. The machine-learning parts
(the empathy learner, the emotion and intent classifiers, the evaluations)
are yours to write, because they're what you'll be examined on and you
should be able to explain every line. Safety-critical plumbing (the gate,
the confirm box) can be drafted by Claude and then read through and tested
by you.

For every step:

1. **Read** the step below and the "Learn" items. Ask Claude to explain
   anything that isn't clear, with examples.
2. **Plan** with Claude: which functions, which tests.
3. **Build** on the laptop in `D:\Jarvis_AI_Assistant\Jarvis`.
4. **Test:** `uv run pytest`, then try it for real.
5. **Measure:** the number the step asks for.
6. **Review:** paste the diff, test output and numbers to Claude.
7. **Record:** a dev-log entry, then commit and push (below).

```
git pull
uv run pytest -q
git add -A
git commit -m "Short summary of what changed"
git push
```

Who writes what is marked on each step: **you**, **Claude drafts, you
review**, or **you run**.

## Milestones at a glance

| # | Milestone | Who | Status |
|---|---|---|---|
| M0 | Laptop check: setup, hardware check, first conversation, first measurements | you run | **now** |
| M1 | Greeting (done) and replying in the language you speak | Claude drafts, you review | greeting built; language next |
| M2 | Empathy feedback learner (Thompson sampling) | **you** | next |
| M3 | Phase 2: tools, safety gate and intent test set | Claude drafts the gate; **you** write tools, tests and the safety test set | planned |
| M4 | Study skill, level 1 | **you**, with Claude's outline | planned |
| M5 | Emotion model beside Whisper (Phase 1.5) | **you** | planned |
| M6 | Jarvis window, tray, wake word, double clap, phone calls (Phase 1.6) | Claude drafts the window; **you** write the clap detector | planned |
| M7 | Visualise, Data, Research and News skills; Telegram | together | planned |
| M8 | Gestures (Phase 3), then the evaluation and report (Phase 8) | **you** | later |
| R | Recording rounds, then our own Sinhala speech model (runs alongside) | **you** | round 1 ready; training planned |

---

## M0. Laptop check (now)

**Goal:** prove the foundation works on your hardware and get the first
real numbers.

**Do:**

1. Finish `Setup Jarvis.cmd` (keys in `.env`, push-to-talk key, hardware
   check). If anything failed, paste the end of the output to Claude.
2. Double-click Jarvis; have a 5-minute conversation in English, then
   Sinhala (`/lang si`).
3. Latency: `uv run python -m jarvis.telemetry` (summarises the newest session)
   and note p50/p95 for `stt_done`, `first_token`, `first_audio`. The
   turn-by-turn table under it shows which step made a slow turn slow.
   First result (21 Oct): 3.2 s at p50, mostly a badly timed filler (fixed);
   measure again after `git pull`.
4. Recording round 1 (`eval/README.md`): write your Sinhala and Singlish
   sentences, record all three files, run `scripts/eval_stt.py` for `small`
   and `large-v3-turbo`.
5. Check the Sinhala greeting lines in `config/languages.toml` and rewrite
   them the way you'd say them.

**Learn:** what p50 and p95 mean (median, and the slowest 5%); what WER and
CER measure.

**Done when:** a dev-log entry with the smoke-test result, the latency
table and the WER/CER table. These are your first results.

## M1. Replying in the language you speak (D22)

**Goal:** Jarvis replies in the language you spoke when it's sure, asks
once when it's a maybe, and stays put on short words.

**Build:** in `app.py` (`voice_turn`), use `result.detected` and
`result.detected_probability` from `voice/stt.py`; a small "pending
question" state for "Shall I continue in Sinhala?"; a setting
`[general] reply_language = "same" | "en" | "si" | "ask"`.

**Learn:** a probability threshold as a decision rule; why short utterances
give unreliable language guesses.

**Test:** fake transcripts with chosen probabilities (sure, maybe, short),
checking switch, ask and stay.

**Done when:** tests pass, and on the laptop a mixed English and Sinhala
conversation switches correctly; log wrong switches and how often it
asked.

## M2. Empathy feedback learner (you)

**Goal:** Jarvis learns which empathy mode you prefer from your feedback.

**Learn first:** the Beta distribution (what Beta(1, 1) and Beta(8, 2) look
like); exploration and exploitation; Thompson sampling (ARCHITECTURE.md,
section 8).

**Build:**

- `src/jarvis/learning/bandit.py`: `BetaBandit(arms)` with `choose(rng)`,
  `update(arm, reward)`, `save(path)` and `load(path)`; the counts live in
  `state/empathy_bandit.json`.
- Feedback detection: "thanks", "perfect" = good; "too much", "be more
  direct", "not what I asked" = bad. The phrases go in `persona.toml`.
- In `app.py`: pick the mode for each reply with the bandit, unless you set
  one with `/empathy`; never leave the allowed range; real distress always
  gets supportive.

**Test:** a seeded random generator gives repeatable choices; a simulation
where "supportive" is liked 80% of the time shows the bandit choosing it
more and more.

**Done when:** tests pass, plus a plot from the simulation (choices over 200
rounds) for your report.

## M3. Phase 2: tools and safety

**Goal:** Jarvis acts on the PC safely; every action is checked and logged.
Follow the nine build steps in ROADMAP.md, "Phase 2".

**Build, in order:**

1. `src/jarvis/tools/registry.py` and `gate.py` (Claude drafts, you review):
   tool definitions, the four tiers, allowed folders, the action log.
   Tested with fake tools only.
2. Read-only tools with `verify()` (you): `open_app`, `open_file`,
   `search_files`, `list_folder`, `system_info`.
3. Reversible tools with undo (you): `create_note`, `copy_file`,
   `move_file`, `rename_file`; the recycle folder.
4. The confirm box (Claude drafts): tkinter, Cancel focused, item tick
   boxes, alternatives, 60-second timeout; voice can only cancel.
5. Untrusted-content marking; 6. the code runner; 7. the skills loader,
   router and threads; 8. one MCP server; 9. the evaluation run.

**Also (you):** the intent test set `eval/intents.json` in English, Sinhala
and Singlish (about 10 intents, 10 examples each), and the safety test set
(30 risky requests, 10 booby-trapped files).

**Learn:** JSON schema for tool arguments; what prompt injection is; why
"verified" and "claimed" differ.

**Done when:** 20-30 fixed tasks with verified and claimed completion side
by side; zero unsafe actions on the safety test set; intent accuracy per
language for pipelines A, B and C.

## M4. Study skill, level 1 (you)

**Goal:** a tutor for physics and maths that gives hints first and checks
every maths result.

**Build:** `skills/study/SKILL.md` (tutor rules); `config/courses.toml`
(your subjects this semester); a `check_maths` tool using SymPy
(derivatives, integrals, series, exact ODE solutions) and a units check;
Study uses gpt-oss-120b with higher `reasoning_effort` for hard problems.

**Learn:** SymPy basics (`diff`, `integrate`, `series`, `dsolve`); why hints
beat answers for learning (the Bastani study).

**Test:** 20 problems with known answers, including some deliberately wrong
"answers" the check must catch.

**Done when:** you've used it for a week on one subject (numerical methods,
say) and the check caught every wrong answer in the test set.

## M5. Emotion model beside Whisper (you)

**Goal:** Jarvis notices how you said something, and mentions it only when
it's confident.

**Build:** `src/jarvis/perception/emotion.py`: load the chosen model
(compare emotion2vec and a wav2vec2 IEMOCAP model; check licences first),
run it on the same audio as Whisper in parallel, return label and
confidence; pass it to the LLM through the confidence gate (ARCHITECTURE.md,
section 8); `/mood` and corrections store features and labels in a
gitignored folder.

**Learn:** self-supervised speech features; frozen encoder plus small
classifier; macro-F1; leave-one-speaker-out; the C_FA / (C_FA + C_FN)
threshold.

**Done when:** baseline macro-F1 on your round-1 and role-play clips, and the
false "you sound upset" rate. Later (step 5 of Phase 1.5): your own
classifier on the stored features, compared with the baseline.

## M6. Window, tray, wake word, clap and phone (Phase 1.6)

**Goal:** Jarvis runs in the background, wakes on "Hey Jarvis" or a double
clap, and shows the orb window.

**Build:**

- Tray icon and life cycle (Claude drafts): pystray; Open, Pause listening,
  Quit; "close window = sleep" by default.
- The window (Claude drafts from a design you approve in the Design
  canvas): the orb with the skills around it, conversation, KaTeX
  equations, plots, confirmations, action log.
- Wake word (you): openWakeWord "hey jarvis"; test whether "Hi Jarvis" also
  works.
- Double clap detector (you; a nice signal-processing exercise): the
  short-time energy envelope, two sharp peaks 0.2-0.6 s apart, rejection of
  long sounds.
- Phone calls: hold-to-talk over WebRTC, then Tailscale.

**Learn:** keyword spotting; onset detection from an energy envelope; how a
background process and a window talk (a local web page).

**Done when:** missed wakes and false wakes per hour (with a film playing)
for the wake word and the clap; phone first-audio p50/p95.

## M7. More skills

Visualise, Data, Research, News, each with its "done when" from the
roadmap; Telegram as an optional channel. Build each as a `SKILL.md` plus
its tools, through the gate.

## M8. Gestures, then evaluation and report

- **Gestures (you):** MediaPipe Gesture Recognizer for open palm and thumbs
  up/down; motion rules for swipes and the double wave; half-second hold;
  measure accuracy and false activations per hour.
- **Evaluation (you):** the reproducible run of every measurement above,
  Godspeed and SUS in a small user study (with consent and, if needed,
  ethics approval), and the report.

## R. Recording rounds and our own Sinhala model (alongside everything)

Why this matters: on 21 Oct, Whisper `small` heard Sinhala correctly as a
language (p = 0.95 to 0.99) but wrote nonsense. A Sinhala model of our own is
the most useful thing this project can add.

1. **Round 1, you:** English, Sinhala and Singlish test sentences
   (`eval/`). These are the **test set**: never train on them.
2. **Baselines, you run:** `scripts/eval_stt.py` on round 1 with `small`,
   `large-v3-turbo` and one community fine-tune converted for
   faster-whisper (docs/LANGUAGES.md). Note WER and CER.
3. **Train our own, you (Claude outlines the notebook):**
   - Data: [OpenSLR 52](https://openslr.org/52/) from Google, crowd-sourced,
     about 185,000 utterances (about 224 hours) with transcripts. Read its
     LICENSE.txt first. Start with a 30-hour subset.
   - Model: fine-tune `whisper-small`, so it drops into the existing
     faster-whisper path (convert with `ct2-transformers-converter`, then set
     `stt_model` under `[si]`). Later, compare a CTC model (Wav2Vec2-BERT):
     a 2026 study got 4.6% CER from 60 hours of OpenSLR 52 without a
     language model ([arXiv 2607.06289](https://arxiv.org/abs/2607.06289)).
   - Compute: Kaggle for long runs (free T4 or P100, 12-hour sessions,
     about 30 GPU hours a week; "Save & Run All" keeps training with the
     browser closed), Colab for quick tests (needs the tab open; free limits
     unpublished). Also ask the department whether students can use a
     university GPU server.
   - Storage: download the data subset straight into the cloud machine from
     OpenSLR, prepare it once, and keep the prepared subset and checkpoints
     in Google Drive (mounted in Colab; 15 GB free, shared with Gmail) or a
     private Hugging Face repo (works from Kaggle, Colab and the laptop).
     Save a checkpoint every 30 minutes and resume from the last one.
     Recordings of your voice stay on the laptop; testing runs there.
   - Measure: CER and WER on your round-1 recordings, and Whisper time on
     the laptop, before and after.
4. **Round 2:** the intent examples, partly recorded.
5. **Round 3:** friends with written consent (`--speaker friend1`).
6. **Role-play clips** for emotion: calm, rushed, frustrated, confused.

**Learn:** what fine-tuning changes (start from Whisper's weights, small
learning rate); train, validation and test splits; why the test speakers and
sentences must be ones the model never saw; why CER suits Sinhala better
than WER.

**Done when:** one table (model, CER, WER, ms per utterance on the laptop)
for `small`, `large-v3-turbo`, a community fine-tune, and ours.

Ask a lecturer early whether recording other people needs ethics approval,
and whether this can be your final-year research project.
