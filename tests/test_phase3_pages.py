"""Tests for Encounter Progression, Trends, and Export pages.

These are integration tests: each builds a real in-memory database with
representative data, instantiates the page widget, calls reload(), and
asserts on the observable state (table rows, label text, CSV content, HTML
content). They run headless via QT_QPA_PLATFORM=offscreen.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from ascend.data.database import Database
from ascend.data.models import Fight, FightParticipant, Report
from ascend.data.repositories import ReportRepository
from ascend.ui.encounter_progression_page import EncounterProgressionPage
from ascend.ui.export_page import ExportPage, _encounter_summary_rows, _roster_attendance_rows, export_html
from ascend.ui.trends_page import TrendsPage


# -- helpers -----------------------------------------------------------------

def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _seed_encounter(db: Database, encounter_id: int = 1, name: str = "Test Boss",
                    n_wipes: int = 5, with_kill: bool = True, n_farm: int = 0) -> None:
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code="R001", start_time=1700000000000.0))
    fight_id = 1
    for _ in range(n_wipes):
        repo.upsert_fight(Fight(
            report_id=report.id, fight_id=fight_id,
            name=name, encounter_id=encounter_id, kill=False,
            start_time=1700001000000.0, end_time=1700001120000.0,
        ))
        fight_id += 1
    if with_kill:
        repo.upsert_fight(Fight(
            report_id=report.id, fight_id=fight_id,
            name=name, encounter_id=encounter_id, kill=True,
            start_time=1700001200000.0, end_time=1700001500000.0,
        ))
        fight_id += 1
    for _ in range(n_farm):
        repo.upsert_fight(Fight(
            report_id=report.id, fight_id=fight_id,
            name=name, encounter_id=encounter_id, kill=True,
            start_time=1700002000000.0, end_time=1700002120000.0,
        ))
        fight_id += 1


def _seed_roster(db: Database) -> None:
    repo = ReportRepository(db)
    r = repo.upsert_report(Report(report_code="RROST"))
    f = repo.upsert_fight(Fight(report_id=r.id, fight_id=1, name="Boss"))
    repo.upsert_fight_participant(FightParticipant(fight_id=f.id, actor_id=1, name="Kysarra", server="Stormrage"))
    repo.upsert_fight_participant(FightParticipant(fight_id=f.id, actor_id=2, name="Mookson", server="Stormrage"))


# -- Encounter Progression ---------------------------------------------------

class TestEncounterProgressionPage:
    def test_empty_state_with_no_data(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            page = EncounterProgressionPage(db)
            # detail widget is hidden, empty state is shown
            assert not page.detail_widget.isVisible()
        finally:
            db.close()

    def test_loads_encounter_in_combo(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, name="Ulgrax")
            page = EncounterProgressionPage(db)
            assert page.encounter_combo.count() == 1
            assert page.encounter_combo.itemText(0) == "Ulgrax"
        finally:
            db.close()

    def test_first_kill_milestone_label(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, n_wipes=4, with_kill=True)
            page = EncounterProgressionPage(db)
            text = page.milestone_label.text()
            assert "First kill on pull 5" in text
        finally:
            db.close()

    def test_still_progressing_label_when_no_kill(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, n_wipes=6, with_kill=False)
            page = EncounterProgressionPage(db)
            text = page.milestone_label.text()
            assert "Still progressing" in text
        finally:
            db.close()

    def test_pull_table_has_correct_row_count(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, n_wipes=3, with_kill=True, n_farm=2)
            page = EncounterProgressionPage(db)
            # 3 wipes + 1 kill + 2 farm = 6 rows
            assert page.pull_table.rowCount() == 6
        finally:
            db.close()

    def test_pull_table_phase_column(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, n_wipes=2, with_kill=True, n_farm=1)
            page = EncounterProgressionPage(db)
            phases = [page.pull_table.item(row, 6).text() for row in range(page.pull_table.rowCount())]
            assert phases[:3] == ["Progression", "Progression", "Progression"]
            assert phases[3] == "Farm"
        finally:
            db.close()


# -- Trends ------------------------------------------------------------------

class TestTrendsPage:
    def test_empty_state_with_no_data(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            page = TrendsPage(db)
            # body has no cards when no encounters
            assert page._body.count() == 0
        finally:
            db.close()

    def test_loads_with_encounter_data(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, n_wipes=5, with_kill=True)
            page = TrendsPage(db)
            # body has 3 cards: kill-rate curves, raid night, unavail note
            assert page._body.count() == 3
        finally:
            db.close()

    def test_raid_night_kill_rates_computation(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, n_wipes=3, with_kill=True)
            page = TrendsPage(db)
            rows = page._compute_raid_night_kill_rates()
            assert len(rows) == 1
            date, title, enc_count, pulls, kills = rows[0]
            assert pulls == 4   # 3 wipes + 1 kill
            assert kills == 1
        finally:
            db.close()


# -- Export ------------------------------------------------------------------

class TestExportData:
    def test_encounter_summary_rows_empty(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            assert _encounter_summary_rows(db) == []
        finally:
            db.close()

    def test_encounter_summary_rows_with_data(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, name="Ulgrax", n_wipes=4, with_kill=True, n_farm=2)
            rows = _encounter_summary_rows(db)
            assert len(rows) == 1
            row = rows[0]
            assert row["Encounter"] == "Ulgrax"
            assert row["Total Pulls"] == 7
            assert row["Kills"] == 3   # 1 progression kill + 2 farm kills
            assert row["Wipes"] == 4
            assert row["First Kill Pull"] == "5"
            assert row["Progression Pulls"] == 5
            assert row["Farm Pulls"] == 2
        finally:
            db.close()

    def test_roster_attendance_rows_with_data(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_roster(db)
            rows = _roster_attendance_rows(db)
            names = [r["Name"] for r in rows]
            assert "Kysarra" in names
            assert "Mookson" in names
        finally:
            db.close()

    def test_html_export_contains_table_headings(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            _seed_encounter(db, name="Broodtwister Ovi'nax", n_wipes=3, with_kill=True)
            _seed_roster(db)
            html = export_html(db)
            assert "<table>" in html
            assert "Encounter Summary" in html
            assert "Roster Attendance" in html
            assert "Broodtwister Ovi'nax" in html
        finally:
            db.close()

    def test_html_export_includes_disclaimer(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            html = export_html(db)
            assert "Performance stats" in html
            assert "event-level" in html
        finally:
            db.close()


class TestExportPage:
    def test_page_instantiates(self, tmp_path):
        db = _make_db(tmp_path)
        try:
            page = ExportPage(db)
            assert page is not None
        finally:
            db.close()
