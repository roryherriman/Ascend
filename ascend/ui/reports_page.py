"""Reports page - searchable report table, report-code entry, and basic retrieval.

Bulk discovery, multi-report sync, and analysis are added in Phase 2/3; their
buttons are present (per the full spec) but disabled with a tooltip explaining
when they arrive, rather than faking functionality that isn't built yet.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ascend.api.client import WCLClient
from ascend.data.database import Database
from ascend.data.models import Report
from ascend.data.repositories import ReportRepository, SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.sync_service import sync_report_by_code
from ascend.ui.dialogs import ReportCodeDialog, confirm, show_error, show_info
from ascend.ui.widgets import BackgroundTaskPanel

COLUMNS = [
    "Title", "Code", "Guild / Owner", "Date", "Encounter(s)", "Difficulty",
    "Pulls", "Kill / Progression", "Character", "Spec", "Analysis Status",
]


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return ""
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (OSError, OverflowError, ValueError):
        return ""


class ReportsPage(QWidget):
    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.secure_storage = secure_storage
        self.task_manager = task_manager
        self.repo = ReportRepository(db)
        self.settings_repo = SettingsRepository(db)
        self._reports: list[Report] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Reports")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search reports...")
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_edit, stretch=1)

        self.discover_button = QPushButton("Discover Reports")
        self.discover_button.setEnabled(False)
        self.discover_button.setToolTip("Available in Phase 2 (guild/user report discovery).")
        toolbar.addWidget(self.discover_button)

        self.add_code_button = QPushButton("Add Report Code")
        self.add_code_button.setObjectName("primaryButton")
        self.add_code_button.clicked.connect(self._on_add_report_code)
        toolbar.addWidget(self.add_code_button)

        self.sync_selected_button = QPushButton("Sync Selected")
        self.sync_selected_button.setEnabled(False)
        self.sync_selected_button.setToolTip("Available in Phase 2 (bulk sync).")
        toolbar.addWidget(self.sync_selected_button)

        self.sync_all_button = QPushButton("Sync All")
        self.sync_all_button.setEnabled(False)
        self.sync_all_button.setToolTip("Available in Phase 2 (bulk sync).")
        toolbar.addWidget(self.sync_all_button)

        self.analyze_button = QPushButton("Analyze Selected")
        self.analyze_button.setEnabled(False)
        self.analyze_button.setToolTip("Available in Phase 2/3 (pull-level analysis).")
        toolbar.addWidget(self.analyze_button)

        self.delete_button = QPushButton("Delete Local Data")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self._on_delete_local_data)
        toolbar.addWidget(self.delete_button)

        self.open_wcl_button = QPushButton("Open on Warcraft Logs")
        self.open_wcl_button.clicked.connect(self._on_open_on_wcl)
        toolbar.addWidget(self.open_wcl_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.clicked.connect(self._on_cancel_sync)
        layout.addWidget(self.task_panel)

        self._active_task = None
        self.reload()

    def reload(self) -> None:
        self._reports = self.repo.list_all()
        self._populate_table(self._reports)

    def _populate_table(self, reports: list[Report]) -> None:
        self.table.setRowCount(len(reports))
        for row, report in enumerate(reports):
            fights = self.repo.fights_for_report(report.id) if report.id else []
            encounter_names = sorted({f.name for f in fights if f.name})
            kills = sum(1 for f in fights if f.kill)
            wipes = sum(1 for f in fights if f.kill is False)
            values = [
                report.title or "",
                report.report_code,
                report.guild_name or report.owner_name or "",
                _format_date(report.start_time),
                ", ".join(encounter_names) if encounter_names else "",
                "",  # Difficulty varies per fight; shown in Encounter Analysis (Phase 2)
                str(len(fights)),
                f"{kills} kill / {wipes} wipe" if fights else "",
                "",  # Character mapping arrives with Phase 2 analysis
                "",  # Spec mapping arrives with Phase 2 analysis
                report.analysis_status.replace("_", " ").title(),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, report.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, report.report_code)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

    def _apply_filter(self, text: str) -> None:
        text = text.strip().lower()
        if not text:
            self._populate_table(self._reports)
            return
        filtered = [
            r for r in self._reports
            if text in (r.title or "").lower()
            or text in r.report_code.lower()
            or text in (r.guild_name or "").lower()
            or text in (r.owner_name or "").lower()
        ]
        self._populate_table(filtered)

    def _selected_report(self) -> Report | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        report_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        for report in self._reports:
            if report.id == report_id:
                return report
        return None

    def _build_client(self) -> WCLClient | None:
        client_id = self.settings_repo.get("wcl_client_id", "")
        client_secret = self.secure_storage.get_client_secret() or ""
        timeout = self.settings_repo.get("api_timeout_seconds", 15)
        if not client_id or not client_secret:
            show_error(
                self, "Warcraft Logs credentials not set",
                "Enter your Warcraft Logs client ID and client secret in Settings first.",
            )
            return None
        return WCLClient(client_id, client_secret, timeout_seconds=float(timeout))

    def _on_add_report_code(self) -> None:
        dialog = ReportCodeDialog(self)
        if not dialog.exec():
            return
        code = dialog.report_code()
        client = self._build_client()
        if client is None:
            return

        self.add_code_button.setEnabled(False)
        self.task_panel.start(f"Fetching report {code}...")

        task = self.task_manager.submit(sync_report_by_code, self.db, client, code)
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(lambda result: self._on_sync_finished(result))
        task.signals.error.connect(self._on_sync_error)
        task.signals.cancelled.connect(self._on_sync_cancelled)

    def _on_sync_finished(self, report: Report | None) -> None:
        self.add_code_button.setEnabled(True)
        self._active_task = None
        if report is None:
            self.task_panel.reset()
            return
        self.task_panel.finish(f"Synced report {report.report_code}.")
        self.reload()
        show_info(self, "Report synced", f"'{report.title or report.report_code}' was synced successfully.")

    def _on_sync_error(self, message: str) -> None:
        self.add_code_button.setEnabled(True)
        self._active_task = None
        self.task_panel.reset()
        if "ReportCodeNotFoundError" in message:
            message = message.split(":", 1)[-1].strip()
        show_error(self, "Could not sync report", message)

    def _on_sync_cancelled(self) -> None:
        self.add_code_button.setEnabled(True)
        self._active_task = None
        self.task_panel.finish("Sync cancelled.")

    def _on_cancel_sync(self) -> None:
        if self._active_task is not None:
            self._active_task.cancel()

    def _on_delete_local_data(self) -> None:
        report = self._selected_report()
        if report is None:
            show_error(self, "No selection", "Select a report to delete first.")
            return
        if confirm(
            self, "Delete local data",
            f"Delete all locally stored data for report '{report.title or report.report_code}'? "
            "This only removes local data; nothing is changed on Warcraft Logs.",
        ):
            self.repo.delete_report(report.id)
            self.reload()

    def _on_open_on_wcl(self) -> None:
        report = self._selected_report()
        if report is None:
            show_error(self, "No selection", "Select a report first.")
            return
        QDesktopServices.openUrl(QUrl(f"https://www.warcraftlogs.com/reports/{report.report_code}"))
