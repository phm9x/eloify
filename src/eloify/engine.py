"""Rating engine: replay the game log to derive current ELOs and stats.

Ratings are always recomputed from the full chronological game log rather than
stored mutably, so the model (see elo.py) can change freely and a corrected or
deleted game just changes the replay. Every entry point takes an optional
`model`; omitting it uses the registered default.
"""

from __future__ import annotations

from .elo import Matchup, Model, default_model
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


def _ensure(stats: dict[str, PlayerStats], name: str, model: Model) -> PlayerStats:
    if name not in stats:
        stats[name] = PlayerStats(name=name, rating=model.start_rating)
    return stats[name]


def _matchup(stats: dict[str, PlayerStats], game: Game, model: Model) -> Matchup:
    def rating(n: str) -> float:
        return stats[n].rating if n in stats else model.start_rating

    def games(n: str) -> int:
        return stats[n].games if n in stats else 0

    return Matchup(
        team_a=[rating(n) for n in game.team_a],
        team_b=[rating(n) for n in game.team_b],
        team_a_games=[games(n) for n in game.team_a],
        team_b_games=[games(n) for n in game.team_b],
        score_a=game.score_a,
        score_b=game.score_b,
    )


def apply_game(
    stats: dict[str, PlayerStats], game: Game, model: Model
) -> dict[str, float]:
    """Apply one game's rating + W/L updates to `stats` in place.

    Returns name -> delta for the players involved.
    """
    deltas_a, deltas_b = model.rate(_matchup(stats, game, model))
    a_won = game.score_a > game.score_b
    out: dict[str, float] = {}
    for n, d in zip(game.team_a, deltas_a):
        s = _ensure(stats, n, model)
        s.rating += d
        s.games += 1
        s.wins += 1 if a_won else 0
        s.losses += 0 if a_won else 1
        out[n] = d
    for n, d in zip(game.team_b, deltas_b):
        s = _ensure(stats, n, model)
        s.rating += d
        s.games += 1
        s.wins += 0 if a_won else 1
        s.losses += 1 if a_won else 0
        out[n] = d
    return out


def replay(
    player_names: list[str], games: list[Game], model: Model | None = None
) -> dict[str, PlayerStats]:
    """Replay games in order; return name -> PlayerStats with final ratings."""
    model = model or default_model()
    stats: dict[str, PlayerStats] = {
        n: PlayerStats(name=n, rating=model.start_rating) for n in player_names
    }
    for game in games:
        apply_game(stats, game, model)
    return stats


def replay_modes(
    player_names: list[str], games: list[Game], model: Model | None = None
) -> dict[str, dict[str, PlayerStats]]:
    """Derive overall / singles / doubles ratings from one game log.

    Same rows, three filters — each is an independent replay, so a player's
    singles rating is unaffected by their doubles games and vice versa.
    """
    model = model or default_model()
    return {
        "overall": replay(player_names, games, model),
        "singles": replay(player_names, [g for g in games if g.mode == "1v1"], model),
        "doubles": replay(player_names, [g for g in games if g.mode == "2v2"], model),
    }


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
    model: Model | None = None,
) -> dict[str, tuple[float, float, float]]:
    """Return name -> (before, after, delta) for a prospective game."""
    model = model or default_model()
    game = Game(
        id=0, played_at="", mode="", team_a=team_a, team_b=team_b,
        score_a=score_a, score_b=score_b,
    )
    deltas_a, deltas_b = model.rate(_matchup(stats, game, model))
    out: dict[str, tuple[float, float, float]] = {}
    for n, d in zip(team_a, deltas_a):
        before = stats[n].rating if n in stats else model.start_rating
        out[n] = (before, before + d, d)
    for n, d in zip(team_b, deltas_b):
        before = stats[n].rating if n in stats else model.start_rating
        out[n] = (before, before + d, d)
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
