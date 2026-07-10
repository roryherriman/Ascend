"""Loads Ascend's original SVG icon set - see resources/icons/LICENSE.txt."""
from __future__ import annotations

from PySide6.QtGui import QIcon

from ascend.resources import resource_path

_ICONS_DIR = resource_path("ascend", "resources", "icons")
_cache: dict[str, QIcon] = {}


def icon(name: str) -> QIcon:
    if name not in _cache:
        path = _ICONS_DIR / f"{name}.svg"
        _cache[name] = QIcon(str(path)) if path.exists() else QIcon()
    return _cache[name]


def icon_path(name: str) -> str:
    return str(_ICONS_DIR / f"{name}.svg")
