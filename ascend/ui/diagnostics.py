"""Diagnostics page - surfaces app/db/environment health for troubleshooting.

Never displays secrets: only whether secure credential storage is working and
which backend it's using (see ascend/data/secure_storage.py).

Developer Tools section (fixture export/import) is only for development use.
Sanitized fixtures strip credentials, replace player/guild names, and hash
report codes - see ascend/services/fixture_sanitizer.py for details.
"""
from __future__ import annotations

import json
import platform
import sqlite3
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ascend import metadata
from ascend.data.database import Database, default_app_data_root, load_bootstrap_config
from ascend.data.migrations import current_version
from ascend.data.repositories import SessionOperationRepository, SyncHistoryRepository
from ascend.data.secure_storage import SecureStorage


class DiagnosticsPage(QWidget):
    def __init__(self, db: Database, secure_storage: SecureStorage, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.secure_storage = secure_storage

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Diagnostics")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        group = QGroupBox("System Information")
        form = QFormLayout(group)

        app_root = default_app_data_root()
        config = load_bootstrap_config(app_root)

        self._values = {
            "Application": f"{metadata.APP_NAME} v{metadata.APP_VERSION} (build {metadata.BUILD_NUMBER})",
            "Analysis engine version": metadata.ANALYSIS_ENGINE_VERSION,
            "Scoring model version": metadata.SCORING_MODEL_VERSION,
            "Database schema version": str(self._db_schema_version()),
            "Python version": platform.python_version(),
            "Operating system": platform.platform(),
            "Data directory": config.get("data_dir", str(app_root)),
            "Log directory": str(app_root / "logs"),
            "Database health": self._db_health(),
            "Credential storage": self._credential_status_text(),
            "Last sync attempt": self._last_sync_text(),
            "Unclosed sessions (crash indicator)": self._unclosed_sessions_text(),
        }
        self._value_labels: dict[str, QLabel] = {}
        for key, value in self._values.items():
            label = QLabel(value)
            label.setWordWrap(True)
            self._value_labels[key] = label
            form.addRow(f"{key}:", label)

        layout.addWidget(group)

        buttons_row = QWidget()
        from PySide6.QtWidgets import QHBoxLayout

        buttons_layout = QHBoxLayout(buttons_row)
        buttons_layout.setContentsMargins(0, 12, 0, 0)

        copy_button = QPushButton("Copy Diagnostics")
        copy_button.clicked.connect(self._on_copy_diagnostics)
        buttons_layout.addWidget(copy_button)

        open_logs_button = QPushButton("Open Logs Folder")
        open_logs_button.clicked.connect(self._on_open_logs_folder)
        buttons_layout.addWidget(open_logs_button)
        buttons_layout.addStretch()

        layout.addWidget(buttons_row)

        layout.addWidget(self._build_dev_tools_section())
        layout.addStretch()

    def _db_schema_version(self) -> int:
        try:
            return current_version(self.db.connection)
        except Exception:  # noqa: BLE001
            return 0

    def _db_health(self) -> str:
        try:
            row = self.db.query_one("SELECT 1")
            return "OK" if row is not None else "Unknown"
        except sqlite3.Error as exc:
            return f"Error: {exc}"

    def _credential_status_text(self) -> str:
        status = self.secure_storage.status()
        return f"{status['backend']}" + (
            f" (fallback reason: {status['reason']})" if status["using_fallback"] else ""
        )

    def _last_sync_text(self) -> str:
        recent = SyncHistoryRepository(self.db).recent(limit=1)
        if not recent:
            return "No sync attempts yet."
        entry = recent[0]
        return f"{entry.started_at} - {entry.status}"

    def _unclosed_sessions_text(self) -> str:
        interrupted = [
            row for row in SessionOperationRepository(self.db).recent(limit=20)
            if row["status"] == "interrupted"
        ]
        if not interrupted:
            return "None detected."
        return f"{len(interrupted)} interrupted session(s) detected (possible past crash)."

    def _on_copy_diagnostics(self) -> None:
        lines = [f"{key}: {value}" for key, value in self._values.items()]
        QApplication.clipboard().setText("\n".join(lines))

    def _on_open_logs_folder(self) -> None:
        log_dir = Path(self._values["Log directory"])
        log_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))

    # -- Developer Tools -------------------------------------------------------

    def _build_dev_tools_section(self) -> QGroupBox:
        group = QGroupBox("Developer Tools — Sanitized API Fixture Export/Import")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        warning = QLabel(
            "DEVELOPER ONLY — For building and testing the death-event parser without "
            "real credentials. Exported fixtures replace player/guild names, hash report "
            "codes, redact tokens, and shift timestamps. Review the output before sharing. "
            "Do not use these functions on production data you can't verify."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #e0a020; font-size: 11px;")
        layout.addWidget(warning)

        # Export
        export_group = QWidget()
        export_layout = QVBoxLayout(export_group)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(6)

        export_label = QLabel("Paste raw Warcraft Logs JSON response to sanitize and export as a fixture file:")
        export_label.setWordWrap(True)
        export_layout.addWidget(export_label)

        endpoint_row = QHBoxLayout()
        endpoint_lbl = QLabel("Source endpoint:")
        endpoint_lbl.setFixedWidth(130)
        endpoint_row.addWidget(endpoint_lbl)
        self._endpoint_input = QLineEdit()
        self._endpoint_input.setPlaceholderText("e.g. reportData.report.events")
        endpoint_row.addWidget(self._endpoint_input)
        export_layout.addLayout(endpoint_row)

        self._fixture_input = QLineEdit()
        self._fixture_input.setPlaceholderText("Paste raw JSON here…")
        self._fixture_input.setMinimumHeight(36)
        export_layout.addWidget(self._fixture_input)

        self._export_status = QLabel("")
        self._export_status.setWordWrap(True)
        self._export_status.setStyleSheet("font-size: 11px;")

        export_btn = QPushButton("Export Sanitized Fixture…")
        export_btn.clicked.connect(self._on_export_fixture)
        export_layout.addWidget(export_btn)
        export_layout.addWidget(self._export_status)
        layout.addWidget(export_group)

        # Import
        import_row = QHBoxLayout()
        import_btn = QPushButton("Load Fixture for Inspection…")
        import_btn.clicked.connect(self._on_load_fixture)
        import_row.addWidget(import_btn)
        import_row.addStretch()
        self._import_status = QLabel("")
        self._import_status.setWordWrap(True)
        self._import_status.setStyleSheet("font-size: 11px;")
        import_row.addWidget(self._import_status)
        layout.addLayout(import_row)

        return group

    def _on_export_fixture(self) -> None:
        from ascend.services.fixture_sanitizer import export_fixture_json

        raw = self._fixture_input.text().strip()
        if not raw:
            self._export_status.setText("Paste a JSON payload into the field above first.")
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._export_status.setText(f"Invalid JSON: {exc}")
            return

        endpoint = self._endpoint_input.text().strip() or "unknown"
        fixture_json = export_fixture_json(payload, source_endpoint=endpoint)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sanitized Fixture",
            "ascend_fixture.json",
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            Path(path).write_text(fixture_json, encoding="utf-8")
            self._export_status.setText(f"Saved: {path}")
        except OSError as exc:
            self._export_status.setText(f"Save failed: {exc}")

    def _on_load_fixture(self) -> None:
        from ascend.services.fixture_sanitizer import load_fixture

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Sanitized Fixture",
            "",
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            payload = load_fixture(path)
            keys = list(payload.keys()) if isinstance(payload, dict) else ["(list)"]
            self._import_status.setText(
                f"Loaded OK — top-level keys: {', '.join(str(k) for k in keys[:8])}"
            )
        except (ValueError, OSError) as exc:
            self._import_status.setText(f"Load failed: {exc}")
