"""Encounter rules service.

Rules let users tag specific encounter names with notes, mechanic labels,
and a pass/fail threshold. This is a lightweight annotation layer on top of
the encounter data — it does not re-classify raw log events (that requires
event-level data).

Rules are stored in the `encounter_rules` SQLite table created on first use.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ascend.data.database import Database


@dataclass
class EncounterRule:
    id: int | None
    encounter_name: str
    mechanic_label: str
    note: str
    created_at: str | None = None


class EncounterRulesRepository:
    def __init__(self, db: Database):
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS encounter_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                encounter_name TEXT NOT NULL,
                mechanic_label TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

    def list_all(self) -> list[EncounterRule]:
        rows = self._db.query_all(
            "SELECT id, encounter_name, mechanic_label, note, created_at "
            "FROM encounter_rules ORDER BY encounter_name, id"
        )
        return [EncounterRule(*r) for r in rows]

    def rules_for_encounter(self, encounter_name: str) -> list[EncounterRule]:
        rows = self._db.query_all(
            "SELECT id, encounter_name, mechanic_label, note, created_at "
            "FROM encounter_rules WHERE encounter_name = ? ORDER BY id",
            (encounter_name,),
        )
        return [EncounterRule(*r) for r in rows]

    def create(self, rule: EncounterRule) -> EncounterRule:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._db.execute(
            "INSERT INTO encounter_rules (encounter_name, mechanic_label, note, created_at) "
            "VALUES (?, ?, ?, ?)",
            (rule.encounter_name, rule.mechanic_label, rule.note, now),
        )
        rule.id = cursor.lastrowid
        rule.created_at = now
        return rule

    def update(self, rule: EncounterRule) -> None:
        self._db.execute(
            "UPDATE encounter_rules SET encounter_name=?, mechanic_label=?, note=? WHERE id=?",
            (rule.encounter_name, rule.mechanic_label, rule.note, rule.id),
        )

    def delete(self, rule_id: int) -> None:
        self._db.execute("DELETE FROM encounter_rules WHERE id = ?", (rule_id,))
