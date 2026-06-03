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

**Locally:**

```bash
pip install -e ".[web]"
elo-web                       # reads the same ~/.config/eloify/.env → http://localhost:8000
```

(`elo-web` runs uvicorn with `--workers 1` so its short data cache stays
coherent. For autoreload while developing: `uvicorn eloify.web.app:app --reload`.)

**Docker / OrbStack:**

```bash
docker compose up --build     # http://localhost:8000, also on the LAN + a *.orb.local domain
```

Compose mounts `~/.config/eloify` read-only for credentials. Because that path
is mounted at `/root/.config/eloify` inside the container, the simplest setup is
to pass the key as **inline JSON** rather than a host file path:

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat ~/.config/eloify/eloify-secret.json)"
docker compose up --build
```

(`ELOIFY_SPREADSHEET_ID` / `ELOIFY_MODEL` are passed through too if set.)

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
