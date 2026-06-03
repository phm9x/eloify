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
| `elo history <name> [opponent]` | A player's recent games + trend; add a 2nd name for head-to-head |
| `elo odds <p1> <p2>` | Win odds, projected score, and each player's rating trend |
| `elo headshot <name>` | Show a player's ASCII-art headshot |
| `elo set-headshot <name> <file-or-url>` | Give a player a headshot |
| `elo last [N]` | The last N games |
| `elo undo [-y]` | Remove the most recent game |
| `elo init` | One-time: write header rows to empty tabs |

## Headshots

Players can have a little braille avatar, shown in `elo history` (and via
`elo headshot <name>`). Add one from a local file or a URL:

```bash
elo set-headshot pablo ~/Pictures/pablo.jpg          # from a local file
elo set-headshot pablo https://example.com/pablo.png # or a URL
```

Only the **rendered braille** is committed (`src/eloify/assets/headshots/<username>.txt`)
— the source photo is face-cropped to a thumbnail kept in the git-ignored
`headshots/` folder. Commit the new `.txt` to share the face. Adding headshots
needs the extra (`pip install 'eloify[headshots]'` for Pillow + OpenCV) and
`chafa` (`brew install chafa`) for the rendering; displaying them needs neither.

## Web interface

Same board, same log-a-game flow, in the browser. It's a second presentation
layer over the same core (and the same Google Sheet). Two self-contained ways to
run it (no `pip`/venv needed for the Docker one) — see **[SETUP.md](SETUP.md)** for
the step-by-step:

```bash
# Docker / OrbStack — no Python toolchain required:
docker compose up --build                    # → http://localhost:8000 (and on the LAN)

# or local Python, in a virtualenv (python3 -m venv brings its own pip):
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[web]" && elo-web           # → http://localhost:8000
```

Reads mirror the CLI (board, players, history, odds, last, models); writes are
an HTMX log-a-game form with a live projected-delta preview, plus add-player and
undo. Headshots are *shown* (the committed braille), but **set** only from the
CLI (`elo set-headshot`), which needs Pillow/OpenCV/chafa.

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