"""Parse the positional `add` grammar into a ParsedGame.

Grammar (nothing to memorize — your side, their side, the scores):
    1v1:  elo add duncan peter 21 18
    2v2:  elo add duncan peter sam alex 21 15

Rules:
    - Trailing integer tokens are scores (exactly 2, one per team).
    - Everything before the scores is names.
    - 2 names -> 1v1, 4 names -> 2v2; names group 2-and-2 for doubles.
    - An optional "vs" / "/" separator may be used for clarity; if present it
      splits the teams, otherwise teams split by count. It is never required.
    - First score maps to the team listed first; higher score wins.
"""

from __future__ import annotations

from dataclasses import dataclass

SEPARATORS = {"vs", "v", "/", "|"}


class ParseError(ValueError):
    """Raised when the `add` arguments can't be interpreted."""


@dataclass
class ParsedGame:
    mode: str  # "1v1" | "2v2"
    team_a: list[str]
    team_b: list[str]
    score_a: int
    score_b: int


def _is_int(token: str) -> bool:
    try:
        int(token)
        return True
    except ValueError:
        return False


def parse_add(tokens: list[str]) -> ParsedGame:
    if not tokens:
        raise ParseError("No players or scores given. e.g. elo add duncan peter 21 18")

    # Peel trailing integer tokens off the end as scores.
    split = len(tokens)
    scores: list[int] = []
    while split > 0 and _is_int(tokens[split - 1]):
        scores.insert(0, int(tokens[split - 1]))
        split -= 1
    names = tokens[:split]

    if len(scores) != 2:
        raise ParseError(
            f"Expected exactly 2 trailing scores, found {len(scores)}. "
            "e.g. elo add duncan peter 21 18"
        )
    score_a, score_b = scores

    # Split teams: use an explicit separator if present, else by count.
    sep_idx = next(
        (i for i, t in enumerate(names) if t.lower() in SEPARATORS), None
    )
    if sep_idx is not None:
        team_a = [n for n in names[:sep_idx] if n.lower() not in SEPARATORS]
        team_b = [n for n in names[sep_idx + 1 :] if n.lower() not in SEPARATORS]
    else:
        clean = [n for n in names if n.lower() not in SEPARATORS]
        if len(clean) == 2:
            team_a, team_b = [clean[0]], [clean[1]]
        elif len(clean) == 4:
            team_a, team_b = clean[:2], clean[2:]
        else:
            raise ParseError(
                f"Expected 2 names (1v1) or 4 names (2v2), found {len(clean)}: "
                f"{' '.join(clean) or '(none)'}"
            )

    if len(team_a) != len(team_b) or len(team_a) not in (1, 2):
        raise ParseError(
            f"Teams must be equal size — 1v1 or 2v2. "
            f"Got {len(team_a)} vs {len(team_b)}."
        )

    mode = "1v1" if len(team_a) == 1 else "2v2"
    return ParsedGame(mode=mode, team_a=team_a, team_b=team_b,
                      score_a=score_a, score_b=score_b)
