import pytest

from eloify.validate import ScoreError, is_legal_score, validate_score

LEGAL = [
    (21, 18),  # clean to 21
    (11, 9),   # clean to 11
    (12, 10),  # 11-game deuce
    (23, 21),  # 21-game deuce
    (5, 3),    # clean to 5
    (7, 5),    # 5-game deuce
    (6, 4),    # 5-game deuce
    (13, 11),  # long 11 deuce
    (11, 0),   # shutout
    (10, 8),   # marathon to-5 deuce (4-4, 6-4, ... 10-8): win by 2 from target 5
]

ILLEGAL = [
    (11, 10),  # won by 1, must deuce
    (21, 20),  # won by 1
    (5, 4),    # won by 1
    (3, 1),    # 3 isn't a target
    (4, 2),    # target not reached, loser below deuce
    (6, 3),    # won by 3 but loser never reached deuce (<=3) and 6 isn't a target
    (10, 3),   # 10 isn't a target; loser below deuce range
    (21, 21),  # tie
    (-1, 5),   # negative
]


@pytest.mark.parametrize("a,b", LEGAL)
def test_legal_scores(a, b):
    assert is_legal_score(a, b)
    validate_score(a, b)            # should not raise
    assert is_legal_score(b, a)     # order independent


@pytest.mark.parametrize("a,b", ILLEGAL)
def test_illegal_scores(a, b):
    assert not is_legal_score(a, b)
    with pytest.raises(ScoreError):
        validate_score(a, b)
