from ascend.api.client import WCLClient, WCLGraphQLError, WCLRateLimitError
from ascend.logging_setup import setup_logging

SECRET_MARKER = "super-secret-value-should-never-be-logged-xyz"


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
        return SECRET_MARKER  # simulates a real access token flowing through the client

    def invalidate(self):
        pass


def _log_file_text(log_dir) -> str:
    log_file = log_dir / "ascend.log"
    return log_file.read_text(encoding="utf-8") if log_file.exists() else ""


def test_graphql_error_is_logged_without_leaking_secret(tmp_path):
    setup_logging(tmp_path, force=True)
    session = FakeHTTPSession(FakeHTTPResponse(200, {"errors": [{"message": "Invalid report code."}]}))
    client = WCLClient(
        "client-id", SECRET_MARKER, session=session, oauth_client=StubOAuth()
    )

    try:
        client.execute("query { reportData { report(code: \"x\") { code } } }")
    except WCLGraphQLError:
        pass

    text = _log_file_text(tmp_path)
    assert "GraphQL error" in text
    assert SECRET_MARKER not in text


def test_rate_limit_is_logged_without_leaking_secret(tmp_path):
    setup_logging(tmp_path, force=True)
    session = FakeHTTPSession(FakeHTTPResponse(429, {}))
    client = WCLClient(
        "client-id", SECRET_MARKER, session=session, oauth_client=StubOAuth()
    )

    try:
        client.execute("query { rateLimitData { limitPerHour } }")
    except WCLRateLimitError:
        pass

    text = _log_file_text(tmp_path)
    assert "rate limit" in text.lower()
    assert SECRET_MARKER not in text
