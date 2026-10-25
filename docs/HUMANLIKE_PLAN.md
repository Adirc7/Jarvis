# Making Jarvis feel like talking to a person (plan, 24 Oct 2026)

**Status:** Proposed (status words as in CODEX_IMPROVEMENT_SUGGESTIONS.md).
It builds on ROADMAP.md ("Human-like conversation", "Understanding what
you ask", "Learning from use"), Codex's suggestions and REVIEW_FIXES.md. No
accepted decision changes: it follows D14-D17, D21, D25-D27.

**The goal (Adhi, 24 Oct):** talking to Jarvis or Friday should feel like
talking to a capable person who knows you. It understands you however you
put it, answers without a long pause, says when it didn't catch something,
remembers what you were doing, notices how you are, and stays honest that
it's an AI.

**The problem it starts from (laptop, 24 Oct):** "Can you open YouTube?"
and "Now I mean pause the video" reached the model, which said it couldn't.
A person would have understood both. Change one or two words and the fixed
rules miss.

## 1. What makes a conversation feel human

| Part | What you notice with a person | Jarvis today | The gap |
|---|---|---|---|
| **Understanding** | Any wording works, and mixed Sinhala-English too | Fixed rules for the web tools, then the model | A new wording reaches the model, which can't act |
| **Timing** | Replies come about 0.2 s after you finish ([Stivers et al. 2009](https://www.pnas.org/doi/10.1073/pnas.0903616106)) | First audio about 1.35 s (p50), a filler if slower | Push-to-talk; no hands-free turn-taking |
| **Repair** | "Sorry, did you say Bing or YouTube?" | "Sorry, I couldn't make that out" | It doesn't say what it heard or offer the likely options |
| **Voice and register** | Talks like people talk | Lewis and Emma voices (Kokoro); character sheet | Friday's Sinhala is written-style (ලිඛිත), bookish when spoken |
| **Continuity** | "So, did the Fourier problem work out?" | Name, 50 facts, recent conversation | No topic threads, no "where were we", memory isn't searched |
| **Attunement** | Notices you're tired or rushed | Empathy modes, switched by hand | Feedback bandit and emotion model not built |
| **Presence** | Eye contact, a nod while you talk, a raised hand for "wait" | A CMD window | No orb, captions, wake word or gestures |
| **Character** | The same person every day | Character sheet, honest boundaries | Keep it as it is |

## 2. The main fix: understanding in three layers

One wording miss shouldn't mean "I can't". Each request goes through three
layers, from fastest and strictest to slowest and most flexible. All three
end at the same tool code and, from M3 on, the same safety gate, so a
flexible layer can never do more than a strict one.

```
 what you said (Whisper text, or typed)
   |
   v
 1. Fixed rules (tools/web.py)        ~0 ms, exact, misses new wordings
   |  no match                         match -> act
   v
 2. Intent classifier (Adhi, M3)      a few ms, offline, gives p(intent)
   |  p >= 0.70 -> act
   |  0.40-0.70 -> "Did you mean A or B?"
   |  p < 0.40 or not a command
   v
 3. The model with tools (D21)        any wording; slower, needs internet
   |  calls a tool -> the same tool code -> act
   v
 plain chat reply

 Every correction ("no, I meant...", a click on what Jarvis heard)
   -> a labelled example (opt-in, on the laptop)
   -> the weekly retrain and the similar-examples lookup (section 3)
```

- **Why not only the model:** it needs the internet, takes a second, uses
  the daily quota and can be confidently wrong. **Why not only the
  classifier:** it only knows the intents it was trained on. **Why keep the
  rules:** they are exact for the phrases you use most.
- **Thresholds** start at 70% and 40% (the roadmap's 70% gate) and are tuned
  on the test set in stage H1.
- **Layer 3 can come first, before any training.** Groq documents tool
  calling with `openai/gpt-oss-120b`
  ([Groq docs](https://console.groq.com/docs/tool-use/local-tool-calling)).
  The web tools become function definitions (`open_site(site)`,
  `search(site, query)`, `play_result(n)`, `pause_media()`,
  `resume_media()`, `go_back()`), backed by the same `WebTools` code.
  Providers without tool support skip this layer, and the persona's "say
  the exact words" line stays as the last resort.

## 3. Where RAG fits: four places, one embedding model

RAG (retrieval) doesn't help Jarvis understand *what you want*: that's the
classifier's job. It gives Jarvis the right *knowledge* at the moment it
answers: your corrections, your past, your notes, the web.

| Retrieved | From | Used for | Stage |
|---|---|---|---|
| Your corrected examples | Labelled examples on the laptop | The 5 most similar go into the prompt as examples; the classifier can also vote by nearest neighbours | H2 |
| Memory | Facts and one-line session summaries | The relevant few, instead of all 50; "where were we?" | H4 |
| Lecture notes | Your PDFs (PMAT, AMAT, PHYS, IT) split into chunks | Study answers that name the source ("PMAT 21272 notes, page 12") | H4 (M4) |
| Web pages | Search-and-read (Tavily or Brave, trafilatura) | Current facts, with the site named | H4, after M3 |

- **One encoder for all four, and for the classifier's level 2:**
  multilingual-e5-small (about 118M parameters) runs on the laptop. Its
  XLM-R base was trained on Sinhala, but romanised Singlish may be weaker,
  so measure it against the character n-gram features, which handle
  spelling variation.
- **Store:** FAISS or LanceDB, in a gitignored folder.
- **Safety (Codex section 9):** retrieved text is quoted as data, never
  followed as instructions, never triggers a tool, and is capped in length.

## 4. Where Codex's suggestions fit

| Codex suggestion | What it adds to feeling human | Stage |
|---|---|---|
| Captions for every spoken reply | You see what Jarvis said, and a misheard word is obvious | H3 |
| *Added:* a "what I heard" line you can click and fix | The fix becomes a labelled example (D27) | H3 |
| Orb states: listening, thinking, speaking | The nod a person gives to show they're listening | H3 |
| Truthful status labels; planned modules never shown as live | Honesty, so you trust what it says | H3 |
| Jarvis gold, Friday teal or rose | You see who you're talking to | H3 |
| Honorific as a setting | Already `address` in persona.toml; show it in the window | H3 |
| Shared controllers, semantic events | Voice, keyboard, clap and gesture all behave the same way | H3 |
| Wake by voice ("Hey Jarvis", roadmap) | Calling someone by name | H3 |
| Double-clap wake | Convenience more than human feel; optional, off by default | H3, after the wake word |
| Open palm = stop | The natural "wait" sign | H6, or as an early slice once the window exists |
| Thumbs up or down | Feeds the empathy bandit | H5-H6 |
| Swipe between modules | Navigation | H6 |
| Virtual mouse | Useful, not human; registered tools first (Codex agrees) | Last |
| Safety invariants | A good human assistant also asks before anything risky | M3, before any new tool |

## 5. The stages

Each stage keeps everything before it working, and is measured before the
next starts.

### H1, now (1-2 weeks, no training): "never says it can't"

1. **The model gets the web tools** (layer 3 above). **Built 25 Oct** (see DEVLOG). The fixed rules stay
   first. Test: the "Can you open YouTube?" transcript from 24 Oct, with the
   rules switched off, opens YouTube through a tool call.
2. **Friday speaks spoken Sinhala, not written.** A per-language rule in
   the character sheet and 6-8 example pairs checked by Adhi (written ->
   spoken, e.g. "මම මෙය සිදු කරන්නෙමි" -> "මම මේක කරන්නම්"). Technical words
   stay in English the way you say them ("Fourier series එක"). Measure:
   native speakers rate both versions, same sentences.
3. **Repair says what it heard.** When the text is close to a command but
   matches nothing (fuzzy match, e.g. rapidfuzz), or Whisper's confidence is
   low: "I heard 'open you two'. Did you mean YouTube?" Only "yes" or a
   repeat acts on it.
4. **The messy-phrasing test set** (started 25 Oct: `eval/commands.jsonl`, 60 lines, run with
   `scripts/command_check.py`). About 150 real ways Adhi says the
   current commands, in English, Sinhala and Singlish: polite forms,
   fillers, self-corrections ("open Bing, no, YouTube"), Whisper's typical
   errors. Typed first, then spoken. This becomes the classifier's test set
   too; it is never used for training.
5. **Telemetry counts** the "wrongly said I can't" rate, repair turns ("no,
   I meant", "what?") per 100 turns, and first-audio p50/p95.

**Done when:** on the messy set, "wrongly said I can't" is 0, and the right
action is taken for at least 90% of requests in each language, with wrong
actions at most 2%.

### H2 (M3, Adhi's ML): understands any wording

6. **The classifier:** level 1 (character n-gram TF-IDF with logistic
   regression; LightGBM to compare), then level 2 (multilingual-e5-small
   features with logistic regression). It trains on the 15,630 generated
   sentences plus confirmed corrections, is tested on the messy set, and
   plugs in through `IntentRouter`. Slots (site, query, number) come from
   the rules, or from the model when they can't. **Ready to train 25 Oct:**
   the guide `docs/TRAINING_INTENT.md`, the sets (`scripts/make_intent_sets.py`),
   the scoring (`scripts/intent_eval.py`), and `[intents]` in settings.toml,
   which puts the trained file in front of the routing rules; acting on
   commands comes once it scores well on the real set.
7. **Confidence gate** with a two-option question ("Bing or YouTube?").
8. **Learning from corrections** (D27): opt-in examples, the
   similar-examples lookup, a weekly retrain, and the new model kept only if
   it beats the old one on the fixed test set.
9. **The M3 safety gate, registry and action log** (Codex step 3), needed
   before any tool beyond Bing and YouTube.

**Done when:** right action at least 95% per language, wrong action at most
1%, an unnecessary question at most 10% of the time, and confidence
calibrated (expected calibration error reported).

### H3 (M6 window, Codex steps 4-6): looks like it's listening

10. **The window:** the orb with its states, captions, the "what I heard"
    line, the status labels and colours (Codex section 4).
11. **Hands-free turn-taking:** wake word "Hey Jarvis", then Silero VAD
    decides when you've finished. It waits longer after an unfinished-
    sounding ending ("and", "eka", "ඒ කියන්නේ"). Echo cancellation lets
    you interrupt Jarvis by speaking. Push-to-talk stays as a backup.
12. **Optional double clap** (Codex section 6), after the wake word works.

**Done when:** p50 first audio under 1.2 s; Jarvis starts talking while
you're still speaking in under 5% of turns; false wakes per hour measured
with a lecture video playing.

### H4 (M4 Study and memory): remembers like a friend would

13. **Threads** with one-line summaries (D26). "Back to the Newton thing"
    resumes a thread; once per session, the greeting may offer to carry on
    ("Last time it was Fourier series. Shall we carry on?").
14. **Memory retrieval:** the relevant facts and summaries, not all of
    them, with the same encoder.
15. **Notes RAG** for Study, citing the page.
16. **Search-and-read** (REVIEW_FIXES.md), after M3.

**Done when:** 20 questions about earlier sessions and notes are answered
correctly with the source named, and nothing is invented.

### H5 (Phase 1.5): notices how you feel

17. The feedback bandit (quick win 3), then the emotion model beside
    Whisper, using the improvement ladder already in ROADMAP.md.
18. Voice speed and pauses follow the mode; an expressive TTS voice gets
    compared only if ratings show the voice is what sounds flat.

### H6 (Phases 3 and 5): body language and initiative

19. Open palm to pause, thumbs for feedback (Codex section 7), with camera
    use opt-in and local. Palm to pause (right hand, D29) can start early:
    IMPLEMENTATION_PLAN.md, M8.
20. Speaking up on its own: rare, opt-in, at most a few times a day ("Your
    PMAT exam is on Monday. Want a quick revision plan?").
21. The virtual mouse last, as Codex recommends.

## 6. Measuring "feels human"

- **Blind pairwise test per stage:** the same 20 requests answered by the
  old and new version; listeners (Adhi, and friends with consent) pick which
  felt more like talking to a person. Report the win rate.
- **Godspeed and the System Usability Scale**, as ROADMAP.md already plans.
- **Turn numbers from telemetry:** first audio p50/p95, the "wrongly said I
  can't" rate, repair turns per 100, unnecessary questions, cut-offs.
- **Sinhala naturalness:** native speakers rate Friday's replies from 1 to
  5, spoken-style against written-style.
- **Wellbeing in long trials** (Fang et al. 2025, in ROADMAP.md): daily use
  and a short loneliness questionnaire, since feeling human can also mean
  too much reliance.

## 7. What we won't do

- Pretend to be human or claim feelings: the character sheet's boundaries
  stay.
- Fine-tune the hosted model to "sound human": we can't, and the character
  sheet and context should be enough (D14). A personal LoRA model stays a
  later research option ("Learning from use").
- Say "mm-hm" while you're talking: with push-to-talk it would talk over
  you. The orb shows listening instead.
- Let voice, a clap or a gesture approve anything risky (Codex section 9).
- Train on Jarvis's own unchecked guesses (D27).
