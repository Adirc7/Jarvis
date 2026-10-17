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
**Why:** All four speak the same API, so one class covers them. Switching
mid-reply would produce a garbled answer.
**Privacy:** free hosted tiers may use prompts to improve their products. Don't
send screen contents with private data; route those requests to Ollama later.

## D3. Activation: push-to-talk first (10.2)
**Decision:** Hold a hotkey to talk (Phase 1). Add openWakeWord's pretrained
"hey jarvis" model later (its licence allows non-commercial use only, which is
fine here).
**Why:** Simplest, no always-on audio processing, nothing to tune.

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
(`voice/tts.py`). English uses Kokoro's British voice `bm_george` by default.
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
