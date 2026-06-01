# Eloify setup

One-time setup, ~5 minutes.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs two equivalent commands: **`elo`** and **`eloify`**.

## 2. Credentials

You need a Google **service-account key** (a JSON file with
`"type": "service_account"`). You already have one from a previous project.

1. Save the JSON somewhere private (it stays out of git — `.gitignore`
   excludes `*.json` and `.env`).
2. In `.env`, point to it:
   ```
   GOOGLE_SERVICE_ACCOUNT_FILE=/absolute/path/to/service-account.json
   ```
   (Or paste the JSON inline as `GOOGLE_SERVICE_ACCOUNT_JSON=...` — see `.env`.)

## 3. Share the spreadsheet ← the step everyone forgets

Open the JSON and copy the **`client_email`** (looks like
`something@your-project.iam.gserviceaccount.com`). In the Google Sheet, click
**Share** and add that address as an **Editor**. Without this, every call
returns a 403.

## 4. Initialise the tabs

```bash
elo init
```

This writes header rows to the Games and Players tabs **only if they're empty**,
so it won't clobber existing data.

## 5. Go

```bash
elo add duncan peter 21 18
elo board
```

## Sheet layout

- **Games** (gid 0): `id · played_at · mode · team_a · team_b · score_a · score_b`
- **Players** (gid 604449976): `name · created_at`

Ratings are **not** stored — they're recomputed from the full game log every
time, so you can tweak the formula or delete a bad game and everything stays
consistent.
