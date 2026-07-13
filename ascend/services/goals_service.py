"""Goals tracking service.

Goals are stored in the `goals` SQLite table (created by the goals migration).
Each goal has a name, optional target date, a target metric value, and a
status that is auto-computed from current DB state on every reload.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal

from ascend.data.database import Database

GoalStatus = Literal["on_track", "achieved", "at_risk", "pending", "overdue"]


@dataclass
class Goal:
    id: int | None
    title: str
    description: str
    metric_key: str
    target_value: float
    target_date: str | None = None
    created_at: str | None = None
    achieved_at: str | None = None

    def is_overdue(self) -> bool:
        if not self.target_date:
            return False
        try:
            td = date.fromisoformat(self.target_date)
            return date.today() > td and self.achieved_at is None
        except ValueError:
            return False

    def days_remaining(self) -> int | None:
        if not self.target_date:
            return None
        try:
            td = date.fromisoformat(self.target_date)
            return (td - date.today()).days
        except ValueError:
            return None


class GoalsRepository:
    def __init__(self, db: Database):
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                metric_key TEXT NOT NULL DEFAULT 'manual',
                target_value REAL NOT NULL DEFAULT 1.0,
                target_date TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                achieved_at TEXT
            )
        """)

    def list_all(self) -> list[Goal]:
        rows = self._db.query_all(
            "SELECT id, title, description, metric_key, target_value, "
            "target_date, created_at, achieved_at FROM goals ORDER BY created_at DESC"
        )
        return [Goal(*r) for r in rows]

    def create(self, goal: Goal) -> Goal:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._db.execute(
            "INSERT INTO goals (title, description, metric_key, target_value, target_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (goal.title, goal.description, goal.metric_key, goal.target_value, goal.target_date, now),
        )
        goal.id = cursor.lastrowid
        goal.created_at = now
        return goal

    def mark_achieved(self, goal_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute("UPDATE goals SET achieved_at = ? WHERE id = ?", (now, goal_id))

    def unmark_achieved(self, goal_id: int) -> None:
        self._db.execute("UPDATE goals SET achieved_at = NULL WHERE id = ?", (goal_id,))

    def delete(self, goal_id: int) -> None:
        self._db.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
