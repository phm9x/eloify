# Eloify setup (~2 min)

## 1. Install the `elo` command

```bash
brew install pipx && pipx ensurepath   # then open a NEW terminal
pipx install -e .                       # from inside the cloned repo
```

This puts `elo` (and `eloify`) on your PATH — runnable from any directory.

## 2. Add your credentials

Eloify reads a Google service-account key. **Message Peter for the JSON file.**
Save it and a one-line `.env` under `~/.config/eloify/`:

```bash
mkdir -p ~/.config/eloify
mv ~/Downloads/eloify-secret.json ~/.config/eloify/        # the file from Peter
chmod 600 ~/.config/eloify/eloify-secret.json
```

Create `~/.config/eloify/.env`:

```
GOOGLE_SERVICE_ACCOUNT_FILE=/Users/<you>/.config/eloify/eloify-secret.json
```

(Use your absolute home path — `/Users/<you>/...`.)

## 3. Go

```bash
elo board
elo add duncan peter 21 18
```

That's it — the sheet is already set up and shared.

## 4. (Optional) Run the web interface

A browser UI with the same board and log-a-game flow, talking to the same sheet.
You still need credentials (step 2). Pick **one** of the two ways below — they're
each self-contained, so you don't need `pip`, a virtualenv, or the `elo` CLI from
step 1 already set up.

### Option A — Docker / OrbStack (no Python needed)

The simplest path if you don't already have a Python toolchain. Install
[OrbStack](https://orbstack.dev) (or Docker Desktop), then from the repo:

```bash
# Pass the service-account key in as inline JSON (see note below on why):
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat ~/.config/eloify/eloify-secret.json)"
docker compose up --build
```

Open <http://localhost:8000> — it's also reachable on the LAN and at the
`*.orb.local` domain OrbStack assigns. `ELOIFY_SPREADSHEET_ID` / `ELOIFY_MODEL`
are passed through too if you set them.

> **Why inline JSON?** Compose mounts `~/.config/eloify` read-only into the
> container, but a `GOOGLE_SERVICE_ACCOUNT_FILE` path in your `.env` points at a
> host path that doesn't exist inside the container. Passing the key as
> `GOOGLE_SERVICE_ACCOUNT_JSON` sidesteps that.

### Option B — Local Python (in a virtualenv)

No system `pip` required: `python3 -m venv` creates an isolated environment with
its own `pip` inside. You just need Python 3.10+ (`python3 --version`; on macOS,
`brew install python` if you don't have it).

```bash
# From inside the repo:
python3 -m venv .venv          # one-time: creates ./.venv with its own pip
source .venv/bin/activate       # activate it (re-run this in each new shell)
pip install -e ".[web]"         # install the web deps into the venv
python -m eloify.web            # → http://localhost:8000
```

`python -m eloify.web` reads the same `~/.config/eloify/.env` as the CLI and runs
uvicorn with `--workers 1` so its short data cache stays coherent. For autoreload
while developing: `uvicorn eloify.web.app:app --reload`.

To run it again later: `cd` into the repo, `source .venv/bin/activate`,
`python -m eloify.web`. (`deactivate` leaves the venv.)

> **Use `python -m eloify.web`, not the bare `elo-web` command.** There's also an
> `elo-web` script, but if you ever installed `elo` globally (step 1) an old copy
> can sit on your `PATH` and shadow the venv's — running it against a Python that
> has no `fastapi`. `python -m eloify.web` always uses the interpreter from the
> activated venv, so it sidesteps that. See Troubleshooting below.

> We use a venv here rather than `pipx` (step 1): `pipx` is for installing the
> standalone `elo` command globally, whereas the web server runs from the repo
> with its own dependencies, which a venv keeps neatly isolated.

### Troubleshooting

**`ModuleNotFoundError: No module named 'fastapi'` when starting the server** —
the deps installed fine, but the wrong `elo-web` ran. The traceback names the
culprit, e.g. `/Users/you/.local/bin/elo-web` (a stale global install) instead of
`…/eloify/.venv/bin/elo-web`. Confirm and fix:

```bash
which -a elo-web                # likely shows ~/.local/bin/elo-web first
python -m eloify.web            # ← just use this; it ignores PATH entirely
```

If you'd rather remove the stale copy: `pipx uninstall eloify` (or delete
`~/.local/bin/elo-web` / `~/.local/bin/elo` if a plain `pip --user` put them there).

## 5. (Optional) Adding headshots

Viewing headshots needs nothing extra. *Adding* one (`elo set-headshot`) renders
a photo to braille, which needs a couple of extra tools:

```bash
pipx inject eloify pillow opencv-python-headless   # image + face-crop libs
brew install chafa                                  # braille renderer
```

> **NB:** `pipx install -e .` links the command to the repo, so a `git pull` is
> usually all you need. If a pull adds a new dependency (or the `elo` command
> starts misbehaving), refresh the install with `pipx reinstall eloify`.
