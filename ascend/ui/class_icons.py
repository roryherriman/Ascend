"""Centralized World of Warcraft class icon + color mapping.

Icons are original glyphs (see resources/class_icons/LICENSE.txt), not
Blizzard's class icon artwork - the Warcraft Logs API's GameClass/GameSpec
schema exposes no icon field (verified before implementing this), so
downloading or scraping a "real" class icon isn't an option without a
separate Battle.net Game Data API integration, which is out of scope here.

Never import resources/class_icons paths directly elsewhere - always go
through class_icon()/class_color() so the mapping stays centralized.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap

_ICONS_DIR = Path(__file__).resolve().parent.parent / "resources" / "class_icons"

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
    key = class_name.strip().lower().replace(" ", "_")
    return key if (_ICONS_DIR / f"{key}.svg").exists() else "unknown"


def class_icon(class_name: str | None) -> QIcon:
    """Never raises and never blocks on network - these are bundled SVGs."""
    slug = _slug(class_name)
    if slug not in _icon_cache:
        path = _ICONS_DIR / f"{slug}.svg"
        _icon_cache[slug] = QIcon(str(path)) if path.exists() else QIcon()
    return _icon_cache[slug]


def class_icon_pixmap(class_name: str | None, size: int) -> QPixmap:
    return class_icon(class_name).pixmap(size, size)


def class_color(class_name: str | None) -> str:
    return _CLASS_COLORS_BY_LOWER.get((class_name or "").strip().lower(), UNKNOWN_COLOR)
