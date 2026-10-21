"""Can Friday have native Sinhala pronunciation in Emma's voice? Voice conversion test.

Piper's "dilu" voice was trained on real Sinhala speech, so its pronunciation
is native; Kokoro's Emma is the voice Adhi chose for Friday. kNN-VC (MIT
licence, github.com/bshall/knn-vc) re-voices dilu's Sinhala in Emma's voice:
it describes every 20 ms of speech with WavLM features and swaps each frame
for the closest-sounding frame of Emma's speech. No training: it only needs a
few minutes of Emma talking, which Kokoro makes in seconds.

Three steps, run by scripts/try_friday_voice.cmd:

  --prepare DIR   (Jarvis's environment) Emma's reference speech: Harvard
                  sentences and longer ones in English, plus her eSpeak
                  Sinhala; dilu's Sinhala sentences; today's Friday.
  --convert DIR   (a test environment with torch) dilu -> Emma with kNN-VC,
                  once per --topk value (default 2, 4 and 8), to compare.
  --finish DIR    (Jarvis's environment) the Jarvis voice effects on all three
                  versions, written to DIR/listen/ to compare.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.voice.audio_io import load_wav, save_wav  # noqa: E402  (standard library and numpy only)

SINHALA = [
    "ආයුබෝවන්, මම ෆ්‍රයිඩේ.",
    "හරි, මම දැන් සිංහලෙන් කතා කරන්නම්.",
    "තාපගති විද්‍යාවේ පළමු නියමය කියන්නේ ශක්තිය නිර්මාණය කරන්නවත් විනාශ කරන්නවත් බැහැ කියන එකයි.",
    "සමාවෙන්න, මට තේරුණේ නෑ. ආයේ පාරක් කියන්න, නැත්නම් ටයිප් කරන්න.",
    "අද ලැබ් එකේදී අපි පරිපථයක් හැදුවා, ඒත් අගය බලාපොරොත්තු වුණාට වඩා අඩුයි.",
]

# Harvard sentences (IEEE 1969, public domain): they cover English sounds evenly.
HARVARD = [
    "The birch canoe slid on the smooth planks.", "Glue the sheet to the dark blue background.",
    "It's easy to tell the depth of a well.", "These days a chicken leg is a rare dish.",
    "Rice is often served in round bowls.", "The juice of lemons makes fine punch.",
    "The box was thrown beside the parked truck.", "The hogs were fed chopped corn and garbage.",
    "Four hours of steady work faced us.", "A large size in stockings is hard to sell.",
    "The boy was there when the sun rose.", "A rod is used to catch pink salmon.",
    "The source of the huge river is the clear spring.", "Kick the ball straight and follow through.",
    "Help the woman get back to her feet.", "A pot of tea helps to pass the evening.",
    "Smoky fires lack flame and heat.", "The soft cushion broke the man's fall.",
    "The salt breeze came across from the sea.", "The girl at the booth sold fifty bonds.",
    "The small pup gnawed a hole in the sock.", "The fish twisted and turned on the bent hook.",
    "Press the pants and sew a button on the vest.", "The swan dive was far short of perfect.",
    "The beauty of the view stunned the young boy.", "Two blue fish swam in the tank.",
    "Her purse was full of useless trash.", "The colt reared and threw the tall rider.",
    "It snowed, rained, and hailed the same morning.", "Read verse out loud for pleasure.",
    "Hoist the load to your left shoulder.", "Take the winding path to reach the lake.",
    "Note closely the size of the gas tank.", "Wipe the grease off his dirty face.",
    "Mend the coat before you go out.", "The wrist was badly strained and hung limp.",
    "The stray cat gave birth to kittens.", "The young girl gave no clear response.",
    "The meal was cooked before the bell rang.", "What joy there is in living.",
]
LONGER = [
    "Good evening. All systems are running normally, and nothing needs your attention right now.",
    "The first law of thermodynamics says that energy can change its form, but it is never created or destroyed.",
    "When the current through a resistor doubles, the voltage across it doubles as well, as Ohm's law predicts.",
    "Entropy measures how many ways the parts of a system can be arranged without changing what we see.",
    "A wave carries energy from one place to another, while the medium itself mostly stays where it is.",
    "If the series converges, its terms must shrink towards zero, although that alone is not enough.",
    "Your lecture starts in forty minutes, so there is still time for a quick cup of tea.",
    "I have saved the report in your documents folder and made a copy for the project as well.",
    "The weather looks clear this afternoon, with a light breeze coming in from the west.",
    "Shall I read the last message again, or would you like me to summarise it instead?",
    "Radioactive decay is random for a single nucleus, yet very predictable for a large sample.",
    "Let's take it one step at a time: first the forces, then the equations, and finally the answer.",
    "The photoelectric effect showed that light arrives in packets of energy called photons.",
    "A capacitor stores energy in its electric field and releases it when the circuit asks for it.",
    "Numerical methods trade a little accuracy for answers we could never find with pen and paper.",
    "Please remember to drink some water; you have been studying for almost three hours.",
    "The matrix has two equal eigenvalues, so we should check whether it can still be diagonalised.",
    "I couldn't find that file, but there is a similar one from last week in the downloads folder.",
    "Quantum mechanics describes particles with wave functions that give the chance of each result.",
    "That was a good session. Shall I note down what we covered, so we can pick it up tomorrow?",
    "Momentum is conserved in every collision, even when some of the kinetic energy turns into heat.",
    "The derivative tells us how fast a quantity changes, and the integral adds up all those changes.",
    "Sound travels faster in water than in air, because the molecules are packed much more closely.",
    "A good way to revise is to explain each idea out loud, as if you were teaching it to a friend.",
    "The train to Colombo leaves in half an hour, and the next one is not until the evening.",
    "Your battery is getting low, so it might be a good moment to plug in the charger.",
    "Electric and magnetic fields are two sides of the same thing, as Maxwell's equations show.",
    "I've drafted a reply to the email, but you might want to change the second paragraph.",
    "Gravity bends the path of light, which is why distant galaxies can look stretched and doubled.",
    "Standard deviation tells you how far the values usually sit from the average, in the same units.",
    "Before we solve the equation, let's check the units on both sides, to catch any mistakes early.",
    "Heat always flows from the hotter object to the colder one, unless some work is done to reverse it.",
    "The experiment went well overall, though the last two readings look a little suspicious.",
    "If you're feeling tired, a short walk outside might help more than another cup of coffee.",
    "Good night. Everything is saved, and I'll be right here when you need me tomorrow.",
]


def prepare(out: Path) -> None:
    from jarvis.config import load_settings
    from jarvis.voice.tts import KokoroTTS, PiperTTS

    settings = load_settings()
    model = settings.path("tts.kokoro_model", "models/kokoro-v1.0.onnx")
    voices = settings.path("tts.kokoro_voices", "models/voices-v1.0.bin")
    device = str(settings.get("tts.device", "auto"))
    emma_en = KokoroTTS(model, voices, "bf_emma", "en-gb", device=device)
    emma_si = KokoroTTS(model, voices, "bf_emma", "si", device=device)
    dilu_path = settings.path("tts.piper_dir", "models/piper") / "si_LK-dilu-medium.onnx"
    dilu = PiperTTS(dilu_path)

    t0 = time.perf_counter()
    seconds = 0.0
    for i, text in enumerate(HARVARD + LONGER):                     # Emma's "voice matrix"
        audio = emma_en.synthesize(text)
        save_wav(out / "reference" / f"emma_en_{i:03d}.wav", audio, emma_en.sample_rate)
        seconds += len(audio) / emma_en.sample_rate
    for i, text in enumerate(SINHALA):                              # her try at Sinhala sounds
        audio = emma_si.synthesize(text)
        save_wav(out / "reference" / f"emma_si_{i:03d}.wav", audio, emma_si.sample_rate)
        save_wav(out / "now" / f"{i:03d}.wav", audio, emma_si.sample_rate)
        seconds += len(audio) / emma_si.sample_rate
    for i, text in enumerate(SINHALA):                              # native pronunciation
        save_wav(out / "dilu" / f"{i:03d}.wav", dilu.synthesize(text), dilu.sample_rate)
    print(f"Emma reference: {seconds / 60:.1f} minutes of speech; {len(SINHALA)} Sinhala sentences "
          f"by dilu and by today's Friday ({time.perf_counter() - t0:.0f} s, Emma on {emma_en.device})")


def convert(out: Path, topks: list[int]) -> None:
    import torch
    import torchaudio

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"torch {torch.__version__} on {device}; loading kNN-VC (the first time downloads about 1.3 GB)...")
    knn_vc = torch.hub.load("bshall/knn-vc", "knn_vc", prematched=True, trust_repo=True, pretrained=True,
                            device=device)

    def load16k(path: Path) -> torch.Tensor:
        audio, sr = load_wav(path)                                  # no torchaudio file reading on Windows
        x = torch.from_numpy(audio)[None]
        return torchaudio.functional.resample(x, sr, 16000) if sr != 16000 else x

    t0 = time.perf_counter()
    refs = [load16k(p) for p in sorted((out / "reference").glob("*.wav"))]
    matching = knn_vc.get_matching_set(refs)
    print(f"Emma's matching set: {matching.shape[0]} frames ({time.perf_counter() - t0:.0f} s)")
    # topk: how many of Emma's closest frames are averaged for each 20 ms.
    # Fewer = more distinctly Emma but rougher; more = smoother, more of dilu.
    for src in sorted((out / "dilu").glob("*.wav")):
        t = time.perf_counter()
        query = knn_vc.get_features(load16k(src))
        feature_s = time.perf_counter() - t
        for k in topks:
            t = time.perf_counter()
            wav = knn_vc.match(query, matching, topk=k).cpu().numpy().astype(np.float32)
            save_wav(out / f"converted_k{k}" / src.name, wav, 16000)
            print(f"  {src.name} k={k}: {len(wav) / 16000:.1f} s of speech in "
                  f"{feature_s + time.perf_counter() - t:.1f} s")


def finish(out: Path) -> None:
    from jarvis.config import load_settings
    from jarvis.voice.effects import VoiceStyle

    style = VoiceStyle.from_dict(load_settings().get("voice_style", {}))
    names = {"now": "1_friday_now_espeak", "dilu": "2_dilu_original"}
    for folder in sorted(out.glob("converted_k*"), key=lambda d: int(d.name.split("_k")[1])):
        names[folder.name] = f"3_friday_converted_{folder.name.split('_')[1]}"     # 3_friday_converted_k2 ...
    for folder, name in names.items():
        parts, rate = [], None
        for f in sorted((out / folder).glob("*.wav")):
            audio, sr = load_wav(f)
            rate = rate or sr
            parts += [audio, np.zeros(int(0.6 * sr), np.float32)]
        if not parts:
            print(f"  {name}: nothing to compare (did a step fail?)")
            continue
        audio = style.process(np.concatenate(parts), rate)
        save_wav(out / "listen" / f"{name}.wav", audio, rate)
        print(f"  {out / 'listen' / (name + '.wav')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    step = ap.add_mutually_exclusive_group(required=True)
    step.add_argument("--prepare", type=Path, metavar="DIR")
    step.add_argument("--convert", type=Path, metavar="DIR")
    step.add_argument("--finish", type=Path, metavar="DIR")
    ap.add_argument("--topk", default="2,4,8",
                    help="Emma frames averaged per 20 ms, comma-separated for several versions (kNN-VC default 4)")
    args = ap.parse_args()
    if args.prepare:
        prepare(args.prepare)
    elif args.convert:
        convert(args.convert, [int(k) for k in str(args.topk).split(",")])
    else:
        finish(args.finish)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
