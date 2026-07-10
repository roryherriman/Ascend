"""SQLite database wrapper for Ascend.

A single Database instance is shared across the GUI thread and background
worker threads. SQLite connections are not thread-safe by default, so all
access is serialized through an internal lock - simple and safe for a
single-user desktop app at this scale.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from ascend.data.migrations import apply_migrations

APP_DIR_NAME = "Ascend"


def default_app_data_root() -> Path:
    """Root folder for all app data, following Windows conventions.

    Falls back to a local ``.ascend_data`` folder next to the app if
    ``LOCALAPPDATA`` is not set (e.g. on non-Windows dev machines).
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


def load_bootstrap_config(app_data_root: Path) -> dict:
    """Load (or create) the tiny bootstrap config that points at the data/export folders.

    This lives outside the SQLite database on purpose: the app needs to know
    where the database file is *before* it can open the database.
    """
    app_data_root.mkdir(parents=True, exist_ok=True)
    config_path = app_data_root / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    defaults = {
        "data_dir": str(app_data_root),
        "export_dir": str(app_data_root / "exports"),
    }
    config_path.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
    return defaults


def save_bootstrap_config(app_data_root: Path, config: dict) -> None:
    app_data_root.mkdir(parents=True, exist_ok=True)
    (app_data_root / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    @classmethod
    def default_path_instance(cls) -> "Database":
        app_data_root = default_app_data_root()
        config = load_bootstrap_config(app_data_root)
        data_dir = Path(config.get("data_dir", str(app_data_root)))
        data_dir.mkdir(parents=True, exist_ok=True)
        # Demo Mode uses a completely separate database file so demo and real
        # data can never mix (see docs/ARCHITECTURE.md - Demo Mode).
        db_filename = "ascend_demo.db" if config.get("demo_mode") else "ascend.db"
        return cls(data_dir / db_filename)

    def initialize(self) -> int:
        """Open the connection and bring the schema up to date. Returns schema version."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.row_factory = sqlite3.Row
            return apply_migrations(self._conn)

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database.initialize() must be called before use")
        return self._conn

    @property
    def is_open(self) -> bool:
        return self._conn is not None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.connection.execute(sql, tuple(params))
            self.connection.commit()
            return cur

    def executemany(self, sql: str, seq_of_params: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
        with self._lock:
            cur = self.connection.executemany(sql, [tuple(p) for p in seq_of_params])
            self.connection.commit()
            return cur

    def query_all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.connection.execute(sql, tuple(params)).fetchall())

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(sql, tuple(params)).fetchone()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
