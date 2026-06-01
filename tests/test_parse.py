import pytest

from eloify.parse import ParseError, parse_add


def test_1v1_basic():
    g = parse_add(["duncan", "peter", "21", "18"])
    assert g.mode == "1v1"
    assert g.team_a == ["duncan"]
    assert g.team_b == ["peter"]
    assert (g.score_a, g.score_b) == (21, 18)


def test_2v2_positional():
    g = parse_add(["duncan", "peter", "sam", "alex", "21", "15"])
    assert g.mode == "2v2"
    assert g.team_a == ["duncan", "peter"]
    assert g.team_b == ["sam", "alex"]
    assert (g.score_a, g.score_b) == (21, 15)


def test_winner_not_required_first():
    # Lower score listed first still parses; higher score wins downstream.
    g = parse_add(["peter", "duncan", "18", "21"])
    assert g.team_a == ["peter"] and g.score_a == 18
    assert g.team_b == ["duncan"] and g.score_b == 21


def test_optional_vs_separator_is_ignored():
    g = parse_add(["duncan", "peter", "vs", "sam", "alex", "21", "15"])
    assert g.team_a == ["duncan", "peter"]
    assert g.team_b == ["sam", "alex"]


def test_optional_slash_separator():
    g = parse_add(["duncan", "/", "peter", "21", "18"])
    assert g.mode == "1v1"
    assert g.team_a == ["duncan"] and g.team_b == ["peter"]


def test_separator_with_uneven_teams_errors():
    with pytest.raises(ParseError):
        parse_add(["a", "b", "vs", "c", "21", "18"])


@pytest.mark.parametrize("tokens", [
    ["duncan", "peter", "21"],            # one score
    ["duncan", "peter", "21", "18", "5"], # three scores
    ["duncan", "21", "18"],               # one name
    ["a", "b", "c", "21", "18"],          # three names, no separator
    [],
])
def test_malformed_inputs_raise(tokens):
    with pytest.raises(ParseError):
        parse_add(tokens)
