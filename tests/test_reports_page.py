from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.ui.reports_page import COLUMNS, ReportsPage


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_columns_include_character_and_class_not_spec():
    assert "Character" in COLUMNS
    assert "Class" in COLUMNS
    assert "Spec" not in COLUMNS


def test_table_shows_detected_character_and_class(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        character = CharacterRepository(db).create(
            Character(
                display_name="Kysarra", character_name="Kysarra",
                region="US", server="Stormrage", character_role="primary",
            )
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))
        fight = reports_repo.upsert_fight(
            Fight(report_id=report.id, fight_id=1, name="Test Boss", kill=True)
        )
        reports_repo.upsert_fight_participant(
            FightParticipant(
                fight_id=fight.id, actor_id=1, name="Kysarra", server="Stormrage",
                class_name="Priest", character_id=character.id,
            )
        )

        page = ReportsPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
        qtbot.addWidget(page)

        character_col = COLUMNS.index("Character")
        class_col = COLUMNS.index("Class")
        assert page.table.item(0, character_col).text() == "Kysarra"
        assert page.table.item(0, class_col).text() == "Priest"
    finally:
        db.close()


def test_view_raid_night_requested_emits_selected_report_id(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))

        page = ReportsPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
        qtbot.addWidget(page)
        page.table.selectRow(0)

        with qtbot.waitSignal(page.view_raid_night_requested, timeout=1000) as blocker:
            page._on_view_raid_night_summary()
        assert blocker.args == [report.id]
    finally:
        db.close()
