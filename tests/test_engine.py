from eloify.engine import replay_modes
from eloify.models import Game


def _g(gid, mode, a, b, sa, sb):
    return Game(id=gid, played_at="", mode=mode, team_a=a, team_b=b, score_a=sa, score_b=sb)


GAMES = [
    _g(1, "1v1", ["duncan"], ["peter"], 21, 18),
    _g(2, "1v1", ["duncan"], ["sam"], 21, 10),
    _g(3, "2v2", ["duncan", "peter"], ["sam", "alex"], 21, 15),
]
PLAYERS = ["duncan", "peter", "sam", "alex"]


def test_overall_counts_all_games():
    overall = replay_modes(PLAYERS, GAMES)["overall"]
    assert overall["duncan"].games == 3   # 2 singles + 1 doubles
    assert overall["alex"].games == 1     # 1 doubles only


def test_singles_ignores_doubles():
    singles = replay_modes(PLAYERS, GAMES)["singles"]
    assert singles["duncan"].games == 2
    assert singles["duncan"].wins == 2
    assert singles["peter"].games == 1    # only the 1v1 loss
    assert singles["alex"].games == 0     # never played singles


def test_doubles_ignores_singles():
    doubles = replay_modes(PLAYERS, GAMES)["doubles"]
    assert doubles["duncan"].games == 1
    assert doubles["alex"].games == 1
    assert doubles["alex"].losses == 1


def test_ratings_are_independent_across_modes():
    modes = replay_modes(PLAYERS, GAMES)
    # alex never played singles -> stays at the 1000 default there,
    # but moved in doubles.
    assert modes["singles"]["alex"].rating == 1000
    assert modes["doubles"]["alex"].rating < 1000
