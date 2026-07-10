"""Raid tier (zone) fetching and caching.

Fetches raid zones from the Warcraft Logs worldData.zones API and caches
them in the api_cache table. Falls back to the static WOW_RAID_TIERS list
when the API is unavailable.

Each cached zone has:
  id, name, frozen, expansion_id, expansion_name

Zones are sorted: non-frozen (current/active) first by expansion_id desc,
then frozen zones by expansion_id desc. This puts the current tier at the top.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ascend.api.client import WCLClient
    from ascend.data.database import Database

CACHE_KEY = "raid_tiers_v1"
CACHE_TTL_HOURS = 24


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_cached_zones(db: "Database") -> tuple[list[dict], str | None]:
    """Return (zones, cached_at_iso) from api_cache, or ([], None) if absent/expired."""
    row = db.query_one(
        "SELECT response_json, fetched_at, expires_at FROM api_cache WHERE cache_key = ?",
        (CACHE_KEY,),
    )
    if row is None:
        return [], None
    try:
        zones = json.loads(row["response_json"])
    except (json.JSONDecodeError, TypeError):
        return [], None
    return zones, row["fetched_at"]


def save_zones_to_cache(db: "Database", zones: list[dict]) -> None:
    now = _now_iso()
    expires = (
        datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS)
    ).isoformat()
    db.execute(
        """
        INSERT INTO api_cache (cache_key, response_json, fetched_at, expires_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            response_json = excluded.response_json,
            fetched_at = excluded.fetched_at,
            expires_at = excluded.expires_at
        """,
        (CACHE_KEY, json.dumps(zones), now, expires),
    )


def sort_zones(zones: list[dict]) -> list[dict]:
    """Sort zones: non-frozen by expansion_id desc, then frozen by expansion_id desc."""
    active = sorted(
        [z for z in zones if not z.get("frozen")],
        key=lambda z: (z.get("expansion_id") or 0),
        reverse=True,
    )
    frozen = sorted(
        [z for z in zones if z.get("frozen")],
        key=lambda z: (z.get("expansion_id") or 0),
        reverse=True,
    )
    return active + frozen


def fetch_and_cache_zones(db: "Database", client: "WCLClient") -> list[dict]:
    """Fetch zones from WCL and persist to cache. Returns sorted zone list."""
    zones = client.fetch_zones()
    sorted_zones = sort_zones(zones)
    save_zones_to_cache(db, sorted_zones)
    return sorted_zones


def get_zones_for_display(db: "Database") -> tuple[list[dict], str | None, bool]:
    """Return (zones, cached_at, is_from_cache) for UI display.

    Falls back to the static WOW_RAID_TIERS list if nothing is cached.
    cached_at is an ISO string or None.
    is_from_cache is True when returning API-fetched data from the db cache.
    """
    zones, cached_at = get_cached_zones(db)
    if zones:
        return zones, cached_at, True

    from ascend.data.wow_data import WOW_RAID_TIERS
    static_zones = [{"id": None, "name": name, "frozen": False, "expansion_id": None,
                     "expansion_name": ""} for name in WOW_RAID_TIERS]
    return static_zones, None, False


def zone_display_name(zone: dict) -> str:
    return zone.get("name", "")


def format_cached_at(cached_at: str | None) -> str:
    if not cached_at:
        return "Never synchronized — click Refresh to load from Warcraft Logs"
    try:
        dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        local = dt.astimezone()
        return f"Last synchronized: {local.strftime('%B %-d, %Y at %-I:%M %p')}"
    except (ValueError, AttributeError):
        return f"Last synchronized: {cached_at}"
