"""Death Review - fetches and displays Warcraft Logs' Deaths table for a
raid night.

WCL does not publish a GraphQL type for Report.table's contents (see
ascend/api/graphql_queries.py's DEATH_TABLE_QUERY docstring) - the payload
shape is undocumented and explicitly marked "not considered frozen." Rather
than guess at field names and risk mislabeling data, this page shows the
raw fetched JSON as evidence. A structured death timeline, manual
avoidable/unavoidable classification, and repeated-cause tracking (the rest
of this page's Phase 3 roadmap scope) land in a follow-up once the payload
shape has been empirically verified against real API responses.
"""
from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ascend.api.client import WCLClient
from ascend.data.database import Database
from ascend.data.repositories import ReportRepository, SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.death_data import fetch_death_table_task, get_cached_death_table
from ascend.theme import apply_card_elevation
from ascend.ui.components import AscendEmptyState
from ascend.ui.dialogs import show_error
from ascend.ui.widgets import BackgroundTaskPanel


class DeathReviewPage(QWidget):
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
        self.settings_repo = SettingsRepository(db)
        self.reports_repo = ReportRepository(db)
        self._reports = []
        self._active_task = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(14)

        title = QLabel("Death Review")
        title.setObjectName("pageTitle")
        self._layout.addWidget(title)

        subtitle = QLabel(
            "Warcraft Logs doesn't publish a fixed schema for death data, so this shows the raw "
            "evidence as returned rather than guessing at a structure. A classified death "
            "timeline arrives once that shape is verified against real responses."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        self._layout.addWidget(subtitle)

        self._picker_row = QHBoxLayout()
        picker_label = QLabel("Raid Night:")
        picker_label.setProperty("class", "muted")
        self._picker_row.addWidget(picker_label)
        self.report_combo = QComboBox()
        self.report_combo.setMinimumWidth(320)
        self.report_combo.currentIndexChanged.connect(self._on_report_selected)
        self._picker_row.addWidget(self.report_combo)

        self.fetch_button = QPushButton("Fetch Death Data")
        self.fetch_button.setObjectName("primaryButton")
        self.fetch_button.clicked.connect(self._on_fetch_clicked)
        self._picker_row.addWidget(self.fetch_button)
        self._picker_row.addStretch()
        self._layout.addLayout(self._picker_row)

        self.empty_state: AscendEmptyState | None = None
        self.detail_container = self._build_detail_panel()
        self._layout.addWidget(self.detail_container, stretch=1)

        self.reload()

    def _build_detail_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.setEnabled(False)
        layout.addWidget(self.task_panel)

        self.raw_data_view = QPlainTextEdit()
        self.raw_data_view.setReadOnly(True)
        self.raw_data_view.setPlaceholderText(
            "No death data fetched for this raid night yet - click Fetch Death Data."
        )
        layout.addWidget(self.raw_data_view, stretch=1)

        return card

    # -- Data -----------------------------------------------------------

    def reload(self) -> None:
        self._reports = self.reports_repo.list_all()
        self._show_empty_state(not self._reports)
        if not self._reports:
            return

        self.report_combo.blockSignals(True)
        self.report_combo.clear()
        for report in self._reports:
            self.report_combo.addItem(report.title or report.report_code, userData=report.id)
        self.report_combo.blockSignals(False)
        self._refresh_view()

    def _show_empty_state(self, empty: bool) -> None:
        self.detail_container.setVisible(not empty)
        for i in range(self._picker_row.count()):
            widget = self._picker_row.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(not empty)
        if empty and self.empty_state is None:
            self.empty_state = AscendEmptyState(
                title="No Raid Nights Yet",
                description="Analyze a Warcraft Logs report to fetch and review its death data here.",
                icon_name="deaths",
            )
            self._layout.addWidget(self.empty_state, stretch=1)
        if self.empty_state is not None:
            self.empty_state.setVisible(empty)

    def _current_report(self):
        report_id = self.report_combo.currentData()
        return next((r for r in self._reports if r.id == report_id), None)

    def _on_report_selected(self, _index: int) -> None:
        self._refresh_view()

    def _refresh_view(self) -> None:
        report = self._current_report()
        if report is None:
            self.raw_data_view.setPlainText("")
            return
        cached = get_cached_death_table(self.db, report.report_code)
        self.raw_data_view.setPlainText(json.dumps(cached, indent=2) if cached is not None else "")

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

    def _on_fetch_clicked(self) -> None:
        report = self._current_report()
        if report is None:
            return
        client = self._build_client()
        if client is None:
            return

        fight_ids = [f.fight_id for f in self.reports_repo.fights_for_report(report.id)]
        self.fetch_button.setEnabled(False)
        self.task_panel.start(f"Fetching death data for {report.title or report.report_code}...")

        task = self.task_manager.submit(
            fetch_death_table_task, self.db, client, report.report_code, fight_ids
        )
        self._active_task = task
        task.signals.finished.connect(self._on_fetch_finished)
        task.signals.error.connect(self._on_fetch_error)

    def _on_fetch_finished(self, payload) -> None:
        self.fetch_button.setEnabled(True)
        self._active_task = None
        self.task_panel.finish("Done.")
        self.raw_data_view.setPlainText(json.dumps(payload, indent=2) if payload is not None else "(empty response)")

    def _on_fetch_error(self, message: str) -> None:
        self.fetch_button.setEnabled(True)
        self._active_task = None
        self.task_panel.reset()
        show_error(self, "Could not fetch death data", message)
