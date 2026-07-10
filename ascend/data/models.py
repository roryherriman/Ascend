"""Plain dataclasses mirroring the SQLite schema.

These are simple data containers, not an ORM - repositories.py does the
SQL and hands back / accepts these types.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Character:
    display_name: str
    character_name: str
    region: str
    server: str
    wcl_character_id: int | None = None
    character_class: str | None = None
    character_role: str = "primary"  # 'primary' or 'alternate'
    enabled: bool = True
    notes: str = ""
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Report:
    report_code: str
    title: str | None = None
    owner_name: str | None = None
    guild_name: str | None = None
    zone_id: int | None = None
    zone_name: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    fetched_at: str | None = None
    analysis_status: str = "not_analyzed"
    id: int | None = None
    fight_count: int = 0
    kill_count: int = 0


@dataclass
class Fight:
    report_id: int
    fight_id: int
    name: str | None = None
    encounter_id: int | None = None
    difficulty: int | None = None
    kill: bool | None = None
    start_time: float | None = None
    end_time: float | None = None
    id: int | None = None


@dataclass
class SyncHistoryEntry:
    operation_type: str
    status: str
    started_at: str
    finished_at: str | None = None
    reports_processed: int = 0
    pulls_processed: int = 0
    error_message: str | None = None
    id: int | None = None
