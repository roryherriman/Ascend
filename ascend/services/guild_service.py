"""Guild search and verification service.

Wraps the WCL guildData.guild() API call, normalises realm slugs, and
persists verified guild identity to the settings repository.

Guild state keys stored in the settings table:
  guild_name          — canonical name from WCL after verification
  guild_region        — region slug (us, eu, kr, tw, cn)
  guild_realm         — canonical realm name
  guild_realm_slug    — WCL server slug (lowercase, hyphenated)
  guild_wcl_id        — stable integer guild ID from WCL
  guild_faction       — e.g. "Alliance", "Horde"
  guild_verified      — True when WCL-verified
  guild_last_sync_at  — ISO timestamp of last successful sync
  guild_last_sync_status — "ok" | "failed" | "not_synced"
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ascend.api.client import WCLClient
    from ascend.data.repositories import SettingsRepository


def realm_to_slug(realm: str) -> str:
    """Convert a realm name to a WCL serverSlug (lowercase, spaces→hyphens)."""
    slug = realm.strip().lower()
    slug = re.sub(r"['’]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def verify_guild(
    client: "WCLClient",
    name: str,
    realm: str,
    region: str,
) -> dict[str, Any] | None:
    """Look up a guild via the WCL API.

    Returns a normalized guild dict on success, None if not found.
    Raises WCLNetworkError / WCLAuthError on hard API failures.
    """
    server_slug = realm_to_slug(realm)
    region_lower = region.strip().lower()
    return client.fetch_guild(name.strip(), server_slug, region_lower)


def save_verified_guild(settings_repo: "SettingsRepository", guild: dict[str, Any]) -> None:
    """Persist WCL-verified guild identity to settings."""
    from datetime import datetime, timezone
    settings_repo.set("guild_name", guild.get("name", ""))
    settings_repo.set("guild_region", guild.get("region_slug", ""))
    settings_repo.set("guild_realm", guild.get("server_name", ""))
    settings_repo.set("guild_realm_slug", guild.get("server_slug", ""))
    settings_repo.set("guild_wcl_id", guild.get("id"))
    settings_repo.set("guild_faction", guild.get("faction_name", ""))
    settings_repo.set("guild_verified", True)
    settings_repo.set("guild_last_sync_at", datetime.now(timezone.utc).isoformat())
    settings_repo.set("guild_last_sync_status", "ok")


def clear_guild(settings_repo: "SettingsRepository") -> None:
    """Remove active guild context (preserves historical data in reports)."""
    for key in (
        "guild_name", "guild_region", "guild_realm", "guild_realm_slug",
        "guild_wcl_id", "guild_faction", "guild_verified",
        "guild_last_sync_at", "guild_last_sync_status",
    ):
        settings_repo.set(key, None)


def get_guild_summary(settings_repo: "SettingsRepository") -> dict[str, Any]:
    """Return a dict of current guild state for display."""
    return {
        "name": settings_repo.get("guild_name") or "",
        "region": settings_repo.get("guild_region") or "",
        "realm": settings_repo.get("guild_realm") or "",
        "realm_slug": settings_repo.get("guild_realm_slug") or "",
        "wcl_id": settings_repo.get("guild_wcl_id"),
        "faction": settings_repo.get("guild_faction") or "",
        "verified": bool(settings_repo.get("guild_verified", False)),
        "last_sync_at": settings_repo.get("guild_last_sync_at"),
        "last_sync_status": settings_repo.get("guild_last_sync_status") or "not_synced",
    }
