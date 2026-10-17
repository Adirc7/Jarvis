# eval/

Test sentences for measuring speech recognition (the plan's "transcript
accuracy check").

1. Write the sentences. `sentences_en.txt` is ready. For Sinhala and Tamil,
   create `sentences_si.txt` and `sentences_ta.txt` with about 20 things you'd
   really say to Jarvis, in your own words and spelling, one per line.
2. Record them:
   `uv run python scripts/record_eval_set.py eval/sentences_si.txt --lang si`
3. Score models:
   `uv run python scripts/eval_stt.py --lang si --model small --model large-v3-turbo`

Recordings are saved in `eval/recordings/`, which is in `.gitignore`: your
voice stays on your laptop. Only record other people if they agree, and keep
their recordings out of the repo too.
