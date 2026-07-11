"""PR 6 tests: Report Library card-based redesign."""
from __future__ import annotations

import pytest


def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _seed_report(db, code="abc123", title="Test Report", zone_name="Nerub-ar Palace", guild="Test Guild"):
    from ascend.data.models import Report
    from ascend.data.repositories import ReportRepository
    r = Report(
        report_code=code,
        title=title,
        zone_name=zone_name,
        guild_name=guild,
        start_time=1700000000000,
        end_time=1700003600000,
    )
    return ReportRepository(db).upsert_report(r)


def _make_page(tmp_path, qtbot):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.reports_page import ReportsPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    page = ReportsPage(db, storage, mgr)
    qtbot.addWidget(page)
    return page, db


# ---------------------------------------------------------------------------
# Page structure
# ---------------------------------------------------------------------------

def test_reports_page_has_no_table_widget(qtbot, tmp_path):
    from PySide6.QtWidgets import QTableWidget
    page, _ = _make_page(tmp_path, qtbot)
    assert not page.findChildren(QTableWidget), "QTableWidget must be removed in PR 6"


def test_reports_page_has_scroll_area(qtbot, tmp_path):
    from PySide6.QtWidgets import QScrollArea
    page, _ = _make_page(tmp_path, qtbot)
    assert page.findChildren(QScrollArea)


def test_reports_page_has_zone_filter(qtbot, tmp_path):
    page, _ = _make_page(tmp_path, qtbot)
    assert hasattr(page, "zone_filter")


def test_reports_page_has_search_edit(qtbot, tmp_path):
    page, _ = _make_page(tmp_path, qtbot)
    assert hasattr(page, "search_edit")


def test_reports_page_title_is_report_library(qtbot, tmp_path):
    from PySide6.QtWidgets import QLabel
    page, _ = _make_page(tmp_path, qtbot)
    labels = page.findChildren(QLabel)
    titles = [l for l in labels if l.objectName() == "pageTitle"]
    assert titles and "Library" in titles[0].text()


# ---------------------------------------------------------------------------
# Cards render
# ---------------------------------------------------------------------------

def test_empty_state_shown_when_no_reports(qtbot, tmp_path):
    from ascend.ui.reports_page import _ReportCard
    page, _ = _make_page(tmp_path, qtbot)
    cards = page.findChildren(_ReportCard)
    assert len(cards) == 0


def test_card_shown_for_each_report(qtbot, tmp_path):
    from ascend.ui.reports_page import _ReportCard
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "aaa", "Report A")
    _seed_report(db, "bbb", "Report B")
    page.reload()
    cards = page.findChildren(_ReportCard)
    assert len(cards) == 2


def test_card_shows_report_title(qtbot, tmp_path):
    from PySide6.QtWidgets import QLabel
    from ascend.ui.reports_page import _ReportCard
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "xyz", "My Awesome Report")
    page.reload()
    cards = page.findChildren(_ReportCard)
    assert cards
    all_text = " ".join(lbl.text() for lbl in cards[0].findChildren(QLabel))
    assert "My Awesome Report" in all_text


def test_card_shows_zone_name(qtbot, tmp_path):
    from PySide6.QtWidgets import QLabel
    from ascend.ui.reports_page import _ReportCard
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "zzz", "A Report", zone_name="Liberation of Undermine")
    page.reload()
    cards = page.findChildren(_ReportCard)
    all_text = " ".join(lbl.text() for lbl in cards[0].findChildren(QLabel))
    assert "Liberation of Undermine" in all_text


def test_card_has_view_delete_and_open_buttons(qtbot, tmp_path):
    from ascend.ui.reports_page import _ReportCard
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "xyz2", "Report")
    page.reload()
    cards = page.findChildren(_ReportCard)
    assert cards
    btns = {b.text() for b in cards[0].findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)}
    assert "View Raid Night" in btns
    assert "Delete" in btns
    assert "Open WCL" in btns


# ---------------------------------------------------------------------------
# Search filter
# ---------------------------------------------------------------------------

def test_search_filters_cards_by_title(qtbot, tmp_path):
    from ascend.ui.reports_page import _ReportCard
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "a1", "Alpha Report", zone_name="Zone A")
    _seed_report(db, "b2", "Beta Report", zone_name="Zone B")
    page.reload()
    page.search_edit.setText("alpha")
    cards = page.findChildren(_ReportCard)
    assert len(cards) == 1
    assert cards[0].report.report_code == "a1"


def test_search_filters_cards_by_code(qtbot, tmp_path):
    from ascend.ui.reports_page import _ReportCard
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "unique99", "Some Report")
    _seed_report(db, "other11", "Other Report")
    page.reload()
    page.search_edit.setText("unique")
    cards = page.findChildren(_ReportCard)
    assert len(cards) == 1


def test_search_shows_no_match_empty_state(qtbot, tmp_path):
    from ascend.ui.reports_page import _ReportCard
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "r1", "Report One")
    page.reload()
    page.search_edit.setText("zzznomatch")
    cards = page.findChildren(_ReportCard)
    assert len(cards) == 0


# ---------------------------------------------------------------------------
# Zone filter
# ---------------------------------------------------------------------------

def test_zone_filter_populated_from_reports(qtbot, tmp_path):
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "z1", "Report A", zone_name="Nerub-ar Palace")
    _seed_report(db, "z2", "Report B", zone_name="Liberation of Undermine")
    page.reload()
    zones = [page.zone_filter.itemText(i) for i in range(page.zone_filter.count())]
    assert "Nerub-ar Palace" in zones
    assert "Liberation of Undermine" in zones
    assert "All Zones" in zones


def test_zone_filter_narrows_cards(qtbot, tmp_path):
    from ascend.ui.reports_page import _ReportCard
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "n1", "Nerub Report", zone_name="Nerub-ar Palace")
    _seed_report(db, "l1", "LOU Report", zone_name="Liberation of Undermine")
    page.reload()
    page.zone_filter.setCurrentText("Nerub-ar Palace")
    cards = page.findChildren(_ReportCard)
    assert len(cards) == 1
    assert cards[0].report.report_code == "n1"


# ---------------------------------------------------------------------------
# Discover button state
# ---------------------------------------------------------------------------

def test_discover_button_disabled_without_guild(qtbot, tmp_path):
    page, _ = _make_page(tmp_path, qtbot)
    assert not page.discover_button.isEnabled()


def test_discover_button_enabled_with_guild(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    page, db = _make_page(tmp_path, qtbot)
    SettingsRepository(db).set("guild_wcl_id", 99)
    page.reload()
    assert page.discover_button.isEnabled()


# ---------------------------------------------------------------------------
# Delete action
# ---------------------------------------------------------------------------

def test_delete_removes_card(qtbot, tmp_path, monkeypatch):
    from ascend.ui.reports_page import _ReportCard
    from ascend.ui import reports_page
    # Monkeypatch confirm to always return True
    monkeypatch.setattr(reports_page, "confirm", lambda *a, **kw: True)
    page, db = _make_page(tmp_path, qtbot)
    _seed_report(db, "del1", "To Delete")
    page.reload()
    assert len(page.findChildren(_ReportCard)) == 1
    # Call delete directly
    page._on_delete(page._reports[0])
    assert len(page.findChildren(_ReportCard)) == 0
