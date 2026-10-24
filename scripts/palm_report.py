"""What the palm recordings say: is the points check right, and which limit to use?

    uv run python scripts/palm_report.py                    the newest recording
    uv run python scripts/palm_report.py data/gestures/*.csv   several sessions together

Reads the rows recorded with scripts/gesture_preview.py (P = palm, N = not
palm) and prints, for the "palm" rows and the "not palm" rows separately:
  1. what MediaPipe said (its gesture and its open-palm score),
  2. each finger of the points check, and which way the hand faces, so a
     check that's the wrong way round shows up at once,
  3. a table of limits: how many real palms each limit catches and how many
     "not palm" frames it would wrongly count, frame by frame,
  4. the recording replayed through the 0.5 s hold, as Jarvis would use it:
     palms accepted per minute while you showed palms, and false ones per
     minute while you didn't (and while you waved, if you recorded waves).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import gesture_preview as gp  # the same points check the preview uses

LIMITS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]


def load(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with path.open(encoding="utf-8") as f:
            rows += [dict(r, session=path.stem) for r in csv.DictReader(f)]
    return rows


def hand_of(row: dict) -> gp.Hand:
    points = [(float(row[f"x{i}"]), float(row[f"y{i}"]), float(row[f"z{i}"])) for i in range(21)]
    return gp.Hand(side=row["side"], side_score=float(row["side_score"]), gesture=row["mp_gesture"],
                   gesture_score=float(row["mp_score"]), points=points, world=[])


def share(n: int, total: int) -> str:
    return f"{n / total:4.0%}" if total else "  - "


def mp_palm(row: dict, limit: float) -> bool:
    return row["mp_gesture"] == "Open_Palm" and float(row["mp_score"]) >= limit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", type=Path, help="recordings (default: the newest in data/gestures)")
    args = ap.parse_args()
    paths = args.files or sorted(gp.RECORD_DIR.glob("palm-*.csv"))[-1:]
    if not paths:
        print("No recordings yet. Record some with scripts/gesture_preview.py (P = palm, N = not palm).")
        return 1
    rows = load(paths)
    groups = {"palm": [r for r in rows if r["label"] == "palm"],
              "not palm": [r for r in rows if r["label"] == "other"]}
    if any(r["label"] == "wave" for r in rows):
        groups["wave"] = [r for r in rows if r["label"] == "wave"]
    print(f"{len(rows)} rows from {', '.join(p.name for p in paths)}: "
          + ", ".join(f"{len(g)} {name}" for name, g in groups.items()) + "\n")

    # 1. What MediaPipe said.
    print("1. MediaPipe's gesture")
    for name, group in groups.items():
        counts: dict[str, int] = {}
        for r in group:
            counts[r["mp_gesture"]] = counts.get(r["mp_gesture"], 0) + 1
        top = ", ".join(f"{g} {share(n, len(group)).strip()}" for g, n in sorted(counts.items(), key=lambda kv: -kv[1]))
        print(f"   {name:9} {top}")
    scores = sorted(float(r["mp_score"]) for r in groups["palm"] if r["mp_gesture"] == "Open_Palm")
    if scores:
        print(f"   open-palm score on real palms: low 10% {gp.percentile(scores, 0.1):.2f}, "
              f"middle {gp.percentile(scores, 0.5):.2f}, high 10% {gp.percentile(scores, 0.9):.2f}")

    # 2. The points check, finger by finger, and which way the hand faces.
    print("\n2. Points check (share of rows)")
    print(f"   {'':9} {'thumb':>6} {'index':>6} {'middle':>6} {'ring':>6} {'little':>6} {'all 5':>6} "
          f"{'facing':>7}")
    facing_share = {}
    for name, group in groups.items():
        out = [gp.fingers_out(hand_of(r), int(r["frame_w"]), int(r["frame_h"])) for r in group]
        facing = [gp.palm_facing(hand_of(r), int(r["frame_w"]), int(r["frame_h"])) for r in group]
        n = len(group)
        cols = [share(sum(o[i] for o in out), n) for i in range(5)]
        facing_share[name] = sum(facing) / n if n else 0.0
        print(f"   {name:9} " + " ".join(f"{c:>6}" for c in cols) +
              f" {share(sum(all(o) for o in out), n):>6} {share(sum(facing), n):>7}")
    if groups["palm"] and facing_share["palm"] < 0.3:
        print("   -> Real palms mostly count as 'back of hand': the facing check is the wrong way round "
              "on this camera.\n      Set FACING_SIGN = -1 near the top of scripts/gesture_preview.py "
              "(the table below already uses it).")
        gp.FACING_SIGN = -gp.FACING_SIGN          # use the corrected direction for the table below
    elif groups["palm"]:
        print("   -> The facing check agrees with your palms.")

    # 3. Limits: real palms caught vs "not palm" frames wrongly counted.
    print("\n3. Limits (per frame)        real palms caught   not-palm frames counted")
    for limit in LIMITS:
        caught = sum(mp_palm(r, limit) for r in groups["palm"])
        wrong = sum(mp_palm(r, limit) for r in groups["not palm"])
        print(f"   MediaPipe >= {limit:.2f}          {share(caught, len(groups['palm'])):>6}"
              f"              {share(wrong, len(groups['not palm'])):>6}")

    def points(r: dict) -> bool:
        return gp.points_say_palm(hand_of(r), int(r["frame_w"]), int(r["frame_h"]))

    caught = sum(points(r) for r in groups["palm"])
    wrong = sum(points(r) for r in groups["not palm"])
    print(f"   points check alone          {share(caught, len(groups['palm'])):>6}"
          f"              {share(wrong, len(groups['not palm'])):>6}")
    caught = sum(mp_palm(r, 0.5) or points(r) for r in groups["palm"])
    wrong = sum(mp_palm(r, 0.5) or points(r) for r in groups["not palm"])
    print(f"   MediaPipe >= 0.50 or points {share(caught, len(groups['palm'])):>6}"
          f"              {share(wrong, len(groups['not palm'])):>6}")
    print("\nA good limit catches most real palms while counting almost no 'not palm' frames.")

    # 4. Replay through the hold: what Jarvis would actually do.
    names = list(groups)
    print("\n4. Through the 0.5 s hold (accepted per minute of recording)")
    print("   rule                          " + "".join(f"{name:>12}" for name in names))
    rules = [(f"MediaPipe >= {limit:.2f}", lambda r, limit=limit: mp_palm(r, limit))
             for limit in (0.50, 0.55, 0.60, 0.65, 0.70)]
    rules += [("points check alone", points),
              ("MediaPipe >= 0.50 or points", lambda r: mp_palm(r, 0.5) or points(r))]
    for title, rule in rules:
        cells = []
        for name in names:
            events, minutes = replay(rows_by_segment(rows, name), rule)
            cells.append(f"{events / minutes:5.1f} ({events})" if minutes else "  -")
        print(f"   {title:29} " + "".join(f"{c:>12}" for c in cells))
    print("   Wanted: high under palm (about one per palm you showed), near 0 under not palm and wave.")
    return 0


LABELS = {"palm": "palm", "not palm": "other", "wave": "wave"}


def rows_by_segment(rows: list[dict], name: str) -> list[list[dict]]:
    """Stretches of one label, in time order, per session."""
    segments: list[list[dict]] = []
    last = None
    for r in rows:
        key = (r["session"], r["label"])
        if key != last:
            segments.append([])
            last = key
        if r["label"] == LABELS[name]:
            segments[-1].append(r)
    return [seg for seg in segments if seg]


def replay(segments: list[list[dict]], is_palm) -> tuple[int, float]:
    """Run each stretch through the preview's hold rule; count accepted palms."""
    events, seconds = 0, 0.0
    for seg in segments:
        hold = gp.PalmHold()
        prev = None
        for r in seg:
            t = float(r["t"])
            if prev is not None and t - prev > 0.2:        # the hand left the picture
                for _ in range(hold.max_missed + 1):
                    hold.update(prev + 0.1, False)
                hold.update(t - 0.01, False)
            events += hold.update(t, is_palm(r))
            prev = t
        seconds += float(seg[-1]["t"]) - float(seg[0]["t"])
    return events, seconds / 60


if __name__ == "__main__":
    raise SystemExit(main())
