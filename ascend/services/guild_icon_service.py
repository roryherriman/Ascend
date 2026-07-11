"""Guild identity badge generation, caching, and Blizzard API crest fetch.

Source preference order (most to least preferred):
  1. Blizzard Guild Media API emblem — fetched on demand when BNET credentials
     are configured; stored in the local cache; never re-fetched automatically.
  2. User-chosen custom local image — set via Settings > Guild > Choose Custom Image.
  3. Generated initials badge — always available as a last resort.

All public functions are safe to call unconditionally: they never raise, and
they always return a usable pixmap. Network calls happen only in
try_fetch_blizzard_guild_crest(), which is called from background threads.

Secrets: BNET client secret is passed in at call time from SecureStorage;
it is never stored in SQLite, logs, crash reports, or this module.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

from ascend.data.database import Database, default_app_data_root
from ascend.data.repositories import GuildIconRepository
from ascend.ui.styles.tokens import DARK_TOKENS

_BADGE_BACKGROUND = QColor(DARK_TOKENS.palette.accent_muted)
_BADGE_BORDER = QColor(DARK_TOKENS.palette.accent)
_BADGE_TEXT = QColor(DARK_TOKENS.palette.text_primary)

BNET_OAUTH_URL = "https://us.battle.net/oauth/token"
BNET_API_BASE = "https://us.api.blizzard.com"


def guild_cache_key(region: str, realm: str, guild_name: str, guild_id: int | None = None) -> str:
    raw = f"{(region or '').lower()}|{(realm or '').lower()}|{(guild_name or '').lower()}|{guild_id or ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _initials(guild_name: str) -> str:
    words = [w for w in (guild_name or "").strip().split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _realm_to_bnet_slug(realm: str) -> str:
    """Convert a realm display name to a Blizzard API slug (lowercase, hyphens, no apostrophes)."""
    slug = realm.lower()
    slug = re.sub(r"['’]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    return slug.strip("-")


def _guild_to_bnet_slug(guild_name: str) -> str:
    """Convert a guild name to a Blizzard API slug."""
    slug = guild_name.lower()
    slug = re.sub(r"['’]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    return slug.strip("-")


def _bnet_region_namespace(region: str) -> tuple[str, str]:
    """Return (api_base_url, namespace) for the given region code."""
    r = region.lower()
    if r in ("eu",):
        return "https://eu.api.blizzard.com", f"profile-eu"
    if r in ("kr",):
        return "https://kr.api.blizzard.com", f"profile-kr"
    if r in ("tw",):
        return "https://tw.api.blizzard.com", f"profile-tw"
    if r in ("cn",):
        return "https://gateway.battlenet.com.cn", f"profile-cn"
    return "https://us.api.blizzard.com", "profile-us"


def _get_bnet_access_token(client_id: str, client_secret: str, timeout: float = 10.0) -> str:
    """Obtain a Battle.net OAuth2 client-credentials access token. Raises on failure."""
    import requests
    resp = requests.post(
        BNET_OAUTH_URL,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def make_guild_badge_pixmap(guild_name: str, size: int = 48) -> QPixmap:
    """Renders a polished fallback guild badge: initials + Ascend-branded ring."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = max(1, size // 24)
    rect = pixmap.rect().adjusted(margin, margin, -margin, -margin)

    pen = painter.pen()
    pen.setColor(_BADGE_BORDER)
    pen.setWidth(max(1, size // 16))
    painter.setPen(pen)
    painter.setBrush(_BADGE_BACKGROUND)
    painter.drawEllipse(rect)

    font = QFont()
    font.setPixelSize(int(size * 0.36))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(_BADGE_TEXT)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, _initials(guild_name))

    painter.end()
    return pixmap


def _cache_dir() -> Path:
    path = default_app_data_root() / "guild_icons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def try_fetch_blizzard_guild_crest(
    db: Database,
    region: str,
    realm: str,
    guild_name: str,
    client_id: str,
    client_secret: str,
    guild_id: int | None = None,
    timeout: float = 15.0,
) -> dict | None:
    """Attempt to fetch the guild emblem from the Blizzard Guild Media API.

    Downloads the emblem PNG to the local cache, updates GuildIconRepository,
    and returns the updated record. Returns None on any failure (credentials
    missing, guild not found, network error) — the caller should fall back
    to the generated badge.

    Must be called from a background thread — never from the UI thread.
    """
    if not client_id or not client_secret:
        return None

    import requests

    try:
        token = _get_bnet_access_token(client_id, client_secret, timeout=timeout)
    except Exception:  # noqa: BLE001
        return None

    realm_slug = _realm_to_bnet_slug(realm)
    name_slug = _guild_to_bnet_slug(guild_name)
    api_base, namespace = _bnet_region_namespace(region)

    try:
        url = f"{api_base}/data/wow/media/guild/{realm_slug}/{name_slug}"
        resp = requests.get(
            url,
            params={"namespace": namespace, "locale": "en_US"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001
        return None

    emblem_url: str | None = None
    for asset in data.get("assets", []):
        if asset.get("key") == "emblem":
            emblem_url = asset.get("value")
            break

    if not emblem_url:
        return None

    try:
        img_resp = requests.get(emblem_url, timeout=timeout)
        img_resp.raise_for_status()
    except Exception:  # noqa: BLE001
        return None

    key = guild_cache_key(region, realm, guild_name, guild_id)
    suffix = ".png" if "png" in emblem_url.lower() else ".jpg"
    file_path = _cache_dir() / f"{key}_blizzard{suffix}"
    try:
        file_path.write_bytes(img_resp.content)
    except OSError:
        return None

    repo = GuildIconRepository(db)
    repo.upsert(
        cache_key=key, region=region, realm=realm, guild_name=guild_name, guild_id=guild_id,
        source_url=emblem_url, source_type="official_api",
        cache_file_path=str(file_path), retrieval_status="ok",
    )
    return repo.get(key)


def get_or_create_guild_icon(
    db: Database, region: str, realm: str, guild_name: str, guild_id: int | None = None
) -> dict:
    """Returns the cached guild icon record, generating a fallback badge on first use."""
    repo = GuildIconRepository(db)
    key = guild_cache_key(region, realm, guild_name, guild_id)
    existing = repo.get(key)
    if existing is not None:
        return existing

    file_path = _cache_dir() / f"{key}.png"
    try:
        make_guild_badge_pixmap(guild_name, size=96).save(str(file_path), "PNG")
        status = "ok"
    except Exception:  # noqa: BLE001
        file_path = None
        status = "error"

    repo.upsert(
        cache_key=key, region=region, realm=realm, guild_name=guild_name, guild_id=guild_id,
        source_url=None, source_type="generated_fallback",
        cache_file_path=str(file_path) if file_path else None, retrieval_status=status,
    )
    return repo.get(key)


def get_guild_badge_pixmap(
    db: Database, region: str, realm: str, guild_name: str, size: int = 48, guild_id: int | None = None
) -> QPixmap:
    """Safe to call unconditionally: never raises, always returns a usable pixmap."""
    if not guild_name:
        return make_guild_badge_pixmap("", size=size)
    try:
        record = get_or_create_guild_icon(db, region, realm, guild_name, guild_id)
        cache_file_path = record.get("cache_file_path") if record else None
        if cache_file_path and Path(cache_file_path).exists():
            pixmap = QPixmap(cache_file_path)
            if not pixmap.isNull():
                return pixmap.scaled(
                    size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
    except Exception:  # noqa: BLE001
        pass
    return make_guild_badge_pixmap(guild_name, size=size)


def set_custom_guild_icon(
    db: Database, region: str, realm: str, guild_name: str, image_path: str, guild_id: int | None = None
) -> dict:
    """Copies a user-chosen local image into the cache dir. The source file stays local
    and is never committed automatically - see docs/ASSET_LICENSES.md."""
    repo = GuildIconRepository(db)
    key = guild_cache_key(region, realm, guild_name, guild_id)
    suffix = Path(image_path).suffix or ".png"
    dest_path = _cache_dir() / f"{key}_custom{suffix}"
    shutil.copyfile(image_path, dest_path)

    repo.upsert(
        cache_key=key, region=region, realm=realm, guild_name=guild_name, guild_id=guild_id,
        source_url=None, source_type="custom_local",
        cache_file_path=str(dest_path), retrieval_status="ok",
    )
    return repo.get(key)


def clear_guild_icon(db: Database, region: str, realm: str, guild_name: str, guild_id: int | None = None) -> None:
    repo = GuildIconRepository(db)
    key = guild_cache_key(region, realm, guild_name, guild_id)
    existing = repo.get(key)
    if existing and existing.get("cache_file_path"):
        Path(existing["cache_file_path"]).unlink(missing_ok=True)
    repo.delete(key)


def reset_to_automatic_guild_icon(
    db: Database, region: str, realm: str, guild_name: str, guild_id: int | None = None
) -> dict:
    clear_guild_icon(db, region, realm, guild_name, guild_id)
    return get_or_create_guild_icon(db, region, realm, guild_name, guild_id)
