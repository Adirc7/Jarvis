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
| TTS | Kokoro `bm_lewis` (British), "Jarvis" | MMS-TTS `facebook/mms-tts-tam` (or community Piper voice) | Kokoro `bf_emma` with eSpeak Sinhala, "Friday" (Piper `si_LK-dilu-medium` as the alternative) |
| Free hosted LLMs | good | usually fine | varies: the smoke test checks for Sinhala script |
| Local Ollama (4B) | fine | weak | weak: use a hosted model for Sinhala |

**Sinhala speech recognition is the hardest part.** One community fine-tune
(`hlasith/whisper-sinhala-small`) reports base Whisper-small at 131% WER and
the fine-tune at 62% WER / 15% CER, measured on only 10 samples, so treat those
numbers as a hint, not a result. Measure it yourself (below).

## Sinhala speech: a Whisper trained on Sinhala

Base Whisper can't write Sinhala: on 4 Nov "small" wrote only "වවවවවව..." for
every Sinhala question (Jarvis rightly said he couldn't make it out). In
Sinhala, Jarvis now listens with `models/whisper-si-large-v3`: Whisper
large-v3 fine-tuned on Sinhala (`kasunw/whisper-large-v3-sinhala`,
Apache-2.0), converted for faster-whisper by `itsskofficial`. Its author
measured about 35% of letters wrong on Spoken Dakshina, where large-v3 gets
almost all wrong, so it still misses words: the model usually understands
anyway. It's about 3 GB on disk and 1.5 GB of graphics memory, loaded when
Jarvis switches to Sinhala. Download it once, from the Jarvis folder:

```
set HF_HOME=D:\hf-cache
uv run python -c "from huggingface_hub import snapshot_download; snapshot_download('itsskofficial/livewhisper-si-large-v3', local_dir='models/whisper-si-large-v3')"
```

Without the folder, Jarvis says so at start and uses `[stt] model`.

Whisper small also guesses Sinhala as Malayalam, Hindi or Bengali; only
English, Sinhala and Tamil are possible for Jarvis, so such a guess is mapped
to the likeliest of the three (`[stt] only_my_languages`), and Sinhala spoken
in English mode switches to Friday when it's clearly Sinhala (80% of the
three). Saying "Friday" or "සිංහලෙන් කතා කරන්න" always switches.

## Using another fine-tuned Sinhala Whisper with faster-whisper

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

## Jarvis's own words in each language

The model answers in the active language by itself; the lines Jarvis says
without it are written out in each language (English, Friday's spoken
Sinhala, Tamil), and a language with no line of its own gets the English one:

| Lines | Where |
|---|---|
| greetings, switching, "I couldn't make that out", fillers | `config/languages.toml` |
| the window, closed panels, the 3D explorer, a new computer, the models out of reach, the stand-in | `src/jarvis/said.py` |
| the PC and knowledge tools, the map's layers | `src/jarvis/tools/desk_phrases.py` |
| Bing and YouTube | `src/jarvis/tools/web.py` |
| lessons | `src/jarvis/lesson_mode.py` (`WORDS`) |
| worked problems: spoken lines, units, powers of ten | `src/jarvis/problem_mode.py` (`WORDS`, `UNIT_WORDS`, `POWERS`) |
| worked problems: the marks and the animation's check | `src/jarvis/knowledge/problems.py` (`MARKS`) |
| the worked problem's card in the window | `src/jarvis/ui/problem.js` (`WORDS`) |

English words in a Sinhala line are written in Sinhala letters ("වින්ඩෝ එක",
"ලේයර් එක"), as the voice reads Sinhala script. `tests/test_said.py` checks
every line has an English one and that each translation fills in the same
values. To add a language, add its lines next to the others (a missing one
falls back to English, so nothing breaks while you do).
