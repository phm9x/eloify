"""Rating engine: replay the game log to derive current ELOs and stats.

Ratings are always recomputed from the full chronological game log rather than
stored mutably, so the formula (K, MoV) can change freely and a corrected or
deleted game just changes the replay.
"""

from __future__ import annotations

from statistics import mean

from .elo import START_RATING, compute_deltas
from .models import Game, PlayerStats


def split_team(cell: str) -> list[str]:
    """Parse a 'Duncan, Peter' team cell into names."""
    return [p.strip() for p in str(cell).split(",") if p.strip()]


def record_to_game(rec: dict) -> Game:
    return Game(
        id=int(rec["id"]),
        played_at=str(rec["played_at"]),
        mode=str(rec["mode"]),
        team_a=split_team(rec["team_a"]),
        team_b=split_team(rec["team_b"]),
        score_a=int(rec["score_a"]),
        score_b=int(rec["score_b"]),
    )


def _team_rating(stats: dict[str, PlayerStats], names: list[str]) -> float:
    return mean(
        stats[n].rating if n in stats else START_RATING for n in names
    )


def _ensure(stats: dict[str, PlayerStats], name: str) -> PlayerStats:
    if name not in stats:
        stats[name] = PlayerStats(name=name)
    return stats[name]


def replay(player_names: list[str], games: list[Game]) -> dict[str, PlayerStats]:
    """Replay games in order; return name -> PlayerStats with final ratings."""
    stats: dict[str, PlayerStats] = {n: PlayerStats(name=n) for n in player_names}

    for game in games:
        ra = _team_rating(stats, game.team_a)
        rb = _team_rating(stats, game.team_b)
        delta_a, delta_b = compute_deltas(ra, rb, game.score_a, game.score_b)
        a_won = game.score_a > game.score_b
        for n in game.team_a:
            s = _ensure(stats, n)
            s.rating += delta_a
            s.games += 1
            s.wins += 1 if a_won else 0
            s.losses += 0 if a_won else 1
        for n in game.team_b:
            s = _ensure(stats, n)
            s.rating += delta_b
            s.games += 1
            s.wins += 0 if a_won else 1
            s.losses += 1 if a_won else 0

    return stats


def leaderboard(stats: dict[str, PlayerStats]) -> list[PlayerStats]:
    return sorted(
        stats.values(),
        key=lambda s: (-s.rating, -s.games, s.name.lower()),
    )


def preview_game(
    stats: dict[str, PlayerStats],
    team_a: list[str],
    team_b: list[str],
    score_a: int,
    score_b: int,
) -> dict[str, tuple[float, float, float]]:
    """Return name -> (before, after, delta) for a prospective game."""
    ra = _team_rating(stats, team_a)
    rb = _team_rating(stats, team_b)
    delta_a, delta_b = compute_deltas(ra, rb, score_a, score_b)
    out: dict[str, tuple[float, float, float]] = {}
    for n in team_a:
        before = stats[n].rating if n in stats else START_RATING
        out[n] = (before, before + delta_a, delta_a)
    for n in team_b:
        before = stats[n].rating if n in stats else START_RATING
        out[n] = (before, before + delta_b, delta_b)
    return out


def match_candidates(token: str, known: list[str]) -> list[str]:
    """Fuzzy-match a typed token to known player names (exact > prefix > substr)."""
    tl = token.lower()
    for predicate in (
        lambda n: n.lower() == tl,
        lambda n: n.lower().startswith(tl),
        lambda n: tl in n.lower(),
    ):
        hits = [n for n in known if predicate(n)]
        if hits:
            return hits
    return []
