# 🏓 Eloify

Office ping pong ELO tracker — a CLI (`elo` / `eloify`) backed by a Google Sheet.

```bash
elo add duncan peter 21 18          # 1v1 — higher score wins, order-independent
elo add duncan peter sam alex 21 15 # 2v2 — your side, their side, the scores
elo board                           # leaderboard (overall + singles/doubles)
```

**New here?** See **[SETUP.md](SETUP.md)** (~2 min).

## Entry grammar

Positional, nothing to memorize: **2 names → 1v1, 4 names → 2v2**, trailing
integers are the scores, **higher score wins**. Every `add` previews the parsed
game (flagging unknown names as new players) and confirms before writing.

## Commands

| Command | What it does |
|---|---|
| `elo add <players...> <a> <b>` | Log a game (`-y` skips confirm) |
| `elo board [singles\|doubles] [--top N]` | Leaderboard |
| `elo players` | Roster with current ELO |
| `elo add-player "Name"` | Register a player (optional) |
| `elo history <name>` | A player's recent games + trend |
| `elo last [N]` | The last N games |
| `elo undo [-y]` | Remove the most recent game |
| `elo init` | One-time: write header rows to empty tabs |

## Scoring & rating

- Games go to **5, 11, or 21**, win by **2**; illegal scores are rejected.
- Logistic ELO with **margin-of-victory** weighting (blowouts move more, upsets
  amplified). Everyone starts at 1000; 2v2 uses team-average ratings.
- Ratings are recomputed from the full game log, so the formula can change and
  bad games can be fixed without migrations.

## Development

```bash
pip install -e ".[dev]" && pytest
```

Parser, validation, and ELO are pure and unit-tested; `sheets.py` is the only
part that touches the network.
