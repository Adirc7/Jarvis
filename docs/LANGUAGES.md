# Languages

Jarvis has one active language at a time. Switching changes three things
together, so they never disagree:

| Stage | What changes |
|---|---|
| Speech-to-text | the language Whisper transcribes in (and which Whisper model) |
| LLM | the instruction "always reply in Sinhala, in Sinhala script" |
| Text-to-speech | the voice |

## How to switch

1. **Say it**: "switch to Tamil", "speak Sinhala please", "සිංහලෙන් කතා කරන්න",
   "தமிழில் பேசு", "ඉංග්‍රීසියෙන් කතා කරන්න" (back to English).
2. **Type it** in the text chat: `/lang si`, `/lang ta`, `/lang en`.
3. **Later**: a dropdown in the Electron UI (Phase 2), and a `set_language`
   tool the LLM can call for phrasings the rules miss.

Jarvis confirms in the new language, so a wrong switch is obvious and easy to
undo.

## The rules (src/jarvis/language.py)

A short utterance (up to 10 words) switches language when it contains:

- a **command word** (speak, talk, reply, answer, respond, switch, change,
  කතා, මාරු, பேசு, மாற்று, ...) **and**
- **exactly one** language name (english, sinhala, සිංහලෙන්, தமிழில், ...).

"say" and "translate" are not command words, so "translate this to Tamil" and
"how do you say thanks in Sinhala" are normal requests. Naming two languages
("translate English to Tamil") is also a normal request. All words live in
`config/languages.toml`, so you can tune them without touching code.

Text is normalised first: lowercase, zero-width joiners removed (Sinhala
"ඉංග්‍රීසි" is written with one, and STT may drop it), punctuation removed by
Unicode category. A regex like `[^\w\s]` would break Sinhala and Tamil,
because `\w` doesn't match their vowel signs.

## Getting back out of a language

In Sinhala mode Whisper is told to expect Sinhala, so an English "switch to
English" can come out as garbage. The voice pipeline (Phase 1) therefore also
reads Whisper's language detection for every utterance. If Whisper hears
another language Jarvis knows with probability >= 0.80
(`[stt].retranscribe_threshold`), it transcribes again in that language and
checks for a switch command. The `/lang` command and the hotkey/UI always work
as a fallback.

## Quality: what to expect

| | English | Tamil | Sinhala |
|---|---|---|---|
| Whisper (base models) | good | usable, test it | weak |
| TTS | Piper `en_US-lessac-medium` | MMS-TTS `facebook/mms-tts-tam` (or community Piper voice) | Piper `si_LK-dilu-medium` (community, MIT) |
| Free hosted LLMs | good | usually fine | varies: the smoke test checks for Sinhala script |
| Local Ollama (4B) | fine | weak | weak: use a hosted model for Sinhala |

**Sinhala speech recognition is the hardest part.** One community fine-tune
(`hlasith/whisper-sinhala-small`) reports base Whisper-small at 131% WER and
the fine-tune at 62% WER / 15% CER, measured on only 10 samples, so treat those
numbers as a hint, not a result. Measure it yourself (below).

## Using a fine-tuned Sinhala Whisper with faster-whisper

faster-whisper needs models in CTranslate2 format. Convert a Hugging Face
fine-tune once (this needs `transformers` and `torch`, only for the conversion):

```powershell
uv pip install transformers torch
uv run ct2-transformers-converter --model hlasith/whisper-sinhala-small `
    --output_dir models/whisper-si-small-ct2 --quantization float16
```

Then in `config/languages.toml`, under `[si]`:

```toml
stt_model = "models/whisper-si-small-ct2"
```

Check each model's licence: that one is released for research and educational
use, which fits a self-study project.

## Measuring it yourself (this is also research data)

Record 20 short sentences per language that you'd really say to Jarvis
("open Chrome", "make this bigger"), write down the correct text, and compute
WER/CER for each candidate model. Store the text and the scores, not the
audio, unless the speaker agreed to keep it. This turns "Sinhala is weak" into
a measured number for your report.

## Mixed language (Singlish)

Sri Lankan speech often mixes Sinhala and English in one sentence. Whisper
handles that poorly in either mode. An option to try in Phase 1: Whisper's
`task="translate"`, which turns any language into English text. Jarvis
understands the request in English, and the LLM still replies in the active
language.
