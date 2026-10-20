# eval/

Test sentences and recordings for measuring how well Jarvis hears and
understands you. Research scope: English, Sinhala and Singlish (decision
D23).

## 1. Write the sentences

| File | What to write |
|---|---|
| `sentences_en.txt` | ready |
| `sentences_si.txt` | each hint in Sinhala script, the way you'd really say it |
| `sentences_singlish.txt` | Sinhala mixed with English, in English letters, e.g. `Chrome eka open karanna` |

Write your own natural version under each hint rather than a word-for-word
translation; skip any that feel unnatural and add your own.

## 2. Record

Quiet room, the laptop microphone Jarvis uses, your normal speed and voice.
About 10 minutes per file.

```
uv run python scripts/record_eval_set.py eval/sentences_en.txt --lang en
uv run python scripts/record_eval_set.py eval/sentences_si.txt --lang si
uv run python scripts/record_eval_set.py eval/sentences_singlish.txt --lang si --set singlish
```

A friend reading the same files: add `--speaker friend1` (with their
consent; see below).

## 3. Score

```
uv run python scripts/eval_stt.py --lang en --model small --model large-v3-turbo
uv run python scripts/eval_stt.py --lang si --model small --model large-v3-turbo
```

Singlish is scored differently: Whisper writes Sinhala words in Sinhala
script or garbles them into English, so word error rate against an
English-letter reference is meaningless. Singlish recordings are for
measuring language detection and, later, whether Jarvis understood the
request (intent accuracy).

## Privacy

Recordings are saved in `eval/recordings/`, which is in `.gitignore`: voices
stay on the laptop and never go to GitHub. Record other people only with
their written consent, and let them withdraw.
