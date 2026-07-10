from ascend.analysis.progression_weighting import (
    FARM_WEIGHT,
    FIRST_KILL_WEIGHT,
    PROGRESSION_WEIGHT,
    pull_weights,
)
from ascend.data.models import Fight


def _fight(fight_id, kill=False, difficulty=5):
    return Fight(id=fight_id, report_id=1, fight_id=fight_id, name="Test Boss", difficulty=difficulty, kill=kill)


def test_all_progression_when_never_killed():
    fights = [_fight(1), _fight(2), _fight(3)]
    weights = pull_weights(fights)
    assert weights == {1: PROGRESSION_WEIGHT, 2: PROGRESSION_WEIGHT, 3: PROGRESSION_WEIGHT}


def test_first_kill_pull_gets_reduced_weight_and_later_pulls_are_farm():
    fights = [_fight(1), _fight(2, kill=True), _fight(3), _fight(4, kill=True)]
    weights = pull_weights(fights)
    assert weights[1] == PROGRESSION_WEIGHT
    assert weights[2] == FIRST_KILL_WEIGHT
    assert weights[3] == FARM_WEIGHT
    assert weights[4] == FARM_WEIGHT


def test_weighting_is_independent_per_difficulty():
    fights = [
        _fight(1, difficulty=5),
        _fight(2, difficulty=4),
        _fight(3, difficulty=4, kill=True),
        _fight(4, difficulty=4),
        _fight(5, difficulty=5),
    ]
    weights = pull_weights(fights)
    assert weights[1] == PROGRESSION_WEIGHT
    assert weights[5] == PROGRESSION_WEIGHT
    assert weights[2] == PROGRESSION_WEIGHT
    assert weights[3] == FIRST_KILL_WEIGHT
    assert weights[4] == FARM_WEIGHT


def test_weights_sum_matches_expected_values():
    assert PROGRESSION_WEIGHT == 1.00
    assert FIRST_KILL_WEIGHT == 0.80
    assert FARM_WEIGHT == 0.25
