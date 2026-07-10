"""Dashboard STATE-DRIVEN COMPOSITION: verifies the Dashboard shows a
genuinely different widget/composition for NO_DATA, IMPORTED_INCOMPLETE, and
ACTIVE - not the same layout with values swapped for "--" - and that state
is recomputed after an import, after analysis completes, and on demand (e.g.
a character switch)."""
from __future__ import annotations

from ascend.data.database import Database
from ascend.data.models import Fight, Report
from ascend.data.repositories import AnalysisRunRepository, ReportRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.ui.dashboard_page import ACTIVE, IMPORTED_INCOMPLETE, NO_DATA, DashboardPage
from ascend.ui.dashboard_states import ActiveAnalyticsState, ImportedIncompleteState, NoDataState


def _make_page(tmp_path, qtbot, is_demo: bool = False) -> tuple[DashboardPage, Database]:
    db = Database(tmp_path / "dashboard_states.db")
    db.initialize()
    page = DashboardPage(db, SecureStorage.default_instance(), BackgroundTaskManager(), is_demo=is_demo)
    qtbot.addWidget(page)
    return page, db


def _seed_report(db: Database) -> Report:
    reports_repo = ReportRepository(db)
    reports_repo.upsert_report(Report(report_code="TESTCODE1", title="Test Night"))
    report = reports_repo.get_by_code("TESTCODE1")
    reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Test Boss", kill=False))
    return report


def test_fresh_database_shows_no_data_state(tmp_path, qtbot):
    page, db = _make_page(tmp_path, qtbot)
    try:
        assert page._compute_state() == NO_DATA
        assert page.stack.currentWidget().widget() is page._state_widgets[NO_DATA]
        assert isinstance(page._state_widgets[NO_DATA], NoDataState)
    finally:
        db.close()


def test_reports_without_analysis_shows_imported_incomplete_state(tmp_path, qtbot):
    page, db = _make_page(tmp_path, qtbot)
    try:
        _seed_report(db)
        page.refresh_state()
        assert page._compute_state() == IMPORTED_INCOMPLETE
        assert page.stack.currentWidget().widget() is page._state_widgets[IMPORTED_INCOMPLETE]
        assert isinstance(page._state_widgets[IMPORTED_INCOMPLETE], ImportedIncompleteState)
    finally:
        db.close()


def test_completed_analysis_shows_active_state(tmp_path, qtbot):
    page, db = _make_page(tmp_path, qtbot)
    try:
        report = _seed_report(db)
        AnalysisRunRepository(db).record(
            report_id=report.id,
            character_id=None,
            app_version="test",
            analysis_engine_version="test",
            scoring_model_version="test",
        )
        page.refresh_state()
        assert page._compute_state() == ACTIVE
        assert page.stack.currentWidget().widget() is page._state_widgets[ACTIVE]
        assert isinstance(page._state_widgets[ACTIVE], ActiveAnalyticsState)
    finally:
        db.close()


def test_demo_mode_forces_active_state_even_with_no_reports(tmp_path, qtbot):
    page, db = _make_page(tmp_path, qtbot, is_demo=True)
    try:
        assert page._compute_state() == ACTIVE
        assert page.stack.currentWidget().widget() is page._state_widgets[ACTIVE]
    finally:
        db.close()


def test_character_switch_recomputes_state_without_error(tmp_path, qtbot):
    page, db = _make_page(tmp_path, qtbot)
    try:
        _seed_report(db)
        page._on_character_changed(None)
        assert page._compute_state() in (NO_DATA, IMPORTED_INCOMPLETE, ACTIVE)
    finally:
        db.close()


def test_no_data_and_active_states_are_different_widget_types(tmp_path, qtbot):
    """The core requirement: these are fundamentally different compositions,
    not one layout with "--" substituted for values."""
    page, db = _make_page(tmp_path, qtbot)
    try:
        no_data_widget = page._state_widgets[NO_DATA]
        active_widget = page._state_widgets[ACTIVE]
        imported_widget = page._state_widgets[IMPORTED_INCOMPLETE]
        assert type(no_data_widget) is not type(active_widget)
        assert type(no_data_widget) is not type(imported_widget)
        assert type(active_widget) is not type(imported_widget)
        # No Data must never expose analytics widgets (KPI row, trend chart,
        # raid-night table) that the spec says shouldn't exist there.
        assert not hasattr(no_data_widget, "kpi_row")
        assert not hasattr(no_data_widget, "recent_table")
        assert hasattr(active_widget, "kpi_row")
        assert hasattr(active_widget, "recent_table")
    finally:
        db.close()
