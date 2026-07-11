"""PR 7 tests: Dashboard redesign — no QTableWidget, relative demo dates, row-based recent panel."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest


def _noop_signal():
    """Return a mock that quacks like a Qt Signal (has .emit)."""
    sig = MagicMock()
    return sig


def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _seed_report(db, code="abc", title="Night 1"):
    from ascend.data.models import Report
    from ascend.data.repositories import ReportRepository
    r = Report(report_code=code, title=title, start_time=1700000000000, end_time=1700003600000)
    return ReportRepository(db).upsert_report(r)


# ---------------------------------------------------------------------------
# ActiveAnalyticsState — no QTableWidget
# ---------------------------------------------------------------------------

def test_active_state_has_no_table_widget(qtbot, tmp_path):
    from PySide6.QtWidgets import QTableWidget
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    state = ActiveAnalyticsState(db, storage, mgr, _noop_signal())
    qtbot.addWidget(state)
    assert not state.findChildren(QTableWidget), "QTableWidget must be removed in PR 7"


def test_active_state_has_raid_nights_layout(qtbot, tmp_path):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    state = ActiveAnalyticsState(db, storage, mgr, _noop_signal())
    qtbot.addWidget(state)
    assert hasattr(state, "_raid_nights_layout")


# ---------------------------------------------------------------------------
# _build_raid_night_row
# ---------------------------------------------------------------------------

def test_raid_night_row_shows_date_boss_pulls(qtbot):
    from PySide6.QtWidgets import QLabel
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    row = ActiveAnalyticsState._build_raid_night_row(
        date="Jul 11", boss="Dimensius", pulls="27", character="Aeloria"
    )
    qtbot.addWidget(row)
    all_text = " ".join(lbl.text() for lbl in row.findChildren(QLabel))
    assert "Jul 11" in all_text
    assert "Dimensius" in all_text
    assert "27" in all_text
    assert "Aeloria" in all_text


def test_raid_night_row_score_hidden_when_dashes(qtbot):
    from PySide6.QtWidgets import QLabel
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    row = ActiveAnalyticsState._build_raid_night_row(
        date="Jul 11", boss="Boss", pulls="5", character="Char",
        score="--", classification="--"
    )
    qtbot.addWidget(row)
    labels = [lbl.text() for lbl in row.findChildren(QLabel)]
    # When score is "--" it should not appear as a styled score label
    assert "--" not in labels or labels.count("--") == 0


def test_raid_night_row_shows_score_and_classification_when_set(qtbot):
    from PySide6.QtWidgets import QLabel
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    row = ActiveAnalyticsState._build_raid_night_row(
        date="Jul 11", boss="Boss", pulls="31", character="Char",
        score="84", classification="STRONG"
    )
    qtbot.addWidget(row)
    all_text = " ".join(lbl.text() for lbl in row.findChildren(QLabel))
    assert "84" in all_text
    assert "STRONG" in all_text


# ---------------------------------------------------------------------------
# _refresh_recent_raid_nights populates rows from DB
# ---------------------------------------------------------------------------

def test_refresh_recent_raid_nights_shows_empty_label_when_no_reports(qtbot, tmp_path):
    from PySide6.QtWidgets import QLabel
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    state = ActiveAnalyticsState(db, storage, BackgroundTaskManager(), _noop_signal())
    qtbot.addWidget(state)
    # No reports → empty label in _raid_nights_layout
    items = [state._raid_nights_layout.itemAt(i) for i in range(state._raid_nights_layout.count())]
    widgets = [i.widget() for i in items if i and i.widget()]
    assert widgets  # at least the "No raid nights yet." label
    texts = [w.text() for w in widgets if hasattr(w, "text")]
    assert any("No raid nights" in t for t in texts)


def test_refresh_recent_raid_nights_shows_row_per_report(qtbot, tmp_path):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    db = _make_db(tmp_path)
    _seed_report(db, "a1", "Night 1")
    _seed_report(db, "a2", "Night 2")
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    state = ActiveAnalyticsState(db, storage, BackgroundTaskManager(), _noop_signal())
    qtbot.addWidget(state)
    # Rows are QFrame children of _raid_nights_layout
    items = [state._raid_nights_layout.itemAt(i) for i in range(state._raid_nights_layout.count())]
    row_widgets = [i.widget() for i in items if i and i.widget()]
    # Should have 2 rows (one per report)
    assert len(row_widgets) == 2


# ---------------------------------------------------------------------------
# Demo data uses relative dates (no hard-coded month/year)
# ---------------------------------------------------------------------------

def test_demo_data_dates_are_relative_to_today(qtbot, tmp_path):
    from PySide6.QtWidgets import QLabel
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    state = ActiveAnalyticsState(db, storage, BackgroundTaskManager(), _noop_signal())
    qtbot.addWidget(state)
    state.apply_demo_data()

    # The first demo row should be today's date formatted as "Mon DD"
    from datetime import timedelta
    today_str = datetime.now(timezone.utc).date().strftime("%b %d")
    items = [state._raid_nights_layout.itemAt(i) for i in range(state._raid_nights_layout.count())]
    row_widgets = [i.widget() for i in items if i and i.widget()]
    assert row_widgets, "Expected demo raid night rows"
    first_row_text = " ".join(
        lbl.text() for lbl in row_widgets[0].findChildren(QLabel)
    )
    assert today_str in first_row_text, f"Expected today ({today_str}) in first demo row: {first_row_text}"


def test_demo_data_never_has_future_date(qtbot, tmp_path):
    from PySide6.QtWidgets import QLabel
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.dashboard_states import ActiveAnalyticsState
    from datetime import date, timedelta
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    state = ActiveAnalyticsState(db, storage, BackgroundTaskManager(), _noop_signal())
    qtbot.addWidget(state)
    state.apply_demo_data()

    today = datetime.now(timezone.utc).date()
    items = [state._raid_nights_layout.itemAt(i) for i in range(state._raid_nights_layout.count())]
    row_widgets = [i.widget() for i in items if i and i.widget()]
    for row_w in row_widgets:
        labels = [lbl.text() for lbl in row_w.findChildren(QLabel)]
        for text in labels:
            # Try to parse as a date — if it looks like "Jul 11", check not future
            try:
                parsed = datetime.strptime(f"{text} {today.year}", "%b %d %Y").date()
                assert parsed <= today, f"Demo date {text} is in the future"
            except ValueError:
                pass  # Not a date label


# ---------------------------------------------------------------------------
# Dashboard page state machine still works
# ---------------------------------------------------------------------------

def test_dashboard_page_renders_no_data_state(qtbot, tmp_path):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.dashboard_page import DashboardPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    page = DashboardPage(db, storage, mgr)
    qtbot.addWidget(page)
    assert page is not None
