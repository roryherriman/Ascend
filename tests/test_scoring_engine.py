"""Tests for ascend/analysis/scoring_engine.py.

Validates overall score computation, coverage-ratio gating, classification
thresholds, confidence propagation, and structural completeness of the
returned ScoreBreakdown. Does not test individual category internals - those
are covered by test_scoring_categories.py.
"""
from ascend.analysis.scoring_engine import (
    MIN_COVERAGE_RATIO_FOR_CLASSIFICATION,
    compute_score,
)
from ascend.analysis.scoring_models import (
    CategoryStatus,
    Classification,
    ConfidenceLevel,
    ScoreBreakdown,
)
from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _make_character(db, name="Kysarra"):
    return CharacterRepository(db).create(
        Character(display_name=name, character_name=name, region="US", server="Stormrage")
    )


def _add_pulls(db, character, n, *, kill_last=False):
    """Add n fights for a character, optionally marking the last as a kill."""
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code=f"R{character.id}"))
    for i in range(n):
        fight = repo.upsert_fight(Fight(
            report_id=report.id, fight_id=i + 1, name="Boss",
            encounter_id=1, kill=(kill_last and i == n - 1),
        ))
        repo.upsert_fight_participant(FightParticipant(
            fight_id=fight.id, actor_id=1, name=character.character_name,
            server="Stormrage", character_id=character.id,
        ))
    return report


# -- Return type and structure -------------------------------------------------

def test_compute_score_returns_score_breakdown(tmp_path):
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        result = compute_score(db, char.id)
        assert isinstance(result, ScoreBreakdown)
        assert result.character_id == char.id
        assert result.character_name == char.display_name
    finally:
        db.close()


def test_score_breakdown_has_all_seven_categories(tmp_path):
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        result = compute_score(db, char.id)
        expected = {"survival", "execution", "damage", "consistency", "learning", "utility", "participation"}
        assert set(result.categories.keys()) == expected
    finally:
        db.close()


def test_score_breakdown_coverage_ratio_is_fraction_of_100(tmp_path):
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        result = compute_score(db, char.id)
        assert 0.0 <= result.coverage_ratio <= 1.0
    finally:
        db.close()


# -- Coverage-ratio gating -----------------------------------------------------

def test_no_data_yields_insufficient_data_classification(tmp_path):
    """With no synced reports at all, coverage_ratio = 0 -> INSUFFICIENT_DATA."""
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        result = compute_score(db, char.id)
        assert result.classification == Classification.INSUFFICIENT_DATA
        assert result.confidence == ConfidenceLevel.INSUFFICIENT_DATA
        assert result.overall_score is None
    finally:
        db.close()


def test_low_coverage_forces_insufficient_data_regardless_of_pull_count(tmp_path):
    """Even with 60 pulls, if only Participation (8%) + Learning (10%) are
    non-UNAVAILABLE the coverage_ratio is at most 18/100 = 0.18, well below
    the 0.5 threshold, so classification must be INSUFFICIENT_DATA."""
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        _add_pulls(db, char, 60, kill_last=False)
        result = compute_score(db, char.id)
        # Coverage is participation(8) + potentially learning(10) = 18% max
        assert result.coverage_ratio < MIN_COVERAGE_RATIO_FOR_CLASSIFICATION
        assert result.classification == Classification.INSUFFICIENT_DATA
        assert result.confidence == ConfidenceLevel.INSUFFICIENT_DATA
    finally:
        db.close()


# -- Overall score computation -------------------------------------------------

def test_overall_score_is_none_with_no_data(tmp_path):
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        result = compute_score(db, char.id)
        assert result.overall_score is None
    finally:
        db.close()


def test_overall_score_excludes_unavailable_categories(tmp_path):
    """overall_score is a weighted average only of non-UNAVAILABLE categories."""
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        _add_pulls(db, char, 60)
        result = compute_score(db, char.id)

        # Manually verify: only categories with status != UNAVAILABLE contribute
        included = [
            c for c in result.categories.values()
            if c.status != CategoryStatus.UNAVAILABLE and c.score is not None
        ]
        if included and result.overall_score is not None:
            total_w = sum(c.weight for c in included)
            expected = sum(c.score * c.weight for c in included) / total_w
            assert abs(result.overall_score - round(expected, 1)) < 0.01
    finally:
        db.close()


# -- Classification thresholds -------------------------------------------------

def test_standout_never_awarded_without_required_data(tmp_path):
    """Standout requires Survival/Damage/Consistency/Execution all AVAILABLE.
    Those categories are all UNAVAILABLE today, so Standout can never be
    returned - engine must downgrade to Strong or lower."""
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        _add_pulls(db, char, 60)
        result = compute_score(db, char.id)
        assert result.classification != Classification.STANDOUT
    finally:
        db.close()


# -- Notes and explanatory output ----------------------------------------------

def test_notes_list_contains_category_summary(tmp_path):
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        result = compute_score(db, char.id)
        assert any("available" in n.lower() for n in result.notes)
    finally:
        db.close()


def test_low_coverage_note_is_present_when_coverage_below_threshold(tmp_path):
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        _add_pulls(db, char, 5)
        result = compute_score(db, char.id)
        if result.coverage_ratio < MIN_COVERAGE_RATIO_FOR_CLASSIFICATION:
            assert any("less than half" in n.lower() for n in result.notes)
    finally:
        db.close()


# -- Sample size propagation ---------------------------------------------------

def test_sample_size_is_participated_pull_count(tmp_path):
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        _add_pulls(db, char, 12)
        result = compute_score(db, char.id)
        assert result.sample_size == 12
    finally:
        db.close()


def test_unknown_character_yields_insufficient_data_confidence(tmp_path):
    """A character with 0 participated pulls is treated as unknown identity."""
    db = _make_db(tmp_path)
    try:
        char = _make_character(db)
        result = compute_score(db, char.id)
        assert result.confidence == ConfidenceLevel.INSUFFICIENT_DATA
        assert result.sample_size == 0
    finally:
        db.close()
