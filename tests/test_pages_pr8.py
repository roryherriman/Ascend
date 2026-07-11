"""PR 8 tests: Raid Night, Encounter Analysis, Encounter Progression pages
no longer use QTableWidget."""
from __future__ import annotations

import pytest


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
