"""Sanitized API fixture export/import for developer testing.

Produces a JSON file from raw Warcraft Logs API responses that can be
committed to the repository and used in unit tests without real credentials.
The sanitizer:

  - removes access tokens, client IDs/secrets, and webhook URLs
  - replaces player display names with generated placeholders (Player1, etc.)
  - replaces guild and report names with placeholders
  - hashes report codes consistently (same code -> same hash every export)
  - shifts all timestamps by a fixed random offset (to prevent epoch-matching)
  - preserves structural field names, ability IDs, spell IDs, fight IDs,
    actor IDs, and event types verbatim - these are needed to build and
    test a real parser

The output is clearly labelled with a header indicating it's sanitized and
not a real API payload. This is a developer-only tool; it appears in the
Diagnostics page under a "Developer Tools" section.

Fixture format
--------------
The JSON envelope is::

    {
        "ascend_fixture": true,
        "sanitized": true,
        "warning": "...",
        "schema_version": 1,
        "source_endpoint": "<graphql field path>",
        "exported_at": "<ISO-8601 UTC>",
        "timestamp_shift_ms": <int>,
        "payload": { ... }
    }

The ``payload`` key contains the raw API response tree with the above
substitutions applied. Field names are never renamed; only values are
replaced.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import string
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

FIXTURE_SCHEMA_VERSION = 1

# Patterns that might expose credentials in string values.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(access.?token|auth.?token|bearer)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(client.?id|client.?secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(webhook.?url|webhook)\s*[:=]\s*https?://\S+"),
]

# Max nesting depth to traverse (safety guard against enormous responses).
_MAX_DEPTH = 20


def _hash_code(code: str, salt: str) -> str:
    """Deterministic 8-char hash for a report code, stable within one export."""
    digest = hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()
    return "FIXTURE" + digest[:8].upper()


class _SanitizerState:
    """Accumulates per-export mutable state: name mappings and counters."""

    def __init__(self, salt: str, timestamp_shift_ms: int) -> None:
        self.salt = salt
        self.timestamp_shift_ms = timestamp_shift_ms
        self._name_map: dict[str, str] = {}
        self._counter = 0

    def replace_name(self, name: str) -> str:
        if name not in self._name_map:
            self._counter += 1
            self._name_map[name] = f"Player{self._counter}"
        return self._name_map[name]

    def mapping(self) -> dict[str, str]:
        return dict(self._name_map)


# Keys whose string values are player names, guild names, or report codes.
_NAME_KEYS = frozenset({
    "name", "displayName", "playerName", "characterName", "guildName",
    "reportTitle", "title",
})
_CODE_KEYS = frozenset({"code", "reportCode", "report_code"})
_TIMESTAMP_KEYS = frozenset({"startTime", "endTime", "timestamp", "start_time", "end_time"})
_CREDENTIAL_KEYS = frozenset({
    "accessToken", "access_token", "clientId", "client_id",
    "clientSecret", "client_secret", "webhookUrl", "webhook_url",
    "authorization", "Authorization",
})


def _sanitize_value(key: str, value: Any, state: _SanitizerState, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        return "<truncated>"
    if key in _CREDENTIAL_KEYS:
        return "<redacted>"
    if isinstance(value, str):
        if key in _NAME_KEYS:
            return state.replace_name(value)
        if key in _CODE_KEYS:
            return _hash_code(value, state.salt)
        # Scrub inline credential patterns in arbitrary string values
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                return "<redacted>"
        return value
    if isinstance(value, (int, float)):
        if key in _TIMESTAMP_KEYS:
            return value + state.timestamp_shift_ms
        return value
    if isinstance(value, dict):
        return _sanitize_dict(value, state, depth + 1)
    if isinstance(value, list):
        return [_sanitize_value(key, item, state, depth + 1) for item in value]
    return value


def _sanitize_dict(obj: dict, state: _SanitizerState, depth: int) -> dict:
    return {k: _sanitize_value(k, v, state, depth) for k, v in obj.items()}


def sanitize_fixture(
    payload: dict[str, Any],
    *,
    source_endpoint: str = "unknown",
) -> dict[str, Any]:
    """Return a sanitized fixture envelope ready for JSON serialisation.

    ``payload`` is the raw GraphQL response dict (or any sub-tree of it).
    ``source_endpoint`` is a human-readable label like
    ``"reportData.report.events"`` so a reader knows what they're looking at.
    """
    salt = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
    # Shift by a random number of days (1-365) worth of milliseconds so
    # pull timestamps can't be correlated back to a real raid night by epoch.
    shift_ms = random.randint(1, 365) * 24 * 3600 * 1000 * random.choice([-1, 1])

    state = _SanitizerState(salt, shift_ms)
    sanitized_payload = _sanitize_dict(deepcopy(payload), state, depth=0)

    return {
        "ascend_fixture": True,
        "sanitized": True,
        "warning": (
            "SANITIZED DEVELOPER FIXTURE — not a real API response. "
            "Player names, guild names, and report codes have been replaced. "
            "Timestamps have been shifted by an undisclosed offset. "
            "Credential fields have been redacted. "
            "Structural field names, ability IDs, event types, fight IDs, "
            "and actor IDs are preserved verbatim for parsing development."
        ),
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "source_endpoint": source_endpoint,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "timestamp_shift_ms": shift_ms,
        "payload": sanitized_payload,
    }


def export_fixture_json(
    payload: dict[str, Any],
    *,
    source_endpoint: str = "unknown",
    indent: int = 2,
) -> str:
    """Serialise a sanitized fixture to a JSON string."""
    return json.dumps(sanitize_fixture(payload, source_endpoint=source_endpoint), indent=indent)


def load_fixture(path: str) -> dict[str, Any]:
    """Load a fixture JSON file produced by :func:`export_fixture_json`.

    Raises ``ValueError`` if the file is not a recognised Ascend fixture.
    Returns the ``payload`` dict (the sanitized API response tree).
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not data.get("ascend_fixture") or not data.get("sanitized"):
        raise ValueError(
            f"{path!r} is not an Ascend sanitized fixture "
            "(missing ascend_fixture/sanitized keys)."
        )
    schema = data.get("schema_version", 0)
    if schema != FIXTURE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported fixture schema version {schema} "
            f"(expected {FIXTURE_SCHEMA_VERSION})."
        )
    return data["payload"]
