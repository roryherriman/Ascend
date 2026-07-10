"""Guild identity badge generation and caching.

Warcraft Logs' Guild/GameFaction/GameClass schema exposes no emblem, crest,
icon, or image-URL field (verified against the live schema docs before
implementing this - see docs/WCL_API.md and docs/ASSET_LICENSES.md), and
Ascend has no Battle.net Game Data API credentials configured. Per the
preferred source order, this always falls through to a locally generated
initials badge, or a user-chosen custom local image - never a scraped
image, and never something that blocks the rest of the app if it fails.
"""
from __future__ import annotations

import hashlib
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
    except Exception:  # noqa: BLE001 - a badge failure must never block analysis
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
    except Exception:  # noqa: BLE001 - fall through to a live-generated badge
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
