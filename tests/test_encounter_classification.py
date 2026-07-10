from ascend.data.models import Fight
from ascend.services.encounter_classification import (
    FARM,
    PROGRESSION,
    classify_pulls,
    group_by_pull_range,
)


def _fight(fight_id, kill=False, difficulty=5):
    return Fight(id=fight_id, report_id=1, fight_id=fight_id, name="Test Boss", difficulty=difficulty, kill=kill)


def test_all_pulls_are_progression_when_never_killed():
    fights = [_fight(1), _fight(2), _fight(3)]
    result = classify_pulls(fights)
    assert result == {1: PROGRESSION, 2: PROGRESSION, 3: PROGRESSION}


def test_pulls_after_first_kill_are_farm():
    fights = [_fight(1), _fight(2, kill=True), _fight(3), _fight(4, kill=True)]
    result = classify_pulls(fights)
    assert result == {1: PROGRESSION, 2: PROGRESSION, 3: FARM, 4: FARM}


def test_classification_is_independent_per_difficulty():
    # Mythic (5) never killed; Heroic (4) killed on its second pull.
    fights = [
        _fight(1, difficulty=5),
        _fight(2, difficulty=4),
        _fight(3, difficulty=4, kill=True),
        _fight(4, difficulty=4),
        _fight(5, difficulty=5),
    ]
    result = classify_pulls(fights)
    assert result[1] == PROGRESSION
    assert result[5] == PROGRESSION
    assert result[2] == PROGRESSION
    assert result[3] == PROGRESSION
    assert result[4] == FARM


def test_group_by_pull_range_only_counts_progression_pulls():
    fights = [_fight(i) for i in range(1, 13)]  # 12 progression pulls, no kill
    groups = group_by_pull_range(fights)
    assert groups[0] == {"label": "Pulls 1-10", "pulls": 10, "kills": 0}
    assert groups[1] == {"label": "Pulls 11-25", "pulls": 2, "kills": 0}


def test_group_by_pull_range_excludes_farm_pulls():
    fights = [_fight(i, kill=(i == 3)) for i in range(1, 6)]  # kill on pull 3; pulls 4-5 are farm
    groups = group_by_pull_range(fights)
    assert len(groups) == 1
    assert groups[0] == {"label": "Pulls 1-10", "pulls": 3, "kills": 1}


def test_group_by_pull_range_empty_when_no_pulls():
    assert group_by_pull_range([]) == []
