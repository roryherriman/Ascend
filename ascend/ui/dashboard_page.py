"""Dashboard page.

Ships the primary "Analyze a Raid Night" entry point (URL/code input -> basic
report retrieval) plus placeholder metric cards. Full raid-night analysis
(character detection, scoring, insights) lands in Phase 2/3 - Phase 1 only
validates the URL and performs basic report/fight retrieval.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ascend.api.client import WCLClient
from ascend.api.url_parser import InvalidReportReferenceError, build_report_url, parse_report_reference
from ascend.data.database import Database
from ascend.data.repositories import SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.sync_service import sync_report_by_code
from ascend.ui.dialogs import show_error, show_info
from ascend.ui.widgets import BackgroundTaskPanel, StatCard

STAT_DEFINITIONS: list[tuple[str, str]] = [
    ("Overall Progression Score", "Requires synced + analyzed reports (Phase 2/3)."),
    ("Current Classification", "Below Average / Average / Above Average / Strong / Standout"),
    ("Confidence", "Depends on sample size once analysis is available."),
    ("Current Guild Rank", "Set in Settings; shown here for quick reference."),
    ("Progression Pulls Analyzed", "Count of progression pulls with objective metrics."),
    ("Progression Bosses Analyzed", "Distinct progression encounters analyzed."),
    ("Raid Nights Analyzed", "Count of raid nights (reports) analyzed."),
    ("Attendance / Participation", "Requires guild roster + report sync (Phase 2)."),
    ("First-Death %", "Requires death event ingestion (Phase 3)."),
    ("Confirmed Avoidable Failure Rate", "Requires encounter rules + death review (Phase 3/4)."),
    ("Median Roster-Relative Performance", "Requires roster comparison data (Phase 2)."),
    ("Damage Consistency", "Requires pull-to-pull damage analysis (Phase 2/3)."),
    ("Learning-Speed Rating", "Requires trend analysis across pulls (Phase 3)."),
    ("Strongest Category", "Derived from scoring category breakdown (Phase 3/4)."),
    ("Biggest Improvement Area", "Derived from scoring category breakdown (Phase 3/4)."),
]

RECENT_URLS_SETTING_KEY = "recent_report_urls"
MAX_RECENT_URLS = 5


class DashboardPage(QWidget):
    open_reports_requested = Signal()

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
        self._active_task = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        outer_layout.addWidget(title)

        outer_layout.addWidget(self._build_analyze_card())

        subtitle = QLabel(
            "No performance data has been analyzed yet. Add characters and analyze a raid "
            "night to begin - full scoring, classification, and charts are built out in later phases."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        outer_layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        grid_container = QWidget()
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(0, 16, 0, 0)
        grid.setSpacing(12)

        columns = 3
        self.cards: dict[str, StatCard] = {}
        for index, (title_text, subtext) in enumerate(STAT_DEFINITIONS):
            card = StatCard(title_text, "--", subtext)
            self.cards[title_text] = card
            grid.addWidget(card, index // columns, index % columns)

        for col in range(columns):
            grid.setColumnStretch(col, 1)

        scroll.setWidget(grid_container)
        outer_layout.addWidget(scroll, stretch=1)

        charts_note = QLabel(
            "Charts (score over time, death rate, first-death rate, progression DPS "
            "consistency, priority-target damage, Mage vs. Warlock, progression vs. farm) "
            "will appear here once report analysis is implemented in Phase 2/3."
        )
        charts_note.setProperty("class", "muted")
        charts_note.setWordWrap(True)
        charts_note.setAlignment(Qt.AlignmentFlag.AlignLeft)
        outer_layout.addWidget(charts_note)

    def _build_analyze_card(self) -> QGroupBox:
        card = QGroupBox("Analyze a Raid Night")
        layout = QVBoxLayout(card)

        note = QLabel(
            "Phase 1 validates the URL and retrieves/stores the report and its pulls. "
            "Full analysis (character detection, scoring, insights) arrives in Phase 2/3."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        input_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste a Warcraft Logs report URL or report code...")
        self.url_edit.returnPressed.connect(self._on_analyze_clicked)
        input_row.addWidget(self.url_edit, stretch=1)

        paste_button = QPushButton("Paste from Clipboard")
        paste_button.clicked.connect(self._on_paste_clicked)
        input_row.addWidget(paste_button)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(lambda: self.url_edit.clear())
        input_row.addWidget(clear_button)

        layout.addLayout(input_row)

        actions_row = QHBoxLayout()
        self.recent_combo = QComboBox()
        self.recent_combo.setMinimumWidth(220)
        self._reload_recent_urls()
        self.recent_combo.activated.connect(self._on_recent_selected)
        actions_row.addWidget(QLabel("Recent:"))
        actions_row.addWidget(self.recent_combo)
        actions_row.addStretch()

        self.analyze_button = QPushButton("Analyze Entire Report")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        actions_row.addWidget(self.analyze_button)

        self.open_browser_button = QPushButton("Open in Browser")
        self.open_browser_button.clicked.connect(self._on_open_browser_clicked)
        actions_row.addWidget(self.open_browser_button)

        layout.addLayout(actions_row)

        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.clicked.connect(self._on_cancel)
        layout.addWidget(self.task_panel)

        return card

    def _reload_recent_urls(self) -> None:
        recent = self.settings_repo.get(RECENT_URLS_SETTING_KEY, [])
        self.recent_combo.clear()
        self.recent_combo.addItem("")
        for url in recent:
            self.recent_combo.addItem(url)

    def _remember_recent_url(self, raw_input: str) -> None:
        recent = self.settings_repo.get(RECENT_URLS_SETTING_KEY, [])
        recent = [raw_input] + [u for u in recent if u != raw_input]
        recent = recent[:MAX_RECENT_URLS]
        self.settings_repo.set(RECENT_URLS_SETTING_KEY, recent)
        self._reload_recent_urls()

    def _on_recent_selected(self, index: int) -> None:
        text = self.recent_combo.itemText(index)
        if text:
            self.url_edit.setText(text)

    def _on_paste_clicked(self) -> None:
        clipboard_text = QApplication.clipboard().text()
        if clipboard_text:
            self.url_edit.setText(clipboard_text.strip())

    def _parse_current_input(self):
        raw = self.url_edit.text().strip()
        try:
            return raw, parse_report_reference(raw)
        except InvalidReportReferenceError as exc:
            show_error(self, "Invalid report URL or code", str(exc))
            return raw, None

    def _on_open_browser_clicked(self) -> None:
        raw, parsed = self._parse_current_input()
        if parsed is None:
            return
        QDesktopServices.openUrl(QUrl(build_report_url(parsed.report_code, parsed.fight)))

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

    def _on_analyze_clicked(self) -> None:
        raw, parsed = self._parse_current_input()
        if parsed is None:
            return
        client = self._build_client()
        if client is None:
            return

        self._remember_recent_url(raw)
        self.analyze_button.setEnabled(False)
        self.task_panel.start(f"Fetching report {parsed.report_code}...")

        task = self.task_manager.submit(sync_report_by_code, self.db, client, parsed.report_code)
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_finished)
        task.signals.error.connect(self._on_error)
        task.signals.cancelled.connect(self._on_cancelled)

    def _on_finished(self, report) -> None:
        self.analyze_button.setEnabled(True)
        self._active_task = None
        if report is None:
            self.task_panel.reset()
            return
        self.task_panel.finish(f"Retrieved report {report.report_code}.")
        show_info(
            self, "Report retrieved",
            f"'{report.title or report.report_code}' was retrieved and stored. "
            "Open the Reports page to view it.",
        )
        self.open_reports_requested.emit()

    def _on_error(self, message: str) -> None:
        self.analyze_button.setEnabled(True)
        self._active_task = None
        self.task_panel.reset()
        if "ReportCodeNotFoundError" in message:
            message = message.split(":", 1)[-1].strip()
        show_error(self, "Could not retrieve report", message)

    def _on_cancelled(self) -> None:
        self.analyze_button.setEnabled(True)
        self._active_task = None
        self.task_panel.finish("Cancelled.")

    def _on_cancel(self) -> None:
        if self._active_task is not None:
            self._active_task.cancel()
