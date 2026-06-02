"""Configuration, loaded from .env (with sensible defaults for this sheet)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the current directory first (dev: the repo's .env wins), then
# fall back to a fixed per-user location so `elo` works from any directory when
# installed globally (e.g. via pipx). load_dotenv() doesn't override variables
# that are already set, so the first source loaded takes precedence.
USER_ENV = Path.home() / ".config" / "eloify" / ".env"

load_dotenv()  # cwd / nearest .env (development)
if USER_ENV.exists():
    load_dotenv(USER_ENV)  # fallback for global installs

SPREADSHEET_ID = os.environ.get(
    "ELOIFY_SPREADSHEET_ID", "13V6-luJnRIZCEG3C-M_maM28GBC4NwvqcwHJ-b6nLq4"
)
GAMES_GID = int(os.environ.get("ELOIFY_GAMES_GID", "0"))
PLAYERS_GID = int(os.environ.get("ELOIFY_PLAYERS_GID", "604449976"))

# Which rating model `elo` uses when --model isn't passed. None falls back to
# the registry default; set ELOIFY_MODEL to any key shown by `elo models`.
DEFAULT_MODEL = os.environ.get("ELOIFY_MODEL") or None
