"""PR 5 tests: guild report discovery, incremental sync, new-report notification."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest


def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _make_cancel():
    from ascend.services.background_worker import CancellationToken
    return CancellationToken()


def _noop(p, m):
    pass


# ---------------------------------------------------------------------------
# GraphQL query — GUILD_REPORTS_QUERY exists and is well-formed
# ---------------------------------------------------------------------------

def test_guild_reports_query_exists():
    from ascend.api.graphql_queries import GUILD_REPORTS_QUERY
    assert "guildID" in GUILD_REPORTS_QUERY
    assert "reportData" in GUILD_REPORTS_QUERY
    assert "has_more_pages" in GUILD_REPORTS_QUERY


# ---------------------------------------------------------------------------
# WCLClient.fetch_guild_reports
# ---------------------------------------------------------------------------

def test_fetch_guild_reports_calls_correct_query():
    from ascend.api.client import WCLClient
    client = WCLClient.__new__(WCLClient)
    raw_envelope = {
        "data": [{"code": "abc123", "title": "Test Report", "startTime": 0, "endTime": 0}],
        "total": 1,
        "per_page": 25,
        "current_page": 1,
        "last_page": 1,
        "has_more_pages": False,
    }
    with patch.object(client, "execute", return_value={"reportData": {"reports": raw_envelope}}) as mock_exec:
        result = client.fetch_guild_reports(guild_id=99, page=1, limit=25)
    mock_exec.assert_called_once()
    args = mock_exec.call_args
    assert args[0][1]["guildID"] == 99
    assert args[0][1]["page"] == 1
    assert result == raw_envelope


def test_fetch_guild_reports_returns_empty_on_missing_data():
    from ascend.api.client import WCLClient
    client = WCLClient.__new__(WCLClient)
    with patch.object(client, "execute", return_value={}):
        result = client.fetch_guild_reports(guild_id=1)
    assert result == {}


# ---------------------------------------------------------------------------
# sync_new_guild_reports — unit tests with mocked network
# ---------------------------------------------------------------------------

def _fake_guild_reports_envelope(codes, has_more=False):
    return {
        "data": [{"code": c, "title": f"Report {c}", "startTime": 0, "endTime": 0} for c in codes],
        "total": len(codes),
        "per_page": 25,
        "current_page": 1,
        "last_page": 1,
        "has_more_pages": has_more,
    }


def test_sync_new_guild_reports_returns_empty_when_all_known(tmp_path):
    from ascend.services.sync_service import sync_new_guild_reports
    db = _make_db(tmp_path)
    client = MagicMock()
    client.fetch_guild_reports.return_value = _fake_guild_reports_envelope(["aaa", "bbb"])

    # Pre-populate both reports so they're already "known"
    from ascend.data.models import Report
    from ascend.data.repositories import ReportRepository
    repo = ReportRepository(db)
    repo.upsert_report(Report(report_code="aaa", title="A", start_time=0, end_time=0))
    repo.upsert_report(Report(report_code="bbb", title="B", start_time=0, end_time=0))

    result = sync_new_guild_reports(_noop, _make_cancel(), db, client, guild_id=1)
    assert result == []
    # Should have stopped after one page (all known)
    client.fetch_guild_reports.assert_called_once()


def test_sync_new_guild_reports_syncs_new_codes(tmp_path):
    from ascend.services.sync_service import sync_new_guild_reports
    from ascend.data.models import Report
    db = _make_db(tmp_path)
    client = MagicMock()
    client.fetch_guild_reports.return_value = _fake_guild_reports_envelope(["new1", "new2"])

    synced = []
    def fake_sync_report_by_code(progress_cb, cancel_token, db_, client_, code):
        r = Report(report_code=code, title=f"Title {code}", start_time=0, end_time=0)
        from ascend.data.repositories import ReportRepository
        return ReportRepository(db_).upsert_report(r)

    with patch("ascend.services.sync_service.sync_report_by_code", side_effect=fake_sync_report_by_code):
        result = sync_new_guild_reports(_noop, _make_cancel(), db, client, guild_id=5)

    assert len(result) == 2
    assert {r.report_code for r in result} == {"new1", "new2"}


def test_sync_new_guild_reports_stops_paging_when_sentinel_found(tmp_path):
    from ascend.services.sync_service import sync_new_guild_reports
    from ascend.data.models import Report
    from ascend.data.repositories import ReportRepository
    db = _make_db(tmp_path)

    # Page 1 has one new + one known; has_more_pages=True
    # Because there are no new codes found on the page, paging should stop after page 1
    existing = Report(report_code="old1", title="Old", start_time=0, end_time=0)
    ReportRepository(db).upsert_report(existing)

    page1 = _fake_guild_reports_envelope(["new1", "old1"], has_more=True)
    page2 = _fake_guild_reports_envelope(["old2", "old3"], has_more=False)
    client = MagicMock()
    client.fetch_guild_reports.side_effect = [page1, page2]

    # Pre-populate old2, old3 too so page 2 would trigger the sentinel
    ReportRepository(db).upsert_report(Report(report_code="old2", title="Old2", start_time=0, end_time=0))
    ReportRepository(db).upsert_report(Report(report_code="old3", title="Old3", start_time=0, end_time=0))

    def fake_sync(progress_cb, cancel_token, db_, client_, code):
        r = Report(report_code=code, title=code, start_time=0, end_time=0)
        return ReportRepository(db_).upsert_report(r)

    with patch("ascend.services.sync_service.sync_report_by_code", side_effect=fake_sync):
        result = sync_new_guild_reports(_noop, _make_cancel(), db, client, guild_id=7)

    # new1 is discovered on page1; page2 never fetched because page1 had new codes → continues
    # Actually: new_on_page = ["new1"] (non-empty), has_more = True → continues to page 2
    # page2: no new codes → stops
    assert client.fetch_guild_reports.call_count == 2
    assert len(result) == 1
    assert result[0].report_code == "new1"


def test_sync_new_guild_reports_cancellation_respected(tmp_path):
    from ascend.services.sync_service import sync_new_guild_reports
    from ascend.services.background_worker import CancellationToken
    db = _make_db(tmp_path)
    client = MagicMock()
    client.fetch_guild_reports.return_value = _fake_guild_reports_envelope(["x1", "x2"])
    token = CancellationToken()
    token.cancel()  # pre-cancel

    result = sync_new_guild_reports(_noop, token, db, client, guild_id=1)
    assert result == []
    client.fetch_guild_reports.assert_not_called()


def test_sync_new_guild_reports_skips_failed_individual_reports(tmp_path):
    from ascend.services.sync_service import sync_new_guild_reports, ReportCodeNotFoundError
    from ascend.data.models import Report
    from ascend.data.repositories import ReportRepository
    db = _make_db(tmp_path)
    client = MagicMock()
    client.fetch_guild_reports.return_value = _fake_guild_reports_envelope(["good", "bad"])

    def fake_sync(progress_cb, cancel_token, db_, client_, code):
        if code == "bad":
            raise ReportCodeNotFoundError("Not found")
        r = Report(report_code=code, title=code, start_time=0, end_time=0)
        return ReportRepository(db_).upsert_report(r)

    with patch("ascend.services.sync_service.sync_report_by_code", side_effect=fake_sync):
        result = sync_new_guild_reports(_noop, _make_cancel(), db, client, guild_id=1)

    assert len(result) == 1
    assert result[0].report_code == "good"


# ---------------------------------------------------------------------------
# ReportsPage UI — discover button wired
# ---------------------------------------------------------------------------

def test_reports_page_has_discover_button(qtbot, tmp_path):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.reports_page import ReportsPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    page = ReportsPage(db, storage, mgr)
    qtbot.addWidget(page)
    assert hasattr(page, "discover_button")


def test_reports_page_discover_button_disabled_without_guild(qtbot, tmp_path):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.reports_page import ReportsPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    page = ReportsPage(db, storage, mgr)
    qtbot.addWidget(page)
    # No guild_wcl_id set → button should be disabled
    assert not page.discover_button.isEnabled()


def test_reports_page_discover_button_enabled_with_guild(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.reports_page import ReportsPage
    db = _make_db(tmp_path)
    SettingsRepository(db).set("guild_wcl_id", 12345)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    page = ReportsPage(db, storage, mgr)
    qtbot.addWidget(page)
    assert page.discover_button.isEnabled()
