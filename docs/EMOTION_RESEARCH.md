# Hearing emotion: what's out there, and what it means for Jarvis

Research notes for M5 (the emotion model, [TRAINING_EMOTION.md](TRAINING_EMOTION.md)),
gathered 3 Nov 2026: ready-made models, papers, public datasets and code,
and what each one changes in Jarvis. The training stays Adhi's; what could
be built without him is built (the last section).

## Where Jarvis is now

`superb/wav2vec2-base-superb-er`: wav2vec 2.0 base fine-tuned on IEMOCAP
(acted American English), four labels (neutral, happy, angry, sad), Apache-2.0.
On the laptop's CPU it takes 160-420 ms a turn (log of 3 Nov). Your level 2
classifier learns from its features. Until 3 Nov those were only the **last**
layer, averaged over time.

## 1. Use the middle layers, not only the last one

Three studies probed every layer of wav2vec 2.0 for emotion with frozen
features and a small classifier, and agree:

| Study | Finding |
|---|---|
| Pepino, Riera, Ferrer, *Emotion Recognition from Speech Using Wav2vec 2.0 Embeddings* ([arXiv:2104.03502](https://arxiv.org/pdf/2104.03502)) | A learned weighted mix of all layers beat the last layer: 67.2 against 58.5 on IEMOCAP, 84.3 against 69.0 on RAVDESS. The weights were largest in the middle layers. |
| Li, Mohamied, Bell, Lai, *Exploration of a Self-Supervised Speech Model: A Study on Emotional Corpora* ([arXiv:2210.02595](https://arxiv.org/pdf/2210.02595)) | Accuracy peaks in the middle (layer 6 on IEMOCAP, 5 on RAVDESS); "the last layer could be the worst choice". |
| Singh, Gupta, *Decoding Emotions: A Comprehensive Multilingual Study of Speech Models for SER* ([arXiv:2308.08713](https://arxiv.org/pdf/2308.08713)) | Across 7 languages, the center layers have the richest features; the first and last layers did worst. |

**In Jarvis (built 3 Nov):** every label keeps all 13 layers. Your
training script picks `"last"`, `"middle"`, `"all"` or `"layer6"`, and Jarvis
feeds your classifier the same at run time. Comparing them on your own voice
is a small experiment of your own (section 5).

## 2. Better ready-made models

| Model | What it gives | Learned from | Licence | Fit for Jarvis |
|---|---|---|---|---|
| **emotion2vec+** base, about 90M parameters ([model](https://huggingface.co/emotion2vec/emotion2vec_plus_base/blob/main/README.md); large about 300M, [seed](https://huggingface.co/emotion2vec/emotion2vec_plus_seed)) | 9 labels (angry, disgusted, fearful, happy, neutral, other, sad, surprised, unknown) and 768-wide features | Pseudo-labelled emotional speech: base about 4,800 hours, large about 42,000 | "model-license" (FunASR's) | The strongest open model. Its paper's protocol is exactly yours: frozen features and a small classifier. Needs `pip install funasr modelscope`. The next encoder to try. |
| emotion2vec (the base it grew from; [paper](https://arxiv.org/html/2312.15185v1), ACL Findings 2024) | Features | 262 hours of emotional English | as above | On IEMOCAP with frozen features: 71.8% against wav2vec 2.0's 63.4%, HuBERT 64.9%, WavLM 65.9% (base sizes). |
| audEERING **wav2vec2-large-robust-12-ft-emotion-msp-dim** ([model](https://huggingface.co/audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim), [how-to](https://github.com/audeering/w2v2-how-to)) | Arousal, dominance, valence (about 0 to 1) and features | MSP-Podcast (natural podcast speech, not acted) | CC BY-NC-SA 4.0, research only | Dimensions map well onto your labels: rushed is high arousal; tired is low arousal and low dominance; frustrated is high arousal with low valence. Larger (12 layers of a large model), so slower on the CPU. |
| SpeechBrain emotion-recognition-wav2vec2-IEMOCAP ([model](https://huggingface.co/speechbrain/emotion-recognition-wav2vec2-IEMOCAP)) | 4 IEMOCAP labels | IEMOCAP | Apache-2.0 | 75.3% average on IEMOCAP's test, but the same four acted labels as now, and needs SpeechBrain. Little to gain. |

The paper behind the audEERING model (Wagner et al., *Dawn of the transformer
era in speech emotion recognition: closing the valence gap*, IEEE TPAMI 2023,
[arXiv:2203.07378](https://arxiv.org/abs/2203.07378v4)) adds two findings that
matter here:

- **Valence (pleasant or not) comes largely from the words**, which the
  transformer learns implicitly. So the words Whisper hears are worth adding
  for felt labels: the "fused" step (TRAINING_EMOTION.md, step 6).
- The models are fair across sexes but **not across individual speakers**.
  That's the case for your level 2: a classifier fitted to your own voice.

## 3. Public emotional speech you can add

| Set | What | Licence | Use |
|---|---|---|---|
| **EmoTa** ([data](https://huggingface.co/datasets/aaivu-labs/EmoTa), [paper](https://aclanthology.org/2025.chipsal-1.19), CHiPSAL 2025, University of Moratuwa) | The first Tamil emotional speech set: 22 Sri Lankan Tamil speakers (11 female, 11 male), 936 clips of 19 neutral sentences; anger, happiness, sadness, fear, neutral; Fleiss' kappa 0.74 | Gated; academic use CC BY-NC 4.0, cite the paper, no redistribution | The only Sri Lankan emotional speech set found. Tests the ready-made model on Sri Lankan voices, and adds Sri Lankan speakers to your training. |
| RAVDESS ([Zenodo](https://zenodo.org/record/1188975), [card](https://huggingface.co/datasets/ehcalabres/ravdess_speech/blob/main/README.md)) | 24 actors (12 female, 12 male), North American English, 8 emotions **including calm**, 48 kHz | CC BY-NC-SA 4.0 | Has "calm" like yours. |
| CREMA-D ([TFDS page](https://TensorFlow.org/datasets/catalog/crema_d), [catalogue](https://catalogue.yorvoice.york.ac.uk/catalogue/8PQ99462)) | 7,442 clips from 91 actors (aged 20-74, many backgrounds), 6 emotions at 4 intensities | See its GitHub repository | Many voices: good for learning what isn't one person's habit. |

**Sinhala:** no public Sinhala emotional speech set turned up. The nearest
are Sinhala *text* sets (for example [GeeSanBhava](https://arxiv.org/abs/2511.18146v1),
YouTube comments labelled for valence and arousal). A consented Sinhala and
Singlish set, labelled for emotion, intent and language, would be a first.
It's already in the roadmap as the research contribution.

None of these sets has "rushed" or "confused". Mapping is your call and goes
in the report: neutral and calm to calm is safe; angry to frustrated is a
stretch.

**In Jarvis (built 3 Nov):** `scripts/emotion_features.py` runs a set
(RAVDESS and CREMA-D by their file names, anything else from a CSV of path,
label and speaker) through the same model, and writes the features of every
layer to `data/emotion/corpus-<name>.jsonl`, each speaker a session. The audio
isn't copied; only features are kept.

## 4. Training on few labels of one voice

- **Personalisation pays, and variety beats count.** Ihori et al., *Few-shot
  Personalization via In-Context Learning for SER* (NTT, [arXiv:2509.08344](https://arxiv.org/html/2509.08344v1)):
  a few labelled clips of the speaker lift accuracy, and clips of *different*
  emotions help more than more of the same. Your rounds record every label in
  every session, which matches this.
- **Robustness, without keeping audio.** Jaiswal and Mower Provost, *Best
  Practices for Noise-Based Augmentation…* ([arXiv:2104.08806](https://arxiv.org/pdf/2104.08806)):
  emotion models break with room noise, fading and especially reverberation.
  Augmentation helps (noise, fading, short speed-ups), but pitch shifts,
  whole-clip speed changes over 5% and added laughter or sobs change the
  emotion itself. Jarvis keeps no audio to augment, so do it at the source:
  record some rounds with a fan on, in another room, farther from the mic.
- **Fair comparisons.** EmoBox (Ma et al., [arXiv:2406.07162](https://arxiv.org/abs/2406.07162v1)):
  a benchmark of 10 speech models on 32 emotion sets in 14 languages, with
  fixed splits and speaker-balanced cross-corpus tests. The lesson for you:
  fix the split (whole sessions out), and report cross-condition results
  (acted to felt), not only within one recording session.

## 5. A plan for the report

Same held-out session(s), same metrics (macro-F1, F1 per label, false alarms
on calm), from `scripts/emotion_eval.py`:

| | Classifier | Features | Trained on |
|---|---|---|---|
| A | the ready-made model (nearest label) | n/a | IEMOCAP |
| B | yours | last layer | your labels |
| C | yours | middle layers | your labels |
| D | yours | all layers | your labels |
| E | yours | the best of B-D | a public set + your labels |
| F (if time) | yours | emotion2vec+ features | your labels |

Then the gate (TRAINING_EMOTION.md, step 5), and acted against felt
(`--how felt`).

## What was built from this (3 Nov)

- Every `/mood` label and round take keeps all layers (half precision,
  about 27 KB a label; `encode_layers`, `decode_layers`).
- `features_of(row, "middle")` and `pick_features(layers, spec)`; your saved
  classifier says `"features": ...` and Jarvis uses the same layers.
- `scripts/emotion_eval.py` scores your classifier on the layers it learned from.
- `scripts/emotion_features.py` for RAVDESS, CREMA-D, EmoTa or any CSV.
