"""Dashboard page - a deliberate 12-column grid, not a wall of equal cards.

Row 1: Analyze Raid Night (8 cols) + Progression Profile (4 cols)
Row 2: Compact KPI strip (12 cols)
Row 3: Performance Trend (8 cols) + Actionable Insights (4 cols)
Row 4: Recent Raid Nights (7 cols) + Progression Snapshot (5 cols)
Row 5: Phase status banner (12 cols)

Full raid-night analysis (character detection, scoring, insights) lands in
Phase 2/3 - Phase 1 only validates the URL and performs basic report/fight
retrieval. Every analysis-shaped value is intentionally "--" or a real,
honestly-derived count (raid nights, pull counts, kill/wipe splits) rather
than an invented score - see the "do not fabricate" note on the
Progression Snapshot panel.
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
from ascend.services.sync_service import sync_report_by_code
from ascend.theme import PALETTE, apply_card_elevation
from ascend.ui.components import KPIStrip, ProgressionGauge, TrendChartWidget
from ascend.ui.dialogs import show_error, show_info
from ascend.ui.icons import icon
from ascend.ui.top_context_bar import TopContextBar
from ascend.ui.widgets import BackgroundTaskPanel, Banner

RECENT_URLS_SETTING_KEY = "recent_report_urls"
MAX_RECENT_URLS = 5

_KPI_SPECS: list[tuple[str, str, str]] = [
    # (icon, label, kpi_key)
    ("encounter_progression", "Progression Pulls", "progression_pulls"),
    ("encounter", "Bosses Analyzed", "bosses_analyzed"),
    ("raid_night", "Raid Nights", "raid_nights"),
    ("roster", "Participation", "participation"),
    ("deaths", "First Death %", "first_death"),
    ("rules", "Avoidable Failure %", "avoidable_failure"),
    ("roster", "Roster Percentile", "roster_percentile"),
    ("trends", "Consistency", "consistency"),
    ("insights", "Learning Speed", "learning_speed"),
]


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return "--"
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return "--"


class DashboardPage(QWidget):
    open_reports_requested = Signal()
    settings_requested = Signal()

    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        is_demo: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.secure_storage = secure_storage
        self.task_manager = task_manager
        self.is_demo = is_demo
        self.settings_repo = SettingsRepository(db)
        self.reports_repo = ReportRepository(db)
        self._active_task = None
        self._kpi_chips: dict[str, object] = {}
        self._profile_breakdown_values: dict[str, object] = {}

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(20, 14, 20, 0)
        outer_layout.setSpacing(10)

        self.context_bar = TopContextBar(db)
        self.context_bar.set_title(
            "Dashboard", "Progression overview and actionable performance intelligence"
        )
        self.context_bar.settings_requested.connect(self.settings_requested.emit)
        outer_layout.addWidget(self.context_bar)

        separator = QFrame()
        separator.setObjectName("separator")
        outer_layout.addWidget(separator)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(2, 12, 6, 20)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for col in range(12):
            grid.setColumnStretch(col, 1)

        grid.addWidget(self._build_analyze_panel(), 0, 0, 1, 8)
        grid.addWidget(self._build_progression_profile_panel(), 0, 8, 1, 4)

        self.kpi_strip = self._build_kpi_strip()
        grid.addWidget(self.kpi_strip, 1, 0, 1, 12)

        grid.addWidget(self._build_trend_panel(), 2, 0, 1, 8)
        grid.addWidget(self._build_insights_panel(), 2, 8, 1, 4)

        grid.addWidget(self._build_recent_raid_nights_panel(), 3, 0, 1, 7)
        grid.addWidget(self._build_progression_snapshot_panel(), 3, 7, 1, 5)

        grid.addWidget(self._build_phase_banner(), 4, 0, 1, 12)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll, stretch=1)

        self._refresh_recent_raid_nights()
        self._refresh_progression_snapshot()
        self._refresh_kpis()

        if self.is_demo:
            self._apply_demo_data()

    # -- Analyze panel ---------------------------------------------------

    def _build_analyze_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setObjectName("analyzePanel")
        card.setMinimumHeight(200)
        card.setStyleSheet(f"QFrame#analyzePanel {{ border-top: 2px solid {PALETTE.accent}; }}")
        apply_card_elevation(card, blur_radius=28, y_offset=6)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        icon_label = QLabel()
        icon_label.setPixmap(icon("raid_night").pixmap(18, 18))
        header_row.addWidget(icon_label)
        header_label = QLabel("Analyze Raid Night")
        header_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        header_row.addWidget(header_label)
        header_row.addStretch()
        layout.addLayout(header_row)

        subtitle = QLabel("Paste a Warcraft Logs report to begin performance analysis.")
        subtitle.setProperty("class", "muted")
        subtitle.setToolTip(
            "Phase 1 validates the URL and retrieves/stores the report and its pulls. "
            "Full analysis (character detection, scoring, insights) arrives in Phase 2/3."
        )
        layout.addWidget(subtitle)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Warcraft Logs URL or report code")
        self.url_edit.returnPressed.connect(self._on_analyze_clicked)
        input_row.addWidget(self.url_edit, stretch=1)

        self.analyze_button = QPushButton("ANALYZE")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        input_row.addWidget(self.analyze_button)
        layout.addLayout(input_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)

        paste_button = QPushButton("Paste Clipboard")
        paste_button.setObjectName("secondaryFlatButton")
        paste_button.clicked.connect(self._on_paste_clicked)
        actions_row.addWidget(paste_button)

        self.recent_combo = QComboBox()
        self.recent_combo.setMinimumWidth(150)
        self._reload_recent_urls()
        self.recent_combo.activated.connect(self._on_recent_selected)
        actions_row.addWidget(self.recent_combo)

        fight_button = QPushButton("Analyze Selected Fight")
        fight_button.setObjectName("secondaryFlatButton")
        fight_button.setEnabled(False)
        fight_button.setToolTip("Fight selection arrives in Phase 2.")
        actions_row.addWidget(fight_button)

        self.open_browser_button = QPushButton("Open Warcraft Logs")
        self.open_browser_button.setObjectName("secondaryFlatButton")
        self.open_browser_button.clicked.connect(self._on_open_browser_clicked)
        actions_row.addWidget(self.open_browser_button)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.clicked.connect(self._on_cancel)
        layout.addWidget(self.task_panel)

        return card

    # -- Progression Profile ----------------------------------------------

    def _build_progression_profile_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setMinimumHeight(200)
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(4)

        title = QLabel("Progression Profile")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(title)

        self.gauge = ProgressionGauge()
        self.gauge.setFixedHeight(96)
        layout.addWidget(self.gauge, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.gauge_status_label = QLabel("NO ANALYSIS")
        self.gauge_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gauge_status_label.setStyleSheet(
            f"color: {PALETTE.text_muted}; font-weight: 700; font-size: 11px; letter-spacing: 0.6px;"
        )
        layout.addWidget(self.gauge_status_label)

        self.gauge_note_label = QLabel("Analyze your first raid night to build your progression profile.")
        self.gauge_note_label.setProperty("class", "muted")
        self.gauge_note_label.setWordWrap(True)
        self.gauge_note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gauge_note_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self.gauge_note_label)

        breakdown = QVBoxLayout()
        breakdown.setSpacing(2)
        breakdown.setContentsMargins(0, 4, 0, 0)
        for label_text in ["Roster Percentile", "Survival", "Execution", "Consistency"]:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setProperty("class", "muted")
            label.setStyleSheet("font-size: 11px;")
            value = QLabel("--")
            value.setStyleSheet("font-size: 11px; font-weight: 600;")
            row.addWidget(label)
            row.addStretch()
            row.addWidget(value)
            breakdown.addLayout(row)
            self._profile_breakdown_values[label_text] = value
        layout.addLayout(breakdown)

        return card

    # -- KPI strip ------------------------------------------------------------

    def _build_kpi_strip(self) -> KPIStrip:
        strip = KPIStrip()
        for icon_name, label, key in _KPI_SPECS:
            self._kpi_chips[key] = strip.add_chip(icon_name, label, "--")
        strip.finish()
        return strip

    def _refresh_kpis(self) -> None:
        reports = self.reports_repo.list_all()
        all_fights = [f for r in reports if r.id for f in self.reports_repo.fights_for_report(r.id)]
        encounter_names = {f.name for f in all_fights if f.name}

        self._kpi_chips["raid_nights"].value_label.setText(str(len(reports)) if reports else "--")
        self._kpi_chips["bosses_analyzed"].value_label.setText(
            str(len(encounter_names)) if encounter_names else "--"
        )
        # Progression vs. farm classification (Phase 2) and roster/survival/consistency
        # metrics (Phase 2/3) intentionally stay "--" rather than guessing.

    # -- Performance Trend --------------------------------------------------

    def _build_trend_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setMinimumHeight(230)
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        title = QLabel("Performance Trend")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(title)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(6)
        for i, label in enumerate(["Overall Score", "Roster Percentile", "Survival", "Execution"]):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(i == 0)
            button.setObjectName("secondaryFlatButton")
            controls_row.addWidget(button)
        controls_row.addStretch()
        for i, label in enumerate(["4 Weeks", "Tier", "All Time"]):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(i == 0)
            button.setObjectName("secondaryFlatButton")
            controls_row.addWidget(button)
        layout.addLayout(controls_row)

        self.trend_chart = TrendChartWidget()
        layout.addWidget(self.trend_chart, stretch=1)

        empty_row = QHBoxLayout()
        empty_row.addStretch()
        analyze_shortcut_button = QPushButton("Analyze Raid Night")
        analyze_shortcut_button.setObjectName("primaryButton")
        analyze_shortcut_button.clicked.connect(lambda: self.url_edit.setFocus())
        empty_row.addWidget(analyze_shortcut_button)
        empty_row.addStretch()
        layout.addLayout(empty_row)

        return card

    # -- Actionable Insights --------------------------------------------------

    def _build_insights_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setMinimumHeight(230)
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        title = QLabel("Actionable Insights")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(title)

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)
        for i, label in enumerate(["All", "Strengths", "Improve", "Warnings"]):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(i == 0)
            button.setObjectName("secondaryFlatButton")
            tabs_row.addWidget(button)
        tabs_row.addStretch()
        layout.addLayout(tabs_row)

        self.insights_empty_label = QLabel(
            "No insights yet. Evidence-based strengths, warnings, and improvement areas "
            "arrive once analysis exists in Phase 2/3."
        )
        self.insights_empty_label.setProperty("class", "muted")
        self.insights_empty_label.setWordWrap(True)
        layout.addWidget(self.insights_empty_label)

        self.insights_container = QVBoxLayout()
        self.insights_container.setSpacing(8)
        layout.addLayout(self.insights_container)
        layout.addStretch()

        return card

    # -- Recent Raid Nights --------------------------------------------------

    def _build_recent_raid_nights_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel("Recent Raid Nights")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        header_row.addWidget(title)
        header_row.addStretch()
        view_all_button = QPushButton("View All Reports")
        view_all_button.setObjectName("secondaryFlatButton")
        view_all_button.clicked.connect(self.open_reports_requested.emit)
        header_row.addWidget(view_all_button)
        layout.addLayout(header_row)

        self.recent_table = QTableWidget(0, 8)
        self.recent_table.setHorizontalHeaderLabels(
            ["Date", "Guild", "Character", "Boss", "Pulls", "Score", "Classification", "Trend"]
        )
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setMinimumHeight(170)
        self.recent_table.cellDoubleClicked.connect(lambda *_a: self.open_reports_requested.emit())
        layout.addWidget(self.recent_table)

        self.recent_empty_label = QLabel(
            "No raid nights analyzed yet - paste a report above to get started."
        )
        self.recent_empty_label.setProperty("class", "muted")
        self.recent_empty_label.setWordWrap(True)
        self.recent_empty_label.setVisible(False)
        layout.addWidget(self.recent_empty_label)

        return card

    def _refresh_recent_raid_nights(self) -> None:
        reports = self.reports_repo.list_all()[:5]
        self.recent_table.setVisible(bool(reports))
        self.recent_empty_label.setVisible(not reports)
        self.recent_table.setRowCount(len(reports))
        for row_index, report in enumerate(reports):
            fights = self.reports_repo.fights_for_report(report.id) if report.id else []
            encounter_names = sorted({f.name for f in fights if f.name})
            boss_text = encounter_names[0] if encounter_names else "--"
            if len(encounter_names) > 1:
                boss_text += f" +{len(encounter_names) - 1}"
            values = [
                _format_date(report.start_time),
                report.guild_name or report.owner_name or "--",
                "--",
                boss_text,
                str(len(fights)),
                "--",
                "--",
                "--",
            ]
            for col, value in enumerate(values):
                self.recent_table.setItem(row_index, col, QTableWidgetItem(value))

    # -- Progression Snapshot --------------------------------------------------

    def _build_progression_snapshot_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(6)

        title = QLabel("Progression Snapshot")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(title)

        self.snapshot_container = QVBoxLayout()
        self.snapshot_container.setSpacing(5)
        layout.addLayout(self.snapshot_container)
        layout.addStretch()

        return card

    def _refresh_progression_snapshot(self) -> None:
        while self.snapshot_container.count():
            item = self.snapshot_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        reports = self.reports_repo.list_all()
        encounter_fights: dict[str, list] = {}
        for report in reports:
            if not report.id:
                continue
            for fight in self.reports_repo.fights_for_report(report.id):
                if fight.name:
                    encounter_fights.setdefault(fight.name, []).append(fight)

        if not encounter_fights:
            empty = QLabel("No encounters analyzed yet.")
            empty.setProperty("class", "muted")
            self.snapshot_container.addWidget(empty)
            return

        name, fights = max(encounter_fights.items(), key=lambda kv: len(kv[1]))
        kills = sum(1 for f in fights if f.kill)
        wipes = sum(1 for f in fights if f.kill is False)
        raid_nights = len({f.report_id for f in fights})

        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        name_label.setWordWrap(True)
        self.snapshot_container.addWidget(name_label)

        for label_text, value_text in [
            ("Pulls Logged", str(len(fights))),
            ("Raid Nights", str(raid_nights)),
            ("Kills / Wipes", f"{kills} / {wipes}"),
            ("First Death Rate", "--"),
            ("Mechanic Failure Rate", "--"),
        ]:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setProperty("class", "muted")
            label.setStyleSheet("font-size: 11px;")
            value = QLabel(value_text)
            value.setStyleSheet("font-size: 12px; font-weight: 600;")
            row.addWidget(label)
            row.addStretch()
            row.addWidget(value)
            self.snapshot_container.addLayout(row)

        note = QLabel(
            "Boss-percentage progress isn't available from current data - showing "
            "objective pull and kill/wipe counts instead."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 10px;")
        self.snapshot_container.addWidget(note)

    # -- Phase banner -----------------------------------------------------

    def _build_phase_banner(self) -> QFrame:
        banner = Banner(
            "Phase 1 - Foundation. Full scoring, insights, roster comparison, and "
            "live trend data arrive in Phase 2/3.",
            tone="info",
        )
        view_roadmap_button = QPushButton("View Roadmap")
        view_roadmap_button.setObjectName("secondaryFlatButton")
        view_roadmap_button.clicked.connect(self._open_roadmap)
        banner.layout().addWidget(view_roadmap_button)
        return banner

    @staticmethod
    def _open_roadmap() -> None:
        from pathlib import Path

        roadmap_path = Path(__file__).resolve().parent.parent.parent / "docs" / "ROADMAP.md"
        if roadmap_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(roadmap_path)))

    # -- Demo Mode preview data --------------------------------------------
    #
    # Only reached when is_demo=True (Settings toggle, or `python app.py
    # --demo`). Purely a UI overlay on top of the widgets the real (empty-
    # state) refresh methods above already built - no database writes, and
    # it always runs against the separate ascend_demo.db, never real data.
    # Exists so the Dashboard's visual design can be evaluated before the
    # real analysis engine exists (Phase 2/3).

    def _apply_demo_data(self) -> None:
        self.gauge.set_score(84, "strong")
        self.gauge_status_label.setText("STRONG")
        self.gauge_status_label.setStyleSheet(
            f"color: {PALETTE.success}; font-weight: 700; font-size: 11px; letter-spacing: 0.6px;"
        )
        self.gauge_note_label.setText("Confidence: High")

        demo_breakdown = {
            "Roster Percentile": "78th", "Survival": "92", "Execution": "81", "Consistency": "79",
        }
        for label_text, value in demo_breakdown.items():
            widget = self._profile_breakdown_values.get(label_text)
            if widget:
                widget.setText(value)

        demo_kpis = {
            "progression_pulls": ("214", None),
            "bosses_analyzed": ("3", None),
            "raid_nights": ("6", None),
            "participation": ("96%", None),
            "first_death": ("2.8%", "↓ 1.4%"),
            "avoidable_failure": ("6.1%", "↓ 2.0%"),
            "roster_percentile": ("78th", "↑ 4"),
            "consistency": ("82%", "↑ 3%"),
            "learning_speed": ("Fast", None),
        }
        for key, (value, trend) in demo_kpis.items():
            chip = self._kpi_chips.get(key)
            if chip:
                chip.set_value(value, trend)

        self.trend_chart.set_series([58, 63, 66, 71, 76, 79, 84])

        self.insights_empty_label.setVisible(False)
        demo_insights = [
            ("STRENGTH", "success", "Low First-Death Rate",
             "You were among the final 40% of players alive on 94% of progression pulls."),
            ("IMPROVE", "warning", "Movement Downtime",
             "Your active time was 6.2% below the ranged roster median."),
            ("TREND", "info", "Improving Consistency",
             "Pull-to-pull damage variance improved 14% over the last 3 raid nights."),
        ]
        for tone_text, tone, title_text, description_text in demo_insights:
            self.insights_container.addWidget(
                self._build_demo_insight_row(tone_text, tone, title_text, description_text)
            )

        self._apply_demo_recent_raid_nights()
        self._apply_demo_progression_snapshot()

    @staticmethod
    def _build_demo_insight_row(tone_text: str, tone: str, title_text: str, description_text: str) -> QFrame:
        from ascend.ui.widgets import make_badge

        row = QFrame()
        row.setObjectName("insightRow")
        accent = {"success": PALETTE.success, "warning": PALETTE.warning, "info": PALETTE.info}.get(
            tone, PALETTE.accent
        )
        row.setStyleSheet(f"QFrame#insightRow {{ border-left: 2px solid {accent}; }}")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 2, 0, 2)
        layout.setSpacing(2)

        header_row = QHBoxLayout()
        header_row.addWidget(make_badge(tone_text, tone=tone))
        header_row.addStretch()
        layout.addLayout(header_row)

        title_label = QLabel(title_text)
        title_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        layout.addWidget(title_label)

        desc_label = QLabel(description_text)
        desc_label.setProperty("class", "muted")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(desc_label)

        return row

    def _apply_demo_recent_raid_nights(self) -> None:
        self.recent_table.setVisible(True)
        self.recent_empty_label.setVisible(False)
        demo_rows = [
            ("Jul 12", "Ascend Raiders", "Kysarra", "Dimensius", "31", "84", "STRONG", "+3.2"),
            ("Jul 09", "Ascend Raiders", "Kysarra", "Dimensius", "27", "81", "STRONG", "+1.8"),
            ("Jul 05", "Ascend Raiders", "Kyssandra", "Dimensius", "24", "76", "ABOVE AVERAGE", "+4.1"),
            ("Jul 02", "Ascend Raiders", "Kysarra", "Rasha'nan", "12", "79", "ABOVE AVERAGE", "--"),
            ("Jun 28", "Ascend Raiders", "Kysarra", "Rasha'nan", "18", "72", "AVERAGE", "+2.5"),
        ]
        self.recent_table.setRowCount(len(demo_rows))
        for row_index, values in enumerate(demo_rows):
            for col, value in enumerate(values):
                self.recent_table.setItem(row_index, col, QTableWidgetItem(value))

    def _apply_demo_progression_snapshot(self) -> None:
        while self.snapshot_container.count():
            item = self.snapshot_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        name_label = QLabel("Dimensius the All-Devouring")
        name_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        name_label.setWordWrap(True)
        self.snapshot_container.addWidget(name_label)

        for label_text, value_text in [
            ("Best Pull", "12.4%"),
            ("Progression Pulls", "83"),
            ("Raid Nights", "4"),
            ("First Death Rate", "2.4%"),
            ("Mechanic Failure Rate", "4.8%"),
        ]:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setProperty("class", "muted")
            label.setStyleSheet("font-size: 11px;")
            value = QLabel(value_text)
            value.setStyleSheet("font-size: 12px; font-weight: 600;")
            row.addWidget(label)
            row.addStretch()
            row.addWidget(value)
            self.snapshot_container.addLayout(row)

        bar = QLabel("100% " + "─" * 18 + " 12.4%")
        bar.setStyleSheet(f"font-size: 10px; color: {PALETTE.text_muted}; font-family: monospace;")
        self.snapshot_container.addWidget(bar)

        note = QLabel("+8.3% boss progress over last 2 raid nights")
        note.setStyleSheet(f"font-size: 11px; color: {PALETTE.success}; font-weight: 600;")
        self.snapshot_container.addWidget(note)

    # -- recent URL handling -------------------------------------------------

    def _reload_recent_urls(self) -> None:
        recent = self.settings_repo.get(RECENT_URLS_SETTING_KEY, [])
        self.recent_combo.clear()
        self.recent_combo.addItem("Recent")
        for url in recent:
            self.recent_combo.addItem(url)

    def _remember_recent_url(self, raw_input: str) -> None:
        recent = self.settings_repo.get(RECENT_URLS_SETTING_KEY, [])
        recent = [raw_input] + [u for u in recent if u != raw_input]
        recent = recent[:MAX_RECENT_URLS]
        self.settings_repo.set(RECENT_URLS_SETTING_KEY, recent)
        self._reload_recent_urls()

    def _on_recent_selected(self, index: int) -> None:
        if index > 0:
            self.url_edit.setText(self.recent_combo.itemText(index))

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
        self._refresh_progression_snapshot()
        self._refresh_kpis()
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
