"""Repositories: SQL access for each table, returning/accepting models.py dataclasses."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report, SyncHistoryEntry


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CharacterRepository:
    def __init__(self, db: Database):
        self.db = db

    def list_all(self, enabled_only: bool = False) -> list[Character]:
        sql = "SELECT * FROM characters"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY display_name COLLATE NOCASE"
        return [self._row_to_model(row) for row in self.db.query_all(sql)]

    def get(self, character_id: int) -> Character | None:
        row = self.db.query_one("SELECT * FROM characters WHERE id = ?", (character_id,))
        return self._row_to_model(row) if row else None

    def create(self, character: Character) -> Character:
        now = _now_iso()
        cur = self.db.execute(
            """
            INSERT INTO characters
                (display_name, character_name, region, server, wcl_character_id,
                 class, character_role, enabled, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character.display_name,
                character.character_name,
                character.region,
                character.server,
                character.wcl_character_id,
                character.character_class,
                character.character_role,
                1 if character.enabled else 0,
                character.notes,
                now,
                now,
            ),
        )
        character.id = cur.lastrowid
        character.created_at = now
        character.updated_at = now
        return character

    def update(self, character: Character) -> None:
        if character.id is None:
            raise ValueError("Cannot update a character without an id")
        now = _now_iso()
        self.db.execute(
            """
            UPDATE characters
            SET display_name = ?, character_name = ?, region = ?, server = ?,
                wcl_character_id = ?, class = ?, character_role = ?, enabled = ?,
                notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                character.display_name,
                character.character_name,
                character.region,
                character.server,
                character.wcl_character_id,
                character.character_class,
                character.character_role,
                1 if character.enabled else 0,
                character.notes,
                now,
                character.id,
            ),
        )
        character.updated_at = now

    def delete(self, character_id: int) -> None:
        self.db.execute("DELETE FROM characters WHERE id = ?", (character_id,))

    def set_enabled(self, character_id: int, enabled: bool) -> None:
        self.db.execute(
            "UPDATE characters SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, _now_iso(), character_id),
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Character:
        return Character(
            id=row["id"],
            display_name=row["display_name"],
            character_name=row["character_name"],
            region=row["region"],
            server=row["server"],
            wcl_character_id=row["wcl_character_id"],
            character_class=row["class"],
            character_role=row["character_role"],
            enabled=bool(row["enabled"]),
            notes=row["notes"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class ReportRepository:
    def __init__(self, db: Database):
        self.db = db

    def list_all(self) -> list[Report]:
        sql = """
            SELECT r.*,
                   COUNT(f.id) AS fight_count,
                   SUM(CASE WHEN f.kill = 1 THEN 1 ELSE 0 END) AS kill_count
            FROM reports r
            LEFT JOIN fights f ON f.report_id = r.id
            GROUP BY r.id
            ORDER BY r.start_time DESC
        """
        return [self._row_to_model(row) for row in self.db.query_all(sql)]

    def get_by_code(self, report_code: str) -> Report | None:
        row = self.db.query_one("SELECT * FROM reports WHERE report_code = ?", (report_code,))
        return self._row_to_model(row) if row else None

    def upsert_report(self, report: Report) -> Report:
        """Insert or update a report by its unique report_code. Never creates duplicates."""
        now = _now_iso()
        existing = self.get_by_code(report.report_code)
        if existing is None:
            cur = self.db.execute(
                """
                INSERT INTO reports
                    (report_code, title, owner_name, guild_name, zone_id, zone_name,
                     start_time, end_time, fetched_at, analysis_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.report_code,
                    report.title,
                    report.owner_name,
                    report.guild_name,
                    report.zone_id,
                    report.zone_name,
                    report.start_time,
                    report.end_time,
                    now,
                    report.analysis_status,
                ),
            )
            report.id = cur.lastrowid
        else:
            self.db.execute(
                """
                UPDATE reports
                SET title = ?, owner_name = ?, guild_name = ?, zone_id = ?, zone_name = ?,
                    start_time = ?, end_time = ?, fetched_at = ?
                WHERE report_code = ?
                """,
                (
                    report.title,
                    report.owner_name,
                    report.guild_name,
                    report.zone_id,
                    report.zone_name,
                    report.start_time,
                    report.end_time,
                    now,
                    report.report_code,
                ),
            )
            report.id = existing.id
        report.fetched_at = now
        return report

    def upsert_fight(self, fight: Fight) -> Fight:
        """Insert or update a fight keyed by (report_id, fight_id) - prevents duplicate pulls."""
        cur = self.db.execute(
            """
            INSERT INTO fights (report_id, fight_id, name, encounter_id, difficulty,
                                 kill, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_id, fight_id) DO UPDATE SET
                name = excluded.name,
                encounter_id = excluded.encounter_id,
                difficulty = excluded.difficulty,
                kill = excluded.kill,
                start_time = excluded.start_time,
                end_time = excluded.end_time
            """,
            (
                fight.report_id,
                fight.fight_id,
                fight.name,
                fight.encounter_id,
                fight.difficulty,
                1 if fight.kill else (0 if fight.kill is not None else None),
                fight.start_time,
                fight.end_time,
            ),
        )
        row = self.db.query_one(
            "SELECT id FROM fights WHERE report_id = ? AND fight_id = ?",
            (fight.report_id, fight.fight_id),
        )
        fight.id = row["id"] if row else cur.lastrowid
        return fight

    def fights_for_report(self, report_id: int) -> list[Fight]:
        rows = self.db.query_all(
            "SELECT * FROM fights WHERE report_id = ? ORDER BY fight_id", (report_id,)
        )
        return [
            Fight(
                id=row["id"],
                report_id=row["report_id"],
                fight_id=row["fight_id"],
                name=row["name"],
                encounter_id=row["encounter_id"],
                difficulty=row["difficulty"],
                kill=bool(row["kill"]) if row["kill"] is not None else None,
                start_time=row["start_time"],
                end_time=row["end_time"],
            )
            for row in rows
        ]

    def delete_report(self, report_id: int) -> None:
        self.db.execute("DELETE FROM reports WHERE id = ?", (report_id,))

    def upsert_fight_participant(self, participant: FightParticipant) -> FightParticipant:
        """Insert or update a participant keyed by (fight_id, actor_id) - the
        WCL report-scoped actor id, not a global/persistent id."""
        self.db.execute(
            """
            INSERT INTO fight_participants (fight_id, actor_id, name, server, class_name, character_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(fight_id, actor_id) DO UPDATE SET
                name = excluded.name,
                server = excluded.server,
                class_name = excluded.class_name,
                character_id = excluded.character_id
            """,
            (
                participant.fight_id,
                participant.actor_id,
                participant.name,
                participant.server,
                participant.class_name,
                participant.character_id,
            ),
        )
        row = self.db.query_one(
            "SELECT id FROM fight_participants WHERE fight_id = ? AND actor_id = ?",
            (participant.fight_id, participant.actor_id),
        )
        participant.id = row["id"] if row else None
        return participant

    def participants_for_fight(self, fight_id: int) -> list[FightParticipant]:
        rows = self.db.query_all(
            "SELECT * FROM fight_participants WHERE fight_id = ? ORDER BY name COLLATE NOCASE",
            (fight_id,),
        )
        return [self._participant_row_to_model(row) for row in rows]

    def tracked_characters_for_report(self, report_id: int) -> list[Character]:
        """Distinct tracked Characters detected among this report's fights,
        ordered by how many fights they appear in (most first)."""
        rows = self.db.query_all(
            """
            SELECT c.*, COUNT(*) AS appearances
            FROM fight_participants fp
            JOIN fights f ON f.id = fp.fight_id
            JOIN characters c ON c.id = fp.character_id
            WHERE f.report_id = ?
            GROUP BY c.id
            ORDER BY appearances DESC
            """,
            (report_id,),
        )
        return [CharacterRepository._row_to_model(row) for row in rows]

    @staticmethod
    def _participant_row_to_model(row: sqlite3.Row) -> FightParticipant:
        return FightParticipant(
            id=row["id"],
            fight_id=row["fight_id"],
            actor_id=row["actor_id"],
            name=row["name"],
            server=row["server"],
            class_name=row["class_name"],
            character_id=row["character_id"],
        )

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Report:
        keys = row.keys()
        return Report(
            id=row["id"],
            report_code=row["report_code"],
            title=row["title"],
            owner_name=row["owner_name"],
            guild_name=row["guild_name"],
            zone_id=row["zone_id"],
            zone_name=row["zone_name"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            fetched_at=row["fetched_at"],
            analysis_status=row["analysis_status"],
            fight_count=row["fight_count"] if "fight_count" in keys and row["fight_count"] else 0,
            kill_count=row["kill_count"] if "kill_count" in keys and row["kill_count"] else 0,
        )


class SettingsRepository:
    """Non-secret settings, stored as JSON-encoded values keyed by name."""

    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: Any = None) -> Any:
        row = self.db.query_one("SELECT value FROM settings WHERE key = ?", (key,))
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        self.db.execute(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, json.dumps(value), _now_iso()),
        )

    def get_all(self) -> dict[str, Any]:
        rows = self.db.query_all("SELECT key, value FROM settings")
        result = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                continue
        return result


class SyncHistoryRepository:
    def __init__(self, db: Database):
        self.db = db

    def start(self, operation_type: str) -> int:
        cur = self.db.execute(
            "INSERT INTO sync_history (operation_type, status, started_at) VALUES (?, 'running', ?)",
            (operation_type, _now_iso()),
        )
        return cur.lastrowid

    def finish(
        self,
        history_id: int,
        status: str,
        reports_processed: int = 0,
        pulls_processed: int = 0,
        error_message: str | None = None,
    ) -> None:
        self.db.execute(
            """
            UPDATE sync_history
            SET status = ?, finished_at = ?, reports_processed = ?, pulls_processed = ?,
                error_message = ?
            WHERE id = ?
            """,
            (status, _now_iso(), reports_processed, pulls_processed, error_message, history_id),
        )

    def recent(self, limit: int = 20) -> list[SyncHistoryEntry]:
        rows = self.db.query_all(
            "SELECT * FROM sync_history ORDER BY started_at DESC LIMIT ?", (limit,)
        )
        return [
            SyncHistoryEntry(
                id=row["id"],
                operation_type=row["operation_type"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                reports_processed=row["reports_processed"],
                pulls_processed=row["pulls_processed"],
                error_message=row["error_message"],
            )
            for row in rows
        ]


class SessionOperationRepository:
    """Tracks app-level operations so an unclean shutdown/crash can be detected
    and surfaced on the next launch, instead of silently pretending nothing
    happened (see docs/ARCHITECTURE.md - Session Recovery)."""

    def __init__(self, db: Database):
        self.db = db

    def start(self, operation_type: str, details: str | None = None) -> int:
        cur = self.db.execute(
            "INSERT INTO session_operations (operation_type, status, started_at, details) "
            "VALUES (?, 'started', ?, ?)",
            (operation_type, _now_iso(), details),
        )
        return cur.lastrowid

    def complete(self, operation_id: int) -> None:
        self.db.execute(
            "UPDATE session_operations SET status = 'completed', finished_at = ? WHERE id = ?",
            (_now_iso(), operation_id),
        )

    def mark_unclosed_as_interrupted(self, operation_type: str | None = None) -> int:
        """Called at startup: any 'started' operation left over from a previous
        run means Ascend didn't shut down cleanly. Returns how many were found."""
        if operation_type:
            rows = self.db.query_all(
                "SELECT id FROM session_operations WHERE status = 'started' AND operation_type = ?",
                (operation_type,),
            )
        else:
            rows = self.db.query_all(
                "SELECT id FROM session_operations WHERE status = 'started'"
            )
        for row in rows:
            self.db.execute(
                "UPDATE session_operations SET status = 'interrupted', finished_at = ? WHERE id = ?",
                (_now_iso(), row["id"]),
            )
        return len(rows)

    def recent(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.query_all(
            "SELECT * FROM session_operations ORDER BY started_at DESC LIMIT ?", (limit,)
        )


class AnalysisRunRepository:
    """Records which app/analysis-engine/scoring-model versions produced a given
    analysis, so Ascend can later offer 'Reanalyze using local data' when the
    engine improves (see docs/DATA_MODEL.md). Schema-only in Phase 1 - nothing
    calls record() yet since the analysis engine itself lands in Phase 2/3."""

    def __init__(self, db: Database):
        self.db = db

    def record(
        self,
        report_id: int | None,
        character_id: int | None,
        app_version: str,
        analysis_engine_version: str,
        scoring_model_version: str,
        encounter_rule_version: str | None = None,
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO analysis_runs
                (report_id, character_id, app_version, analysis_engine_version,
                 scoring_model_version, encounter_rule_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                character_id,
                app_version,
                analysis_engine_version,
                scoring_model_version,
                encounter_rule_version,
                _now_iso(),
            ),
        )
        return cur.lastrowid

    def latest_for_report(self, report_id: int) -> sqlite3.Row | None:
        return self.db.query_one(
            "SELECT * FROM analysis_runs WHERE report_id = ? ORDER BY created_at DESC LIMIT 1",
            (report_id,),
        )


class ApiCacheRepository:
    """Preserves raw Warcraft Logs API responses (not just normalized fields),
    so analysis can be recalculated later without redownloading - see
    docs/DATA_MODEL.md (Raw Data Preservation)."""

    def __init__(self, db: Database):
        self.db = db

    def set(self, cache_key: str, response_json: str, expires_at: str | None = None) -> None:
        self.db.execute(
            """
            INSERT INTO api_cache (cache_key, response_json, fetched_at, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response_json = excluded.response_json,
                fetched_at = excluded.fetched_at,
                expires_at = excluded.expires_at
            """,
            (cache_key, response_json, _now_iso(), expires_at),
        )

    def get(self, cache_key: str) -> sqlite3.Row | None:
        return self.db.query_one("SELECT * FROM api_cache WHERE cache_key = ?", (cache_key,))

    def delete(self, cache_key: str) -> None:
        self.db.execute("DELETE FROM api_cache WHERE cache_key = ?", (cache_key,))


class GuildIconRepository:
    """Tracks where each guild's icon came from (generated fallback, a
    user-chosen local image, or - in the future - an official API), so
    Ascend never redownloads/regenerates on every launch and the user can
    refresh, clear, or replace it. See docs/ASSET_LICENSES.md."""

    def __init__(self, db: Database):
        self.db = db

    def get(self, cache_key: str) -> dict | None:
        row = self.db.query_one("SELECT * FROM guild_icons WHERE cache_key = ?", (cache_key,))
        return dict(row) if row is not None else None

    def upsert(
        self,
        cache_key: str,
        region: str | None,
        realm: str | None,
        guild_name: str | None,
        guild_id: int | None,
        source_url: str | None,
        source_type: str,
        cache_file_path: str | None,
        retrieval_status: str = "ok",
    ) -> None:
        self.db.execute(
            """
            INSERT INTO guild_icons
                (cache_key, region, realm, guild_name, guild_id, source_url,
                 source_type, cache_file_path, retrieval_status, last_retrieved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                region = excluded.region,
                realm = excluded.realm,
                guild_name = excluded.guild_name,
                guild_id = excluded.guild_id,
                source_url = excluded.source_url,
                source_type = excluded.source_type,
                cache_file_path = excluded.cache_file_path,
                retrieval_status = excluded.retrieval_status,
                last_retrieved_at = excluded.last_retrieved_at
            """,
            (
                cache_key, region, realm, guild_name, guild_id, source_url,
                source_type, cache_file_path, retrieval_status, _now_iso(),
            ),
        )

    def delete(self, cache_key: str) -> None:
        self.db.execute("DELETE FROM guild_icons WHERE cache_key = ?", (cache_key,))
