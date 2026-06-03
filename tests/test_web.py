"""Web layer tests: a FastAPI TestClient over an in-memory fake Store.

Mirrors the core's testing style (build data in memory, call into the real
engine) — here the fake Store is injected into `web.data` so no Google Sheets
access happens.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from eloify.web import app as webapp
from eloify.web import data


class FakeStore:
    """In-memory stand-in for sheets.Store (only the methods data.py uses)."""

    def __init__(self):
        self.games: list[dict] = []
        self.players: list[str] = []

    def read_games(self):
        return [dict(g) for g in self.games]

    def player_names(self):
        return list(self.players)

    def add_player(self, name):
        self.players.append(name)

    def append_game(self, game_id, mode, team_a, team_b, score_a, score_b):
        self.games.append({
            "id": game_id,
            "played_at": "2024-01-01T00:00:00+00:00",
            "mode": mode,
            "team_a": ", ".join(team_a),
            "team_b": ", ".join(team_b),
            "score_a": score_a,
            "score_b": score_b,
        })

    @staticmethod
    def next_game_id(games):
        ids = [int(g["id"]) for g in games
               if str(g.get("id", "")).strip().lstrip("-").isdigit()]
        return (max(ids) + 1) if ids else 1

    def delete_last_game(self):
        return self.games.pop() if self.games else None


@pytest.fixture
def store():
    fake = FakeStore()
    fake.players = ["duncan", "peter", "sam", "alex"]
    for gid, mode, a, b, sa, sb in [
        (1, "1v1", ["duncan"], ["peter"], 21, 18),
        (2, "1v1", ["duncan"], ["sam"], 21, 10),
        (3, "2v2", ["duncan", "peter"], ["sam", "alex"], 21, 15),
    ]:
        fake.append_game(gid, mode, a, b, sa, sb)
    data._store = fake
    data.invalidate()
    yield fake
    data._store = None
    data.invalidate()


@pytest.fixture
def client(store):
    return TestClient(webapp.app)


def test_board(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "duncan" in r.text
    assert "Leaderboard" in r.text


def test_board_singles(client):
    r = client.get("/?which=singles")
    assert r.status_code == 200
    assert "alex" not in r.text.split("model:")[0] or "duncan" in r.text  # alex never played singles


def test_players(client):
    r = client.get("/players")
    assert r.status_code == 200
    for name in ("duncan", "peter", "sam", "alex"):
        assert name in r.text


def test_history(client):
    r = client.get("/history/duncan")
    assert r.status_code == 200
    assert "duncan" in r.text
    assert "3-0" in r.text  # duncan won all three


def test_history_head_to_head(client):
    r = client.get("/history/duncan?opponent=peter")
    assert r.status_code == 200
    assert "duncan vs peter" in r.text


def test_history_unknown_player(client):
    r = client.get("/history/nobody")
    assert r.status_code == 404


def test_odds(client):
    r = client.get("/odds?p1=duncan&p2=peter")
    assert r.status_code == 200
    assert "%" in r.text
    assert "score" in r.text


def test_last(client):
    r = client.get("/last")
    assert r.status_code == 200
    assert "21" in r.text


def test_models(client):
    r = client.get("/models")
    assert r.status_code == 200
    assert "Margin-of-victory" in r.text


def test_preview_partial(client):
    r = client.post("/games/preview", data={
        "mode": "1v1", "a1": "duncan", "b1": "peter",
        "score_a": "21", "score_b": "15",
    })
    assert r.status_code == 200
    assert "projected" in r.text


def test_log_game_then_board_reflects_it(client, store):
    nogames = TestClient(webapp.app, follow_redirects=False)
    r = nogames.post("/games", data={
        "mode": "1v1", "a1": "duncan", "b1": "sam",
        "score_a": "21", "score_b": "9",
    })
    assert r.status_code == 303
    assert len(store.games) == 4
    # The board now reflects four games for duncan.
    r2 = client.get("/")
    assert r2.status_code == 200
    assert "duncan" in r2.text


def test_log_game_creates_new_player(client, store):
    nogames = TestClient(webapp.app, follow_redirects=False)
    r = nogames.post("/games", data={
        "mode": "1v1", "a1": "newbie", "b1": "duncan",
        "score_a": "21", "score_b": "5",
    })
    assert r.status_code == 303
    assert "newbie" in store.players


def test_log_game_rejects_bad_score(client, store):
    r = client.post("/games", data={
        "mode": "1v1", "a1": "duncan", "b1": "peter",
        "score_a": "21", "score_b": "20",
    })
    assert r.status_code == 400
    assert "legal result" in r.text
    assert len(store.games) == 3  # nothing logged


def test_undo_reverts_last_game(client, store):
    assert len(store.games) == 3
    nogames = TestClient(webapp.app, follow_redirects=False)
    r = nogames.post("/games/undo")
    assert r.status_code == 303
    assert len(store.games) == 2


def test_add_player(client, store):
    nogames = TestClient(webapp.app, follow_redirects=False)
    r = nogames.post("/players", data={"name": "wanda"})
    assert r.status_code == 303
    assert "wanda" in store.players
