"""The three Dashboard compositions: NoDataState, ImportedIncompleteState,
ActiveAnalyticsState. These are deliberately different layouts, not one
layout with values swapped for "--" - see docs/ARCHITECTURE.md - Dashboard
State Composition.

Loading/Analyzing and Error/Recovery are not separate full-page compositions:
loading is represented by AnalyzeBar's own BackgroundTaskPanel inline, and
errors surface as a dismissible ToastCard - a fifth full-page layout would
itself violate the "don't show an empty/redundant state" principle.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.data.repositories import ReportRepository, SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.data_quality import DETECTED, character_identity_confidence, small_sample_warnings
from ascend.theme import PALETTE, apply_card_elevation
from ascend.ui.components import AnalyzeBar, KPIRow, ProgressionGauge, TrendChartWidget
from ascend.ui.icons import icon

_HERO_MAX_WIDTH = 1000
_ACTIVE_MAX_WIDTH = 1600


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return "--"
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return "--"


def _centered(inner: QWidget, max_width: int) -> QScrollArea:
    """Wraps `inner` so it's centered with a constrained max width, and never
    stretches edge-to-edge on wide/ultrawide windows."""
    inner.setMaximumWidth(max_width)

    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.addStretch()
    row_layout.addWidget(inner)
    row_layout.addStretch()

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(row)
    return scroll


# -- State 1: No Data ------------------------------------------------------

class NoDataState(QWidget):
    """First-run / no analyzed data yet. One dominant onboarding experience,
    not an empty version of the analytics dashboard."""

    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.reports_repo = ReportRepository(db)

        hero = QWidget()
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(0, 32, 0, 32)
        layout.setSpacing(28)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addLayout(self._build_hero_header())

        self.analyze_bar = AnalyzeBar(db, secure_storage, task_manager, compact=False)
        layout.addWidget(self.analyze_bar)

        layout.addLayout(self._build_value_indicators())
        layout.addWidget(self._build_how_it_works())

        self.recent_imports_panel = self._build_recent_imports_panel()
        layout.addWidget(self.recent_imports_panel)

        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_centered(hero, _HERO_MAX_WIDTH))

        self.refresh()

    def _build_hero_header(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(10)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        mark = QLabel()
        mark.setPixmap(icon("logo_mark").pixmap(40, 40))
        mark.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(mark)

        heading = QLabel("Build Your Progression Profile")
        heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        heading.setStyleSheet("font-size: 22px; font-weight: 700;")
        col.addWidget(heading)

        subtitle = QLabel(
            "Analyze your Warcraft Logs data to understand how you perform during "
            "progression, where you are improving, and what is holding you back."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle.setFixedWidth(620)
        col.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignHCenter)

        return col

    def _build_value_indicators(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(24)
        specs = [
            ("data_quality", "LOCAL-FIRST", "Your analysis stays on your computer."),
            ("insights", "EVIDENCE-BASED", "Every conclusion should be inspectable."),
            ("encounter_progression", "PROGRESSION-FOCUSED",
             "Consistency, execution, and improvement matter more than parse color."),
        ]
        for icon_name, title_text, description_text in specs:
            col = QVBoxLayout()
            col.setSpacing(2)
            header_row = QHBoxLayout()
            header_row.setSpacing(6)
            icon_label = QLabel()
            icon_label.setPixmap(icon(icon_name).pixmap(15, 15))
            header_row.addWidget(icon_label)
            title_label = QLabel(title_text)
            title_label.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.4px;")
            header_row.addWidget(title_label)
            header_row.addStretch()
            col.addLayout(header_row)

            desc_label = QLabel(description_text)
            desc_label.setProperty("class", "muted")
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("font-size: 11px;")
            col.addWidget(desc_label)
            row.addLayout(col, stretch=1)
        return row

    def _build_how_it_works(self) -> QFrame:
        panel = QFrame()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(10)

        title = QLabel("HOW ASCEND WORKS")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setStyleSheet(
            f"color: {PALETTE.text_secondary}; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;"
        )
        outer.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(0)
        steps = [
            ("raid_night", "IMPORT", "Connect Warcraft Logs and import a raid night."),
            ("encounter_progression", "ANALYZE",
             "Ascend evaluates progression performance, execution, consistency, "
             "survival, and roster-relative metrics."),
            ("trends", "IMPROVE",
             "Review evidence-based strengths, weaknesses, repeated mistakes, and "
             "performance trends."),
        ]
        for i, (icon_name, step_title, step_desc) in enumerate(steps):
            if i > 0:
                connector = QFrame()
                connector.setFrameShape(QFrame.Shape.HLine)
                connector.setFixedHeight(1)
                connector.setStyleSheet(f"background-color: {PALETTE.border}; max-height: 1px;")
                connector_wrap = QVBoxLayout()
                connector_wrap.addSpacing(14)
                connector_wrap.addWidget(connector)
                row.addLayout(connector_wrap, stretch=0)

            step_col = QVBoxLayout()
            step_col.setSpacing(4)
            step_col.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

            icon_label = QLabel()
            icon_label.setPixmap(icon(icon_name).pixmap(20, 20))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            step_col.addWidget(icon_label)

            title_label = QLabel(step_title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            title_label.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
            step_col.addWidget(title_label)

            desc_label = QLabel(step_desc)
            desc_label.setProperty("class", "muted")
            desc_label.setWordWrap(True)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            desc_label.setStyleSheet("font-size: 10px;")
            desc_label.setFixedWidth(230)
            step_col.addWidget(desc_label)

            row.addLayout(step_col, stretch=1)

        outer.addLayout(row)
        return panel

    def _build_recent_imports_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("class", "card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title = QLabel("Recent Imports")
        title.setStyleSheet("font-size: 12px; font-weight: 600;")
        layout.addWidget(title)

        self.recent_imports_list = QVBoxLayout()
        self.recent_imports_list.setSpacing(4)
        layout.addLayout(self.recent_imports_list)

        return panel

    def refresh(self) -> None:
        """Only shows the Recent Imports panel when reports exist without
        complete analysis - never an empty table (Empty Component Rule)."""
        reports = self.reports_repo.list_all()[:5]
        self.recent_imports_panel.setVisible(bool(reports))

        while self.recent_imports_list.count():
            item = self.recent_imports_list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for report in reports:
            row = QHBoxLayout()
            name_label = QLabel(report.title or report.report_code)
            name_label.setStyleSheet("font-size: 11px;")
            date_label = QLabel(_format_date(report.start_time))
            date_label.setProperty("class", "muted")
            date_label.setStyleSheet("font-size: 11px;")
            row.addWidget(name_label, stretch=1)
            row.addWidget(date_label)
            self.recent_imports_list.addLayout(row)


# -- State 2: Imported but incomplete --------------------------------------

class ImportedIncompleteState(QWidget):
    """Reports exist locally, but not enough completed analysis exists yet
    for the full analytics dashboard. A compact "profile is building" panel,
    not a wall of empty analytics cards."""

    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.reports_repo = ReportRepository(db)

        panel = QFrame()
        panel.setProperty("class", "card")
        apply_card_elevation(panel, blur_radius=28, y_offset=6)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel("Your Progression Profile Is Building")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        layout.addWidget(title)

        self.stats_layout = QVBoxLayout()
        self.stats_layout.setSpacing(4)
        layout.addLayout(self.stats_layout)

        capability_row = QVBoxLayout()
        capability_row.setSpacing(2)
        capability_row.setContentsMargins(0, 6, 0, 0)
        self.objective_label = QLabel("✓  Objective analysis available")
        self.objective_label.setStyleSheet(f"color: {PALETTE.success}; font-size: 12px; font-weight: 600;")
        capability_row.addWidget(self.objective_label)
        self.advanced_label = QLabel("○  Advanced scoring not yet available")
        self.advanced_label.setProperty("class", "muted")
        self.advanced_label.setStyleSheet("font-size: 12px;")
        capability_row.addWidget(self.advanced_label)
        layout.addLayout(capability_row)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 10, 0, 0)
        continue_button = QPushButton("Continue Analysis")
        continue_button.setObjectName("primaryButton")
        continue_button.clicked.connect(self._focus_analyze_bar)
        actions_row.addWidget(continue_button)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        self.analyze_bar = AnalyzeBar(db, secure_storage, task_manager, compact=True)
        layout.addWidget(self.analyze_bar)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_centered(panel, _HERO_MAX_WIDTH))
        outer.addStretch()

        self.refresh()

    def _focus_analyze_bar(self) -> None:
        self.analyze_bar.url_edit.setFocus()

    def refresh(self) -> None:
        reports = self.reports_repo.list_all()
        total_pulls = sum(
            len(self.reports_repo.fights_for_report(r.id)) for r in reports if r.id
        )

        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        report_word = "report" if len(reports) == 1 else "reports"
        pull_word = "pull" if total_pulls == 1 else "pulls"
        for text in (
            f"{len(reports)} {report_word} imported",
            f"{total_pulls} {pull_word} discovered",
        ):
            label = QLabel(text)
            label.setStyleSheet("font-size: 13px;")
            self.stats_layout.addWidget(label)


# -- State 3: Active Analytics ----------------------------------------------

_KPI_SPECS: list[tuple[str, str, str]] = [
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


class ActiveAnalyticsState(QWidget):
    """Full analytics dashboard - only shown once the selected character has
    sufficient completed analysis data. Three visual-weight levels:
    Level 1 primary (Progression Profile, Performance Trend, Quick Analyze),
    Level 2 secondary (Insights, Recent Raid Nights, Progression Snapshot),
    Level 3 supporting (KPI row, Data Quality, context info)."""

    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        open_reports_requested,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.reports_repo = ReportRepository(db)
        self.open_reports_requested = open_reports_requested
        self._kpi_metrics: dict[str, object] = {}
        self._profile_breakdown_values: dict[str, object] = {}

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 8, 0, 24)
        layout.setSpacing(16)

        layout.addWidget(self._build_quick_analyze(db, secure_storage, task_manager))

        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        top_row.addWidget(self._build_progression_profile_panel(), stretch=4)
        top_row.addWidget(self._build_trend_panel(), stretch=5)
        top_row.addWidget(self._build_insights_panel(), stretch=3)
        layout.addLayout(top_row)

        self.kpi_row = self._build_kpi_row()
        layout.addWidget(self.kpi_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)
        bottom_row.addWidget(self._build_recent_raid_nights_panel(), stretch=7)
        bottom_row.addWidget(self._build_progression_snapshot_panel(), stretch=5)
        layout.addLayout(bottom_row)

        self.data_quality_banner = self._build_data_quality_banner()
        layout.addWidget(self.data_quality_banner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_centered(content, _ACTIVE_MAX_WIDTH))

        self.refresh()

    def refresh(self) -> None:
        self._refresh_recent_raid_nights()
        self._refresh_progression_snapshot()
        self._refresh_kpis()
        self._refresh_insights()
        self._refresh_data_quality_banner()

    # -- Level 1: Quick Analyze --------------------------------------------

    def _build_quick_analyze(self, db, secure_storage, task_manager) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setObjectName("quickAnalyzePanel")
        card.setMaximumHeight(96)
        card.setStyleSheet(f"QFrame#quickAnalyzePanel {{ border-top: 2px solid {PALETTE.accent}; }}")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)

        self.analyze_bar = AnalyzeBar(db, secure_storage, task_manager, compact=True)
        layout.addWidget(self.analyze_bar)
        return card

    # -- Level 1: Progression Profile ---------------------------------------

    def _build_progression_profile_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setObjectName("progressionProfilePanel")
        card.setMinimumHeight(220)
        card.setStyleSheet(
            f"QFrame#progressionProfilePanel {{ border: 1px solid {PALETTE.accent_muted}; }}"
        )
        apply_card_elevation(card, blur_radius=26, y_offset=6)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(4)

        title = QLabel("Progression Profile")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(title)

        self.gauge = ProgressionGauge()
        self.gauge.setFixedHeight(96)
        layout.addWidget(self.gauge, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.gauge_status_label = QLabel("")
        self.gauge_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.gauge_status_label)

        self.gauge_note_label = QLabel("")
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

    # -- Level 1: Performance Trend ------------------------------------------

    def _build_trend_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setObjectName("trendPanel")
        card.setMinimumHeight(220)
        card.setStyleSheet(f"QFrame#trendPanel {{ border: 1px solid {PALETTE.accent_muted}; }}")
        apply_card_elevation(card, blur_radius=26, y_offset=6)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        title = QLabel("Performance Trend")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(title)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(6)
        for i, label in enumerate(["Overall Score", "Roster Percentile", "Survival"]):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(i == 0)
            button.setObjectName("secondaryFlatButton")
            controls_row.addWidget(button)
        controls_row.addStretch()
        layout.addLayout(controls_row)

        self.trend_chart = TrendChartWidget()
        layout.addWidget(self.trend_chart, stretch=1)

        return card

    # -- Level 2: Actionable Insights ----------------------------------------

    def _build_insights_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        card.setMinimumHeight(220)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        title = QLabel("Actionable Insights")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        self.insights_container = QVBoxLayout()
        self.insights_container.setSpacing(8)
        layout.addLayout(self.insights_container)

        self.insights_empty_label = QLabel("Not enough data for insights yet.")
        self.insights_empty_label.setProperty("class", "muted")
        self.insights_empty_label.setWordWrap(True)
        self.insights_empty_label.setStyleSheet("font-size: 11px;")
        self.insights_empty_label.setVisible(False)
        layout.addWidget(self.insights_empty_label)

        layout.addStretch()

        return card

    def _clear_insights(self) -> None:
        while self.insights_container.count():
            item = self.insights_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _build_insight_row(tone_text: str, tone: str, title_text: str, description_text: str) -> QFrame:
        from ascend.ui.widgets import make_badge

        row = QFrame()
        row.setObjectName("insightRow")
        accent = {"success": PALETTE.success, "warning": PALETTE.warning, "info": PALETTE.info}.get(
            tone, PALETTE.accent
        )
        row.setStyleSheet(f"QFrame#insightRow {{ border-left: 2px solid {accent}; }}")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(8, 2, 0, 2)
        row_layout.setSpacing(2)

        header_row = QHBoxLayout()
        header_row.addWidget(make_badge(tone_text, tone=tone))
        header_row.addStretch()
        row_layout.addLayout(header_row)

        title_label = QLabel(title_text)
        title_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        row_layout.addWidget(title_label)

        desc_label = QLabel(description_text)
        desc_label.setProperty("class", "muted")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 11px;")
        row_layout.addWidget(desc_label)

        return row

    def _refresh_insights(self) -> None:
        """Basic, honestly-derivable insights from data already synced - no
        scoring engine needed. Explainable/evidence-based insights (Phase 3)
        will extend this, not replace it."""
        self._clear_insights()

        reports = self.reports_repo.list_all()
        all_fights = [f for r in reports if r.id for f in self.reports_repo.fights_for_report(r.id)]
        insights: list[tuple[str, str, str, str]] = []

        if all_fights:
            kills = sum(1 for f in all_fights if f.kill)
            decided = sum(1 for f in all_fights if f.kill is not None)
            if decided:
                kill_rate = round(100 * kills / decided)
                insights.append((
                    "TREND", "info", "Kill Rate",
                    f"{kills} of {decided} logged pulls ({kill_rate}%) ended in a kill across "
                    f"{len(reports)} raid night(s).",
                ))

            encounter_counts: dict[str, int] = {}
            for fight in all_fights:
                if fight.name:
                    encounter_counts[fight.name] = encounter_counts.get(fight.name, 0) + 1
            if encounter_counts:
                busiest_name, busiest_count = max(encounter_counts.items(), key=lambda kv: kv[1])
                insights.append((
                    "STRENGTH", "success", "Most-Attempted Encounter",
                    f"{busiest_name} has the most logged pulls ({busiest_count}).",
                ))

        not_detected = [c for c in character_identity_confidence(self.db) if c.status != DETECTED and reports]
        if not_detected:
            names = ", ".join(c.display_name for c in not_detected)
            insights.append((
                "IMPROVE", "warning", "Character Not Yet Detected",
                f"{names} hasn't been matched in any synced report - check Data Quality for details.",
            ))

        if small_sample_warnings(self.db):
            insights.append((
                "IMPROVE", "warning", "Small Sample Size",
                "Some reports or encounters don't have enough pulls logged yet to be very "
                "meaningful - see Data Quality for details.",
            ))

        self.insights_empty_label.setVisible(not insights)
        for tone_text, tone, title_text, description_text in insights:
            self.insights_container.addWidget(
                self._build_insight_row(tone_text, tone, title_text, description_text)
            )

    # -- Level 3: KPI row ------------------------------------------------------

    def _build_kpi_row(self) -> KPIRow:
        row = KPIRow()
        for icon_name, label, key in _KPI_SPECS:
            self._kpi_metrics[key] = row.add_metric(icon_name, label, "--")
        row.finish()
        return row

    def _refresh_kpis(self) -> None:
        reports = self.reports_repo.list_all()
        all_fights = [f for r in reports if r.id for f in self.reports_repo.fights_for_report(r.id)]
        encounter_names = {f.name for f in all_fights if f.name}

        self._kpi_metrics["raid_nights"].set_value(str(len(reports)) if reports else "--")
        self._kpi_metrics["bosses_analyzed"].set_value(
            str(len(encounter_names)) if encounter_names else "--"
        )
        self._kpi_metrics["progression_pulls"].set_value(str(len(all_fights)) if all_fights else "--")

        # Participation: the best-attended tracked character's share of all
        # synced raid nights - real attendance data, not a fabricated stat.
        confidence = character_identity_confidence(self.db)
        detected = [c for c in confidence if c.status == DETECTED]
        if detected and reports:
            best = max(detected, key=lambda c: c.raid_nights)
            pct = round(100 * best.raid_nights / len(reports))
            self._kpi_metrics["participation"].set_value(f"{pct}%")
        else:
            self._kpi_metrics["participation"].set_value("--")

    # -- Level 2: Recent Raid Nights ------------------------------------------

    def _build_recent_raid_nights_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel("Recent Raid Nights")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
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
        from PySide6.QtWidgets import QHeaderView

        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setMinimumHeight(170)
        self.recent_table.cellDoubleClicked.connect(lambda *_a: self.open_reports_requested.emit())
        layout.addWidget(self.recent_table)

        return card

    def _refresh_recent_raid_nights(self) -> None:
        reports = self.reports_repo.list_all()[:5]
        self.recent_table.setRowCount(len(reports))
        for row_index, report in enumerate(reports):
            fights = self.reports_repo.fights_for_report(report.id) if report.id else []
            encounter_names = sorted({f.name for f in fights if f.name})
            boss_text = encounter_names[0] if encounter_names else "--"
            if len(encounter_names) > 1:
                boss_text += f" +{len(encounter_names) - 1}"
            tracked = self.reports_repo.tracked_characters_for_report(report.id) if report.id else []
            character_text = tracked[0].display_name if tracked else "--"
            values = [
                _format_date(report.start_time),
                report.guild_name or report.owner_name or "--",
                character_text,
                boss_text,
                str(len(fights)),
                "--",
                "--",
                "--",
            ]
            for col, value in enumerate(values):
                self.recent_table.setItem(row_index, col, QTableWidgetItem(value))

    # -- Level 2: Progression Snapshot ----------------------------------------

    def _build_progression_snapshot_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(6)

        title = QLabel("Progression Snapshot")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
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

    # -- Level 3: Data Quality -------------------------------------------------

    def _build_data_quality_banner(self) -> QFrame:
        from ascend.ui.widgets import Banner

        banner = Banner("", tone="warning")
        banner.setVisible(False)
        return banner

    def set_data_quality_warning(self, message: str | None) -> None:
        """Only shown when there is an actual warning - never an empty
        'no warnings' state (Empty Component Rule)."""
        if message:
            self.data_quality_banner.set_text(message)
            self.data_quality_banner.setVisible(True)
        else:
            self.data_quality_banner.setVisible(False)

    def _refresh_data_quality_banner(self) -> None:
        warnings = small_sample_warnings(self.db)
        not_detected = [
            c for c in character_identity_confidence(self.db)
            if c.status != DETECTED and self.reports_repo.list_all()
        ]
        if not_detected:
            names = ", ".join(c.display_name for c in not_detected)
            self.set_data_quality_warning(
                f"{names} hasn't been detected in any synced report yet - see Data Quality."
            )
        elif warnings:
            self.set_data_quality_warning(
                f"{len(warnings)} report(s)/encounter(s) have a small pull sample - see Data Quality."
            )
        else:
            self.set_data_quality_warning(None)

    # -- Demo Mode preview data --------------------------------------------

    def apply_demo_data(self) -> None:
        # The bundled demo fixture is deliberately thin (no masterData, only
        # 2 fights) and would otherwise trip the real small-sample/character-
        # not-detected Data Quality checks - suppressed here since Demo Mode
        # is meant to showcase the polished Active state, not real data
        # quality signals about a sample fixture.
        self.set_data_quality_warning(None)

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
            metric = self._kpi_metrics.get(key)
            if metric:
                metric.set_value(value, trend)

        self.trend_chart.set_series([58, 63, 66, 71, 76, 79, 84])

        self._clear_insights()
        self.insights_empty_label.setVisible(False)
        demo_insights = [
            ("STRENGTH", "success", "Low First-Death Rate",
             "You were among the final 40% of players alive on 94% of progression pulls."),
            ("IMPROVE", "warning", "Movement Downtime",
             "Your active time was 6.2% below your role cohort median."),
            ("TREND", "info", "Improving Consistency",
             "Pull-to-pull damage variance improved 14% over the last 3 raid nights."),
        ]
        for tone_text, tone, title_text, description_text in demo_insights:
            self.insights_container.addWidget(
                self._build_insight_row(tone_text, tone, title_text, description_text)
            )

        demo_rows = [
            ("Jul 12", "Stellar Ascent", "Aeloria", "Dimensius", "31", "84", "STRONG", "+3.2"),
            ("Jul 09", "Stellar Ascent", "Aeloria", "Dimensius", "27", "81", "STRONG", "+1.8"),
            ("Jul 05", "Stellar Ascent", "Thornveil", "Dimensius", "24", "76", "ABOVE AVERAGE", "+4.1"),
            ("Jul 02", "Stellar Ascent", "Kaelric", "Rasha'nan", "12", "79", "ABOVE AVERAGE", "--"),
            ("Jun 28", "Stellar Ascent", "Seraphyne", "Rasha'nan", "18", "72", "AVERAGE", "+2.5"),
        ]
        self.recent_table.setRowCount(len(demo_rows))
        for row_index, values in enumerate(demo_rows):
            for col, value in enumerate(values):
                self.recent_table.setItem(row_index, col, QTableWidgetItem(value))

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

        note = QLabel("+8.3% boss progress over last 2 raid nights")
        note.setStyleSheet(f"font-size: 11px; color: {PALETTE.success}; font-weight: 600;")
        self.snapshot_container.addWidget(note)
