"""Local raid session model.

These dataclasses represent a raid session as captured by the combat log
watcher or in-game addon. They are the canonical input type for Ascend's
local (non-WCL) analysis pipeline.

A RaidSession is a top-level container created when the user enters a raid
instance. It holds RaidEncounter records (one per boss) and RaidEvent records
(one per significant in-combat event) written by the watcher in real time.

These models are intentionally flat and serialisable so they can be written to
SQLite or exchanged with the addon via a shared file or named pipe.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RaidSession:
    """One in-game raid session (zone entry → zone exit or disconnect)."""

    session_id: str
    zone_name: str
    difficulty: str
    started_at: float  # Unix timestamp (seconds)
    ended_at: float | None = None
    is_complete: bool = False
    character_name: str = ""
    character_realm: str = ""
    region: str = ""
    notes: str = ""
    encounters: list[RaidEncounter] = field(default_factory=list)


@dataclass
class RaidEncounter:
    """One boss attempt within a RaidSession."""

    encounter_id: int
    encounter_name: str
    pull_number: int
    started_at: float
    ended_at: float | None = None
    outcome: str = "wipe"  # "wipe", "kill", "interrupted"
    duration_ms: int = 0
    events: list[RaidEvent] = field(default_factory=list)


@dataclass
class RaidEvent:
    """A single significant in-combat event (death, mechanic, healing, etc.)."""

    timestamp: float
    event_type: str   # "death", "mechanic_fail", "interrupt", "dispel", "cast", "damage"
    source_name: str
    target_name: str
    spell_id: int | None = None
    spell_name: str | None = None
    amount: int = 0
    notes: str = ""
