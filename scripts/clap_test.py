"""Try the double clap on your own microphone, and pick its settings from your own claps.

    uv run python scripts/clap_test.py                  # 60 s; clap, double-clap, tap the desk, talk
    uv run python scripts/clap_test.py --seconds 120 --min-share 0.25

Prints every sharp sound it hears (its loudness, how far above the room's noise, and its share of energy
above 2 kHz: claps are high, desk taps and knocks low) and every double clap. Nothing is saved.

At the end: the shares of what counted and of what didn't. Put a value between your claps' and your
taps' in config/settings.local.toml:

    [clap]
    enabled = true
    min_high_share = 0.3
"""

from __future__ import annotations

import argparse
import queue
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from jarvis.config import load_settings  # noqa: E402
from jarvis.perception.clap import ClapDetector, ClapSettings  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--min-share", type=float, help="try another min_high_share than the settings'")
    args = ap.parse_args(argv)
    settings = load_settings()
    s = ClapSettings.from_settings(settings)
    if args.min_share is not None:
        s.min_high_share = args.min_share
    detector = ClapDetector(16000, s)
    blocks: queue.Queue = queue.Queue()
    import sounddevice as sd
    device = settings.get("audio.input_device", "") or None
    print(f"Listening for {args.seconds:.0f} s (min_high_share {s.min_high_share}, rise {s.rise_db} dB). "
          "Clap twice, clap once, tap the desk, knock, talk. Ctrl+C stops.")
    counted, refused, doubles = [], [], 0
    start = time.monotonic()
    with sd.InputStream(samplerate=16000, channels=1, dtype="float32", device=device,
                        callback=lambda data, frames, t, status: blocks.put(data[:, 0].copy())):
        try:
            while time.monotonic() - start < args.seconds:
                try:
                    block = blocks.get(timeout=0.5)
                except queue.Empty:
                    continue
                for e in detector.feed(block):
                    if e.kind == "double":
                        doubles += 1
                        print(f"  {e.t:7.2f} s  DOUBLE CLAP  -> Jarvis would listen")
                    elif e.counted:
                        counted.append(e.high_share)
                        print(f"  {e.t:7.2f} s  clap   {e.db:6.1f} dB, {e.above:4.1f} above the room, high share "
                              f"{e.high_share:.2f}")
                    else:
                        refused.append(e.high_share)
                        print(f"  {e.t:7.2f} s  (not a clap: {e.why}) {e.db:6.1f} dB, high share {e.high_share:.2f}")
        except KeyboardInterrupt:
            pass
    print(f"\nRoom noise: {detector.floor_db:.0f} dB. {len(counted)} claps, {len(refused)} low-pitched sounds, "
          f"{doubles} double claps.")
    for name, values in (("claps", counted), ("low-pitched", refused)):
        if values:
            print(f"  {name}: high share {np.min(values):.2f} to {np.max(values):.2f} (middle {np.median(values):.2f})")
    print("Paste this to Claude, or set [clap] min_high_share between the two.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
