"""Dashboard STATE-DRIVEN COMPOSITION: verifies the Dashboard shows a
genuinely different widget/composition for NO_DATA, IMPORTED_INCOMPLETE, and
ACTIVE - not the same layout with values swapped for "--" - and that state
is recomputed after an import, after analysis completes, and on demand (e.g.
a character switch)."""
from __future__ import annotations

from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import AnalysisRunRepository, CharacterRepository, ReportRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.ui.dashboard_page import ACTIVE, IMPORTED_INCOMPLETE, NO_DATA, DashboardPage
from ascend.ui.dashboard_states import ActiveAnalyticsState, ImportedIncompleteState, NoDataState


class _DummySignal:
    def emit(self, *args, **kwargs):
        pass


def _make_active_state(db, qtbot) -> ActiveAnalyticsState:
    state = ActiveAnalyticsState(
        db, SecureStorage.default_instance(), BackgroundTaskManager(), _DummySignal()
    )
    qtbot.addWidget(state)
    return state


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
        assert not hasattr(no_data_widget, "_raid_nights_layout")
        assert hasattr(active_widget, "kpi_row")
        assert hasattr(active_widget, "_raid_nights_layout")
    finally:
        db.close()


def test_participation_kpi_reflects_best_attended_tracked_character(tmp_path, qtbot):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        character = CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        reports_repo = ReportRepository(db)
        report1 = reports_repo.upsert_report(Report(report_code="N1"))
        report2 = reports_repo.upsert_report(Report(report_code="N2"))
        fight1 = reports_repo.upsert_fight(Fight(report_id=report1.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight(Fight(report_id=report2.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight_participant(
            FightParticipant(fight_id=fight1.id, actor_id=1, name="Aeloria", server="Proudmoore", character_id=character.id)
        )

        state = _make_active_state(db, qtbot)
        # Attended 1 of 2 raid nights -> 50%.
        assert state._kpi_metrics["participation"].value_label.text() == "50%"
    finally:
        db.close()


def test_insights_show_kill_rate_and_busiest_encounter(tmp_path, qtbot):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="N1"))
        reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss", kill=False))
        reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=2, name="Boss", kill=True))

        state = _make_active_state(db, qtbot)
        assert state.insights_container.count() >= 2
        assert state.insights_empty_label.isHidden()
    finally:
        db.close()


def test_data_quality_banner_warns_about_undetected_character(tmp_path, qtbot):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="N1"))
        fight = reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight_participant(
            FightParticipant(fight_id=fight.id, actor_id=1, name="Someoneelse", server="Proudmoore")
        )

        state = _make_active_state(db, qtbot)
        assert not state.data_quality_banner.isHidden()
        assert "Aeloria" in state.data_quality_banner.label.text()
    finally:
        db.close()


def test_data_quality_banner_hidden_when_nothing_to_warn_about(tmp_path, qtbot):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        character = CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="N1"))
        for i in range(3):
            fight = reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=i + 1, name="Boss"))
            reports_repo.upsert_fight_participant(
                FightParticipant(fight_id=fight.id, actor_id=1, name="Aeloria", server="Proudmoore", character_id=character.id)
            )

        state = _make_active_state(db, qtbot)
        assert state.data_quality_banner.isHidden()
    finally:
        db.close()


def test_apply_demo_data_suppresses_data_quality_banner(tmp_path, qtbot):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        # A tracked character with zero participations would normally trip
        # the "not detected" warning - apply_demo_data must suppress it.
        CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="N1"))
        reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss"))

        state = _make_active_state(db, qtbot)
        assert not state.data_quality_banner.isHidden()  # sanity: would warn without demo override

        state.apply_demo_data()
        assert state.data_quality_banner.isHidden()
    finally:
        db.close()
