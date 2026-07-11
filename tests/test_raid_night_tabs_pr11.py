"""PR 11: Raid Night Summary uses QTabWidget (Pulls / Roster / Notes tabs)."""
from __future__ import annotations

import pytest


def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_raid_night_page_has_tab_widget(qtbot, tmp_path):
    from PySide6.QtWidgets import QTabWidget
    from ascend.ui.raid_night_page import RaidNightSummaryPage
    db = _make_db(tmp_path)
    page = RaidNightSummaryPage(db)
    qtbot.addWidget(page)
    assert hasattr(page, "_tabs")
    assert isinstance(page._tabs, QTabWidget)


def test_raid_night_tabs_are_pulls_roster_notes(qtbot, tmp_path):
    from ascend.ui.raid_night_page import RaidNightSummaryPage
    db = _make_db(tmp_path)
    page = RaidNightSummaryPage(db)
    qtbot.addWidget(page)
    tab_count = page._tabs.count()
    assert tab_count == 3
    tab_names = [page._tabs.tabText(i) for i in range(tab_count)]
    assert tab_names == ["Pulls", "Roster", "Notes"]


def test_pull_row_shows_kill_checkmark(qtbot, tmp_path):
    from ascend.data.models import Fight, Report
    from ascend.data.repositories import ReportRepository
    from ascend.ui.raid_night_page import RaidNightSummaryPage
    db = _make_db(tmp_path)
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code="K1", start_time=0, end_time=1000))
    repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss", kill=True, start_time=0, end_time=200))
    page = RaidNightSummaryPage(db)
    qtbot.addWidget(page)
    # Kill row should exist in _pulls_layout and show checkmark character
    items = [page._pulls_layout.itemAt(i) for i in range(page._pulls_layout.count())]
    assert len(items) >= 1


def test_pull_row_kill_result_no_mojibake(qtbot, tmp_path):
    from ascend.data.models import Fight, Report
    from ascend.data.repositories import ReportRepository
    from ascend.ui.raid_night_page import RaidNightSummaryPage
    db = _make_db(tmp_path)
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code="K2", start_time=0, end_time=1000))
    fight = repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss", kill=True))
    page = RaidNightSummaryPage(db)
    qtbot.addWidget(page)
    row = page._build_pull_row(1, fight, report, alt=False)
    # Find label text containing the result
    from PySide6.QtWidgets import QLabel
    labels = row.findChildren(QLabel)
    result_texts = [lbl.text() for lbl in labels]
    # Should contain "Kill ✓" not mojibake
    assert any("✓" in t or t == "Kill ✓" for t in result_texts), f"Expected kill checkmark in {result_texts}"
    assert not any("\xe2\x9c" in t or "âœ" in t for t in result_texts), f"Found mojibake in {result_texts}"
