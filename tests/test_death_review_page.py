import json

from ascend.data.database import Database
from ascend.data.repositories import ReportRepository
from ascend.data.models import Report
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.death_data import fetch_and_cache_death_table
from ascend.ui.death_review_page import DeathReviewPage


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_shows_empty_state_when_no_reports(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        page = DeathReviewPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
        qtbot.addWidget(page)
        assert page.empty_state is not None
        assert not page.empty_state.isHidden()
        assert page.detail_container.isHidden()
    finally:
        db.close()


def test_shows_cached_death_data_for_selected_report(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))

        class FakeClient:
            def fetch_death_table(self, report_code, fight_ids=None):
                return {"entries": [{"name": "Kysarra"}]}

        fetch_and_cache_death_table(db, FakeClient(), "ABC123")

        page = DeathReviewPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
        qtbot.addWidget(page)

        assert not page.detail_container.isHidden()
        shown = json.loads(page.raw_data_view.toPlainText())
        assert shown == {"entries": [{"name": "Kysarra"}]}
    finally:
        db.close()


def test_shows_placeholder_when_nothing_cached_yet(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))

        page = DeathReviewPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
        qtbot.addWidget(page)

        assert page.raw_data_view.toPlainText() == ""
    finally:
        db.close()


def test_fetch_button_shows_error_without_credentials(tmp_path, qtbot, monkeypatch):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))

        page = DeathReviewPage(db, SecureStorage.default_instance(), BackgroundTaskManager())
        qtbot.addWidget(page)

        called = {}
        monkeypatch.setattr(
            "ascend.ui.death_review_page.show_error",
            lambda *a, **k: called.setdefault("shown", True),
        )
        page._on_fetch_clicked()
        assert called.get("shown") is True
    finally:
        db.close()
