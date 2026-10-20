# Design decisions

One entry per decision: what, why, and when to revisit. These resolve the open
items in section 10 of the implementation plan.

## D1. Free tools only
**Decision:** No paid services. Hosted LLMs on free tiers, with local Ollama as
the last fallback. Speech and vision run locally.
**Why:** Project constraint. Free tiers change without notice (Google moved its
Pro models to paid in 2026), so no single provider is load-bearing.
**Revisit:** if every free tier becomes too rate-limited for daily testing.

## D2. LLM access through one OpenAI-compatible client with fallback (10.6)
**Decision:** Gemini, Groq, OpenRouter, Ollama, in that order
(`[llm].order`). Fallback only before the first word of a reply.
**Update (2026-10-20):** added OpenAI's open-weight gpt-oss-120b on Groq's
free tier (`groq_oss`, same key, its own limits). Providers can pass extra
request fields (`options`). Claude isn't included: it has no free API and no
open weights; "Claude" models on Hugging Face are other models imitating it.
**Update (2026-10-21, first laptop run):** Groq retired llama-3.3-70b-versatile
on 2026-08-16 (its replacement advice: gpt-oss), and OpenRouter's Llama 3.3
stopped being free. Now: Gemini, Groq gpt-oss-20b (fast), Groq gpt-oss-120b,
OpenRouter Gemma 4 31B (free), Ollama. Thinking models get
`reasoning_effort = "low"`: Gemini took 7 s to its first word without it.
Second run: Groq's gpt-oss-120b and gpt-oss-20b answered in 0.22 and 0.32 s
with tools, Sinhala and Tamil all working; Gemini returned 503 (overloaded)
and OpenRouter's Gemma 4 returned 429. New order, fastest first: groq_oss,
groq, gemini, openrouter (now the `openrouter/free` router), ollama.
**Why:** All four speak the same API, so one class covers them. Switching
mid-reply would produce a garbled answer.
**Privacy:** free hosted tiers may use prompts to improve their products. Don't
send screen contents with private data; route those requests to Ollama later.

## D3. Activation: push-to-talk first (10.2)
**Decision:** Hold a hotkey to talk (Phase 1). Add openWakeWord's pretrained
"hey jarvis" model later (its licence allows non-commercial use only, which is
fine here).
**Why:** Simplest, no always-on audio processing, nothing to tune.
**Update (2026-10-20):** "Hey Jarvis" is planned with the Jarvis window
(Phase 1.6): Jarvis runs in the background with a tray icon, sleeps
listening only for its name, and wakes the window with a time-of-day
greeting. Push-to-talk stays as a backup.

## D4. Concurrency: threads produce, asyncio consumes (10.3)
**Decision:** Mic, camera and OS watchers run in their own threads and publish
typed events to an asyncio event bus. Each consumer has its own queue. High-rate
gesture streams drop the oldest event; transcripts and kill-switch events are
never dropped.
**Why:** The LLM call must never freeze gesture tracking.
**Revisit:** if the smoke test's "tracking during whisper" check shows a big
FPS drop, move camera capture into its own process.

## D5. Kill switch from Phase 0 (10.4)
**Decision:** `Ctrl+Alt+K` from any app bumps the cancel generation. Every
long-running job checks its CancelToken and stops.
**Why:** Safety that's added at the end tends to have gaps. Built first, every
module inherits it.
**Next:** risk tiers in Phase 2 (read-only: automatic; reversible: automatic and
logged; irreversible: confirm first), and treating web page text as untrusted.

## D6. Language: one active language, switched by rules (new)
**Decision:** `language_mode = "fixed"`. Switch by voice command, `/lang`, or
UI. See LANGUAGES.md.
**Why:** Auto-detecting the language of every short command is unreliable,
especially for Sinhala. A deterministic rule is testable.
**Update (2026-10-20):** to be replaced by D22, following the user's
language only when Whisper is confident.

## D7. Data handling (10.5)
**Decision:** No audio or video persisted beyond the current utterance or
frame. Gesture datasets store landmark numbers, not video.

## D8. Latency target (10.1)
**Decision:** Under 1.5 s from end of speech to the first audio of the reply,
for simple questions. Report p50 and p95 from telemetry, never only the mean.

## D9. Python 3.12 with uv
**Decision:** `.python-version` pins 3.12; `uv sync --all-extras` builds the
environment.
**Why:** faster-whisper, MediaPipe and pywinauto all support it, and uv makes
the setup one command.

## D10. Voices: Kokoro for English, Piper for Sinhala, MMS for Tamil (Phase 1)
**Decision:** One engine per language behind a single interface
(`voice/tts.py`). English uses Kokoro's British voice `bm_lewis`, chosen after comparing all four British male voices with and without the effects chain.
**Why:** Kokoro sounds the most natural of the free local options; Piper and
MMS cover the languages Kokoro doesn't.
**Not doing:** cloning a real actor's voice. Jarvis gets its own voice plus an
effects chain (D11).

## D11. A "Jarvis feel" through production, not imitation
**Decision:** Every reply goes through a light chain (high-pass, warmth,
presence, compression, faint chorus, small room reverb), then loudness
matching to -20 dB RMS so all three languages sound equally loud.
**Why:** Most of what makes an assistant voice sound polished is processing.
All of it is adjustable in `[voice_style]`.

## D12. Speak while the reply is still being written
**Decision:** The LLM stream is cut into sentences (`voice/text_split.py`).
The first chunk goes to TTS as soon as it's 12 characters and ends a
sentence; later chunks are at least 40 characters so speech isn't choppy.
TTS runs on one worker thread; the player queues chunks.
**Why:** Waiting for the whole reply would add seconds of silence (plan 10.1).
**Measured:** in the build container (CPU only, fake STT and LLM), first audio
came 0.66 s after transcription. Real numbers come from your laptop's logs.

## D13. Push-to-talk on one held key, mic stream always open
**Decision:** Hold Right Ctrl to talk. The input stream stays open so the first
syllable isn't clipped, but frames are kept only while the key is down.
Pressing the key while Jarvis speaks interrupts it (barge-in).
**Why:** No always-on listening, no echo problem (Jarvis never records itself),
and a natural way to interrupt.

## D14. Emotion awareness through perception, not LLM fine-tuning (Phase 1.5)
**Decision:** Add a speech emotion model beside Whisper and pass its label
and confidence to the LLM as context. Tune only the emotion classifier, on
your own voice, using your corrections as labels. Don't fine-tune the LLM.
**Why:** The LLM already knows how to respond to emotions; what it lacks is
the signal, because transcription removes tone. Free hosted LLMs can't be
fine-tuned, and a small classifier on frozen features fits the RTX 4050.
**Rules:** local only, no stored audio, can be switched off, hedge instead of
asserting. Details in ROADMAP.md.

## D15. A written character sheet, and an honest one
**Decision:** Jarvis's personality, speaking style, limits and current
abilities live in `config/persona.toml` and are built into every prompt,
with the local date and time.
**Why:** A consistent character is the biggest single step toward feeling
human, and a file makes it easy to tune and to compare versions in tests.
**Rules:** Jarvis says it's an AI when asked, doesn't claim feelings,
doesn't flatter, isn't a therapist, and never promises abilities it doesn't
have yet (the `cannot_yet` list is updated each phase).
**Update (2026-10-20):** the character now follows the classic composed
personal assistant Adhi asked for: addresses him as "sir" (a setting),
reports precisely what it did and checked, offers the next step in one
line, warns once when something is unwise and then respects the decision,
greets once per session and otherwise picks up where it left off. Written in
our own words: no film lines or catchphrases.

## D16. Empathy modes: manual now, learned later
**Decision:** Three modes (logical, balanced, supportive) switchable by
command or phrase; each sets an LLM instruction and a voice speed. A
contextual bandit will later learn the user's preferred mode per emotional
state, inside user-set limits.
**Why:** The LLM can already write in any style; what it can't know is which
style this user prefers. Learning that preference is cheap and personal.

## D17. Fillers only when the reply is slow
**Decision:** Short, pre-rendered fillers ("Mm.", "One moment.") play if no
real speech has started 0.7 s after the LLM request; at most one per turn,
never the same one twice in a row, never when muted.
**Why:** People cover thinking time the same way; silence longer than about a
second sounds like a broken assistant. Telemetry marks fillers separately so
`first_audio` still measures the real reply.

## D18. Research priorities from the literature review
**Decision:** Do three quick wins first (verified vs claimed completion,
Godspeed and usability plus wellbeing measures in every study, a
feedback-only empathy bandit), then the two big bets that form the
contribution: emotion context in the desktop agent, and a small consented
Sri Lankan emotional speech set with assistant labels.
**Why:** A review of 23 papers (2026-10-18) found no work combining an acting
desktop agent with emotion-aware replies and per-user empathy, no public
Sinhala emotional-speech corpus, and large accuracy drops for emotion models
on unseen languages. Details and references in ROADMAP.md, "Research
priorities".

## D19. One-click setup on Windows; per-computer settings kept apart
**Decision:** `Setup Jarvis.cmd` runs `scripts/setup_windows.ps1`, which
installs everything, asks only what a script can't know (LLM keys, whether
the keyboard has a Right Ctrl), runs the tests and creates shortcuts.
Settings that belong to one computer go in `config/settings.local.toml`,
merged over `settings.toml` and not committed. When the project is on
another drive than Windows, the large downloads follow it there (the uv
cache must share the project's drive, or every package is copied twice).
**Why:** Setup steps typed by hand get skipped or done in the wrong order,
and a hand-edited `settings.toml` conflicts with every `git pull`. The script
is safe to rerun, so "run setup again" is the answer to both updating and
repairing.
**Checked before the first install:** every dependency resolves to a Windows
wheel for Python 3.12 (nothing compiles on the laptop), and no file is opened
without an explicit encoding, so Sinhala and Tamil text doesn't depend on the
Windows code page.
**Revisit:** if Jarvis is ever installed on a computer that isn't a
developer's, package it properly (an installer) instead.

## D20. Phone access through an internet call, not a phone number (Phase 1.6)
**Decision:** The phone opens a page served by Jarvis and talks to it over
WebRTC, through Tailscale when away from home. No telephone number.
**Why:** Free (D1); full-quality audio instead of phone-line audio, which
matters for Whisper in Sinhala and Tamil; and it reuses the whole voice loop,
since the phone is only another audio source and sink. Phone numbers cost
money after short trials and free temporary ones are likely foreign.
**Rules:** private network only, pairing code, confirmation for anything
beyond read-only once tools exist.
**Revisit:** if calling from an ordinary phone line without internet becomes
a real need.

## D21. Intent: LLM tool calling first, a trained classifier only where it fails
**Decision:** Jarvis decides what you want through LLM tool calling. A JSON
test set in English, Sinhala and Singlish measures it; a
small classifier on a frozen multilingual encoder is trained only for the
intents and languages where the baseline fails, or for speed and offline
use.
**Why:** The LLM already handles English intents without training. The
open question, and the research gap, is Sri Lankan and code-mixed commands:
prior Sinhala and Tamil intent work covered banking only, with about half an
hour of speech and no LLMs (Karunanayake et al. 2019). Measuring first keeps
the result honest and the training small.
**Revisit:** if the test set shows the LLM failing broadly, train earlier.

## D22. Reply in the language the user speaks, gated by confidence
**Decision:** Jarvis replies in the detected language when Whisper is at
least 80% sure and the utterance is long enough; asks once when a change is
likely but uncertain (50-80%); otherwise keeps the current language. A user
setting (same as mine, always one language, or ask) and explicit commands
override it.
**Why:** Asking before every answer would be tiring, and switching on every
guess would flip languages on short words like "ok". A confidence gate
asks only when it matters, and the user's answers become the data for a
small preference learner.
**Revisit:** thresholds after measuring detection accuracy by utterance
length on the test set.

## D23. Research scope: English, Sinhala and Singlish
**Decision:** Datasets, test sets and evaluations cover English, Sinhala
and Singlish. Tamil stays in the app but joins the research only with a
Tamil-speaking helper; Tanglish is dropped.
**Why:** Labels are only as good as the person checking them. Adhi speaks
Sinhala and English and can judge Singlish; he can't judge whether Tamil or
Tanglish examples are right, and wrong labels would make the results
meaningless.
**Revisit:** if a Tamil-speaking classmate or friend agrees to help.

## D24. One core plus skills
**Decision:** Jarvis is a core (voice, languages, emotion, memory, safety,
the tool system) plus skills (Study, Visualise, Data, Research, News,
Friend). A skill is an instruction file plus the tools it needs, running on
the Phase 2 tool system. The roadmap starts with an explicit build order.
**Why:** Every new idea fits the same pattern: the LLM decides, a free tool
gets real results, Jarvis shows the source or the check. Building that
platform once makes each skill small, and keeps the research (emotion,
Sinhala and Singlish, verified and safe actions) in the core instead of
spread across features.
**Revisit:** if a skill needs something the tool system can't express.

## D25. Phase 2 safety: a gate, risk tiers, no raw shell
**Decision:** Every tool call, MCP tools included, passes one gate:
registered tools only, schema-checked arguments, allowed folders only, and
four risk tiers (just do it; do and log with undo; ask first, confirmed
only by a click; never). Voice can cancel an "ask first" action but never
confirm it (2026-10-20, Adhi's idea), so a misheard "no" can't become a
yes. No raw command shell. Deletes go to a recycle folder. Text
from outside (web, news, email, files) is untrusted: while it's in the
turn, anything above "just do it" needs confirmation. LLM-written code runs
on copies in a scratch folder with a time limit and an import check. Private
folders go only to the local model. Every action is verified and logged.
**Why:** The AI will make mistakes and Whisper will mishear; the design
makes those mistakes cheap. Prompt injection is the main outside threat for
an agent that reads the web. Measuring it (zero unsafe actions on a safety
test set, plus how often Jarvis asked unnecessarily) turns safety into a
result.
**Limits:** the code runner stops accidents, not a determined attacker;
malware already on the PC is out of scope.

## D26. Topics in threads, a router with a confidence gate, answers that say how they know
**Decision:** A router assigns every turn to a skill with a confidence;
each topic is its own thread, parked with a summary when you switch and
resumed on "back to..."; the LLM sees only the active thread, the skill's
instructions and short summaries of the rest. Below the confidence
threshold Jarvis asks one short question. Distress overrides any skill.
Answers are labelled checked, sourced, or from general knowledge.
**Why:** One long mixed history makes topics bleed into each other and
LLMs use long contexts poorly; guessing the topic wrongly gives confident
wrong answers. The confidence gate is the same pattern as for language and
emotion, and LLMs' self-reported confidence is overconfident, so certainty
comes from checks and sources instead.
**Addition (2026-10-20, Adhi's idea):** when a thread still grows too long
or confused, Jarvis says so once and offers to summarise and start fresh,
start a new chat, or keep going.
**Revisit:** the 70% threshold, once routing is measured.
