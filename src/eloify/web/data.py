"""Cached data-access / service layer over `sheets.Store` + `engine`.

`sheets.Store` hits the Google API on every read, which is too slow and
rate-limited to do per request. This module keeps a short-lived snapshot of the
game log + player names (refreshed on expiry, guarded by a lock) and exposes
read/write helpers that compose the existing engine calls — the same logic the
CLI commands use, minus the Rich presentation.

Writes go straight to the `Store` and then invalidate the snapshot, so the next
read reflects them. Run uvicorn with `--workers 1` (see the Dockerfile) so this
process-local cache is coherent.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .. import config, elo, engine, headshot
from ..elo import Model
from ..models import Game, PlayerStats
from ..sheets import Store

TTL = 20.0  # seconds a snapshot is considered fresh

_store: Store | None = None
_lock = threading.Lock()
_snapshot: "Snapshot | None" = None


@dataclass
class Snapshot:
    """A point-in-time view of the sheet, shared across requests until TTL."""

    records: list[dict]   # raw game dicts (for `last`, undo preview, next id)
    games: list[Game]     # parsed games for the engine
    names: list[str]      # registered player names
    at: float             # monotonic timestamp of the fetch


def get_store() -> Store:
    """The shared `Store` (created lazily so tests can inject a fake first)."""
    global _store
    if _store is None:
        _store = Store()
    return _store


def _fresh() -> Snapshot:
    """Return a fresh snapshot, refetching from the sheet if the TTL expired."""
    global _snapshot
    with _lock:
        now = time.monotonic()
        if _snapshot is None or now - _snapshot.at > TTL:
            store = get_store()
            records = store.read_games()
            names = store.player_names()
            games = [engine.record_to_game(r) for r in records]
            _snapshot = Snapshot(records, games, names, now)
        return _snapshot


def invalidate() -> None:
    """Drop the cached snapshot so the next read refetches (called after writes)."""
    global _snapshot
    with _lock:
        _snapshot = None


# --- model helpers ---------------------------------------------------------


def resolve_model(key: str | None) -> Model:
    """Resolve a model key/number (or the configured default) to a Model.

    Falls back to the registry default for an unknown key rather than erroring —
    the web UI should never 500 over a stale cookie.
    """
    try:
        return elo.get_model(key or config.DEFAULT_MODEL)
    except KeyError:
        return elo.get_model(None)


def model_list() -> list[Model]:
    return elo.all_models()


# --- reads (mirror the CLI commands) ---------------------------------------


def board(model: Model, which: str = "overall", top: int | None = None) -> dict:
    """Leaderboard data: overall (with singles/doubles columns) or one mode."""
    snap = _fresh()
    modes = engine.replay_modes(snap.names, snap.games, model)
    which = (which or "overall").lower()
    if which not in ("overall", "singles", "doubles"):
        which = "overall"

    if which in ("singles", "doubles"):
        ranked = [s for s in engine.leaderboard(modes[which]) if s.games > 0]
        if top:
            ranked = ranked[:top]
        return {"which": which, "ranked": ranked, "model": model}

    overall, singles, doubles = modes["overall"], modes["singles"], modes["doubles"]
    ranked = [s for s in engine.leaderboard(overall) if s.games > 0]
    if top:
        ranked = ranked[:top]
    rows = []
    for s in ranked:
        sg, dg = singles.get(s.name), doubles.get(s.name)
        rows.append({
            "stats": s,
            "singles": sg.rating if sg and sg.games > 0 else None,
            "doubles": dg.rating if dg and dg.games > 0 else None,
        })
    return {"which": "overall", "rows": rows, "model": model}


def players(model: Model) -> list[PlayerStats]:
    """Every registered player, ranked, with current overall rating."""
    snap = _fresh()
    stats = engine.replay(snap.names, snap.games, model)
    return engine.leaderboard(stats)


def player_names() -> list[str]:
    return list(_fresh().names)


def resolve_player(name: str) -> str | None:
    """Map a name to a known player (first fuzzy match) or None."""
    cands = engine.match_candidates(name, _fresh().names)
    return cands[0] if cands else None


def history(player: str, opponent: str | None, model: Model) -> dict:
    """A player's games (optionally head-to-head) with their rating after each.

    Mirrors `cli.history`: replay the whole log incrementally so we capture this
    player's rating before/after each of *their* games, optionally filtered to a
    single opponent.
    """
    snap = _fresh()
    stats: dict[str, PlayerStats] = {
        n: PlayerStats(name=n, rating=model.start_rating) for n in snap.names
    }
    rows = []
    for g in snap.games:
        before = stats[player].rating if player in stats else model.start_rating
        engine.apply_game(stats, g, model)
        after = stats[player].rating if player in stats else before
        if player not in (g.team_a + g.team_b):
            continue
        on_a = player in g.team_a
        their_team = g.team_b if on_a else g.team_a
        if opponent and opponent not in their_team:
            continue
        mine = g.score_a if on_a else g.score_b
        theirs = g.score_b if on_a else g.score_a
        rows.append({
            "id": g.id,
            "res": "W" if mine > theirs else "L",
            "mine": mine,
            "theirs": theirs,
            "opp": " & ".join(their_team),
            "before": before,
            "after": after,
        })

    wins = sum(1 for r in rows if r["res"] == "W")
    trend = ([rows[0]["before"]] + [r["after"] for r in rows]) if rows else []
    return {
        "player": player,
        "rival": opponent,
        "model": model,
        "rows": rows,
        "wins": wins,
        "losses": len(rows) - wins,
        "trend": trend,
        "headshot": None if opponent else headshot.art_text(player),
    }


def odds(p1: str, p2: str, model: Model) -> dict:
    """Win probability + projected score for p1 vs p2, plus both rating trends."""
    snap = _fresh()
    stats = engine.replay(snap.names, snap.games, model)
    r1 = stats[p1].rating if p1 in stats else model.start_rating
    r2 = stats[p2].rating if p2 in stats else model.start_rating
    p1_win = elo.expected(r1, r2)
    fav, fav_p = (p1, p1_win) if p1_win >= 0.5 else (p2, 1 - p1_win)
    fav_pts, dog_pts = elo.projected_score(fav_p)
    return {
        "p1": p1, "p2": p2, "r1": r1, "r2": r2,
        "p1_win": p1_win, "p2_win": 1 - p1_win,
        "fav": fav, "fav_p": fav_p,
        "fav_pts": fav_pts, "dog_pts": dog_pts,
        "odds_ratio": (fav_p / (1 - fav_p)) if fav_p < 1.0 else None,
        "trend1": engine.rating_trend(snap.games, p1, model),
        "trend2": engine.rating_trend(snap.games, p2, model),
        "headshot1": headshot.art_text(p1),
        "headshot2": headshot.art_text(p2),
        "model": model,
    }


def last(n: int = 5) -> list[dict]:
    """The most recent n games as raw records (newest last), like `cli.last`."""
    return _fresh().records[-n:]


def peek_last() -> dict | None:
    """The single most recent game (for the undo confirmation), or None."""
    recs = _fresh().records
    return recs[-1] if recs else None


# --- name resolution + preview (the add-game flow) -------------------------


def resolve_name(token: str) -> tuple[str | None, bool, list[str]]:
    """Resolve a typed name to a canonical player.

    Returns (name, is_new, candidates):
      - (name, False, [])   exact/unique match
      - (token, True, [])   no match → a brand-new player
      - (None, False, [..]) ambiguous → caller must disambiguate
    """
    token = token.strip()
    cands = engine.match_candidates(token, _fresh().names)
    if len(cands) == 1:
        return cands[0], False, []
    if not cands:
        return token, True, []
    return None, False, cands


def preview(
    team_a: list[str], team_b: list[str], score_a: int, score_b: int, model: Model
) -> dict[str, tuple[float, float, float]]:
    """Projected (before, after, delta) per player — the pre-submit projection."""
    snap = _fresh()
    stats = engine.replay(snap.names, snap.games, model)
    return engine.preview_game(stats, team_a, team_b, score_a, score_b, model)


# --- writes (invalidate the cache afterwards) ------------------------------


def log_game(
    mode: str,
    team_a: list[str],
    team_b: list[str],
    score_a: int,
    score_b: int,
    new_players: list[str],
) -> int:
    """Register any new players, append the game, and return its id."""
    store = get_store()
    records = _fresh().records
    for name in new_players:
        store.add_player(name)
    game_id = store.next_game_id(records)
    store.append_game(game_id, mode, team_a, team_b, score_a, score_b)
    invalidate()
    return game_id


def add_player(name: str) -> bool:
    """Register a player. Returns False if a name (case-insensitive) already exists."""
    store = get_store()
    if name.lower() in {n.lower() for n in _fresh().names}:
        return False
    store.add_player(name)
    invalidate()
    return True


def undo_last() -> dict | None:
    """Delete the most recent game; return it (or None if there were none)."""
    deleted = get_store().delete_last_game()
    invalidate()
    return deleted
