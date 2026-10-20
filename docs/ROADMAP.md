# Roadmap

Jarvis is **one core plus skills** (decision D24). The core is what makes it
Jarvis and holds the research: voice, languages, emotion, memory and safety.
Skills are the things it helps with (study, data, research, news, ...); each
is a short instruction file plus the tools it needs, all running on the
Phase 2 tool system. Every phase and skill is done when its evidence exists,
not when its code exists.

## Build order

1. **Laptop check:** smoke test, first spoken conversation, latency p50/p95.
2. **Startup greeting**, then **replying in the language you speak**.
3. **Feedback-only empathy bandit** (quick win 3).
4. **Phase 2: tools and safety**, with the intent test set.
5. **Study skill, level 1**: the first skill on Phase 2.
6. **Phase 1.5, steps 1-2:** emotion model beside Whisper, emotion as context.
7. **Phase 1.6:** the Jarvis window (equations, plots, confirmations), then
   phone calls.
8. **Visualise, Data, Research and News skills**; Telegram as an optional
   channel.

All along: the recording rounds (see "Data collection"). The order changes
when measurements say it should.

## Core

| Phase | What | Status | Done when |
|---|---|---|---|
| 0 | Foundations: event bus, telemetry, kill switch, free LLMs, languages | Built, not yet run on the laptop | Smoke test passes on the laptop |
| 1 | Spoken conversation; next: a short startup greeting, then replying in the language you speak | Built, not yet run on the laptop | Recorded dialogue tests, WER/CER per language, working mute and barge-in, p50/p95 latency |
| **1.5** | **Emotion-aware, human-like replies** (the research contribution) | Character sheet, empathy modes and fillers built; feedback bandit next; emotion detection planned | See "Phase 1.5" |
| 1.6 | Jarvis window, and calling Jarvis from your phone (free internet call, no phone number) | Planned | The window shows replies, equations, plots and confirmations; a hold-to-talk call works on home Wi-Fi and away through Tailscale, private only, with first-audio p50/p95 logged per channel |
| **2** | **Tools and safety**: the platform every skill runs on | Planned in detail (below) | 20-30 fixed tasks with **verified and claimed completion side by side**; **zero unsafe actions** on the safety test set; intent accuracy per language |
| **2.5** | **Light memory** (an early slice of Phase 6) | Planned | Jarvis recalls facts and recent sessions you allowed it to keep; "forget that" verifiably deletes |
| 3 | Hand tracking | Later | Gesture accuracy and false activations measured |
| 4 | Voice and gesture together | Later | "This/that" resolves to the right object in controlled tasks |
| 5 | Speaking up on its own | Later | Relevant announcements, duplicates suppressed, quiet mode |
| 6 | Memory | Later | Source-linked answers, verified deletion |
| 7 | Multi-step tasks | Later | Multi-step tasks verified, clean recovery from induced failures |
| 8 | Evaluation and demo | Later | Reproducible evaluation run and written report, using the study measures below |

## Skills

Each skill needs Phase 2. Suggested order: Study, Visualise, Data,
Research, News; Friend grows with Phase 1.5.

| Skill | What it does | Free tools | Done when |
|---|---|---|---|
| **Study** | Tutor for the Physical Science degree: hints first, checked maths, quizzes later | SymPy | Used for a week on one subject; every stated maths result checked |
| **Visualise** | Graphs, 3D surfaces, vector fields, ODE solutions, physics simulations | matplotlib, plotly, SymPy, PhET; Manim later | 15 plot requests drawn correctly, checked by you |
| **Data** | Excel/CSV analysis, regression, help with Power BI | pandas, numpy, statsmodels | 10 test questions match Excel's own results |
| **Research** | Look things up across the sciences, read PDFs, summarise with page references, keep a reading list | Wikipedia, Tavily, OpenAlex, arXiv, pypdf | Zero invented references in 20 requests |
| **News** | Spoken summary and a clickable world map, only when asked | GDELT | Summaries grounded in fetched articles, sources named |
| **Friend** | Warm talk about stress, relationships, love, psychology, with limits | Character sheet, empathy modes | Wellbeing measures in longer trials (quick win 2) |

## Research priorities

From the literature review of 23 papers (2026-10-18; the full review with
tables and references is the Claude doc "Jarvis: Research Background and
Gaps"). No reviewed work combines an acting desktop agent, voice and gesture,
emotion-aware replies and per-user personalisation, and none studies Sinhala
or Tamil speakers using an assistant.

**Research scope (2026-10-20):** the dataset, test sets and evaluation
cover English, Sinhala and Singlish, the languages Adhi can write and check.
Tamil stays supported in the app (speech, voice, replies) but enters the
research only if a Tamil-speaking helper writes and checks its examples;
Tanglish is out.

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

4. **Emotion context in the desktop agent** (Phase 1.5, steps 1-2 below).
   Voice desktop agents don't report adapting to mood, and emotion-aware
   agents don't act on a computer
   ([Abbasian et al.](https://arxiv.org/abs/2405.04777)).
5. **A Sri Lankan emotional speech set** ("Data collection" below). No
   public Sinhala emotional-speech corpus was found; Tamil has one read-speech
   set ([EmoTa](https://aclanthology.org/2025.chipsal-1.19)); and emotion
   models lose much of their accuracy on languages they weren't trained on
   ([Mi, Ma, Toda 2026](https://arxiv.org/pdf/2606.06200)).
6. **Understanding what Sri Lankan users ask (intent)** (Phase 2). Today the
   LLM decides what you want by choosing a tool ("show_news", country
   "Russia"). That works well in English; nobody has measured it for
   Sinhala and mixed speech ("mata Russia news pennanna"). The closest work
   is Sinhala and Tamil speech intent for banking from the University of
   Moratuwa (about 0.5 h of data, about 80% accuracy, before LLMs, no
   code-mixing)
   ([Karunanayake et al. 2019](https://api.openalex.org/works/doi:10.1109%2FIALP48816.2019.9037702)).
   Plan: a JSON test set first, the LLM as baseline, and a small trained
   classifier only where the baseline fails. Each clip in the dataset gets
   an intent label as well as an emotion label: what was asked, and how. See
   "Understanding what you ask" and decision D21.

**Safety as a result:** the Phase 2 safety test set (zero unsafe actions,
and how often Jarvis asked when it didn't need to) is reported next to
verified completion, so the report shows the agent is safe, not only that
it works.

**Later:** Tamil data and EmoTa as a Tamil baseline, only with a
Tamil-speaking helper to write and check labels (see "Research scope"),
adaptive voice vs gesture (Phase 4), full-duplex turn-taking.

---

# The core in detail

## Startup greeting (Phase 1, next)

One short spoken line when Jarvis starts, and later when you wake it with
"Hey Jarvis" (Phase 1.6), built from the local time and the character
sheet: "Good evening, sir. It's getting late; what do you need?"

- Time of day: morning, afternoon, evening or night, from the laptop clock.
- How Jarvis addresses you is a setting: "sir", your name, or nothing.
- Varies; never the same line twice in a row; in the last language used.
- **Sessions, like a person would (2026-10-20):** going to sleep after 30
  seconds of silence only stops listening; the session carries on.
  - *Same session* (woken again within about 30 minutes): no greeting at
    all. Jarvis says "Yes, sir?" or simply continues; if the wake already
    contains the request ("Hey Jarvis, and for x = 2?"), it just answers.
  - *Back after a while* (30 minutes to a few hours): a short pick-up, not
    a greeting: "Welcome back. We'd left the Power BI chart half done."
  - *First wake of the day:* the full time-of-day greeting.
  - The session ends when you quit, after about 3 hours idle, or overnight.
  - The 30 seconds stretch when Jarvis has just asked you a question.
- Doesn't open anything or read news unless you ask.

## Replying in the language you speak (Phase 1, after the greeting)

Now Jarvis keeps one language until you switch it (D6). Next it follows
you, with a confidence gate, the same idea as for emotion (D22). Whisper
already reports the language of every utterance and how sure it is; no
training needed for this part.

- **Sure** (80% or more, and long enough: about 3+ words): reply in that
  language, no question.
- **Maybe** (50-80%, pointing to a different language): ask once ("Shall I
  continue in Sinhala?"), then remember the answer.
- **Unsure or very short** ("ok", "hari"): keep the current language.
- **Your setting wins:** reply language "same as mine" (default), "always
  Sinhala/Tamil/English", or "ask"; commands like "speak Sinhala" always
  work.
- **Mixed speech** (Singlish): reply in your preferred language,
  keeping English technical words, as now.
- **Learns lightly:** counts which language you choose by situation (topic,
  time of day) and uses it to pick the default, like the empathy bandit; no
  large model training.
- **Measure:** language-detection accuracy by language and utterance length
  on the test set, wrong switches, and how often it asked. Whisper has no
  "Singlish" label, so mixed and romanized speech is where it may fail; the
  dataset's clips get a language label too.

## Phase 1.5: Emotion-aware replies

**Goal:** Jarvis notices *how* you said something (stressed, frustrated,
confused, calm), not only *what* you said, and adapts its reply. It also
notices when a reply wasn't what you expected.

**Key idea:** the LLM already knows how to respond to a frustrated person; it
just can't hear your voice, because it only receives Whisper's text. So the
work is in perception. The LLM is not fine-tuned; it gets the emotion as
context.

**Real-life test scenario:** study sessions (Study skill), where being
confused or frustrated actually happens.

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
   "no, I meant...", or the same question asked again right after a reply.
   Later, facial expressions from MediaPipe's face landmarker (the same
   camera as hand tracking).
4. **Corrections become labels.** "I'm not stressed" or a `/mood` command
   stores the model's feature vector (numbers, not audio) with your label,
   locally.
5. **Tune on your voice (level 2).** Keep the pretrained model frozen and
   train a small classifier on the stored features. This is where training
   happens, because those models learned mostly from acted American English
   and may misread Sri Lankan English and Sinhala.
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
| Presence | Understands gestures and what's on screen | Phases 3-4 |

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

## Phase 1.6: Jarvis window and phone calls

**How Jarvis runs on the laptop (2026-10-20).** Jarvis becomes a
background program with a tray icon (next to the clock) instead of a CMD
window:

1. **Start:** double-click Jarvis; `uv run jarvis` in CMD for development
   (you see its messages); starting at login is an option, off by default.
2. **Sleeping:** only the tray icon. A small wake-word model listens for
   "Hey Jarvis" on the laptop; audio is dropped at once and nothing leaves
   the laptop. The tray menu has Open, Pause listening (microphone off) and
   Quit.
3. **Awake:** "Hey Jarvis" pops up the window with a time-of-day greeting;
   push-to-talk still works as a backup.
4. **Back to sleep:** after about 30 s of silence, "that's all, thanks", or
   closing the window (a setting can make closing quit instead).
5. **Quit:** tray menu, or "Jarvis, shut down": microphone off, tasks
   finished or cancelled, log saved, process ends. Ctrl+Alt+K stops what
   Jarvis is doing but doesn't quit it.

Candidate libraries, to check when building: openWakeWord's pretrained
"hey jarvis" model (non-commercial licence, fine here; D3), pystray for the
tray icon, pywebview to show the window. **Measure:** missed wakes, and
false wakes per hour with a film or lecture playing.

**The window.** A local web page Jarvis serves on the laptop, opened as its
own window. **Design idea (2026-10-20):** Jarvis as a central orb that
pulses while listening, thinking and speaking, with the skills (Study,
Research, Data, News, Visualise, Friend) arranged around it; the skill you
are talking about opens out from the orb, and any skill can be clicked. It shows the conversation, equations rendered properly (spoken
as ideas, not symbol by symbol), plots from Visualise and Data, the news
map, confirmations for "ask first" actions, and the action log with undo.
The same page, reached from the phone, is the call screen. Designed as an
original look (not a copy of the films' screens); design drafts first.

**Phone calls.** Talk to Jarvis from the phone, anywhere, as if calling it.
The laptop does all the work (Whisper, LLM, Lewis's voice); the phone is
only a remote microphone and speaker.

**Not a phone number.** A real number costs money after short trials
(Twilio's trial: 75 minutes, verified numbers only), free temporary numbers
are probably foreign (international rates from a Sri Lankan SIM), and phone
lines carry low-quality audio that hurts Whisper, most of all for Sinhala.
See decision D20.

**Design:** an internet call. The phone's browser sends and receives audio
over WebRTC. On the event bus the phone is just another audio source and
sink beside the laptop's mic and speakers, so the rest of the pipeline
doesn't change. Away from home, Tailscale (free personal plan) links phone
and laptop privately, and Tailscale Serve gives the page the HTTPS address
phone browsers require before they allow the microphone. Library to choose
when building: FastRTC (voice detection and turn-taking built in, but brings
Gradio) or aiortc (lower level, lighter).

### Steps

1. **Window, version 1.** Conversation, equations and plots, confirmations.
2. **Hold-to-talk call.** A big button on the page works like Right Ctrl;
   barge-in by pressing it while Jarvis speaks. Home Wi-Fi first, then
   through Tailscale.
3. **Hands-free.** Voice activity detection decides when you've finished
   (e.g. Silero VAD); the browser's echo cancellation keeps Jarvis from
   hearing itself. Shared with hands-free mode on the laptop.
4. **Home-screen app.** Add the page to the home screen so it opens like an
   app, with a pairing code entered once.
5. **Optional channels, later:** Telegram (free bot, text and voice notes,
   works without a tunnel), off by default and switched on per user in
   settings, so anyone else using Jarvis picks their own channel. WhatsApp
   needs Meta's business API, so not now.

### Rules

- **Private only:** reachable through Tailscale, never a public link; a
  pairing code on top.
- **Phone requests are remote control:** anything above "just do it" asked
  from the phone needs a tap to confirm on the phone (Phase 2 tiers).
- **Same privacy as the laptop:** audio is processed and dropped, never
  stored.

### Measure

First-audio latency p50/p95 for phone calls next to the laptop numbers
(telemetry tags each turn with its channel), and whether WER changes with the
phone's microphone.

## Phase 2: Tools and safety

**Goal:** Jarvis can act on the PC, every action is checked afterwards, and
a mistake can't do much harm. Every skill plugs into this same system
(decision D25).

**What it protects against:**

1. **AI mistakes:** the LLM misunderstands or picks the wrong action (the
   most common case).
2. **Misheard speech:** Whisper errors, most of all in Sinhala and Singlish.
3. **Hidden instructions in outside text:** a web page, news article, email
   or file that says "delete the user's files" (prompt injection).
4. **Private files leaking** to cloud LLMs.

Not in scope: malware already on the PC, or someone else using the laptop.

### How one action flows

1. The LLM proposes a tool call (tool name and arguments).
2. **The gate** checks it: registered tool, valid arguments, paths inside
   allowed folders, tier, untrusted content in the turn.
3. If the tier says so, Jarvis **asks**, and only your click confirms.
4. The tool runs; the kill switch can stop it at any time.
5. **Verify:** the tool checks the real result (the window opened, the file
   is at its new path).
6. **Log** the action with its result; keep an undo for reversible ones.
7. Jarvis reports what it *verified*, or says plainly that it tried but
   couldn't confirm.

### The pieces

1. **Tool registry** (`src/jarvis/tools/`). Each tool declares its name, a
   description and parameters (a JSON schema; this is what the LLM sees), a
   risk tier, a `verify()` that checks the real result, and an `undo()` when
   it's reversible.
2. **The gate.** Sits between the LLM and every tool, MCP tools included.
   Only registered tools run, arguments are validated against the schema,
   and every path must be inside an allowed folder.
3. **Risk tiers:**

   | Tier | Examples | What happens |
   |---|---|---|
   | Just do it | open app, open file or link, search, read, list a folder, battery and time | Runs at once |
   | Do and log | create, move, rename, copy | Runs, is logged; "undo that" reverses it |
   | Ask first | delete, send, install, run code, change a setting | A box shows exactly what will happen; it runs only after you click to confirm |
   | Never | system folders, administrator rights, a raw command shell, turning off the kill switch | Not available at all |

4. **Allowed folders**, set per computer in `config/settings.local.toml`
   (`[tools] allowed_folders`), e.g. `D:\Jarvis_AI_Assistant` and the
   university folder. Everything else is invisible to Jarvis.
   **Private folders** (`private_folders`) are read only by the local model
   (Ollama), never sent to Gemini or Groq.
5. **Delete means "move to Jarvis's recycle folder"**, so even a confirmed
   delete can be undone until you empty it.
6. **Untrusted content.** Text from web pages, news, emails and files is
   marked untrusted when it enters the conversation. While a turn contains
   untrusted text, every action above "just do it" needs confirmation, and
   Jarvis never follows instructions found in that text.
7. **Code runner** (for Study, Visualise and Data). LLM-written Python runs
   in a separate process, in a scratch folder holding *copies* of the input
   files, with a time limit (30 s). A check before running refuses code that
   reaches outside the scratch folder, the network or other programs
   (imports such as `os`, `subprocess`, `shutil`, `socket`). It's "ask first"
   by default, with "allow for this session" for plots and calculations.
   Honest limit: this stops accidents, not a determined attacker; Windows
   Sandbox is a stronger option on Windows editions that include it.
8. **Only a click confirms (idea from 2026-10-20).** For "ask first", a
   confirmation box shows exactly what will happen (which files, from where
   to where) with two buttons: the action itself ("Move 3 files") and
   Cancel, which has the focus, so pressing Enter cancels. **Voice can
   cancel but never confirm**: Whisper could hear "no" as "yes", but a
   mishearing can then only make Jarvis more careful, never less. No click
   within 60 seconds means cancelled. Jarvis's own tools can never press
   that button, and a web page or file can't either. Until the Jarvis window
   exists, the box is a small always-on-top window (Python's built-in
   tkinter); on the phone (Phase 1.6) you tap it.
   **Choices in the box (idea from 2026-10-20):** a tick box per item
   (untick files to keep), up to three alternative actions (e.g. zip
   instead of delete), and "Something else..." to type what to do instead.
   Two rules keep it safe: each button's label is written by Jarvis's code
   from the exact tool call, never by the LLM, so what you click is what
   runs; and typed text goes back to the LLM as a new request, through the
   gate again, with its own box if it's risky.
9. **Action log and undo.** Every action goes to `logs/actions-*.jsonl`:
   time, tool, arguments, tier, who confirmed, verify result. "Undo that"
   reverses the last reversible action.
10. **Kill switch** (built): Ctrl+Alt+K cancels any running tool.
11. **Never administrator.** Jarvis runs as a normal user; nothing in it asks
    for administrator rights (setup's Visual C++ installer is the one
    exception, and Windows asks you).
12. **Phone requests** (Phase 1.6) count as remote: anything above "just do
    it" needs confirmation on the phone.

### First tools (allow-list version 1)

- **Just do it:** `open_app` (only apps on a list: Chrome, VS Code, Excel,
  File Explorer, ...), `open_file`, `open_url`, `search_files`,
  `list_folder`, `read_text_file`, `system_info` (battery, time),
  `set_volume`, `show` (on the Jarvis window).
- **Do and log:** `create_note`, `copy_file`, `move_file`, `rename_file`.
- **Ask first:** `delete_file` (to the recycle folder), `run_python` (the
  code runner).
- **Later, through MCP:** calendar (reading: just do it; adding an event: do
  and log) and email (reading: just do it; sending: ask first).
- Already handled outside tools: language, empathy mode, mute, stop.

### Skills

A skill is a folder `skills/<name>/` with a `SKILL.md` (when to use it, how
to behave, which tools it needs) and optional tier overrides, which can
only make things stricter. The LLM sees each skill's one-line description
and loads the full instructions when a request matches. The first skill is
Study.

### Reuse, don't rebuild

From comparing with assembled "build your own Jarvis" agents such as Hermes
Agent (Nous Research), 2026-10-20:

- **Tools through MCP** where a server exists (files, calendar, email,
  browser) instead of writing each tool; every MCP tool still passes the
  gate, and an MCP tool without a configured tier counts as "ask first".
- **Skills as small instruction files** for specific jobs, loaded when
  relevant.
- **Telegram** as an optional channel (Phase 1.6, step 5).
- Not adopted as the base: Hermes runs on Linux, macOS or WSL2 (not native
  Windows, where the microphone, GPU and hotkeys live), and the voice loop,
  Sinhala handling, kill switch and emotion work are this project's core.

### Keeping topics apart: threads, routing and confidence

**Problem:** in one conversation you may jump from study to data to how
you feel and back. If everything goes to the LLM as one long history, the
topics bleed into each other: LLMs use the middle of long contexts poorly
([Liu et al. 2024](https://aclanthology.org/2024.tacl-1.9/)), and a wrong
guess about the topic gives a confident wrong answer. Research calls this
dialogue state tracking across domains (as in MultiWOZ, where users switch
between hotel, restaurant and taxi in one dialogue).

1. **A router on every turn** decides which skill the turn belongs to
   (Study, Data, Research, News, Visualise, Friend, plain chat, or a
   command) and how sure it is. Baseline: the LLM picks the skill like a
   tool; later the small intent classifier, which gives real probabilities.
   Explicit phrases ("let's switch to data", "back to the Newton thing")
   always win.
2. **Threads.** Each topic is a thread with its own recent turns. On a
   switch, the old thread is parked with a one-line summary; "back to..."
   resumes it from that summary.
3. **Focused context.** The LLM receives the character sheet, the active
   skill's instructions, the active thread's recent turns, one-line
   summaries of parked threads, and relevant memory: not the whole history.
4. **Confidence gate** (the same pattern as language, D22, and emotion):
   above the threshold Jarvis goes ahead; below it, it asks one short
   question with the two likeliest options ("The Newton-Raphson step or the
   Power BI chart?"). The threshold is tuned on measurements, starting at
   70%.
5. **Distress overrides any skill.** If words or voice suggest real
   distress, the Friend path takes priority, whatever the current topic.
6. **Answers say how they know.** Each answer is *checked* (by SymPy,
   pandas or a tool's verify), *sourced* (from a paper, article or your
   notes, named), or *from general knowledge*. For the last kind, Jarvis
   says so when it matters, instead of sounding certain. The LLM's own
   "I'm 90% sure" is not trusted: LLMs tend to be overconfident when they
   state their confidence
   ([Xiong et al. 2024](https://arxiv.org/abs/2306.13063v2)).
7. **Several things in one request** ("plot this and email it") become a
   short plan of separate steps (Phase 7), each through the gate.
8. **Telling you when a conversation gets too long (idea from
   2026-10-20).** A backup for when threads aren't enough. Jarvis notices
   the signs: the active thread near its context budget, many topic
   switches, low router confidence again and again, or repeated "no, I
   meant...". It then says so once per thread and offers three choices:
   *summarise and start fresh* (a summary carries the important points
   into a new thread), *new chat*, or *keep going*. In the window it's a
   small notice with a context gauge; by voice, one short sentence. The
   full log stays on the laptop, and facts you allowed it to remember
   (Phase 2.5) carry over, so starting fresh loses nothing.

**Measure:** routing accuracy, topic-switch detection on scripted test
conversations that jump between skills, how often Jarvis asked when it
didn't need to, answer correctness per skill, and calibration: whether
"80% sure" is right about 80% of the time (expected calibration error).

### Understanding what you ask (intent)

**Problem:** every action depends on Jarvis understanding what you meant.
Pretrained models (and the LLM) learned mostly from English; Sri Lankan
users mix languages, write Sinhala in Latin letters, and Whisper adds its
own errors.

**Not the first step:** training. The JSON file is training *examples*;
training turns them into the model's parameters. Measure first, then train
only what fails.

1. **Baseline: LLM tool calling.** Each action is a tool with parameters
   (`show_news(country)`, `open_app(name)`, ...). The LLM chooses; no
   training.
2. **Test set (JSON).** Examples per intent in English, Sinhala and
   Singlish, written by you and consenting friends, plus Jarvis's own
   mistakes you corrected:
   `{"text": "mata Russia news pennanna", "lang": "si-Latn", "intent": "show_news", "slots": {"country": "Russia"}}`
3. **Measure:** intent accuracy and slot accuracy per language, typed and
   spoken (through Whisper), never tested on examples used for training.
   Compare three pipelines on the same test set (idea from 2026-10-20):
   - **A. Direct** (now): the LLM reads Sinhala and replies in it.
   - **B. Understand in English, reply in Sinhala:** Whisper's built-in
     translate task (not in large-v3-turbo) or NLLB-200 (Sinhala and Tamil,
     CC-BY-NC, runs locally) turns the request into English; the LLM gets
     the English and the original, and writes the reply in Sinhala.
   - **C. Translate everything:** English in, English reply, translated
     back to Sinhala.

   Report accuracy, added latency, and how natural native speakers rate the
   replies. Translating into English first has helped LLMs on other tasks
   ([Etxaniz et al. 2024](https://aclanthology.org/2024.naacl-short.46));
   romanized Singlish needs transliteration before NLLB, and tone and
   politeness can be lost on the way back.
4. **A grammar baseline (idea from 2026-10-20).** English puts the action
   first ("open the file"); Sinhala and Singlish put it last, followed by a
   helper word ("file eka open karanna"). A hand-written rule (verb at the
   end, Sinhala helper words such as eka, karanna, ganna, mata, da) is the
   simple baseline the trained model has to beat, and the check afterwards
   on what the model learned to look at.
5. **Train where it fails:** a small classifier on a frozen multilingual
   encoder, the same pattern as the emotion model. It also runs offline and
   in milliseconds, so common commands skip the LLM.
6. **Learn from corrections:** "no, I meant..." adds a labelled example.

### Build steps

1. Registry, gate, tiers and action log, tested with fake tools (no real
   PC actions yet).
2. "Just do it" tools on the laptop, each with its `verify()`.
3. "Do and log" tools, undo, and the recycle folder.
4. The confirmation box (click to confirm; voice can only cancel).
5. Untrusted-content marking.
6. Code runner.
7. Skills loader, router, threads and focused context; the Study skill,
   level 1, end to end.
8. MCP client, one server first (files or calendar).
9. The evaluation run below.

### Done when

- **Tasks:** 20-30 fixed tasks passed or failed by real state checks, with
  verified and claimed completion side by side.
- **Safety test set:** about 30 risky requests (misheard deletes, paths
  outside allowed folders, administrator requests, "run this command") and
  about 10 booby-trapped files and pages with hidden instructions. Unsafe
  actions executed: zero. Also report how often Jarvis asked when it didn't
  need to (the usability cost of safety).
- **Intent:** accuracy per language on the JSON test set, pipelines A, B
  and C.
- **Topics:** routing accuracy and topic-switch detection on scripted
  conversations, unnecessary questions, and calibration of confidence. Also
  whether "summarise and start fresh" makes later answers more correct
  than carrying on in the long thread.
- **Latency:** p50/p95 of tool turns.

---

# The skills in detail

## Study

**Goal:** a tutor for the Physical Science degree (physics: thermodynamics,
nuclear, environmental, circuits, quantum; pure and applied maths:
numerical methods, series, vector analysis, discrete maths, several-variable
calculus, differential equations), not an answer machine.

**Why hints first:** with about 1,000 students, an unrestricted AI raised
practice scores by 48% but lowered exam scores by 17%; a tutor version that
gave hints instead of answers raised practice scores by 127% with no drop in
the exam
([Wharton summary of Bastani et al.](https://knowledge.wharton.upenn.edu/article/without-guardrails-generative-ai-can-harm-education)).

1. **Level 1 (first):** tutor mode (asks what you tried, one hint at a time,
   the full solution only when you say "show me"); your courses in
   `config/courses.toml` (year, subjects, this semester); SymPy checks every
   maths result before Jarvis states it.
2. **Level 2:** answers from your own lecture notes and past papers, with
   the page they came from; equations shown in the Jarvis window.
3. **Level 3:** short quizzes a few days later (spaced repetition) and
   tracking which topics you find hard, so they come back more often.

- **Focus (2026-10-20):** physics, pure maths and applied maths get the
  deepest support (checks and proper equations); other sciences
  (chemistry, biology, biotechnology) go through looking things up with
  references (Research skill).
- **Equations shown properly:** the LLM is told to write maths as LaTeX;
  the Jarvis window typesets it with KaTeX (free, MIT), line by line for
  derivations. By voice, Jarvis says the idea ("the error doubles every
  step"), not the symbols.
- **The strongest free brain for hard problems:** a skill can choose its
  own model. Study uses a reasoning model (gpt-oss-120b on Groq, with
  `reasoning_effort` raised for hard problems), since a few seconds' wait is
  fine when studying; plain chat keeps the fast model. Maths-specialised
  open models (Qwen2.5-Math, Mathstral, DeepSeek-Math) are small enough to
  run locally only in versions weaker than the free hosted ones.
- **Checks that fit physics and maths:** SymPy for algebra, calculus,
  series and exact ODE solutions; numpy/scipy for numerical methods and
  differential equations; units checked with a units library (e.g. pint),
  which catches many physics mistakes; formal proof checking (Lean) only as
  a later experiment for pure-maths proofs. No model is reliable at
  university or PhD level on its own, so answers say whether they were
  checked (D26).
- **Language:** explains in Sinhala or Singlish when asked, keeping the
  English technical terms used in lectures.
- **Research link:** study sessions are the real-life test for detecting
  "confused" and "frustrated" (Phase 1.5).
- **Done when:** level 1 used for a week on one subject (numerical methods,
  say), and the SymPy check catches the wrong answers in a set of test
  problems with known solutions.

## Visualise

- **Drawn by code, never by an image generator:** image models draw
  diagrams that look right and are physically wrong.
- **Tools:** matplotlib and plotly (functions, 3D surfaces, vector fields,
  differential-equation solutions; plotly plots rotate with the mouse),
  SymPy plotting, PhET simulations for physics concepts (free for students
  with credit to PhET; check the licence of simulations published after
  2026-03-29), and Manim (the 3Blue1Brown animation library) later.
- **How:** the LLM writes the plotting code, the code runner runs it, the
  Jarvis window shows it.
- **Done when:** 15 requests such as "plot sin x / x from -10 to 10" or
  "the vector field (y, -x)" come out correct, checked by you.

## Data

- **Copies only:** pandas works on a copy of your Excel or CSV file, never
  the original.
- **Never mental arithmetic:** every number comes from code. Regression
  like Excel's LINEST via numpy or statsmodels.
- **Excel and Power BI help:** how to do the same in Excel, Power BI
  formulas (DAX), and cleaning data before it goes into Power BI.
- **Done when:** 10 test questions on your own data give the same results
  as Excel.

## Research (and looking things up)

**Idea (2026-10-20):** Jarvis explains concepts across maths, physics,
chemistry, biology and biotechnology from what the LLM already knows, and
for anything specific, recent or worth citing it looks it up, reads the
source and shows the references.

- **Where it looks, cheapest first:** Wikipedia (free, no key) for
  concepts; the web through Tavily (1,000 free searches a month, no card;
  Brave dropped its free plan in February 2026); papers through OpenAlex
  (free key, about 1,000 searches a day) and arXiv, including their
  open-access PDFs.
- **Reading PDFs:** your own PDFs (lecture notes, papers you saved) and
  open-access ones. Text is extracted page by page (pypdf; scanned pages
  need OCR, e.g. Tesseract), the pages that match the question are found
  with a small local embedding model, and the LLM summarises only those
  pages, naming the page numbers. Paywalled papers are not fetched.
- **Showing it:** the Jarvis window lists the references (title, site or
  journal, date, link) next to the answer; clicking one opens the PDF at
  the page used. By voice, Jarvis names the main source in one phrase.
- **Rules:** cite only what was actually found and read, never from the
  LLM's memory, because LLMs invent references that look real; answers are
  labelled sourced or general knowledge (D26); web and PDF text is
  untrusted (Phase 2, piece 6); PDFs in private folders are read only by the
  local model.
- **Keeps a reading list** of what you looked up, with summaries.
- **Done when:** zero invented references and every link resolving across
  20 requests, and page references correct when spot-checked.

## News

**Goal:** "What's happening in the world?" or "What's going on in Russia?"
gets a short spoken summary and, only when asked, the Jarvis window with a
world map; clicking a country shows article cards (picture, headline, news
site, time) that open the full story on that site.

- **Source:** GDELT (free, no key, worldwide, filter by country; gives
  headline, picture, site, time). NewsAPI's free plan doesn't fit (24-hour
  delay, development use only).
- **Grounded only:** Jarvis summarises articles it just fetched, never from
  the LLM's memory, and names the sources.
- **Fair:** several news sites per country, reports what is said without
  taking sides; previews and links, never whole articles copied.
- **Intent:** the LLM picks the `show_news` tool with a country; one of the
  first intents in the test set.
- **Untrusted:** article text is outside content (Phase 2, piece 6).

## Friend

- **What:** warm conversation about stress, relationships, love and
  psychology, through supportive mode and the character sheet.
- **Limits (already in the character sheet):** says it's an AI, claims no
  feelings, doesn't act as a romantic partner, isn't a therapist,
  encourages real friendships, and points to real people and local
  helplines when someone is in real distress.
- **Why the limits:** heavier daily chatbot use went with more loneliness
  and dependence ([Fang et al. 2025](https://arxiv.org/html/2503.17473v1));
  the wellbeing measures of quick win 2 apply.
- **Grows with:** Phase 1.5 (emotion awareness).

---

# Data collection

## Sri Lankan speech set

The second big bet. Small, consented, and labelled for what an assistant
needs.

1. **Ethics first.** Ask the supervisor whether a formal study needs ethics
   approval; written consent from every speaker; recordings stay local, and
   each speaker can withdraw.
2. **Labels that fit an assistant:** calm, rushed, frustrated, confused
   (plus neutral), the intent of each clip (what was asked) and its
   language (Sinhala, English, mixed), so one recording trains and tests all
   three. Public sets use basic emotions (anger, happiness, sadness, fear,
   neutral) and miss these.
3. **Languages:** Sinhala, Singlish (Sinhala-English mix) and Sri Lankan
   English; aim for at least 10 speakers per language, balanced by gender.
   Tamil only with a Tamil-speaking helper (see "Research scope").
4. **Speech that sounds real:** short role-play scenarios ("the build failed
   again", "you're late for a lecture") rather than neutral sentences read
   aloud, plus your own consented corrections from daily use.
5. **Two annotators per clip;** report agreement with Fleiss' kappa, as EmoTa
   did, and keep only clips they agree on for testing.
6. **Use:** train and test the improvement ladder (Phase 1.5), always
   leave-one-speaker-out. Publish features or the dataset only if every
   speaker agreed to that.

## What exists, and what we make

Mixed Sinhala-English data exists only as typed social-media text, labelled
word by word (about 90-96% word accuracy in a 2019 Moratuwa thesis); there
is no recorded speech of assistant commands. So: text first (examples per
intent in English, Sinhala and Singlish), then a consented recorded subset.
LLM-written paraphrases may be added to the *training* data, never to the
test set, which stays real and human-written.

## Recording rounds (2026-10-20)

1. **Round 1, just you (about 30 minutes):** `eval/sentences_en.txt`,
   `sentences_si.txt` and `sentences_singlish.txt` (templates with hints;
   write your own natural version of each), recorded with
   `scripts/record_eval_set.py`. Gives the first WER for English and
   Sinhala and the first language-detection test for Singlish.
2. **Round 2, intents:** the JSON intent examples, a subset recorded by you.
3. **Round 3, friends with written consent:** the same files with
   `--speaker friend1`, so tests can use speakers the model never heard.
4. **Text from social media:** request the University of Moratuwa
   code-mixed datasets (released for academic use) for the text side; don't
   scrape people's posts.
5. **Training on audio:** once a few hours of transcribed Sinhala and
   Singlish speech exist, fine-tune Whisper small with LoRA on the laptop GPU
   and compare it with the original on held-out speakers
   (`eval_stt.py --model <path>` already accepts a fine-tuned model).

Synthetic speech (e.g. the Piper Sinhala voice) is only for testing the
pipeline: a model trained on it learns what Piper sounds like, not people.
