"""Seeds Demo Mode with sanitized bundled fixture data.

Demo Mode always uses its own separate SQLite database (see
ascend/data/database.py - default_path_instance), so this never touches real
user data. It exists so the GUI and analysis workflow can be explored without
Warcraft Logs credentials.
"""
from __future__ import annotations

import json
from pathlib import Path

from ascend.data.database import Database
from ascend.data.repositories import ReportRepository
from ascend.services.background_worker import CancellationToken
from ascend.services.sync_service import sync_report_by_code

_DEMO_REPORT_PATH = Path(__file__).resolve().parent.parent / "resources" / "demo_report.json"


class _DemoClient:
    """Stands in for WCLClient in Demo Mode: returns bundled fixture data, no network access."""

    def __init__(self, report: dict):
        self._report = report

    def fetch_report_by_code(self, _report_code: str):
        return self._report


def _noop_progress(_percent: int, _message: str) -> None:
    pass


def ensure_demo_report_seeded(db: Database) -> None:
    """Idempotently loads the bundled demo report into a Demo Mode database."""
    report = json.loads(_DEMO_REPORT_PATH.read_text(encoding="utf-8"))
    if ReportRepository(db).get_by_code(report["code"]) is not None:
        return
    sync_report_by_code(
        _noop_progress, CancellationToken(), db, _DemoClient(report), report["code"]
    )
