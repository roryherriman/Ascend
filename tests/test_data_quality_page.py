from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository, SyncHistoryRepository
from ascend.ui.data_quality_page import DataQualityPage


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_confidence_rows_reflect_detection_status(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC"))
        fight = reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight_participant(
            FightParticipant(
                fight_id=fight.id, actor_id=1, name="Aeloria", server="Proudmoore", character_id=fight.report_id
            )
        )

        page = DataQualityPage(db)
        qtbot.addWidget(page)

        # 1 header row + 1 data row
        assert page._confidence_rows_layout.count() == 2
    finally:
        db.close()


def test_sync_history_rows_show_recent_entries(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        history = SyncHistoryRepository(db)
        history_id = history.start("report_code:ABC")
        history.finish(history_id, "success", reports_processed=1, pulls_processed=5)

        page = DataQualityPage(db)
        qtbot.addWidget(page)

        # 1 header row + 1 data row
        assert page._sync_rows_layout.count() == 2
    finally:
        db.close()


def test_data_quality_page_has_no_table_widget(tmp_path, qtbot):
    from PySide6.QtWidgets import QTableWidget
    db = _make_db(tmp_path)
    try:
        page = DataQualityPage(db)
        qtbot.addWidget(page)
        assert not page.findChildren(QTableWidget)
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
