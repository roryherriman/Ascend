import requests

from ascend.api.auth import OAuthClient, WCLAuthError, WCLNetworkError


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses=None, raise_exc=None):
        self.responses = list(responses or [])
        self.raise_exc = raise_exc
        self.calls = 0

    def post(self, *_args, **_kwargs):
        self.calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.responses.pop(0)


def test_successful_token_fetch_and_caching():
    session = FakeSession(responses=[FakeResponse(200, {"access_token": "tok-1", "expires_in": 3600})])
    client = OAuthClient(session=session)

    token1 = client.get_access_token("id", "secret")
    token2 = client.get_access_token("id", "secret")

    assert token1 == "tok-1"
    assert token2 == "tok-1"
    assert session.calls == 1  # cached, no second network call


def test_invalid_credentials_raises_auth_error():
    session = FakeSession(responses=[FakeResponse(401, {"error": "invalid_client"})])
    client = OAuthClient(session=session)

    try:
        client.get_access_token("bad-id", "bad-secret")
        assert False, "expected WCLAuthError"
    except WCLAuthError:
        pass


def test_network_failure_raises_network_error():
    session = FakeSession(raise_exc=requests.exceptions.ConnectionError("boom"))
    client = OAuthClient(session=session)

    try:
        client.get_access_token("id", "secret")
        assert False, "expected WCLNetworkError"
    except WCLNetworkError:
        pass


def test_missing_credentials_raise_without_network_call():
    session = FakeSession(responses=[])
    client = OAuthClient(session=session)

    try:
        client.get_access_token("", "")
        assert False, "expected WCLAuthError"
    except WCLAuthError:
        pass

    assert session.calls == 0


def test_invalidate_forces_refresh():
    session = FakeSession(
        responses=[
            FakeResponse(200, {"access_token": "tok-1", "expires_in": 3600}),
            FakeResponse(200, {"access_token": "tok-2", "expires_in": 3600}),
        ]
    )
    client = OAuthClient(session=session)

    token1 = client.get_access_token("id", "secret")
    client.invalidate()
    token2 = client.get_access_token("id", "secret")

    assert token1 == "tok-1"
    assert token2 == "tok-2"
    assert session.calls == 2


def test_server_error_raises_network_error():
    session = FakeSession(responses=[FakeResponse(503, {})])
    client = OAuthClient(session=session)

    try:
        client.get_access_token("id", "secret")
        assert False, "expected WCLNetworkError"
    except WCLNetworkError:
        pass
