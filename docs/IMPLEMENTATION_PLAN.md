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
| M8 | Gestures (Phase 3), then the evaluation and report (Phase 8) | **you** | palm to pause can start now (no window needed); the rest later |
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

**Training data for the intent classifier (ready, 21 Oct):**
`uv run python scripts/make_intent_data.py` writes about 15,400 labelled
sentences (8,300 in Sinhala script, 4,700 Singlish, 2,500 English) for 43
intents, from the patterns in `src/jarvis/intents/patterns.py`: Sinhala verb
forms (polite, casual, for me, question, formal), synonyms, "එක" after
English words, cases, word order, wake words and two-sentence requests.
Twelve study intents get the most examples (explain, solve, derive or prove,
check my answer, write code, fix code, exam revision, quiz, summarise,
research papers, data analysis, graphs), over 307 university topics in
`data/generated/study_topics.tsv`: pure and applied maths, physics,
statistics, data science, computing, research and management, including the
Kelaniya PMAT, AMAT and PHYS modules and the IT modules, by course code.
Train on these, test on your real sentences. Class sizes differ a lot
(greetings 10, study requests 360 in Sinhala), so use class weights.

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
- Double clap detector (you; a nice signal-processing exercise). What it
  means is decided in D29; how to build it is "The double clap, step by
  step" below. The detector itself can be written and tested now, before
  the tray exists.
- Phone calls: hold-to-talk over WebRTC, then Tailscale.

**Learn:** keyword spotting; onset detection from an energy envelope; how a
background process and a window talk (a local web page).

**Done when:** missed wakes and false wakes per hour (with a film playing)
for the wake word and the clap; phone first-audio p50/p95.

### The double clap, step by step

**Meaning (D29):** sleeping -> wake; awake and quiet -> listen now; while
Jarvis speaks -> ignored. Never sleep, quit, cancel or confirm.

**Libraries:** none new. `numpy` for the maths and `sounddevice` for the
microphone, both already in Jarvis. No model: a clap is a sharp, short,
broadband sound, and signal processing can find that.

1. **`src/jarvis/sensors/clap.py`, a pure detector (you).** `ClapDetector`
   gets blocks of 16 kHz audio and returns events; no microphone inside, so
   it can be tested with made-up audio.
   - Frames of 10 ms (160 samples); energy of each frame in dB.
   - **Noise floor** that adapts: the 20th percentile of the last 3 s.
   - **A peak** (one clap): the energy jumps at least ~15 dB above the floor
     within 20 ms (a sharp start), and falls back by ~10 dB within 100 ms
     (a short sound). Speech, music and a fan rise slowly or last long, so
     they fail one of the two.
   - **Broadband check:** a clap has much of its energy above 2 kHz; a door
     knock or desk tap is mostly low. Measure the share on your own claps
     before choosing the threshold.
   - **Pairing:** a second peak 0.2-0.6 s after the first; no third peak in
     the next 0.6 s (applause, knock-knock-knock); then 2 s of cooldown.
   - **Ignored while Jarvis plays audio** and for 0.5 s after; the voice
     sink tells the detector when it's playing.
2. **Tests (you), `tests/test_clap.py`, on made-up audio:** two clicks 0.3 s
   apart -> one double clap; one click -> none; 0.1 s or 0.9 s apart ->
   none; three clicks -> none; a 1 s tone or white noise -> none; two
   clicks while "speaking" -> none.
3. **Calibration:** 2-3 s of room noise when the clap is switched on; a
   sensitivity setting; the window later shows "first clap heard" before
   waking (Codex section 6).
4. **`scripts/clap_test.py` (you):** opens the microphone, prints each peak
   with its dB and high-frequency share, and each double clap. Nothing is
   saved.
5. **Wire it (Claude drafts, you review):** `[clap] enabled = false`; when
   on, the microphone stays open (your consent; the console says "clap
   listener on", `/clap off` turns it off, and later the window shows it
   next to the microphone and camera). A double clap publishes an event to
   the `LifecycleController` (Codex section 12), the same controller the
   wake word, tray and keyboard use, so every input does the same thing
   (Codex section 5). It turns the event into "wake" or "listen now" (D29).
6. **Optional ML stage to compare:** MediaPipe's Audio Classifier with
   YAMNet (AudioSet classes include clapping, knocking and tapping) checks
   the second around each candidate. Report false wakes per hour with and
   without it.

**Measure (Codex sections 6 and 11):** missed wakes out of 50 double claps
at 0.5, 1 and 2 m; false wakes per hour with Jarvis speaking, a lecture or
YouTube video, the fan, typing, desk taps and door knocks.

**Done when (Codex section 11):** Jarvis's own speech never triggers it; with
no microphone or no permission, Jarvis carries on with push-to-talk and the
keyboard and says once that the clap is off; missed-wake and false-wake
rates are in the dev log; no wake at all during the film, fan, typing and
desk-tap test.

**Learn:** decibels and short-time energy; onset detection; spectral
energy above a frequency (an FFT per frame); adaptive thresholds;
precision against false alarms per hour.

## M7. More skills

Visualise, Data, Research, News, each with its "done when" from the
roadmap; Telegram as an optional channel. Build each as a `SKILL.md` plus
its tools, through the gate.

## M8. Gestures, then evaluation and report

- **Gestures (you):** MediaPipe Gesture Recognizer for open palm and thumbs
  up/down; motion rules for swipes and the double wave; half-second hold;
  measure accuracy and false activations per hour. Palm to pause comes
  first, and can start now: see below.
- **Evaluation (you):** the reproducible run of every measurement above,
  Godspeed and SUS in a small user study (with consent and, if needed,
  ethics approval), and the report.

### Palm to pause, step by step (can start now)

**Meaning (D29):** right hand only, open palm held 0.5 s. While Jarvis
speaks: stop speaking ("hold on"). While a video Jarvis opened is on: play
or pause it. Otherwise nothing. Never confirms anything.

**Libraries:** `mediapipe` (Google, Apache-2.0), already in Jarvis's
`vision` extra, which `update.cmd` installs. It brings `cv2`
(opencv-contrib-python) for the camera. MediaPipe 1.x has only the
**Tasks API**: tutorials that use `mp.solutions.hands` or
`mp.solutions.drawing_utils` are for the old version and won't run, so
draw landmarks with `cv2.circle` yourself. The model,
`models/gesture_recognizer.task`, comes from
`uv run python scripts/download_models.py`.

**How it works, per camera frame:**

1. The camera gives a frame; flip it like a mirror (`cv2.flip(frame, 1)`)
   and convert BGR to RGB.
2. MediaPipe finds each hand: 21 landmarks (finger joints), the handedness
   ("Left" or "Right" with a score) and a gesture ("Open_Palm",
   "Closed_Fist", "Thumb_Up", "Thumb_Down", "Pointing_Up", "Victory",
   "ILoveYou" or "None", with a score). No training needed.
3. Jarvis keeps only the right hand with an Open_Palm score of at least
   0.7, and then the rules: held 0.5 s -> one "palm" event; then the hand
   must drop or close for 0.5 s before the next one counts; at most one
   event a second. If the hand is lost for more than two frames mid-hold,
   the hold starts again (low confidence is always a safe "nothing").

```python
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

options = vision.GestureRecognizerOptions(
    base_options=BaseOptions(model_asset_path="models/gesture_recognizer.task"),
    running_mode=vision.RunningMode.LIVE_STREAM,   # drops frames while busy
    num_hands=2,                                   # so the right hand can be picked
    min_hand_detection_confidence=0.5,             # defaults; raise them if
    min_hand_presence_confidence=0.5,              # false palms appear
    min_tracking_confidence=0.5,
    result_callback=on_result)                     # on_result(result, image, timestamp_ms)
recognizer = vision.GestureRecognizer.create_from_options(options)
# per frame: recognizer.recognize_async(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ms)
# result.gestures[i][0].category_name, result.handedness[i][0].category_name,
# result.hand_landmarks[i] (21 points, x and y from 0 to 1)
```

**Steps:**

1. **`scripts/gesture_preview.py` (Claude wrote it, 24 Oct; you run it):**
   a camera window with the
   landmarks, the gesture name, the hand and the scores, at about 15
   frames a second. Show the gesture being considered ("Open_Palm 0.91,
   holding 0.3 s") separately from the one accepted ("accepted"), and the
   frame rate and time per frame (Codex sections 7 and 8, debug view).
   This is Codex's "camera landmarks in the HUD only, no actions" step,
   done in an OpenCV window before the Jarvis window exists. Raise your right hand: it must say "Right". If it says
   "Left", add a `swap_handedness` setting (which way round it reports
   depends on whether the frame is mirrored; check it rather than assume).
   `scripts/smoke_test.py` already opens the camera with the hand
   landmarker, so start from there.
2. **`src/jarvis/sensors/gestures.py`, the rules without the camera
   (you).** `PalmTrigger.update(t, hands) -> bool`, where `hands` is a list of
   (hand, gesture, score). A small state machine: waiting -> holding ->
   fired -> re-arming. Allow one or two missed frames in the middle of a
   hold (tracking flickers).
   Later the same file holds the `GestureRouter` (Codex section 12): it
   gives the hand to exactly one mode at a time, so while the virtual mouse
   is on, swipes are off and the palm means "freeze the pointer" (D29).
3. **Tests (you), `tests/test_gestures.py`, with made-up frames:** held
   0.6 s -> one event; 0.3 s -> none; left hand -> none; held 3 s -> still
   one; one missed frame mid-hold -> still one; hand lost for five frames
   mid-hold -> none; palm, drop 0.6 s, palm -> two.
4. **The camera thread, `src/jarvis/sensors/camera.py` (you):**
   `CameraSource` (OpenCV owns the camera; only one part of Jarvis may hold
   it at a time, Codex section 8) and `HandTracker` (MediaPipe). It opens
   the camera only when `[gestures] enabled = true` (or `/camera on`; the
   console says "camera on", `/camera off` closes it), sends
   frames with timestamps that only go up, keeps only the newest result,
   and publishes `GestureEvent(name="open_palm", ...)` (it already exists
   in `events.py`) with `bus.publish_threadsafe`. Frames are dropped after
   the landmarks; nothing is saved.
5. **Wire it into the app (Claude drafts, you review):** on `open_palm`, if
   the voice is playing -> cancel the turn's reply and stop the voice (like
   barge-in, not the kill switch, so Jarvis stays ready); else if a video
   Jarvis opened is on -> the media key; log `gesture` in telemetry.
6. **Settings:** `[gestures] enabled = false`, `hand = "right"`,
   `hold_ms = 500`, `min_score = 0.7`, `rearm_ms = 500`, `fps = 15`.

**Measure:** out of 100 palms (different light, distances, sitting back or
close), how many fire; false palms per hour of normal work (typing,
drinking tea, waving to someone, someone else in view); time from the palm
appearing to the voice stopping (target under 0.8 s, of which 0.5 s is the
hold); CPU use at 15 frames a second.

**Done when (Codex section 11):** one deliberate palm gives exactly one
action; losing the hand or low confidence never does anything; accuracy and
false palms per hour are in the dev log; with no camera or no permission,
Jarvis carries on without gestures and says so once; no video is stored and
the camera is on only while the setting or `/camera on` says so.

**Why this can start before the window (differs from Codex's order).**
Codex section 10 puts camera work after the M3 safety gate and the M6
window. Palm to pause can come earlier because it adds no new power: it
only stops Jarvis's own voice or presses the play/pause key that "pause the
video" already presses, and it can never confirm anything. The rest of
Codex's order stays: swipes after the window, the virtual mouse after M3.
Rollback: it's off by default and one setting turns it off.

**Learn:** hand landmarks and handedness; live-stream mode and timestamps;
debouncing and hysteresis; small state machines; why one frame is never
enough (Codex section 7).

## R. Recording rounds and our own Sinhala model (alongside everything)

Why this matters: on 21 Oct, Whisper `small` heard Sinhala correctly as a
language (p = 0.95 to 0.99) but wrote nonsense. A Sinhala model of our own is
the most useful thing this project can add.

1. **Round 1, you:** English, Sinhala and Singlish test sentences
   (`eval/`). These are the **test set**: never train on them.
2. **Baselines, you run:** `scripts/eval_stt.py` on round 1 with `small`,
   `large-v3-turbo` and one community fine-tune converted for
   faster-whisper (docs/LANGUAGES.md). Note WER and CER.
3. **Train our own, you (Claude outlines the notebook in
   [TRAINING_SINHALA.md](TRAINING_SINHALA.md)):**
   - Data: [OpenSLR 52](https://openslr.org/52/) from Google, crowd-sourced,
     about 185,000 utterances (about 224 hours) with transcripts, CC BY-SA
     4.0, in 16 parts of about 0.9 GB (about 14 hours each). Start with two
     parts.
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
