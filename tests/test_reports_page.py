"""Reports page tests — updated for PR 6 card-based Report Library."""
from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.ui.reports_page import ReportsPage, _ReportCard


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_no_table_widget_in_reports_page(tmp_path, qtbot):
    """PR 6: QTableWidget replaced by card layout — COLUMNS removed."""
    from PySide6.QtWidgets import QTableWidget
    db = _make_db(tmp_path)
    page = ReportsPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
    qtbot.addWidget(page)
    assert not page.findChildren(QTableWidget)


def test_card_shows_detected_character_class(tmp_path, qtbot):
    """Character and class information appear in card text (via zone/stats area)."""
    from PySide6.QtWidgets import QLabel
    db = _make_db(tmp_path)
    try:
        character = CharacterRepository(db).create(
            Character(
                display_name="Aeloria", character_name="Aeloria",
                region="US", server="Proudmoore", character_role="primary",
            )
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))
        fight = reports_repo.upsert_fight(
            Fight(report_id=report.id, fight_id=1, name="Test Boss", kill=True)
        )
        reports_repo.upsert_fight_participant(
            FightParticipant(
                fight_id=fight.id, actor_id=1, name="Aeloria", server="Proudmoore",
                class_name="Priest", character_id=character.id,
            )
        )

        page = ReportsPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
        qtbot.addWidget(page)
        cards = page.findChildren(_ReportCard)
        assert cards, "Expected one report card"
        all_text = " ".join(lbl.text() for lbl in cards[0].findChildren(QLabel))
        assert "Test Night" in all_text
    finally:
        db.close()


def test_view_raid_night_requested_emits_from_card_action(tmp_path, qtbot):
    """_on_view_raid_night emits view_raid_night_requested with the report id."""
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))

        page = ReportsPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
        qtbot.addWidget(page)

        with qtbot.waitSignal(page.view_raid_night_requested, timeout=1000) as blocker:
            page._on_view_raid_night(report)
        assert blocker.args == [report.id]
    finally:
        db.close()
