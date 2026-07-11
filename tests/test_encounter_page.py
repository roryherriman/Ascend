from ascend.data.database import Database
from ascend.data.models import Fight, Report
from ascend.data.repositories import ReportRepository
from ascend.ui.encounter_page import EncounterAnalysisPage


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_shows_empty_state_when_no_encounters(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        page = EncounterAnalysisPage(db)
        qtbot.addWidget(page)
        assert page.empty_state is not None
        assert not page.empty_state.isHidden()
        assert page.detail_container.isHidden()
    finally:
        db.close()


def test_shows_pull_history_and_classification_across_reports(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report1 = reports_repo.upsert_report(
            Report(report_code="NIGHT1", title="Night 1", start_time=1_000_000)
        )
        report2 = reports_repo.upsert_report(
            Report(report_code="NIGHT2", title="Night 2", start_time=2_000_000)
        )
        reports_repo.upsert_fight(
            Fight(report_id=report1.id, fight_id=1, name="Test Boss", encounter_id=99,
                  difficulty=5, kill=False, start_time=0, end_time=60000)
        )
        reports_repo.upsert_fight(
            Fight(report_id=report1.id, fight_id=2, name="Test Boss", encounter_id=99,
                  difficulty=5, kill=True, start_time=100000, end_time=160000)
        )
        reports_repo.upsert_fight(
            Fight(report_id=report2.id, fight_id=1, name="Test Boss", encounter_id=99,
                  difficulty=5, kill=False, start_time=0, end_time=30000)
        )

        page = EncounterAnalysisPage(db)
        qtbot.addWidget(page)

        assert page.empty_state is None or page.empty_state.isHidden()
        assert not page.detail_container.isHidden()
        assert page.encounter_combo.count() == 1
        assert page.encounter_combo.currentText() == "Test Boss"

        # 3 pull rows in _pulls_layout
        assert page._pulls_layout.count() == 3
        # Check result labels: Wipe, Kill ✓, Wipe
        from PySide6.QtWidgets import QLabel
        def _result_text(row_idx):
            w = page._pulls_layout.itemAt(row_idx).widget()
            labels = w.findChildren(QLabel)
            for lbl in labels:
                t = lbl.text()
                if "Kill" in t or "Wipe" in t:
                    return t
            return ""
        assert "Wipe" in _result_text(0)
        assert "Kill" in _result_text(1)
        assert "Wipe" in _result_text(2)
    finally:
        db.close()


def test_reload_picks_up_new_encounters(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        page = EncounterAnalysisPage(db)
        qtbot.addWidget(page)
        assert page.encounter_combo.count() == 0

        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="NIGHT1", title="Night 1"))
        reports_repo.upsert_fight(
            Fight(report_id=report.id, fight_id=1, name="New Boss", encounter_id=5, kill=False)
        )

        page.reload()
        assert page.encounter_combo.count() == 1
        assert page.encounter_combo.currentText() == "New Boss"
    finally:
        db.close()
