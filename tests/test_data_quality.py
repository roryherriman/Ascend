from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository
from ascend.services.data_quality import (
    DETECTED,
    NO_DATA,
    NOT_DETECTED,
    character_identity_confidence,
    small_sample_warnings,
)


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_character_confidence_is_no_data_when_nothing_synced(tmp_path):
    db = _make_db(tmp_path)
    try:
        CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        result = character_identity_confidence(db)
        assert len(result) == 1
        assert result[0].status == NO_DATA
    finally:
        db.close()


def test_character_confidence_is_not_detected_when_reports_exist_but_no_match(tmp_path):
    db = _make_db(tmp_path)
    try:
        CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC"))
        fight = reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight_participant(
            FightParticipant(fight_id=fight.id, actor_id=1, name="Someoneelse", server="Proudmoore")
        )

        result = character_identity_confidence(db)
        assert result[0].status == NOT_DETECTED
        assert result[0].participations == 0
    finally:
        db.close()


def test_character_confidence_is_detected_when_matched(tmp_path):
    db = _make_db(tmp_path)
    try:
        character = CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC"))
        fight = reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight_participant(
            FightParticipant(
                fight_id=fight.id, actor_id=1, name="Aeloria", server="Proudmoore", character_id=character.id
            )
        )

        result = character_identity_confidence(db)
        assert result[0].status == DETECTED
        assert result[0].participations == 1
        assert result[0].raid_nights == 1
    finally:
        db.close()


def test_small_sample_warnings_flags_reports_below_threshold(tmp_path):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC", title="Short Night"))
        reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss"))

        warnings = small_sample_warnings(db, min_pulls=3)
        report_warnings = [w for w in warnings if w.kind == "report"]
        assert len(report_warnings) == 1
        assert report_warnings[0].subject == "Short Night"
        assert report_warnings[0].pulls == 1
    finally:
        db.close()


def test_small_sample_warnings_ignores_reports_at_or_above_threshold(tmp_path):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC", title="Full Night"))
        for i in range(3):
            reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=i + 1, name="Boss"))

        warnings = small_sample_warnings(db, min_pulls=3)
        assert warnings == []
    finally:
        db.close()


def test_small_sample_warnings_flags_low_pull_encounters(tmp_path):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC"))
        reports_repo.upsert_fight(
            Fight(report_id=report.id, fight_id=1, name="Rare Boss", encounter_id=7)
        )

        warnings = small_sample_warnings(db, min_pulls=3)
        encounter_warnings = [w for w in warnings if w.kind == "encounter"]
        assert len(encounter_warnings) == 1
        assert encounter_warnings[0].subject == "Rare Boss"
        assert encounter_warnings[0].pulls == 1
    finally:
        db.close()
