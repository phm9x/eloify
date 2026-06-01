"""Configuration, loaded from .env (with sensible defaults for this sheet)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

SPREADSHEET_ID = os.environ.get(
    "ELOIFY_SPREADSHEET_ID", "13V6-luJnRIZCEG3C-M_maM28GBC4NwvqcwHJ-b6nLq4"
)
GAMES_GID = int(os.environ.get("ELOIFY_GAMES_GID", "0"))
PLAYERS_GID = int(os.environ.get("ELOIFY_PLAYERS_GID", "604449976"))
