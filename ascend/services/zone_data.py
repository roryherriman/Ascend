"""Caches per-zone difficulty labels (e.g. "Mythic", "Heroic").

Fight.difficulty is a bare int with no self-describing enum - the id-to-name
mapping is scoped per zone (Zone.difficulties) and effectively static once a
tier is released, so it's fetched once per zone and cached indefinitely in
api_cache rather than re-fetched on every sync.
"""
from __future__ import annotations

import json

from ascend.api.client import WCLClient
from ascend.data.database import Database
from ascend.data.repositories import ApiCacheRepository


def _cache_key(zone_id: int) -> str:
    return f"zone_difficulties:{zone_id}"


def get_cached_zone_difficulties(db: Database, zone_id: int) -> dict[int, str]:
    """Returns {difficulty_id: name} from the cache only - no network call."""
    row = ApiCacheRepository(db).get(_cache_key(zone_id))
    if row is None:
        return {}
    difficulties = json.loads(row["response_json"])
    return {d["id"]: d["name"] for d in difficulties if d.get("id") is not None}


def label_for_difficulty(db: Database, zone_id: int | None, difficulty_id: int | None) -> str:
    """Cache-only lookup for display code - never makes a network call, so
    it's safe to call from the GUI thread. Returns "--" if unknown/uncached."""
    if zone_id is None or difficulty_id is None:
        return "--"
    return get_cached_zone_difficulties(db, zone_id).get(difficulty_id, "--")


def ensure_zone_difficulties_cached(db: Database, client: WCLClient, zone_id: int) -> dict[int, str]:
    """Returns the cached mapping, fetching and caching it first if needed.
    Meant to be called from a background task (e.g. during sync), not the
    GUI thread."""
    cached = get_cached_zone_difficulties(db, zone_id)
    if cached:
        return cached
    difficulties = client.fetch_zone_difficulties(zone_id)
    ApiCacheRepository(db).set(_cache_key(zone_id), json.dumps(difficulties))
    return {d["id"]: d["name"] for d in difficulties if d.get("id") is not None}
