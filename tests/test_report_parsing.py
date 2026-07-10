import json
from pathlib import Path

import pytest

from ascend.api.client import WCLClient, WCLGraphQLError, WCLRateLimitError
from ascend.data.database import Database
from ascend.data.repositories import ReportRepository, SyncHistoryRepository
from ascend.services.background_worker import CancellationToken
from ascend.services.sync_service import ReportCodeNotFoundError, sync_report_by_code

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_sample_report() -> dict:
    return json.loads((FIXTURES_DIR / "sample_report.json").read_text(encoding="utf-8"))


class FakeWCLClient:
    def __init__(self, report: dict | None):
        self._report = report
        self.calls = 0

    def fetch_report_by_code(self, report_code: str):
        self.calls += 1
        return self._report


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    yield database
    database.close()


def _noop_progress(_percent, _message):
    pass


def test_sync_report_by_code_stores_report_and_fights(db):
    client = FakeWCLClient(load_sample_report())
    token = CancellationToken()

    report = sync_report_by_code(_noop_progress, token, db, client, "AbCdEfGh123456")

    assert report is not None
    assert report.title == "Sanitized Test Raid Night"
    assert report.guild_name == "Test Guild"

    fights = ReportRepository(db).fights_for_report(report.id)
    assert len(fights) == 2
    assert fights[0].kill is False
    assert fights[1].kill is True


def test_sync_report_by_code_is_idempotent(db):
    client = FakeWCLClient(load_sample_report())
    token = CancellationToken()

    sync_report_by_code(_noop_progress, token, db, client, "AbCdEfGh123456")
    sync_report_by_code(_noop_progress, token, db, client, "AbCdEfGh123456")

    reports = ReportRepository(db).list_all()
    matching = [r for r in reports if r.report_code == "AbCdEfGh123456"]
    assert len(matching) == 1
    assert matching[0].fight_count == 2


def test_sync_report_not_found_raises_and_records_history(db):
    client = FakeWCLClient(None)
    token = CancellationToken()

    with pytest.raises(ReportCodeNotFoundError):
        sync_report_by_code(_noop_progress, token, db, client, "DoesNotExist")

    history = SyncHistoryRepository(db).recent()
    assert history[0].status == "error"


def test_sync_report_cancellation_stops_and_records_history(db):
    client = FakeWCLClient(load_sample_report())
    token = CancellationToken()
    token.cancel()  # simulate cancellation requested before/at the start of ingestion

    result = sync_report_by_code(_noop_progress, token, db, client, "AbCdEfGh123456")

    assert result is None
    history = SyncHistoryRepository(db).recent()
    assert history[0].status == "cancelled"


class FakeHTTPResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload


class FakeHTTPSession:
    def __init__(self, response):
        self._response = response

    def post(self, *_args, **_kwargs):
        return self._response


class StubOAuth:
    def get_access_token(self, *_args, **_kwargs):
        return "fake-token"

    def invalidate(self):
        pass


def test_graphql_errors_array_raises_wclgraphqlerror():
    session = FakeHTTPSession(FakeHTTPResponse(200, {"errors": [{"message": "Invalid report code."}]}))
    client = WCLClient("id", "secret", session=session, oauth_client=StubOAuth())

    with pytest.raises(WCLGraphQLError):
        client.execute("query { reportData { report(code: \"x\") { code } } }")


def test_rate_limit_response_raises_wclratelimiterror():
    session = FakeHTTPSession(FakeHTTPResponse(429, {}))
    client = WCLClient("id", "secret", session=session, oauth_client=StubOAuth())

    with pytest.raises(WCLRateLimitError):
        client.execute("query { rateLimitData { limitPerHour } }")


def test_fetch_death_table_extracts_table_json_payload():
    payload = {"data": {"reportData": {"report": {"table": {"entries": [{"name": "Kysarra"}]}}}}}
    session = FakeHTTPSession(FakeHTTPResponse(200, payload))
    client = WCLClient("id", "secret", session=session, oauth_client=StubOAuth())

    result = client.fetch_death_table("ABC123", fight_ids=[1, 2])
    assert result == {"entries": [{"name": "Kysarra"}]}


def test_fetch_death_table_returns_none_when_table_missing():
    payload = {"data": {"reportData": {"report": {}}}}
    session = FakeHTTPSession(FakeHTTPResponse(200, payload))
    client = WCLClient("id", "secret", session=session, oauth_client=StubOAuth())

    assert client.fetch_death_table("ABC123") is None
