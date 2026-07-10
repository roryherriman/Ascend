"""Basic roster comparison: attendance across the players you actually raid
with, derived from fight_participants.

Performance comparison (damage, percentiles, same-spec/same-class ranking)
needs event-level data Ascend doesn't ingest yet (Phase 3) - this is
attendance only: raid nights and pulls seen together, which is honestly
derivable from what's already synced.
"""
from __future__ import annotations

from dataclasses import dataclass

from ascend.data.database import Database


@dataclass
class RosterMember:
    name: str
    server: str | None
    class_name: str | None
    character_id: int | None
    raid_nights: int
    pulls: int


def roster_summary(db: Database) -> list[RosterMember]:
    """Every distinct participant (by name+server) seen across all synced
    fights, most-attended first."""
    rows = db.query_all(
        """
        SELECT fp.name AS name, fp.server AS server,
               MAX(fp.class_name) AS class_name, MAX(fp.character_id) AS character_id,
               COUNT(DISTINCT f.report_id) AS raid_nights, COUNT(*) AS pulls
        FROM fight_participants fp
        JOIN fights f ON f.id = fp.fight_id
        WHERE fp.name IS NOT NULL
        GROUP BY fp.name, fp.server
        ORDER BY raid_nights DESC, pulls DESC, fp.name COLLATE NOCASE ASC
        """
    )
    return [
        RosterMember(
            name=row["name"],
            server=row["server"],
            class_name=row["class_name"],
            character_id=row["character_id"],
            raid_nights=row["raid_nights"],
            pulls=row["pulls"],
        )
        for row in rows
    ]
