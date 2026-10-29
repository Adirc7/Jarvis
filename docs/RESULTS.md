# Results

Made by scripts/evaluate_all.py on 2026-10-30 00:52 from the laptop's logs/ (read-only copy, 30 Oct). Run it again for fresh numbers; the DEVLOG says what changed between runs.

## Hardware check (scripts/smoke_test.py)

Latest run 2026-10-28 08:12: 42 pass, 5 warnings, 1 failed.

| Check | Result | Detail |
|---|---|---|
| python | PASS | 3.12.12 on Windows 11 |
| cuda for whisper | PASS | 1 CUDA device(s) visible to CTranslate2 |
| nvidia-smi | PASS | NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB, 0 MiB, 591.44 |
| whisper load | PASS | small on cuda/int8_float16 in 1720 ms |
| whisper speed | PASS | 142 ms for 6.0 s of audio (real-time factor 0.02; under 0.5 is good) |
| llm groq_oss | PASS | openai/gpt-oss-120b: first token 2547 ms, total 2549 ms, said 'OK' |
| llm groq | PASS | openai/gpt-oss-20b: first token 829 ms, total 830 ms, said 'OK' |
| llm openrouter | PASS | openrouter/free: first token 1622 ms, total 1637 ms, said 'OK' |
| llm gemini | FAIL | No LLM provider answered (gemini: InternalServerError: Error code: 503 - [{'error': {'code |
| llm ollama | WARN | No LLM provider answered (ollama: APIConnectionError: Connection error.) Start it with 'ol |
| llm gemini_lite | PASS | gemini-flash-lite-latest: first token 804 ms, total 806 ms, said 'OK' |
| llm groq_oss_think | PASS | openai/gpt-oss-120b: first token 925 ms, total 927 ms, said 'OK' |
| llm groq_qwen | PASS | qwen/qwen3.8-27b: first token 428 ms, total 429 ms, said 'OK' |
| voice English | PASS | kokoro/bm_lewis: 512 ms for 2.6 s (real-time factor 0.20) |
| voice Sinhala | PASS | kokoro/bf_emma: 240 ms for 3.2 s (real-time factor 0.07) |
| voice Tamil | PASS | mms/facebook/mms-tts-tam: 676 ms for 3.3 s (real-time factor 0.20) |

## Responsiveness (Jarvis's own logs)

18 sessions, 2026-10-21 10:01 to 2026-10-28 08:27; 105 turns (chat 76, tool 12, unclear 9, cancelled 7, stt_error 1).

| Measure | p50 / p95 |
|---|---|
| First spoken word after you stop talking (voice) | 1.8 s / 8.9 s (n=64) |
| First spoken word after you press Enter (typed) | 1.9 s / 2.6 s (n=8) |
| Request understood and done (PC and web tools) | - |
| Speech recognition (Whisper) | 506 ms / 4.7 s (n=94) |
| ... per second of speech | 119 ms / 854 ms (n=94) |
| A voice speaking one sentence (TTS) | 278 ms / 1.1 s (n=258) |

Each model's first words (from sending the question):

| Model | p50 / p95 | slowest |
|---|---|---|
| groq_oss (openai/gpt-oss-120b) | 835 ms / 2.0 s (n=60) | 3.8 s |
| groq (openai/gpt-oss-20b) | 933 ms / 8.7 s (n=23) | 13.5 s |
| gemini_lite (gemini-flash-lite-latest) | 7.0 s / 7.0 s (n=1) | 7.0 s |

Fallbacks to the next model: gemini APITimeoutError x1, groq APIError x1; first-reply deadline used 0 times; interrupted by talking over Jarvis 8 times.

## Speech recognition: language and clarity

| Language Jarvis was in | utterances | detected as it | asked to repeat (unclear) |
|---|---|---|---|
| en | 86 | 75 (87%) | 3 |
| si | 8 | 8 (100%) | 6 |

Word and character error rates come from scripts/eval_stt.py on the recorded test sentences.

## Understanding commands (scripts/command_check.py)

| Set | when | English | Singlish | Sinhala | all | actions nobody asked for |
|---|---|---|---|---|---|---|
| commands | 2026-10-25 16:44 | 32/33 | 16/16 | 11/11 | 59/60 (98%) | 0 |
| commands_heldout | 2026-10-25 16:46 | 27/27 | 13/13 | 8/8 | 48/48 (100%) | 0 |

commands_heldout was written and committed before any tuning.

## Safety

The gate, 22 risky tool calls (eval/safety_calls.jsonl, run now, nobody clicking): 17 refused, 5 waited for a click; **0 acted**.

The model-level check (scripts/safety_check.py, 20 risky requests) hasn't run on this laptop yet.

## PC tools in use (logs/actions-*.jsonl)

5 decisions: ran 4, refused 1
Of the actions that ran: checked 3, not measurable 1.
By tool: open_app 1, change_volume 1, set_timer 1, create_note 1.
