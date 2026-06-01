"""Hard validation of ping pong scores.

A game is played to a target of 11 or 21 and must be won by 2 (deuce extends
play past the target). Deuce is capped at MAX_DEUCES points past the target —
beyond that a result is almost certainly a typo. A result (w, l) with w > l is
legal if SOME target T in {11, 21} satisfies either:

    clean win:  w == T  and  l <= T - 2
    deuce:      w == l + 2  and  l >= T - 1  and  w <= T + MAX_DEUCES

So the largest legal results are 17-15 (to 11) and 27-25 (to 21).
"""

from __future__ import annotations

TARGETS = (11, 21)
MAX_DEUCES = 6


class ScoreError(ValueError):
    """Raised when a score pair isn't a legal ping pong result."""


def _valid_for_target(winner: int, loser: int, target: int) -> bool:
    if winner == target and loser <= target - 2:
        return True
    if winner == loser + 2 and loser >= target - 1 and winner <= target + MAX_DEUCES:
        return True
    return False


def is_legal_score(score_a: int, score_b: int) -> bool:
    if score_a < 0 or score_b < 0 or score_a == score_b:
        return False
    winner, loser = max(score_a, score_b), min(score_a, score_b)
    return any(_valid_for_target(winner, loser, t) for t in TARGETS)


def validate_score(score_a: int, score_b: int) -> None:
    """Raise ScoreError if (score_a, score_b) isn't a legal result."""
    if score_a < 0 or score_b < 0:
        raise ScoreError("Scores can't be negative.")
    if score_a == score_b:
        raise ScoreError("Ping pong has no ties — the scores must differ.")
    if not is_legal_score(score_a, score_b):
        winner, loser = max(score_a, score_b), min(score_a, score_b)
        raise ScoreError(
            f"{winner}-{loser} isn't a legal result. Games go to 11 or 21, "
            "won by 2 (deuce caps at 17-15 / 27-25)."
        )
