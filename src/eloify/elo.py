"""ELO rating math with a margin-of-victory weighting.

Standard logistic ELO, with the K-factor scaled by a margin multiplier
(the FiveThirtyEight / World-Football form):

    expected_a = 1 / (1 + 10 ** ((R_b - R_a) / 400))
    mov        = ln(|margin| + 1) * (2.2 / ((R_winner - R_loser) * 0.001 + 2.2))
    delta_a    = K * mov * (actual_a - expected_a)

The (R_winner - R_loser) term damps autocorrelation: a heavy favorite winning
big gains less, while an upset (lower-rated winner) is amplified.

For 2v2 the team rating is the average of its two players; the resulting delta
is applied to each teammate.
"""

from __future__ import annotations

import math

START_RATING = 1000.0
K = 24.0


def expected(rating_a: float, rating_b: float) -> float:
    """Expected score for A against B (0..1)."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def mov_multiplier(margin: int, winner_rating: float, loser_rating: float) -> float:
    """Margin-of-victory multiplier on the K-factor."""
    return math.log(abs(margin) + 1) * (
        2.2 / ((winner_rating - loser_rating) * 0.001 + 2.2)
    )


def compute_deltas(
    team_a_rating: float,
    team_b_rating: float,
    score_a: int,
    score_b: int,
    k: float = K,
) -> tuple[float, float]:
    """Return (delta_a, delta_b) to apply to each player on team A / team B."""
    exp_a = expected(team_a_rating, team_b_rating)
    a_won = score_a > score_b
    actual_a = 1.0 if a_won else 0.0
    winner_rating, loser_rating = (
        (team_a_rating, team_b_rating) if a_won else (team_b_rating, team_a_rating)
    )
    mov = mov_multiplier(abs(score_a - score_b), winner_rating, loser_rating)
    delta_a = k * mov * (actual_a - exp_a)
    return delta_a, -delta_a
