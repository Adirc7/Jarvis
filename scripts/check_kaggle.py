"""Does Jarvis's Kaggle token work? Signs in and says so; never prints the token.

    uv run python scripts/check_kaggle.py

Reads KAGGLE_API_TOKEN from .env (Kaggle > Settings > API Tokens > Generate New
Token; docs/TRAINING_STANDIN.md), asks Kaggle whose token it is, and lists one
of your notebooks to be sure the API answers. Prints the username and OK, or
what's wrong.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis.config import load_dotenv  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env")
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if not token:
        print("No KAGGLE_API_TOKEN in .env. Add a line KAGGLE_API_TOKEN=<your token> to .env and save it.")
        return 1
    if token.startswith(("'", '"')) or token != os.environ["KAGGLE_API_TOKEN"]:
        print("Note: the token in .env has spaces or quotes around it; Jarvis trims them.")
        os.environ["KAGGLE_API_TOKEN"] = token.strip("'\"")
    print(f"Token found ({len(token)} characters; not shown).")
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        print(f"The Kaggle package isn't installed ({exc}). Run scripts\\update.cmd first.")
        return 1
    api = KaggleApi()
    try:
        signed_in = api._authenticate_with_access_token()     # the token only: no kaggle.json fallback
    except Exception as exc:  # noqa: BLE001 - no internet, Kaggle down: say so plainly
        print(f"Couldn't reach Kaggle: {type(exc).__name__}: {str(exc)[:200]}")
        print("Check the internet connection and try again.")
        return 1
    if not signed_in:
        print("Kaggle doesn't accept this token (mistyped, cut short, or deleted on the website).")
        print("Generate a new one (Settings > API Tokens), put it in .env and run this again.")
        return 1
    username = api.config_values.get(api.CONFIG_NAME_USER, "?")
    api._authenticated = True
    try:
        api.kernels_list(mine=True, page_size=1)
    except Exception as exc:  # noqa: BLE001
        print(f"Signed in as {username}, but listing your notebooks failed: {type(exc).__name__}: {str(exc)[:200]}")
        return 1
    print(f"OK: Kaggle works. Signed in as {username}.")
    print("For the free GPU, your phone number must be verified (Kaggle > Settings > Phone Verification).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
