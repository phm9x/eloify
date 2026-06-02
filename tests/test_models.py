import math

import pytest

from eloify import elo
from eloify.elo import Matchup, Model, all_models, default_model, get_model, register


def _matchup(ra, rb, sa, sb, ga=0, gb=0):
    return Matchup(
        team_a=[ra], team_b=[rb],
        team_a_games=[ga], team_b_games=[gb],
        score_a=sa, score_b=sb,
    )


def test_default_is_mov():
    assert default_model().key == "mov"
    assert get_model(None) is default_model()


def test_registry_lists_default_first():
    keys = [m.key for m in all_models()]
    assert keys[0] == "mov"
    assert set(keys) >= {"mov", "elo", "provisional"}


def test_unknown_model_raises_keyerror():
    with pytest.raises(KeyError):
        get_model("nope")


def test_lookup_by_number():
    models = all_models()
    assert get_model("1") is models[0] is default_model()
    assert get_model("2") is models[1]
    # numbers and keys agree
    assert get_model(str(len(models))) is get_model(models[-1].key)


def test_out_of_range_number_raises():
    with pytest.raises(KeyError):
        get_model("0")
    with pytest.raises(KeyError):
        get_model(str(len(all_models()) + 1))


def test_score_share_lets_close_loser_gain():
    # A is a heavy underdog (900 vs 1100) but only loses 19-21: they over-
    # performed the spread, so they should gain rating despite losing.
    (da,), (db,) = get_model("share").rate(_matchup(900, 1100, 19, 21))
    assert da > 0 > db


def test_score_share_blowout_loss_costs_more_than_close_loss():
    close, _ = get_model("share").rate(_matchup(1000, 1000, 19, 21))
    blowout, _ = get_model("share").rate(_matchup(1000, 1000, 3, 21))
    assert close[0] > blowout[0]  # losing closer is better


def test_mov_model_matches_compute_deltas():
    # The default model must reproduce the standalone formula exactly.
    da_fn, db_fn = elo.compute_deltas(1000, 1000, 21, 18)
    (da,), (db,) = get_model("mov").rate(_matchup(1000, 1000, 21, 18))
    assert math.isclose(da, da_fn) and math.isclose(db, db_fn)


def test_plain_elo_ignores_margin():
    close, _ = get_model("elo").rate(_matchup(1000, 1000, 21, 19))
    blowout, _ = get_model("elo").rate(_matchup(1000, 1000, 21, 3))
    assert math.isclose(close[0], blowout[0])  # margin doesn't matter


def test_mov_model_cares_about_margin():
    close, _ = get_model("mov").rate(_matchup(1000, 1000, 21, 19))
    blowout, _ = get_model("mov").rate(_matchup(1000, 1000, 21, 3))
    assert blowout[0] > close[0]


def test_provisional_new_player_moves_more():
    # Same matchup, but a rookie (0 games) swings harder than a veteran (20).
    rookie, _ = get_model("provisional").rate(_matchup(1000, 1000, 21, 10, ga=0))
    vet, _ = get_model("provisional").rate(_matchup(1000, 1000, 21, 10, ga=20))
    assert rookie[0] > vet[0]


def test_models_are_zero_sum():
    for key in ("mov", "elo", "provisional", "share"):
        (da,), (db,) = get_model(key).rate(_matchup(1000, 1000, 21, 10))
        assert math.isclose(da, -db)


def test_register_rejects_duplicate_key():
    with pytest.raises(ValueError):
        register(Model(key="mov", label="x", description="x", rate=lambda m: ([], [])))
