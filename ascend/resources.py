"""Frozen-aware resource path resolution for Ascend.

In a development environment, resources live relative to this file inside the
source tree.  When the application is frozen by PyInstaller the same tree is
extracted to sys._MEIPASS at startup.  All resource lookups must go through
resource_path() so they work in both modes.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _base() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    # development: ascend/resources.py → go up one level to the project root
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Return an absolute path to a bundled resource.

    Works in both development (source tree) and PyInstaller frozen builds.

    Usage::

        resource_path("ascend", "resources", "icons", "dashboard.svg")
        resource_path("docs", "ROADMAP.md")
    """
    return _base().joinpath(*parts)
