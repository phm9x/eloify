# 🏓 Eloify

Insurify ping pong ELO tracker.

```bash
elo add                             # guided flow — pick mode, players, scores
elo add duncan peter 21 18          # 1v1 — higher score wins, order-independent
elo add duncan peter sam alex 21 15 # 2v2 — your side, their side, the scores
elo board                           # leaderboard (overall + singles/doubles)
```

See **[SETUP.md](SETUP.md)** for install (~3 min).

## Entry grammar

Positional, nothing to memorize: **2 names → 1v1, 4 names → 2v2**, trailing
integers are the scores, **higher score wins**. Every `add` previews the parsed
game (flagging unknown names as new players) and confirms before writing.

Prefer not to type it all out? Run **`elo add`** with no arguments for a guided
flow (à la `gh pr create`): pick the game type, select players from the roster
(or add new ones), and enter the score — with the same preview and confirmation.

## Commands

| Command | What it does |
|---|---|
| `elo add <players...> <a> <b>` | Log a game (`-y` skips confirm) |
| `elo add` | Log a game via the guided interactive flow |
| `elo board [singles\|doubles] [--top N]` | Leaderboard |
| `elo players` | Roster with current ELO |
| `elo add-player "Name"` | Register a player (optional) |
| `elo history <name>` | A player's recent games + trend |
| `elo last [N]` | The last N games |
| `elo undo [-y]` | Remove the most recent game |
| `elo init` | One-time: write header rows to empty tabs |

## Scoring & rating

- Games go to **11 or 21**, win by **2** (deuce caps at 17-15 / 27-25); other
  scores are rejected as typos.
- Logistic ELO with **margin-of-victory** weighting (blowouts move more, upsets
  amplified). Everyone starts at 1000; 2v2 uses team-average ratings.
- Ratings are recomputed from the full game log, so the formula can change and
  bad games can be fixed without migrations.

## Development

```bash
pip install -e ".[dev]" && pytest
```