"""PR 8 tests: Report Library source filter + sort; Raid Night, Encounter Analysis,
Encounter Progression pages no longer use QTableWidget."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# ReportsPage — source filter and newest-first sort
# ---------------------------------------------------------------------------

def _make_reports_page(tmp_path):
    from ascend.data.database import Database
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.reports_page import ReportsPage
    db = Database(tmp_path / "test.db")
    db.initialize()
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    return ReportsPage(db, storage, mgr), db


def test_reports_page_has_source_filter(qtbot, tmp_path):
    page, _ = _make_reports_page(tmp_path)
    qtbot.addWidget(page)
    assert hasattr(page, "source_filter")
    items = [page.source_filter.itemText(i) for i in range(page.source_filter.count())]
    assert "All Sources" in items
    assert "Manual" in items
    assert "Guild Sync" in items


def test_reports_page_source_filter_manual(qtbot, tmp_path):
    from ascend.data.models import Report
    from ascend.data.repositories import ReportRepository
    page, db = _make_reports_page(tmp_path)
    qtbot.addWidget(page)
    repo = ReportRepository(db)
    repo.upsert_report(Report(report_code="A1", title="Manual", start_time=1000, end_time=2000, report_source="manual"))
    repo.upsert_report(Report(report_code="B2", title="Guild", start_time=3000, end_time=4000, report_source="guild_discovery"))
    page.reload()
    page.source_filter.setCurrentText("Manual")
    filtered = page._filtered_reports()
    assert all(r.report_source != "guild_discovery" for r in filtered)
    assert any(r.report_code == "A1" for r in filtered)
    assert not any(r.report_code == "B2" for r in filtered)


def test_reports_page_source_filter_guild(qtbot, tmp_path):
    from ascend.data.models import Report
    from ascend.data.repositories import ReportRepository
    page, db = _make_reports_page(tmp_path)
    qtbot.addWidget(page)
    repo = ReportRepository(db)
    repo.upsert_report(Report(report_code="A1", title="Manual", start_time=1000, end_time=2000, report_source="manual"))
    repo.upsert_report(Report(report_code="B2", title="Guild", start_time=3000, end_time=4000, report_source="guild_discovery"))
    page.reload()
    page.source_filter.setCurrentText("Guild Sync")
    filtered = page._filtered_reports()
    assert all(r.report_source == "guild_discovery" for r in filtered)
    assert any(r.report_code == "B2" for r in filtered)


def test_reports_page_sorted_newest_first(qtbot, tmp_path):
    from ascend.data.models import Report
    from ascend.data.repositories import ReportRepository
    page, db = _make_reports_page(tmp_path)
    qtbot.addWidget(page)
    repo = ReportRepository(db)
    repo.upsert_report(Report(report_code="OLD", title="Old", start_time=1000, end_time=2000))
    repo.upsert_report(Report(report_code="NEW", title="New", start_time=9000, end_time=10000))
    page.reload()
    filtered = page._filtered_reports()
    assert filtered[0].report_code == "NEW"
    assert filtered[1].report_code == "OLD"


def test_reports_page_has_count_label(qtbot, tmp_path):
    page, _ = _make_reports_page(tmp_path)
    qtbot.addWidget(page)
    assert hasattr(page, "_count_label")


def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


# ---------------------------------------------------------------------------
# RaidNightSummaryPage
# ---------------------------------------------------------------------------

def test_raid_night_page_has_no_table_widget(qtbot, tmp_path):
    from PySide6.QtWidgets import QTableWidget
    from ascend.ui.raid_night_page import RaidNightSummaryPage
    db = _make_db(tmp_path)
    page = RaidNightSummaryPage(db)
    qtbot.addWidget(page)
    assert not page.findChildren(QTableWidget)


def test_raid_night_page_has_pulls_layout(qtbot, tmp_path):
    from ascend.ui.raid_night_page import RaidNightSummaryPage
    db = _make_db(tmp_path)
    page = RaidNightSummaryPage(db)
    qtbot.addWidget(page)
    assert hasattr(page, "_pulls_layout")
    assert hasattr(page, "_roster_layout")


# ---------------------------------------------------------------------------
# EncounterAnalysisPage
# ---------------------------------------------------------------------------

def test_encounter_page_has_no_table_widget(qtbot, tmp_path):
    from PySide6.QtWidgets import QTableWidget
    from ascend.ui.encounter_page import EncounterAnalysisPage
    db = _make_db(tmp_path)
    page = EncounterAnalysisPage(db)
    qtbot.addWidget(page)
    assert not page.findChildren(QTableWidget)


def test_encounter_page_has_pulls_layout(qtbot, tmp_path):
    from ascend.ui.encounter_page import EncounterAnalysisPage
    db = _make_db(tmp_path)
    page = EncounterAnalysisPage(db)
    qtbot.addWidget(page)
    assert hasattr(page, "_pulls_layout")


# ---------------------------------------------------------------------------
# EncounterProgressionPage
# ---------------------------------------------------------------------------

def test_encounter_progression_page_has_no_table_widget(qtbot, tmp_path):
    from PySide6.QtWidgets import QTableWidget
    from ascend.ui.encounter_progression_page import EncounterProgressionPage
    db = _make_db(tmp_path)
    page = EncounterProgressionPage(db)
    qtbot.addWidget(page)
    assert not page.findChildren(QTableWidget)


def test_encounter_progression_page_has_pulls_layout(qtbot, tmp_path):
    from ascend.ui.encounter_progression_page import EncounterProgressionPage
    db = _make_db(tmp_path)
    page = EncounterProgressionPage(db)
    qtbot.addWidget(page)
    assert hasattr(page, "_pulls_layout")


# ---------------------------------------------------------------------------
# PullDetailDialog — no QTableWidget
# ---------------------------------------------------------------------------

def test_pull_detail_dialog_has_no_table_widget(qtbot, tmp_path):
    from PySide6.QtWidgets import QTableWidget
    from ascend.data.models import Fight, Report
    from ascend.data.repositories import ReportRepository, FightParticipant
    from ascend.ui.raid_night_page import PullDetailDialog
    db = _make_db(tmp_path)
    rr = ReportRepository(db)
    report = rr.upsert_report(Report(report_code="X1", zone_id=44))
    fight = rr.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss", kill=True))
    dialog = PullDetailDialog(db, report, fight, pull_number=1)
    qtbot.addWidget(dialog)
    assert not dialog.findChildren(QTableWidget)
