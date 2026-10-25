# Training your intent model

A small model, trained by you, that reads a sentence in English, Singlish or
Sinhala and says what kind of request it is ("open_app", "explain_concept",
"pause_media", ... 46 intents), and how sure it is. It runs on the laptop in
about 1 ms (level 1) or about 10-20 ms (level 2), with no internet.

**Who does what:** you write the two training scripts and run everything;
this file says what each step does, why, and what to check. The data
scripts, the evaluation and the place it plugs into Jarvis are ready. Paste
numbers and errors to Claude at any step.

## What it does in Jarvis

Today: when `models/intent/intent.joblib` exists, Jarvis asks your model
first which kind of request it is, and that picks the model that answers
(the "command", "maths", "teach", "code", "talk" ... routes in
`agent/router.py`). When your model is less sure than `min_confidence`,
the keyword rules decide, exactly as now. Every decision goes in the log
with your model's intent and confidence, so you can see how it does on
real use.

Later, when it's good on real sentences: offline commands (no internet, no
big model), the empathy learner (M2) knowing when you're talking about how
you feel, and the emotion model (M5) next to it.

It never acts by itself: an intent picks who answers, it doesn't press keys.
Opening, playing and searching still go through the rules and the tools,
which check everything.

## Step 0: install (once)

```
scripts\update.cmd
scripts\update.cmd ml
```

(the first gets the new update.cmd, the second adds scikit-learn, joblib
and sentence-transformers to what you have; after that, plain `scripts\update.cmd` keeps them. Don't
use `uv sync --extra ml` alone: uv sync removes what you don't list, voice
and camera included). Check:

```
uv run python -c "import sklearn, sentence_transformers; print(sklearn.__version__)"
```

## Step 1: the data

```
uv run python scripts/make_intent_sets.py
```

```
train      13577 sentences (en 1700, si 7725, si-Latn 4152)
dev         2053 sentences from templates train never saw (en 847, si 617, si-Latn 589)
test_real    108 real phrasings (en 60, si 19, si-Latn 29); 20 need the list on screen
labels        46 intents -> data/intent
```

| File | What it is | You may |
|---|---|---|
| `train.jsonl` | generated sentences (from `src/jarvis/intents/patterns.py`) plus yours | learn from it |
| `dev.jsonl` | generated sentences from templates train never saw | choose settings on it |
| `test_real.jsonl` | the real phrasings of `eval/commands*.jsonl`, with the intents that count as right | report on it, **never tune on it** |
| `mine.jsonl` | your own sentences (step 4); you make this one | add to it any time |

Each line looks like `{"text": "youtube eka arinna", "lang": "si-Latn", "intent": "open_app", "pattern": "{app} eka {open}"}`.

**Why dev is split by template:** the generated sentences come from
templates like `{please} {open} {app}`. Split at random, sentences from the
same template land in both sets, and the model gets marked right for
recognising a template it has already seen. Holding whole templates out
asks the real question: does it understand a way of saying it that it never
saw? The same idea is why the real test is never used for choices: once you
pick settings by it, it stops telling you how Jarvis does on new sentences.

**Look before training (10 minutes):** open `train.jsonl` and count
sentences per intent and per language (a `collections.Counter` is enough).
Write down the smallest classes. Read 20 random English lines. You'll see
why step 4 matters: the English is thinner than the Sinhala.

## Step 2: level 1, word pieces and logistic regression

Write `scripts/train_intent_level1.py`:

```python
"""Level 1 intent model: character n-grams + logistic regression."""
import json
import time
from datetime import date
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "intent"
OUT = ROOT / "models" / "intent" / "level1.joblib"


def load(name):
    lines = (DATA / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


train = load("train.jsonl")
texts = [r["text"] for r in train]
intents = [r["intent"] for r in train]

pipeline = Pipeline([
    ("features", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2)),
    ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
])
start = time.time()
pipeline.fit(texts, intents)
print(f"trained on {len(texts)} sentences in {time.time() - start:.0f} s")

OUT.parent.mkdir(parents=True, exist_ok=True)
joblib.dump({"kind": "text", "pipeline": pipeline, "trained": str(date.today())}, OUT)
print("saved", OUT)
```

```
uv run python scripts/train_intent_level1.py
```

About 10 seconds. What each choice means (look these up and say each in
your own words before moving on):

- **`char_wb`, 2 to 5 characters:** the features are pieces of words
  ("ari", "rinn", "inna"), not whole words. Singlish is spelled many ways
  (arinna, arinnako, arinn), and Sinhala adds endings (විවෘත කරන්න,
  විවෘත කරලා); pieces still match when whole words don't. `wb` keeps the
  pieces inside word boundaries.
- **TF-IDF, `sublinear_tf`:** a piece in every sentence ("the", "ක") counts
  for little; a piece in few sentences counts for more. Sublinear: the 5th
  repeat in one sentence adds less than the 1st.
- **`min_df=2`:** a piece seen in only one sentence is dropped (noise).
- **Logistic regression:** one weight per piece per intent; softmax turns
  the scores into probabilities. Its top probability is the "confidence".
- **`class_weight="balanced"`:** greetings have about 10 examples and study
  requests about 360; without weights the model learns to say "study".

## Step 3: measure

```
uv run python scripts/intent_eval.py models/intent/level1.joblib
```

It loads your file with the same loader Jarvis uses
(`src/jarvis/intents/classifier.py`), so what you measure is what Jarvis
runs. On 25 Oct, the code above gave:

```
dev        accuracy 77.3%, macro-F1 0.716  (en 72%, si-Latn 79%, si 82%)
real test  55.7%  (en 20/48, si-Latn 16/24, si 13/16)
confident  limit 0.6: decides alone 10/88, right when it does 10/10
```

How to read it:

- **dev vs real test:** 77% on unseen templates, 56% on real sentences. The
  gap is the main lesson: generated data says "open YouTube", "launch
  YouTube", real people say "pull up YouTube" and "bring up that video
  site". A model is only as good as how close its training sentences are
  to real ones (look up *distribution shift*).
- **macro-F1:** the average F1 over intents, so a rare intent counts as
  much as a common one. Accuracy alone hides a model that never says
  "thanks".
- **confident:** how many real lines the model would decide alone at each
  limit, and how often it's right when it does. 10/10 at 0.6 means it's
  safe but shy: most lines go to the rules. That's by design: an unsure
  model hands over instead of guessing.
- **real mistakes:** each line, what it said and how sure. Read them all:
  they tell you what to add in step 4.
- **dev confusions:** which intents it mixes up (explain_concept and
  solve_problem, for example). Some are honest ambiguity; some need data.

**Tune on dev only:** try `C` in `LogisticRegression` (0.3, 1, 3, 10) and
`ngram_range` (2-4, 2-5, 1-6). Keep a small table: setting, dev macro-F1,
training time. Pick by dev, then look at the real test once.

## Step 4: add real sentences

Make `data/intent/mine.jsonl`, one sentence per line:

```
{"text": "pull up the video site", "lang": "en", "intent": "open_app"}
{"text": "mata fourier series eka therenne naha", "lang": "si-Latn", "intent": "explain_concept"}
{"text": "මට අද හරිම මහන්සියි", "lang": "si", "intent": "feeling_low"}
```

The intents are in `data/intent/labels.txt`. One more is yours: **`chat`**,
for talk, opinions, discussions and advice that aren't one of the 46 (the
generated data has no such class, so without it every chat line is forced
into some task). Any other new name works too, and the script lists new
names with their counts, so a typo shows up.

**Keep the labels fine, not coarse.** "device_control" would be one label
for volume up, volume down, brightness, Wi-Fi and shutdown, but Jarvis has
to do different things for each. Fine labels can always be merged later
(volume_up + volume_down -> device_control is one line of code); a coarse
label can never be split back without labelling everything again.

Then run
`scripts/make_intent_sets.py` again (it adds yours to train, each counted 3
times since they're real; `--mine-weight` changes that), train, measure.

Rules, so the numbers stay honest:

- **Write new sentences, don't copy the test.** A line that is also in the
  real test is left out and named by the script. Writing near-copies of the
  test lines you saw in the mistakes list is the same thing in disguise:
  write how *you* would say it on another day.
- **Say it the way you talk:** half-English half-Sinhala, short, with
  "ane", "machan", typos and all. 10-20 per intent you use often beats 200
  in neat textbook English.
- **Grow the real test too, first:** when you find a new way of saying
  something, put one version in `eval/commands_heldout.jsonl` (commit it
  before training), and a *different* version in `mine.jsonl`.
- To fix a whole family of phrasings (every "pull up / bring up / fire up
  X"), add the words to `src/jarvis/intents/patterns.py` instead, and run
  `scripts/make_intent_data.py` before `make_intent_sets.py`.

## Step 5: level 2, sentence meaning (deep learning)

Level 1 knows word pieces. Level 2 uses `intfloat/multilingual-e5-small`, a
transformer trained on about 100 languages (Sinhala among them) to turn a
sentence into 384 numbers such that sentences with the same meaning get
close vectors. You keep the encoder frozen and train only a classifier on
the vectors: the encoder brings the meaning, your data brings the intents.

Write `scripts/train_intent_level2.py`:

```python
"""Level 2 intent model: multilingual-e5-small sentence vectors + logistic regression."""
import json
import time
from datetime import date
from pathlib import Path

import joblib
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression

ENCODER = "intfloat/multilingual-e5-small"
PREFIX = "query: "                    # e5 was trained with this in front of every query
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "intent"
OUT = ROOT / "models" / "intent" / "level2.joblib"


def load(name):
    lines = (DATA / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


train = load("train.jsonl")
encoder = SentenceTransformer(ENCODER)       # about 470 MB, downloaded once
start = time.time()
vectors = encoder.encode([PREFIX + r["text"] for r in train], batch_size=64,
                         normalize_embeddings=True, show_progress_bar=True)
print(f"encoded {len(train)} sentences in {time.time() - start:.0f} s; vectors {vectors.shape}")

model = LogisticRegression(max_iter=3000, class_weight="balanced", C=10)
model.fit(vectors, [r["intent"] for r in train])

OUT.parent.mkdir(parents=True, exist_ok=True)
joblib.dump({"kind": "embedding", "encoder": ENCODER, "prefix": PREFIX,
             "classifier": model, "trained": str(date.today())}, OUT)
print("saved", OUT)
```

```
uv run python scripts/train_intent_level2.py
uv run python scripts/intent_eval.py models/intent/level1.joblib models/intent/level2.joblib
```

Encoding takes a few minutes on the CPU (less if torch sees the RTX 4050);
the classifier itself is seconds. Things to know:

- **`query: `** must be in front at training *and* at use. The loader adds
  it for you from the saved `prefix`; leave it out in training and the
  vectors won't match.
- **`normalize_embeddings=True`:** every vector gets length 1, so only the
  direction (the meaning) counts.
- **`C=10`:** the vectors are few (384) and dense, so less regularisation
  than level 1 usually helps. Try 1, 3, 10, 30 on dev.
- **Speed up the tries:** encoding is the slow part and doesn't change
  with `C`. Save `vectors` once (`numpy.save`) and load them for each try.
- Not tested here: the cloud workspace can't download the encoder, so
  level 2 ran first on your laptop. The file format and the loader are
  tested.

What to expect: level 2 should close part of the dev-to-real gap ("pull
up" and "open" mean nearly the same to the encoder), and be slower (10-20
ms) and heavier (about 500 MB of memory). Whether it's worth it is what the
side-by-side tells you.

## Step 6: choose, and put it in Jarvis

1. Pick the model with the better **real test** score at a fair speed (if
   they're close, level 1: smaller and faster).
2. Pick the limit from the **confident** table: the lowest limit where
   "right when it does" is still at least 95%. Put it in
   `config/settings.toml`:

   ```toml
   [intents]
   model = "models/intent/intent.joblib"
   min_confidence = 0.6
   ```

3. Copy your choice to that name: `copy models\intent\level1.joblib models\intent\intent.joblib`
4. Start Jarvis. The first lines say:
   `[intent model] intent.joblib (text, trained 2026-10-25)`.
   Nothing else changes when it works. If the file is broken it says
   "couldn't load ... using the keyword rules" and carries on.
5. To switch it off, rename or delete the file.

The `models/` folder is gitignored: your model stays on the laptop.

## Step 7: the learning loop (D27)

Every request Jarvis routes goes in `logs/` with your model's intent and
confidence (`"event": "route"`). Once a week:

1. Look for lines where it was unsure (low confidence) or wrong (the reply
   went to the wrong kind of model).
2. **You** decide the right intent for each; reviewed lines go into
   `mine.jsonl`. Nothing goes in by itself (D27: Jarvis learns only what
   you confirm).
3. Make the sets, train, measure. Keep the new model only if the real test
   and dev didn't get worse. Note the numbers in `docs/DEVLOG.md`.

A small review tool that shows logged lines and lets you press a key for
the intent can come later; ask Claude when the logs have enough lines.

## What to report

Paste these to Claude (or into the DEVLOG) after each round:

- the intent_eval output for each model you trained
- your small tuning table from steps 3 and 5
- how many sentences are in `mine.jsonl`, per language
- three mistakes you think are fair (the sentence really is ambiguous) and
  three you think aren't

## Learn

Look up and explain in your own words: TF-IDF; character n-grams; softmax
and logistic regression for many classes; regularisation (`C`); class
weights; accuracy vs macro-F1; data leakage; distribution shift; sentence
embeddings and cosine similarity; why a frozen encoder plus a small
classifier needs far less data than training a transformer; confidence vs
calibration (a model that says 0.9 should be right about 9 times in 10:
check yours with the confident table).

## When something goes wrong

| What you see | What it means |
|---|---|
| `No data/intent/dev.jsonl` | run `scripts/make_intent_sets.py` first |
| `ModuleNotFoundError: sklearn` | `scripts\update.cmd ml` |
| `ConvergenceWarning` | raise `max_iter`; harmless if dev scores are fine |
| `expected a dict saved with joblib` | save the dict as in the code above, not the bare pipeline |
| level 2: a download error | the first run needs internet (huggingface.co); after that it's cached |
| real test far below dev | normal at first: step 4 |
