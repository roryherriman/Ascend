"""GraphQL client for the Warcraft Logs API v2 client-credentials endpoint.

Endpoint verified against the official docs: the client-credentials-protected
GraphQL endpoint is https://www.warcraftlogs.com/api/v2/client (as opposed to
/api/v2/user, which is for user-authenticated access and is not used here).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ascend.api.auth import OAuthClient, WCLAuthError, WCLNetworkError
from ascend.api.graphql_queries import RATE_LIMIT_QUERY, REPORT_BY_CODE_QUERY
from ascend.logging_setup import get_logger

GRAPHQL_URL = "https://www.warcraftlogs.com/api/v2/client"


class WCLGraphQLError(Exception):
    """Raised when the GraphQL response contains a non-empty `errors` array."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages) or "Unknown GraphQL error")


class WCLRateLimitError(Exception):
    """Raised when Warcraft Logs reports the request was rate-limited (HTTP 429)."""


@dataclass
class ConnectionTestResult:
    ok: bool
    message: str
    limit_per_hour: int | None = None
    points_spent_this_hour: float | None = None


class WCLClient:
    """Thin GraphQL client. Never logs or exposes the access token."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        graphql_url: str = GRAPHQL_URL,
        timeout_seconds: float = 15.0,
        session: requests.Session | None = None,
        oauth_client: OAuthClient | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.graphql_url = graphql_url
        self.timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._oauth = oauth_client or OAuthClient(
            timeout_seconds=timeout_seconds, session=self._session
        )

    def execute(
        self, query: str, variables: dict[str, Any] | None = None, _retry: bool = True
    ) -> dict[str, Any]:
        token = self._oauth.get_access_token(self.client_id, self.client_secret)
        try:
            response = self._session.post(
                self.graphql_url,
                json={"query": query, "variables": variables or {}},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.RequestException as exc:
            raise WCLNetworkError(f"Could not reach Warcraft Logs: {exc}") from exc

        if response.status_code == 401 and _retry:
            # The cached token may have expired early or been revoked - refresh once and retry.
            self._oauth.invalidate()
            return self.execute(query, variables, _retry=False)

        if response.status_code == 429:
            get_logger().warning("Warcraft Logs API rate limit reached (HTTP 429).")
            raise WCLRateLimitError(
                "Warcraft Logs API rate limit reached. Please wait before retrying."
            )
        if response.status_code >= 500:
            get_logger().warning("Warcraft Logs server error (HTTP %s).", response.status_code)
            raise WCLNetworkError(f"Warcraft Logs server error (HTTP {response.status_code}).")
        if not response.ok:
            get_logger().warning("Unexpected HTTP %s from Warcraft Logs.", response.status_code)
            raise WCLNetworkError(f"Unexpected HTTP {response.status_code} from Warcraft Logs.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise WCLNetworkError("Warcraft Logs returned a non-JSON response.") from exc

        if payload.get("errors"):
            messages = [err.get("message", str(err)) for err in payload["errors"]]
            get_logger().warning("Warcraft Logs GraphQL error: %s", "; ".join(messages))
            raise WCLGraphQLError(messages)

        return payload.get("data") or {}

    def test_connection(self) -> ConnectionTestResult:
        try:
            data = self.execute(RATE_LIMIT_QUERY)
        except (WCLAuthError, WCLNetworkError, WCLGraphQLError, WCLRateLimitError) as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

        rate = data.get("rateLimitData") or {}
        return ConnectionTestResult(
            ok=True,
            message="Connected to the Warcraft Logs API successfully.",
            limit_per_hour=rate.get("limitPerHour"),
            points_spent_this_hour=rate.get("pointsSpentThisHour"),
        )

    def fetch_report_by_code(self, report_code: str) -> dict[str, Any] | None:
        data = self.execute(REPORT_BY_CODE_QUERY, {"code": report_code})
        report_data = data.get("reportData") or {}
        return report_data.get("report")
