# Training our own Sinhala speech model

The plan for section R of IMPLEMENTATION_PLAN.md: fine-tune Whisper `small` on
Sinhala so Jarvis can write what you say. On 21 Oct the base model knew you
were speaking Sinhala (p = 0.95 to 0.99) but wrote nonsense.

**Who does what:** you write and run the notebook; this file says what each
step must do, what to look up, and what to check. Paste errors and numbers
to Claude at any step.

## The four stages

| Stage | Where | What you get |
|---|---|---|
| 1. Test set and "before" score | laptop | CER of today's models on *your* voice |
| 2. Accounts | browser | Kaggle with GPU and internet, a Hugging Face token |
| 3. Training | Kaggle notebook | a fine-tuned model saved on Hugging Face |
| 4. Into Jarvis and "after" score | laptop | Jarvis hearing Sinhala, and the CER table |

## Stage 1: test set and "before" score (laptop, about 40 minutes)

1. Check the three Sinhala files (129 sentences, drafted with Claude):
   `eval\sentences_si.txt` (commands), `eval\sentences_si_study.txt`
   (physics and maths), `eval\sentences_si_talk.txt` (conversation and short
   paragraphs). Change any wording you wouldn't use; add your own.
2. Record each file, as many sittings as you like:
   `uv run python scripts/record_eval_set.py eval/sentences_si_study.txt --lang si`
   (and the same for the other two). They all go into one Sinhala test set.
3. Score today's models:
   `uv run python scripts/eval_stt.py --lang si --model small --model large-v3-turbo`

These recordings are the test set: they never go into training, and they
stay on the laptop. Note the CER: it is the "before" number.

Written sentences on their own can't teach the speech model: it learns
from audio and its text together. One experiment can bridge the two: turn
some of the 8,300 generated Sinhala sentences
(`data/generated/sinhala_sentences.txt`, from `scripts/make_intent_data.py`)
into speech with the Sinhala voices and add that to training as a small
share (say 10%) of OpenSLR 52. Synthetic speech teaches the words and topics
you use, but a model trained mostly on it learns the synthetic voice, so
keep it small and always test on real recordings. Your recordings are the test set; the
training audio is OpenSLR 52. Text alone helps elsewhere: the intent
classifier, a word list for Whisper's prompt, and (an option from the 2026
study) a Sinhala language model to rescore Whisper's guesses.

## Stage 2: accounts (about 10 minutes)

1. **Kaggle** (kaggle.com, sign in with Google). Settings, then verify your
   phone number: without it, notebooks get no GPU and no internet.
2. **Hugging Face** (huggingface.co). Settings, Access Tokens, new token with
   *write* access. It's how the notebook saves the model and the laptop
   downloads it.
3. In the Kaggle notebook: Add-ons, Secrets, add `HF_TOKEN`. Never paste the
   token into code, a notebook cell's output, or GitHub.

## Stage 3: the notebook (Kaggle)

Notebook settings: accelerator **GPU T4** (fp16 works well on it), internet
**on**. Work in `/kaggle/temp` or `/tmp` for the big files; `/kaggle/working`
is kept as output and has a 20 GB limit.

Cell by cell (write the code yourself; look up the names in **bold** in the
Hugging Face documentation):

1. **Install** `transformers`, `datasets`, `evaluate`, `jiwer`, `accelerate`,
   `soundfile`. Print the versions; Kaggle already has `torch`.
2. **Download** `utt_spk_text.tsv` and two parts, `asr_sinhala_0.zip` and
   `asr_sinhala_1.zip` (about 0.9 GB and 14 hours each), from a mirror such
   as `https://openslr.trmal.net/resources/52/`, then unzip. Check: how many
   audio files, and what's the sample rate of one? (Whisper wants 16 kHz.)
3. **Build the table:** read the TSV (utterance id, speaker id, text), keep
   the rows whose audio file you have, add each clip's duration. Drop clips
   over 30 s (Whisper's limit) and under about 1 s. Print 10 random rows and
   read them: is the text clean Sinhala?
4. **Split by speaker** (look up `GroupShuffleSplit` in scikit-learn): about
   90% of speakers for training, 5% validation, 5% test, and no speaker in
   two splits. Otherwise the scores measure memorised voices, not Sinhala.
5. **Baseline:** `openai/whisper-small` on 200 validation clips with
   `language="si"`, scored with **`evaluate.load("cer")`**. This should be
   bad; write the number down.
6. **Prepare:** **`WhisperProcessor`** for `openai/whisper-small` with
   `language="sinhala"`, `task="transcribe"`. Turn audio into log-Mel
   features and text into label ids. Check that no label is longer than
   448 tokens.
7. **Collator:** pad the features and the labels; label padding becomes
   `-100` so the loss ignores it (the Hugging Face blog "Fine-Tune Whisper
   For Multilingual ASR with Transformers" shows this pattern).
8. **Model:** **`WhisperForConditionalGeneration`** from
   `openai/whisper-small`; set the generation language to Sinhala and the
   task to transcribe.
9. **Training arguments** (**`Seq2SeqTrainingArguments`**), a starting
   point to adjust: `fp16=True`, batch size 16, learning rate `1e-5`, 500
   warm-up steps, `max_steps` about 3000, `gradient_checkpointing=True`,
   evaluate and save every 500 steps, `save_total_limit=2`,
   `predict_with_generate=True`, `metric_for_best_model="cer"`,
   `greater_is_better=False`, `push_to_hub=True` to a *private* repo with
   `hub_strategy="checkpoint"`.
10. **Train,** watching validation CER every 500 steps. A free session lasts
    12 hours; this may need more than one. In the next session, run the
    cells again and use `trainer.train(resume_from_checkpoint=True)` after
    the last checkpoint comes back from the Hub.
11. **Test** on the test speakers: CER and WER, and print 10 examples next
    to their correct text.
12. **Save:** push the model and the processor to your private repo, with a
    short model card: the data (OpenSLR 52 by Google, CC BY-SA 4.0), the
    hours used, the scores.

**Learn while it trains:** what the loss and the validation CER curves
should look like, overfitting, and why a small learning rate keeps what
Whisper already knows.

## Stage 4: into Jarvis (laptop)

1. Convert for faster-whisper (once):
   ```
   uv pip install transformers torch
   uv run ct2-transformers-converter --model <your-name>/<your-repo> --output_dir models/whisper-si-small-ct2 --quantization int8_float16 --copy_files tokenizer.json preprocessor_config.json
   ```
2. Score it on your recordings, next to the "before" models:
   `uv run python scripts/eval_stt.py --lang si --model small --model large-v3-turbo --model models/whisper-si-small-ct2`
3. If it's better, in `config/languages.toml` under `[si]`:
   `stt_model = "models/whisper-si-small-ct2"`, then talk to Jarvis in
   Sinhala.

**Done when:** the table (model, CER, WER, ms per utterance) for the base
models and ours, in DEVLOG.md. That table is a result for your report.

## Licence

OpenSLR 52 is CC BY-SA 4.0. Credit "Google, OpenSLR 52" wherever you use it.
A model trained on it may count as an adaptation, so if you ever publish the
model, use the same licence (CC BY-SA 4.0).
