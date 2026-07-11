"""Detect local WoW combat log files.

Scans well-known installation paths for WoWCombatLog.txt and returns
the most-recently-modified file found (or None if nothing is detected).
Supports Retail, Classic Era, and Classic Cataclysm variants.

Never reads the file contents — only checks existence and stat metadata.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_WOW_SUBFLAVORS = [
    "_retail_",
    "_classic_",
    "_classic_era_",
    "_classic_ptr_",
    "_retail_ptr_",
]

_LOG_RELATIVE = Path("Logs") / "WoWCombatLog.txt"


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []

    # Check all drive letters on Windows
    drives = [f"{d}:\\" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ"]
    for drive in drives:
        if not os.path.exists(drive):
            continue
        for base in [
            Path(drive) / "Program Files (x86)" / "World of Warcraft",
            Path(drive) / "Program Files" / "World of Warcraft",
            Path(drive) / "Games" / "World of Warcraft",
            Path(drive) / "World of Warcraft",
        ]:
            if base.exists():
                roots.append(base)

    # Also check environment variable override for testing
    override = os.environ.get("ASCEND_WOW_ROOT")
    if override:
        roots.insert(0, Path(override))

    return roots


def _candidate_logs(roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for root in roots:
        for flavor in _WOW_SUBFLAVORS:
            p = root / flavor / _LOG_RELATIVE
            if p.exists():
                candidates.append(p)
    return candidates


@dataclass
class CombatLogInfo:
    path: Path
    flavor: str
    size_bytes: int
    last_modified: datetime

    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    def last_modified_str(self) -> str:
        return self.last_modified.astimezone().strftime("%Y-%m-%d %H:%M")


def detect_combat_logs() -> list[CombatLogInfo]:
    """Return info for every detected WoWCombatLog.txt, newest-first."""
    roots = _candidate_roots()
    candidates = _candidate_logs(roots)
    results: list[CombatLogInfo] = []
    for path in candidates:
        try:
            stat = path.stat()
        except OSError:
            continue
        parts = path.parts
        flavor = next(
            (p for p in parts if p.startswith("_") and p.endswith("_")),
            "unknown",
        )
        results.append(
            CombatLogInfo(
                path=path,
                flavor=flavor,
                size_bytes=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
        )
    results.sort(key=lambda r: r.last_modified, reverse=True)
    return results


def detect_primary_combat_log() -> CombatLogInfo | None:
    """Return the most-recently-modified WoWCombatLog.txt, or None."""
    logs = detect_combat_logs()
    return logs[0] if logs else None
