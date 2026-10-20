"""Choose the push-to-talk key by pressing it.

    uv run python scripts/choose_key.py              press the key you want
    uv run python scripts/choose_key.py --name f9    set it by name

The key is saved in config/settings.local.toml (settings for this computer,
kept when you update). Pick one you don't type with: Right Ctrl, Right Alt,
F9 (on laptops maybe Fn+F9), Insert, Pause, ...
"""

from __future__ import annotations

import argparse
import queue
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import LOCAL_SETTINGS, load_settings, set_local_value  # noqa: E402
from jarvis.voice.capture import check_push_to_talk_key, describe_key, parse_key  # noqa: E402

LOCAL_PATH = ROOT / "config" / LOCAL_SETTINGS


def key_name(key) -> str | None:
    """pynput key -> the name settings.toml uses ('ctrl_r', 'f9', 'a'), or None."""
    name = getattr(key, "name", None)        # keyboard.Key members
    if name:
        return name
    char = getattr(key, "char", None)        # keyboard.KeyCode with a character
    return char or None


def drain_console() -> None:
    """Throw away keys typed while choosing, so they don't end up in the next prompt."""
    try:
        import msvcrt
    except ImportError:
        return
    while msvcrt.kbhit():
        msvcrt.getwch()


def save(name: str) -> int:
    problem = check_push_to_talk_key(name)
    if problem:
        print(f"Not saved: {problem}")
        return 1
    try:
        parse_key(name)
    except ValueError as exc:
        print(f"Not saved: {exc}")
        return 1
    except Exception:   # pynput can't load without a desktop; nothing to check against
        pass
    set_local_value(LOCAL_PATH, "hotkeys", "push_to_talk", name)
    print(f"Saved. Hold {describe_key(name)} to talk to Jarvis.")
    return 0


def press_to_choose(current: str) -> int:
    try:
        from pynput import keyboard
    except Exception as exc:   # no desktop session, library missing
        print(f"Can't watch the keyboard here ({exc}). Use --name instead, e.g. --name f9")
        return 1

    print(f"Push-to-talk key now: {describe_key(current)}")
    print("Press the key you want to hold while talking, or Esc to keep it.")
    print("(Not the Windows or Copilot key, and not one you type with.)")
    pressed: queue.Queue = queue.Queue()
    with keyboard.Listener(on_press=pressed.put):
        while True:
            key = pressed.get()
            if key == keyboard.Key.esc:
                drain_console()
                print(f"Kept {describe_key(current)}.")
                return 0
            name = key_name(key)
            problem = check_push_to_talk_key(name)
            if problem:
                print(f"  {problem} Try another key.")
                continue
            break
    drain_console()
    return save(name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--name", help="key name instead of pressing it: ctrl_r, alt_r, f9, insert, ...")
    args = ap.parse_args()
    if args.name:
        return save(args.name.strip().lower())
    current = load_settings().get("hotkeys.push_to_talk", "ctrl_r")
    return press_to_choose(current)


if __name__ == "__main__":
    raise SystemExit(main())
