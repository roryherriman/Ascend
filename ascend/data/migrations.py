"""Versioned SQLite schema migrations.

Each migration is a (version, description, sql) tuple. Migrations are applied
in order, inside a transaction, and the applied version is recorded in the
``schema_version`` table so the app can detect what still needs to run on a
later startup. New phases add new migrations here rather than editing old
ones, so existing installs upgrade in place.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str


MIGRATIONS: list[Migration] = [
    Migration(
        version=1,
        description="Phase 1: characters, reports, fights, settings, sync history, api cache",
        sql="""
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            character_name TEXT NOT NULL,
            region TEXT NOT NULL,
            server TEXT NOT NULL,
            wcl_character_id INTEGER,
            class TEXT,
            character_role TEXT NOT NULL DEFAULT 'primary'
                CHECK (character_role IN ('primary', 'alternate')),
            enabled INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (region, server, character_name)
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_code TEXT NOT NULL UNIQUE,
            title TEXT,
            owner_name TEXT,
            guild_name TEXT,
            zone_id INTEGER,
            zone_name TEXT,
            start_time REAL,
            end_time REAL,
            fetched_at TEXT,
            analysis_status TEXT NOT NULL DEFAULT 'not_analyzed'
        );

        CREATE TABLE IF NOT EXISTS fights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            fight_id INTEGER NOT NULL,
            name TEXT,
            encounter_id INTEGER,
            difficulty INTEGER,
            kill INTEGER,
            start_time REAL,
            end_time REAL,
            UNIQUE (report_id, fight_id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            reports_processed INTEGER NOT NULL DEFAULT 0,
            pulls_processed INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS api_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL UNIQUE,
            response_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            expires_at TEXT
        );
        """,
    ),
    Migration(
        version=2,
        description=(
            "Ascend rebrand: session-operation tracking + analysis-versioning schema "
            "(supporting raw-data preservation and future reanalysis)"
        ),
        sql="""
        CREATE TABLE IF NOT EXISTS session_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'started'
                CHECK (status IN ('started', 'completed', 'interrupted')),
            started_at TEXT NOT NULL,
            finished_at TEXT,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
            character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
            app_version TEXT NOT NULL,
            analysis_engine_version TEXT NOT NULL,
            scoring_model_version TEXT NOT NULL,
            encounter_rule_version TEXT,
            created_at TEXT NOT NULL
        );
        """,
    ),
    Migration(
        version=3,
        description="Guild icon cache (World of Warcraft visual integration)",
        sql="""
        CREATE TABLE IF NOT EXISTS guild_icons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL UNIQUE,
            region TEXT,
            realm TEXT,
            guild_name TEXT,
            guild_id INTEGER,
            source_url TEXT,
            source_type TEXT NOT NULL DEFAULT 'generated_fallback'
                CHECK (source_type IN ('generated_fallback', 'custom_local', 'official_api')),
            cache_file_path TEXT,
            retrieval_status TEXT NOT NULL DEFAULT 'ok',
            last_retrieved_at TEXT NOT NULL
        );
        """,
    ),
    Migration(
        version=4,
        description="Phase 2: fight participants (character detection)",
        sql="""
        CREATE TABLE IF NOT EXISTS fight_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fight_id INTEGER NOT NULL REFERENCES fights(id) ON DELETE CASCADE,
            actor_id INTEGER NOT NULL,
            name TEXT,
            server TEXT,
            class_name TEXT,
            character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
            UNIQUE (fight_id, actor_id)
        );

        CREATE INDEX IF NOT EXISTS idx_fight_participants_character
            ON fight_participants(character_id);
        """,
    ),
    Migration(
        version=5,
        description="Phase 2: manual report annotations",
        sql="""
        ALTER TABLE reports ADD COLUMN notes TEXT;
        """,
    ),
    Migration(
        version=6,
        description="Productization PR D: spec_role on characters (tank/healer/ranged/melee)",
        sql="""
        ALTER TABLE characters ADD COLUMN spec_role TEXT
            CHECK (spec_role IN ('tank', 'healer', 'ranged', 'melee') OR spec_role IS NULL);
        """,
    ),
    Migration(
        version=7,
        description="First-release fixes: app_state for setup lifecycle, guild verification columns",
        sql="""
        CREATE TABLE IF NOT EXISTS app_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            setup_state TEXT NOT NULL DEFAULT 'not_started'
                CHECK (setup_state IN ('not_started', 'in_progress', 'completed', 'reset_required')),
            setup_completed_at TEXT,
            setup_version INTEGER NOT NULL DEFAULT 1,
            last_reset_at TEXT
        );

        INSERT OR IGNORE INTO app_state (id, setup_state)
            SELECT 1,
                CASE WHEN EXISTS (
                    SELECT 1 FROM settings
                    WHERE key = 'first_run_completed' AND value = 'true'
                ) THEN 'completed' ELSE 'not_started' END;
        """,
    ),
]


def current_version(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if cur.fetchone() is None:
        return 0
    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    return row[0] if row else 0


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply any migrations newer than the current schema version.

    Returns the resulting schema version.
    """
    version = current_version(conn)
    for migration in sorted(MIGRATIONS, key=lambda m: m.version):
        if migration.version <= version:
            continue
        with conn:
            conn.executescript(migration.sql)
            conn.execute(
                "INSERT INTO schema_version (id, version) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET version = excluded.version",
                (migration.version,),
            )
        version = migration.version
    return version
