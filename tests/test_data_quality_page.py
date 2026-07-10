from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository, SyncHistoryRepository
from ascend.ui.data_quality_page import DataQualityPage


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_confidence_table_reflects_detection_status(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        character = CharacterRepository(db).create(
            Character(display_name="Kysarra", character_name="Kysarra", region="US", server="Stormrage")
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC"))
        fight = reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight_participant(
            FightParticipant(
                fight_id=fight.id, actor_id=1, name="Kysarra", server="Stormrage", character_id=character.id
            )
        )

        page = DataQualityPage(db)
        qtbot.addWidget(page)

        assert page.confidence_table.rowCount() == 1
        assert page.confidence_table.item(0, 0).text() == "Kysarra"
        assert page.confidence_table.item(0, 1).text() == "1"
    finally:
        db.close()


def test_sync_history_table_shows_recent_entries(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        history = SyncHistoryRepository(db)
        history_id = history.start("report_code:ABC")
        history.finish(history_id, "success", reports_processed=1, pulls_processed=5)

        page = DataQualityPage(db)
        qtbot.addWidget(page)

        assert page.sync_table.rowCount() == 1
        assert page.sync_table.item(0, 2).text() == "success"
        assert page.sync_table.item(0, 4).text() == "5"
    finally:
        db.close()


def test_warnings_hidden_when_no_small_samples(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        page = DataQualityPage(db)
        qtbot.addWidget(page)
        assert not page.no_warnings_label.isHidden()
        assert page.warnings_container.count() == 0
    finally:
        db.close()
