"""Centralized World of Warcraft class icon + color mapping.

Icon loading preference order (never raises, never blocks):
  1. PNG fetched from Blizzard Game Data API (build-time, gitignored)
  2. JPG fetched from Blizzard Game Data API (build-time, gitignored)
  3. SVG original glyph (committed, always present as fallback)

Use class_icon()/class_icon_pixmap()/class_color() everywhere — never import
paths from resources/class_icons directly so the fallback chain stays centralized.
"""
from __future__ import annotations

from PySide6.QtGui import QIcon, QPixmap

from ascend.resources import resource_path

_ICONS_DIR = resource_path("ascend", "resources", "class_icons")

CLASS_COLORS: dict[str, str] = {
    "Death Knight": "#C41F3B",
    "Demon Hunter": "#A330C9",
    "Druid": "#FF7D0A",
    "Evoker": "#33937F",
    "Hunter": "#ABD473",
    "Mage": "#69CCF0",
    "Monk": "#00FF96",
    "Paladin": "#F58CBA",
    "Priest": "#F0EBE0",
    "Rogue": "#FFF569",
    "Shaman": "#0070DE",
    "Warlock": "#8788EE",
    "Warrior": "#C79C6E",
}

UNKNOWN_COLOR = "#9599A2"

_CLASS_COLORS_BY_LOWER = {name.lower(): color for name, color in CLASS_COLORS.items()}

_icon_cache: dict[str, QIcon] = {}


def _slug(class_name: str | None) -> str:
    if not class_name:
        return "unknown"
    return class_name.strip().lower().replace(" ", "_")


def _resolve_icon_path(slug: str) -> str | None:
    """Return the best available icon file path for slug, or None if nothing found."""
    for ext in (".png", ".jpg", ".jpeg", ".svg"):
        candidate = _ICONS_DIR / f"{slug}{ext}"
        if candidate.exists():
            return str(candidate)
    # Fall back to unknown SVG
    fallback = _ICONS_DIR / "unknown.svg"
    return str(fallback) if fallback.exists() else None


def class_icon(class_name: str | None) -> QIcon:
    """Never raises and never blocks on network."""
    slug = _slug(class_name)
    if slug not in _icon_cache:
        path = _resolve_icon_path(slug)
        _icon_cache[slug] = QIcon(path) if path else QIcon()
    return _icon_cache[slug]


def class_icon_pixmap(class_name: str | None, size: int) -> QPixmap:
    return class_icon(class_name).pixmap(size, size)


def class_color(class_name: str | None) -> str:
    return _CLASS_COLORS_BY_LOWER.get((class_name or "").strip().lower(), UNKNOWN_COLOR)
