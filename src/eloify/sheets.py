"""Google Sheets backend via gspread.

Auth uses a service-account key, provided either as a file path
(GOOGLE_SERVICE_ACCOUNT_FILE) or inline JSON (GOOGLE_SERVICE_ACCOUNT_JSON).
The Games and Players worksheets are located by gid (see config).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from . import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
GAMES_HEADERS = ["id", "played_at", "mode", "team_a", "team_b", "score_a", "score_b"]
PLAYERS_HEADERS = ["name", "created_at"]


class SheetsError(RuntimeError):
    """User-facing error talking to Google Sheets."""


def _credentials() -> Credentials:
    inline = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if inline:
        try:
            info = json.loads(inline)
        except json.JSONDecodeError as e:
            raise SheetsError(f"GOOGLE_SERVICE_ACCOUNT_JSON isn't valid JSON: {e}") from e
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    if path:
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            raise SheetsError(
                f"GOOGLE_SERVICE_ACCOUNT_FILE points to a missing file: {path}"
            )
        return Credentials.from_service_account_file(path, scopes=SCOPES)
    raise SheetsError(
        "No credentials found. In .env set GOOGLE_SERVICE_ACCOUNT_FILE (path to "
        "your service-account JSON) or GOOGLE_SERVICE_ACCOUNT_JSON (inline JSON)."
    )


def _explain_api_error(e: Exception) -> str:
    msg = str(e)
    if "PERMISSION_DENIED" in msg or "403" in msg:
        return (
            "Permission denied. Share the spreadsheet with the service account's "
            "client_email (…iam.gserviceaccount.com) as an Editor."
        )
    if "NOT_FOUND" in msg or "404" in msg:
        return "Spreadsheet or tab not found — check the IDs/gids in .env."
    return f"Google Sheets API error: {msg}"


class Store:
    """Thin wrapper over the two worksheets."""

    def __init__(self) -> None:
        self._gc = gspread.authorize(_credentials())
        try:
            self._ss = self._gc.open_by_key(config.SPREADSHEET_ID)
            self.games_ws = self._ss.get_worksheet_by_id(config.GAMES_GID)
            self.players_ws = self._ss.get_worksheet_by_id(config.PLAYERS_GID)
        except gspread.exceptions.APIError as e:
            raise SheetsError(_explain_api_error(e)) from e

    @staticmethod
    def _has_header(ws) -> bool:
        return any(ws.row_values(1))

    # ---- reads ----
    def read_games(self) -> list[dict]:
        if not self._has_header(self.games_ws):
            return []
        return self.games_ws.get_all_records(expected_headers=GAMES_HEADERS)

    def read_players(self) -> list[dict]:
        if not self._has_header(self.players_ws):
            return []
        return self.players_ws.get_all_records(expected_headers=PLAYERS_HEADERS)

    def player_names(self) -> list[str]:
        return [str(r["name"]).strip() for r in self.read_players() if str(r.get("name", "")).strip()]

    # ---- writes ----
    def ensure_headers(self) -> list[str]:
        created = []
        if not self._has_header(self.games_ws):
            self.games_ws.update([GAMES_HEADERS], "A1")
            created.append("Games")
        if not self._has_header(self.players_ws):
            self.players_ws.update([PLAYERS_HEADERS], "A1")
            created.append("Players")
        return created

    @staticmethod
    def next_game_id(games: list[dict]) -> int:
        ids = [int(g["id"]) for g in games if str(g.get("id", "")).strip().lstrip("-").isdigit()]
        return (max(ids) + 1) if ids else 1

    def append_game(
        self,
        game_id: int,
        mode: str,
        team_a: list[str],
        team_b: list[str],
        score_a: int,
        score_b: int,
    ) -> None:
        played_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.games_ws.append_row(
            [game_id, played_at, mode, ", ".join(team_a), ", ".join(team_b), score_a, score_b],
            value_input_option="USER_ENTERED",
        )

    def add_player(self, name: str) -> None:
        played_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.players_ws.append_row(
            [name, played_at], value_input_option="USER_ENTERED"
        )

    def delete_last_game(self) -> dict | None:
        games = self.read_games()
        if not games:
            return None
        self.games_ws.delete_rows(len(games) + 1)  # +1 for the header row
        return games[-1]
