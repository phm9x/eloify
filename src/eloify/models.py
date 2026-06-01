"""Shared data structures."""

from __future__ import annotations

from dataclasses import dataclass, field

from .elo import START_RATING


@dataclass
class Game:
    id: int
    played_at: str
    mode: str
    team_a: list[str]
    team_b: list[str]
    score_a: int
    score_b: int

    @property
    def winner(self) -> list[str]:
        return self.team_a if self.score_a > self.score_b else self.team_b


@dataclass
class PlayerStats:
    name: str
    rating: float = START_RATING
    wins: int = 0
    losses: int = 0
    games: int = 0

    @property
    def win_pct(self) -> float:
        return (self.wins / self.games * 100) if self.games else 0.0
