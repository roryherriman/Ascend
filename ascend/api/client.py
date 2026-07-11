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
from ascend.api.graphql_queries import (
    DEATH_TABLE_QUERY,
    GUILD_LOOKUP_QUERY,
    GUILD_REPORTS_QUERY,
    RATE_LIMIT_QUERY,
    REPORT_BY_CODE_QUERY,
    ZONE_DIFFICULTIES_QUERY,
    ZONES_QUERY,
)
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

    def fetch_zone_difficulties(self, zone_id: int) -> list[dict[str, Any]]:
        """Returns this zone's `[{id, name}]` difficulty list (e.g. Mythic,
        Heroic), used to label a Fight.difficulty int - see
        ascend/services/zone_data.py."""
        data = self.execute(ZONE_DIFFICULTIES_QUERY, {"zoneId": zone_id})
        world_data = data.get("worldData") or {}
        zone = world_data.get("zone") or {}
        return zone.get("difficulties") or []

    def fetch_zones(self) -> list[dict[str, Any]]:
        """Returns all raid zones from worldData.zones.

        Each dict has: id, name, frozen, expansion_id, expansion_name.
        Raises WCLNetworkError or WCLGraphQLError on failure.
        """
        data = self.execute(ZONES_QUERY)
        world_data = data.get("worldData") or {}
        raw_zones = world_data.get("zones") or []
        result = []
        for z in raw_zones:
            expansion = z.get("expansion") or {}
            result.append({
                "id": z.get("id"),
                "name": z.get("name", ""),
                "frozen": bool(z.get("frozen", False)),
                "expansion_id": expansion.get("id"),
                "expansion_name": expansion.get("name", ""),
            })
        return result

    def fetch_guild(
        self, name: str, server_slug: str, server_region: str
    ) -> dict[str, Any] | None:
        """Look up a guild by name, realm slug, and region.

        Returns a dict with id, name, server_name, server_slug, region_slug,
        region_name, faction_id, faction_name — or None if not found.
        """
        try:
            data = self.execute(
                GUILD_LOOKUP_QUERY,
                {"name": name, "serverSlug": server_slug, "serverRegion": server_region},
            )
        except WCLGraphQLError:
            return None
        guild_data = data.get("guildData") or {}
        guild = guild_data.get("guild")
        if not guild:
            return None
        server = guild.get("server") or {}
        region = server.get("region") or {}
        faction = guild.get("faction") or {}
        return {
            "id": guild.get("id"),
            "name": guild.get("name", ""),
            "server_name": server.get("name", ""),
            "server_slug": server.get("slug", ""),
            "region_slug": region.get("slug", ""),
            "region_name": region.get("name", ""),
            "faction_id": faction.get("id"),
            "faction_name": faction.get("name", ""),
        }

    def fetch_guild_reports(
        self, guild_id: int, page: int = 1, limit: int = 25
    ) -> dict[str, Any]:
        """Fetch one page of guild reports from reportData.reports(guildID).

        Returns the raw pagination envelope:
          {data: [{code, title, startTime, endTime, zone, owner, guild}],
           total, per_page, current_page, last_page, has_more_pages}
        Raises WCLGraphQLError / WCLNetworkError on failure.
        """
        data = self.execute(
            GUILD_REPORTS_QUERY,
            {"guildID": guild_id, "limit": limit, "page": page},
        )
        reports_data = (data.get("reportData") or {}).get("reports") or {}
        return reports_data

    def fetch_death_table(self, report_code: str, fight_ids: list[int] | None = None) -> Any:
        """Returns Report.table(dataType: Deaths) for the given fights - an
        opaque JSON payload (see graphql_queries.py docstring), not a
        schema-verified structure. Ascend caches and displays this
        best-effort rather than asserting a field contract it can't verify."""
        data = self.execute(DEATH_TABLE_QUERY, {"code": report_code, "fightIds": fight_ids})
        report = (data.get("reportData") or {}).get("report") or {}
        return report.get("table")
