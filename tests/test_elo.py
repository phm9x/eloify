import math

from eloify.elo import compute_deltas, expected, mov_multiplier


def test_expected_symmetry():
    assert expected(1000, 1000) == 0.5
    assert math.isclose(expected(1000, 1200) + expected(1200, 1000), 1.0)


def test_deltas_are_zero_sum():
    da, db = compute_deltas(1000, 1000, 21, 18)
    assert math.isclose(da, -db)


def test_winner_gains_loser_loses():
    da, db = compute_deltas(1000, 1000, 21, 10)
    assert da > 0 > db


def test_bigger_margin_moves_more():
    close, _ = compute_deltas(1000, 1000, 21, 19)
    blowout, _ = compute_deltas(1000, 1000, 21, 3)
    assert blowout > close


def test_even_match_blowout_is_meaningful():
    # 21-3 between equals should be a solid double-digit swing with K=24.
    da, _ = compute_deltas(1000, 1000, 21, 3)
    assert 10 < da < 40


def test_upset_amplified_vs_expected_win():
    # Same 21-15 margin: underdog winning gains more than the favorite would.
    underdog_win, _ = compute_deltas(900, 1100, 21, 15)   # A is weaker, A wins
    favorite_win, _ = compute_deltas(1100, 900, 21, 15)   # A is stronger, A wins
    assert underdog_win > favorite_win


def test_mov_multiplier_grows_with_margin():
    assert mov_multiplier(2, 1000, 1000) < mov_multiplier(18, 1000, 1000)
