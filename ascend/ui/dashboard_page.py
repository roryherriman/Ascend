"""Dashboard page - the visual showcase of Ascend.

Ships the primary "Analyze a Raid Night" entry point (URL/code input -> basic
report retrieval), a hero row (score/character/guild-rank), key metric
cards, a recent-raid-nights table, strengths/improvement panels, and trend
chart placeholders. Full raid-night analysis (character detection, scoring,
insights) lands in Phase 2/3 - Phase 1 only validates the URL and performs
basic report/fight retrieval; everything analysis-shaped is intentionally
shown as "--" or an empty state rather than invented.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ascend.api.client import WCLClient
from ascend.api.url_parser import InvalidReportReferenceError, build_report_url, parse_report_reference
from ascend.data.database import Database
from ascend.data.repositories import ReportRepository, SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.guild_icon_service import get_guild_badge_pixmap
from ascend.services.sync_service import sync_report_by_code
from ascend.theme import apply_card_elevation
from ascend.ui.class_icons import class_color, class_icon
from ascend.ui.dialogs import show_error, show_info
from ascend.ui.icons import icon
from ascend.ui.widgets import BackgroundTaskPanel, InfoCard, MetricCard, make_badge

KEY_METRICS: list[tuple[str, str]] = [
    ("Progression Pulls Analyzed", "Count of progression pulls with objective metrics."),
    ("Progression Bosses Analyzed", "Distinct progression encounters analyzed."),
    ("Raid Nights Analyzed", "Count of raid nights (reports) analyzed."),
    ("Attendance / Participation", "Requires guild roster + report sync (Phase 2)."),
    ("First-Death %", "Requires death event ingestion (Phase 3)."),
    ("Confirmed Avoidable Failure Rate", "Requires encounter rules + death review (Phase 3/4)."),
    ("Median Roster-Relative Performance", "Requires roster comparison data (Phase 2)."),
    ("Damage Consistency", "Requires pull-to-pull damage analysis (Phase 2/3)."),
    ("Learning-Speed Rating", "Requires trend analysis across pulls (Phase 3)."),
]

CHART_PLACEHOLDERS = [
    ("Score Over Time", "trends"),
    ("Death Rate Over Time", "deaths"),
    ("Priority-Target Damage", "encounter"),
    ("Progression vs. Farm", "encounter_progression"),
]

RECENT_URLS_SETTING_KEY = "recent_report_urls"
MAX_RECENT_URLS = 5


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return "--"
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return "--"


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
        self.reports_repo = ReportRepository(db)
        self._active_task = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(24, 20, 24, 0)
        outer_layout.setSpacing(8)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        description = QLabel("How am I performing? Start here.")
        description.setObjectName("pageDescription")
        header.addWidget(description)
        outer_layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 12, 4, 24)
        content_layout.setSpacing(16)

        content_layout.addWidget(self._build_analyze_card())
        content_layout.addLayout(self._build_hero_row())
        content_layout.addWidget(self._build_key_metrics())
        content_layout.addLayout(self._build_middle_row())
        content_layout.addWidget(self._build_chart_placeholders())
        content_layout.addStretch()

        scroll.setWidget(content)
        outer_layout.addWidget(scroll, stretch=1)

        self._refresh_recent_raid_nights()

    # -- Analyze card ---------------------------------------------------

    def _build_analyze_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card, blur_radius=28, y_offset=6)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        icon_label = QLabel()
        icon_label.setPixmap(icon("raid_night").pixmap(20, 20))
        header_row.addWidget(icon_label)
        header_label = QLabel("Analyze a Raid Night")
        header_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        header_row.addWidget(header_label)
        header_row.addStretch()
        layout.addLayout(header_row)

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

    # -- Hero row: score / character / guild rank ------------------------

    def _build_hero_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        score_card = QFrame()
        score_card.setProperty("class", "card")
        score_card.setMinimumHeight(140)
        apply_card_elevation(score_card)
        score_layout = QVBoxLayout(score_card)
        score_layout.setContentsMargins(20, 16, 20, 16)
        score_layout.setSpacing(6)

        score_title = QLabel("OVERALL PROGRESSION SCORE")
        score_title.setProperty("class", "muted")
        score_title.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.6px;")
        score_layout.addWidget(score_title)

        score_value_row = QHBoxLayout()
        score_value_row.setSpacing(12)
        score_value = QLabel("--")
        score_value.setStyleSheet("font-size: 44px; font-weight: 700;")
        score_value_row.addWidget(score_value)

        badges_col = QVBoxLayout()
        badges_col.setSpacing(4)
        classification_badge = make_badge("NOT YET CLASSIFIED", tone="neutral")
        confidence_badge = make_badge("NO DATA", tone="neutral")
        badges_col.addWidget(classification_badge)
        badges_col.addWidget(confidence_badge)
        score_value_row.addLayout(badges_col)
        score_value_row.addStretch()
        score_layout.addLayout(score_value_row)

        score_note = QLabel("Analyze a raid night to calculate your score - Phase 2/3.")
        score_note.setProperty("class", "muted")
        score_note.setWordWrap(True)
        score_layout.addWidget(score_note)
        row.addWidget(score_card, stretch=2)

        row.addWidget(self._build_character_card(), stretch=1)
        row.addWidget(self._build_guild_card(), stretch=1)

        return row

    def _primary_character(self):
        from ascend.data.repositories import CharacterRepository

        characters = CharacterRepository(self.db).list_all(enabled_only=True)
        primary = next((c for c in characters if c.character_role == "primary"), None)
        return primary or (characters[0] if characters else None)

    def _build_character_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Character")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        primary = self._primary_character()
        body_row = QHBoxLayout()
        body_row.setSpacing(10)

        icon_frame = QFrame()
        icon_frame.setFixedSize(48, 48)
        accent = class_color(primary.character_class if primary else None)
        icon_frame.setStyleSheet(
            f"background-color: rgba(255,255,255,10); border: 2px solid {accent}; border-radius: 24px;"
        )
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(class_icon(primary.character_class if primary else None).pixmap(28, 28))
        icon_layout.addWidget(icon_label)
        body_row.addWidget(icon_frame)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        if primary is None:
            name_label = QLabel("No character configured")
            name_label.setStyleSheet("font-size: 15px; font-weight: 600;")
            text_col.addWidget(name_label)
        else:
            name_label = QLabel(primary.display_name)
            name_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {accent};")
            text_col.addWidget(name_label)
            class_label = QLabel(primary.character_class or "Unknown class")
            class_label.setProperty("class", "muted")
            text_col.addWidget(class_label)
            realm_label = QLabel(f"{primary.server} — {primary.region}")
            realm_label.setProperty("class", "muted")
            realm_label.setStyleSheet("font-size: 11px;")
            text_col.addWidget(realm_label)
        text_col.addStretch()
        body_row.addLayout(text_col)
        body_row.addStretch()
        layout.addLayout(body_row)

        hint = QLabel("Manage characters on the Characters page.")
        hint.setProperty("class", "muted")
        hint.setStyleSheet("font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return card

    def _build_guild_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Guild")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        guild_name = self.settings_repo.get("guild_name", "")
        guild_rank = self.settings_repo.get("guild_us_rank", "")
        primary = self._primary_character()

        body_row = QHBoxLayout()
        body_row.setSpacing(10)

        badge_label = QLabel()
        badge_label.setFixedSize(48, 48)
        region = primary.region if primary else ""
        realm = primary.server if primary else ""
        badge_pixmap = get_guild_badge_pixmap(self.db, region, realm, guild_name, size=48)
        badge_label.setPixmap(badge_pixmap)
        body_row.addWidget(badge_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        name_label = QLabel(guild_name or "No guild set")
        name_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        name_label.setWordWrap(True)
        text_col.addWidget(name_label)
        if primary is not None:
            realm_label = QLabel(f"{primary.server} — {primary.region}")
            realm_label.setProperty("class", "muted")
            realm_label.setStyleSheet("font-size: 11px;")
            text_col.addWidget(realm_label)
        rank_label = QLabel(f"US Rank: {guild_rank}" if guild_rank else "US Rank: --")
        rank_label.setProperty("class", "muted")
        text_col.addWidget(rank_label)
        text_col.addStretch()
        body_row.addLayout(text_col)
        body_row.addStretch()
        layout.addLayout(body_row)

        hint = QLabel("Set guild name and rank in Settings.")
        hint.setProperty("class", "muted")
        hint.setStyleSheet("font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return card

    # -- Key metrics grid -------------------------------------------------

    def _build_key_metrics(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        columns = 3
        for index, (title_text, subtext) in enumerate(KEY_METRICS):
            card = MetricCard(title_text, "--", subtext)
            grid.addWidget(card, index // columns, index % columns)
        for col in range(columns):
            grid.setColumnStretch(col, 1)
        return container

    # -- Middle row: recent raid nights + strengths/improvements ---------

    def _build_middle_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        recent_card = QFrame()
        recent_card.setProperty("class", "card")
        apply_card_elevation(recent_card)
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(16, 14, 16, 14)
        recent_title = QLabel("Recent Raid Nights")
        recent_title.setStyleSheet("font-size: 13px; font-weight: 600;")
        recent_layout.addWidget(recent_title)

        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(["Date", "Title", "Pulls", "Score"])
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_table.setMinimumHeight(160)
        self.recent_table.setAlternatingRowColors(True)
        recent_layout.addWidget(self.recent_table)
        row.addWidget(recent_card, stretch=2)

        panels_col = QVBoxLayout()
        panels_col.setSpacing(12)

        strengths_card = InfoCard("Top Strengths")
        strengths_placeholder = QLabel("No strengths identified yet - arrives with scoring in Phase 3.")
        strengths_placeholder.setProperty("class", "muted")
        strengths_placeholder.setWordWrap(True)
        strengths_card.add_widget(strengths_placeholder)
        panels_col.addWidget(strengths_card)

        improvement_card = InfoCard("Priority Improvements")
        improvement_placeholder = QLabel("No improvement areas identified yet - arrives with scoring in Phase 3.")
        improvement_placeholder.setProperty("class", "muted")
        improvement_placeholder.setWordWrap(True)
        improvement_card.add_widget(improvement_placeholder)
        panels_col.addWidget(improvement_card)

        panels_widget = QWidget()
        panels_widget.setLayout(panels_col)
        row.addWidget(panels_widget, stretch=1)

        return row

    def _refresh_recent_raid_nights(self) -> None:
        reports = self.reports_repo.list_all()[:8]
        self.recent_table.setRowCount(len(reports))
        for row_index, report in enumerate(reports):
            values = [
                _format_date(report.start_time),
                report.title or report.report_code,
                str(report.fight_count),
                "--",
            ]
            for col, value in enumerate(values):
                self.recent_table.setItem(row_index, col, QTableWidgetItem(value))

    # -- Chart placeholders ------------------------------------------------

    def _build_chart_placeholders(self) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        for title_text, icon_name in CHART_PLACEHOLDERS:
            card = QFrame()
            card.setProperty("class", "card")
            card.setMinimumHeight(120)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(6)

            icon_label = QLabel()
            icon_label.setPixmap(icon(icon_name).pixmap(20, 20))
            layout.addWidget(icon_label)

            title_label = QLabel(title_text)
            title_label.setStyleSheet("font-size: 12px; font-weight: 600;")
            layout.addWidget(title_label)

            note_label = QLabel("Chart appears once analysis data exists (Phase 2/3).")
            note_label.setProperty("class", "muted")
            note_label.setWordWrap(True)
            note_label.setStyleSheet("font-size: 11px;")
            layout.addWidget(note_label)
            layout.addStretch()

            row.addWidget(card)
        return container

    # -- recent URL handling -------------------------------------------------

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
        self._refresh_recent_raid_nights()
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
