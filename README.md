# 🏓 Eloify

Office ping pong ELO tracker. A small CLI (`elo` / `eloify`) backed by a Google
Sheet — no server, no app to install. Log a game in one line; ratings recompute
from the full game log.

```bash
elo add duncan peter 21 18          # 1v1 — higher score wins, order-independent
elo add duncan peter sam alex 21 15 # 2v2 — your side, their side, the scores
elo board                           # leaderboard
```

See **[SETUP.md](SETUP.md)** to get going (≈5 min).

## How entry works

The grammar is positional — nothing to memorize:

- **2 names → 1v1, 4 names → 2v2.** Trailing integers are the scores.
- First score maps to the team listed first; **higher score wins**, so you
  don't have to list the winner first.
- An optional `vs` / `/` divider is accepted but never required.

Every `add` shows a confirmation with the parsed teams, **flags unknown names as
new players**, and previews the rating changes before writing:

```
  2v2
  Team A:  Duncan & Peter  21  ← winner
  Team B:  Sam & Alex  15
  projected: Duncan +8   Peter +8   Sam -8   Alex -8
  Confirm? [Y/n]
```

## Commands

| Command | What it does |
|---|---|
| `elo add <players...> <scoreA> <scoreB>` | Log a game (`-y` to skip confirm) |
| `elo board [--top N]` | Leaderboard — overall ELO with singles & doubles columns |
| `elo board singles` / `elo board doubles` | Leaderboard ranked by that game type only |
| `elo players` | Roster with current ELO |
| `elo add-player "Name"` | Register a player (optional) |
| `elo history <name>` | A player's recent games + rating trend |
| `elo last [N]` | The last N games |
| `elo undo [-y]` | Remove the most recent game |
| `elo init` | One-time: write header rows to empty tabs |

## Scoring rules

- Games go to **5, 11, or 21**, win by **2** (deuce extends play). Illegal
  results (e.g. `11-10`, `3-1`) are rejected.
- ELO is standard logistic with a **margin-of-victory** weight: blowouts move
  ratings more, and upsets are amplified. Everyone starts at 1000.
- 2v2 uses each team's average rating; the delta applies to both teammates.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The rating math, parser, and score validation are pure and unit-tested
(`tests/`); the Sheets layer (`sheets.py`) is the only part that touches the
network.
