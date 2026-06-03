"""ELO rating models — a small pluggable registry so new formulas are cheap to try.

Ratings are always recomputed by replaying the whole game log (see engine.py),
so switching the active model, or adding a brand-new one, never requires a data
migration — it just changes the replay. To add a model, write a `RateFn` and
wrap it with `register(Model(...))` at the bottom of this file; it immediately
becomes available to `--model`.

The default model is the FiveThirtyEight / World-Football margin-of-victory
form: standard logistic ELO with the K-factor scaled by a margin multiplier:

    expected_a = 1 / (1 + 10 ** ((R_b - R_a) / 400))
    mov        = ln(|margin| + 1) * (2.2 / ((R_winner - R_loser) * 0.001 + 2.2))
    delta_a    = K * mov * (actual_a - expected_a)

The (R_winner - R_loser) term damps autocorrelation: a heavy favorite winning
big gains less, while an upset (lower-rated winner) is amplified. For team games
the team rating is the average of its players and the delta is shared.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from statistics import mean

START_RATING = 1000.0
K = 24.0


# --- rating primitives (shared building blocks for the models below) ---


def expected(rating_a: float, rating_b: float) -> float:
    """Expected score for A against B (0..1)."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def mov_multiplier(margin: int, winner_rating: float, loser_rating: float) -> float:
    """Margin-of-victory multiplier on the K-factor."""
    return math.log(abs(margin) + 1) * (
        2.2 / ((winner_rating - loser_rating) * 0.001 + 2.2)
    )


def projected_score(win_prob: float, target: int = 21) -> tuple[int, int]:
    """A plausible final game score to `target` for a given win probability.

    The favorite reaches `target`; the underdog's points scale with how close
    the matchup is (their share of the expected odds), capped at `target - 2`
    so the result still reads as a win. Returns (favorite_points, underdog).
    """
    fav = max(win_prob, 1.0 - win_prob)
    dog_points = round(target * (1.0 - fav) / fav) if fav > 0 else target
    return target, min(dog_points, target - 2)


def compute_deltas(
    team_a_rating: float,
    team_b_rating: float,
    score_a: int,
    score_b: int,
    k: float = K,
) -> tuple[float, float]:
    """Return (delta_a, delta_b) for the margin-of-victory model (the default).

    Kept as a standalone function because it's the model's core and is exercised
    directly by the tests.
    """
    exp_a = expected(team_a_rating, team_b_rating)
    a_won = score_a > score_b
    actual_a = 1.0 if a_won else 0.0
    winner_rating, loser_rating = (
        (team_a_rating, team_b_rating) if a_won else (team_b_rating, team_a_rating)
    )
    mov = mov_multiplier(abs(score_a - score_b), winner_rating, loser_rating)
    delta_a = k * mov * (actual_a - exp_a)
    return delta_a, -delta_a


# --- the pluggable model abstraction ---


@dataclass(frozen=True)
class Matchup:
    """One game's inputs from the perspective of the rating math.

    Ratings and game-counts are per player (parallel to team_a / team_b), so a
    model is free to weight teammates differently (e.g. a provisional K-factor
    that depends on how many games each player has under their belt).
    """

    team_a: list[float]        # current ratings of team A's players
    team_b: list[float]        # current ratings of team B's players
    team_a_games: list[int]    # games each team A player has played so far
    team_b_games: list[int]
    score_a: int
    score_b: int

    @property
    def a_won(self) -> bool:
        return self.score_a > self.score_b


# A model computes, for one game, the rating delta for each player on each team.
RateFn = Callable[[Matchup], tuple[list[float], list[float]]]


@dataclass(frozen=True)
class Model:
    key: str            # the value passed to --model
    label: str          # human-readable name
    description: str     # one-line summary shown by `elo models`
    rate: RateFn
    start_rating: float = START_RATING


_REGISTRY: dict[str, Model] = {}
DEFAULT_MODEL = "provisional"


def register(model: Model) -> Model:
    """Register a model so it's selectable via --model. Returns it for chaining."""
    if model.key in _REGISTRY:
        raise ValueError(f"Duplicate model key: {model.key!r}")
    _REGISTRY[model.key] = model
    return model


def get_model(key: str | None) -> Model:
    """Look up a model by key or 1-based number; None yields the default.

    `--model 2` is as valid as `--model elo` — numbers index `all_models()`
    (the same order `elo models` prints), so `1` is always the default. Raises
    KeyError if the key/number doesn't match a model.
    """
    if key is None:
        return _REGISTRY[DEFAULT_MODEL]
    key = key.strip()
    if key.isdigit():
        models = all_models()
        idx = int(key)
        if 1 <= idx <= len(models):
            return models[idx - 1]
        raise KeyError(key)
    try:
        return _REGISTRY[key]
    except KeyError:
        raise KeyError(key) from None


def default_model() -> Model:
    return _REGISTRY[DEFAULT_MODEL]


def all_models() -> list[Model]:
    """Every registered model, default first then in registration order.

    The position here is the model's stable `--model N` number, so new models
    append (keeping existing numbers) — register them at the end of this file.
    """
    default = _REGISTRY[DEFAULT_MODEL]
    rest = [m for k, m in _REGISTRY.items() if k != DEFAULT_MODEL]
    return [default, *rest]


def model_keys() -> list[str]:
    return [m.key for m in all_models()]


# --- concrete models -------------------------------------------------------
# Each is a RateFn over team averages. Adding another is a function + register().


def _mov_rate(m: Matchup) -> tuple[list[float], list[float]]:
    """Margin-of-victory weighted logistic ELO (see module docstring)."""
    delta_a, delta_b = compute_deltas(
        mean(m.team_a), mean(m.team_b), m.score_a, m.score_b
    )
    return [delta_a] * len(m.team_a), [delta_b] * len(m.team_b)


def _plain_rate(m: Matchup) -> tuple[list[float], list[float]]:
    """Classic logistic ELO, K=24, margin ignored — a win is a win."""
    exp_a = expected(mean(m.team_a), mean(m.team_b))
    actual_a = 1.0 if m.a_won else 0.0
    delta = K * (actual_a - exp_a)
    return [delta] * len(m.team_a), [-delta] * len(m.team_b)


def _provisional_rate(m: Matchup) -> tuple[list[float], list[float]]:
    """MoV ELO with a higher K for a player's first 10 games, then settling.

    New players converge to their true level quickly while veterans stay stable.
    Because K is per player, teammates can move by different amounts.
    """
    ra, rb = mean(m.team_a), mean(m.team_b)
    exp_a = expected(ra, rb)
    actual_a = 1.0 if m.a_won else 0.0
    winner, loser = (ra, rb) if m.a_won else (rb, ra)
    mov = mov_multiplier(abs(m.score_a - m.score_b), winner, loser)
    base = mov * (actual_a - exp_a)  # team A's per-K swing; team B is its negative

    def k_for(games: int) -> float:
        return 40.0 if games < 10 else 24.0

    deltas_a = [k_for(g) * base for g in m.team_a_games]
    deltas_b = [-k_for(g) * base for g in m.team_b_games]
    return deltas_a, deltas_b


def _share_rate(m: Matchup) -> tuple[list[float], list[float]]:
    """Score-share ELO: the outcome is the share of points won, not 1/0.

    In the spirit of point-differential rating systems (Massey / Colley), a
    respectable loss is rewarded: with actual = score / total, a player who was
    expected to win only 25% of the time but loses 19-21 (actual 0.475) still
    *gains*, because they over-performed the spread. A blowout loss costs more
    than a narrow one, and a narrow win against a strong favorite earns little.
    """
    exp_a = expected(mean(m.team_a), mean(m.team_b))
    total = m.score_a + m.score_b
    actual_a = m.score_a / total if total else 0.5
    delta = K * (actual_a - exp_a)
    return [delta] * len(m.team_a), [-delta] * len(m.team_b)


register(Model(
    key="mov",
    label="Margin-of-victory ELO",
    description="Logistic ELO with the K-factor scaled by score margin (default).",
    rate=_mov_rate,
))
register(Model(
    key="elo",
    label="Plain ELO",
    description="Classic logistic ELO, K=24 — margin of victory ignored.",
    rate=_plain_rate,
))
register(Model(
    key="provisional",
    label="Provisional-K ELO",
    description="MoV ELO with K=40 for a player's first 10 games, then K=24.",
    rate=_provisional_rate,
))
register(Model(
    key="share",
    label="Score-share ELO",
    description="Outcome = share of points won; a close loss can still gain rating.",
    rate=_share_rate,
))
