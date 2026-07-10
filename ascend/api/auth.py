"""Warcraft Logs OAuth2 client-credentials flow.

Token endpoint, grant type, and basic-auth exchange verified against the
official Warcraft Logs API v2 documentation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS = 60


class WCLAuthError(Exception):
    """Raised when the OAuth client-credentials exchange fails (bad credentials, etc.)."""


class WCLNetworkError(Exception):
    """Raised when a network-level failure prevents talking to Warcraft Logs."""


@dataclass
class _CachedToken:
    access_token: str
    expires_at: float  # time.time()-based


class OAuthClient:
    """Fetches and caches an OAuth access token via the client-credentials grant.

    The access token is kept only in memory for the lifetime of this object
    and is never logged, displayed, or persisted to disk.
    """

    def __init__(
        self,
        token_url: str = TOKEN_URL,
        timeout_seconds: float = 15.0,
        session: requests.Session | None = None,
    ):
        self.token_url = token_url
        self.timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._cached: _CachedToken | None = None

    def get_access_token(self, client_id: str, client_secret: str, force_refresh: bool = False) -> str:
        if not client_id or not client_secret:
            raise WCLAuthError("Warcraft Logs client ID and client secret must both be set.")

        if not force_refresh and self._cached is not None and time.time() < self._cached.expires_at:
            return self._cached.access_token

        try:
            response = self._session.post(
                self.token_url,
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.RequestException as exc:
            raise WCLNetworkError(f"Could not reach Warcraft Logs: {exc}") from exc

        if response.status_code in (400, 401, 403):
            raise WCLAuthError(
                "Warcraft Logs rejected the client ID / client secret. "
                "Double-check your API client credentials in Settings."
            )
        if response.status_code >= 500:
            raise WCLNetworkError(f"Warcraft Logs server error (HTTP {response.status_code}).")
        if not response.ok:
            raise WCLAuthError(
                f"Unexpected response from Warcraft Logs during authentication "
                f"(HTTP {response.status_code})."
            )

        try:
            payload = response.json()
            access_token = payload["access_token"]
            expires_in = float(payload.get("expires_in", 3600))
        except (ValueError, KeyError) as exc:
            raise WCLAuthError("Warcraft Logs returned an unexpected authentication response.") from exc

        self._cached = _CachedToken(
            access_token=access_token,
            expires_at=time.time() + max(expires_in - TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS, 30),
        )
        return access_token

    def invalidate(self) -> None:
        """Drop the cached token, forcing a fresh exchange on the next request."""
        self._cached = None
