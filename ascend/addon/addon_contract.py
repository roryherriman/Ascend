"""Addon data contract — SavedVariables schema.

The in-game WoW Lua addon writes to its SavedVariables file (a Lua table
serialised to disk on logout/reload). The combat log watcher reads this file
and converts it to RaidSession/RaidEncounter/RaidEvent objects.

This module documents the expected SavedVariables structure as Python
constants and a parser stub. The actual Lua-side implementation lives in
the addon repository (separate from this codebase).

CONTRACT VERSION: 1
Bump CONTRACT_VERSION when the schema changes in a backwards-incompatible way.
The watcher must reject data from older contract versions that it cannot parse.
"""
from __future__ import annotations

from ascend.addon.session_model import RaidEncounter, RaidEvent, RaidSession

CONTRACT_VERSION = 1

# Expected top-level keys in the SavedVariables Lua table (after parsing to dict)
REQUIRED_KEYS: list[str] = [
    "contractVersion",
    "sessionId",
    "zoneName",
    "difficulty",
    "startedAt",
    "characterName",
    "characterRealm",
    "region",
    "encounters",
]

# Event type strings the addon is allowed to emit
KNOWN_EVENT_TYPES: frozenset[str] = frozenset([
    "death",
    "mechanic_fail",
    "interrupt",
    "dispel",
    "cast",
    "damage",
    "heal",
    "aura_applied",
    "aura_removed",
])


def parse_saved_variables(data: dict) -> RaidSession | None:
    """Parse a decoded SavedVariables dict into a RaidSession.

    Returns ``None`` and does not raise if the data is missing required keys
    or has an incompatible contract version — the caller should log a warning.

    This is a stub implementation. The full parser will be added when the
    Lua addon is shipped (PR F completion milestone).
    """
    if not isinstance(data, dict):
        return None
    if data.get("contractVersion") != CONTRACT_VERSION:
        return None
    for key in REQUIRED_KEYS:
        if key not in data:
            return None

    encounters = []
    for enc in data.get("encounters", []):
        events = [
            RaidEvent(
                timestamp=e.get("timestamp", 0.0),
                event_type=e.get("eventType", ""),
                source_name=e.get("sourceName", ""),
                target_name=e.get("targetName", ""),
                spell_id=e.get("spellId"),
                spell_name=e.get("spellName"),
                amount=e.get("amount", 0),
            )
            for e in enc.get("events", [])
            if e.get("eventType") in KNOWN_EVENT_TYPES
        ]
        encounters.append(RaidEncounter(
            encounter_id=enc.get("encounterId", 0),
            encounter_name=enc.get("encounterName", ""),
            pull_number=enc.get("pullNumber", 1),
            started_at=enc.get("startedAt", 0.0),
            ended_at=enc.get("endedAt"),
            outcome=enc.get("outcome", "wipe"),
            duration_ms=enc.get("durationMs", 0),
            events=events,
        ))

    return RaidSession(
        session_id=data["sessionId"],
        zone_name=data["zoneName"],
        difficulty=data["difficulty"],
        started_at=data["startedAt"],
        ended_at=data.get("endedAt"),
        is_complete=bool(data.get("isComplete", False)),
        character_name=data["characterName"],
        character_realm=data["characterRealm"],
        region=data["region"],
        notes=data.get("notes", ""),
        encounters=encounters,
    )
