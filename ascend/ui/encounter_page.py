"""Encounter Analysis - drill into one boss across every pull and raid night
it's been attempted in, with an objective progression-vs-farm
classification and pull-range comparisons.

Priority-target damage and mechanic-rule results need event-level data and
configured encounter rules (Phase 3/4) and aren't shown here yet.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.data.repositories import ReportRepository
from ascend.services.encounter_classification import FARM, classify_pulls, group_by_pull_range
from ascend.services.zone_data import label_for_difficulty
from ascend.theme import apply_card_elevation
from ascend.ui.components import AscendEmptyState
from ascend.ui.widgets import make_badge

PULL_COLUMNS = ["Pull #", "Raid Night", "Difficulty", "Result", "Duration", "Status"]


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return "--"
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return "--"


def _format_duration(start: float | None, end: float | None) -> str:
    if start is None or end is None or end < start:
        return "--"
    total_seconds = int((end - start) / 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


class EncounterAnalysisPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.reports_repo = ReportRepository(db)
        self._encounters: list[tuple[int, str]] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(14)

        title = QLabel("Encounter Analysis")
        title.setObjectName("pageTitle")
        self._layout.addWidget(title)

        self._picker_row = QHBoxLayout()
        picker_label = QLabel("Encounter:")
        picker_label.setProperty("class", "muted")
        self._picker_row.addWidget(picker_label)
        self.encounter_combo = QComboBox()
        self.encounter_combo.setMinimumWidth(280)
        self.encounter_combo.currentIndexChanged.connect(self._on_encounter_selected)
        self._picker_row.addWidget(self.encounter_combo)
        self._picker_row.addStretch()
        self._layout.addLayout(self._picker_row)

        self.empty_state: AscendEmptyState | None = None
        self.detail_container = QWidget()
        detail_layout = QVBoxLayout(self.detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(14)

        self.range_row = QHBoxLayout()
        self.range_row.setSpacing(12)
        detail_layout.addLayout(self.range_row)

        detail_layout.addWidget(self._build_pull_history_panel(), stretch=1)
        self._layout.addWidget(self.detail_container, stretch=1)

        self.reload()

    def _build_pull_history_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Pull History")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        self.pull_table = QTableWidget(0, len(PULL_COLUMNS))
        self.pull_table.setHorizontalHeaderLabels(PULL_COLUMNS)
        self.pull_table.verticalHeader().setVisible(False)
        self.pull_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pull_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pull_table.setAlternatingRowColors(True)
        layout.addWidget(self.pull_table)

        return card

    # -- Data -----------------------------------------------------------

    def reload(self) -> None:
        self._encounters = self.reports_repo.distinct_encounters()
        self._show_empty_state(not self._encounters)
        if not self._encounters:
            return

        self.encounter_combo.blockSignals(True)
        self.encounter_combo.clear()
        for encounter_id, name in self._encounters:
            self.encounter_combo.addItem(name, userData=encounter_id)
        self.encounter_combo.blockSignals(False)
        self._refresh_detail()

    def _show_empty_state(self, empty: bool) -> None:
        self.detail_container.setVisible(not empty)
        for i in range(self._picker_row.count()):
            widget = self._picker_row.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(not empty)
        if empty and self.empty_state is None:
            self.empty_state = AscendEmptyState(
                title="No Encounters Yet",
                description="Analyze a Warcraft Logs report to see per-boss pull history and "
                "progression-vs-farm classification here.",
                icon_name="encounter",
            )
            self._layout.addWidget(self.empty_state, stretch=1)
        if self.empty_state is not None:
            self.empty_state.setVisible(empty)

    def _on_encounter_selected(self, _index: int) -> None:
        self._refresh_detail()

    def _clear_range_row(self) -> None:
        while self.range_row.count():
            item = self.range_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_detail(self) -> None:
        encounter_id = self.encounter_combo.currentData()
        if encounter_id is None:
            return

        pairs = self.reports_repo.fights_for_encounter(encounter_id)
        fights = [fight for _report, fight in pairs]
        classification = classify_pulls(fights)

        self._clear_range_row()
        for group in group_by_pull_range(fights):
            self.range_row.addWidget(self._build_range_card(group))
        self.range_row.addStretch()

        self.pull_table.setRowCount(len(pairs))
        for row, (report, fight) in enumerate(pairs):
            difficulty_label = label_for_difficulty(self.db, report.zone_id, fight.difficulty)
            result = "Kill" if fight.kill else ("Wipe" if fight.kill is False else "--")
            status = classification[fight.id]

            values = [
                str(row + 1),
                f"{_format_date(report.start_time)} - {report.title or report.report_code}",
                difficulty_label,
                result,
                _format_duration(fight.start_time, fight.end_time),
            ]
            for col, value in enumerate(values):
                self.pull_table.setItem(row, col, QTableWidgetItem(value))

            badge_wrap = QWidget()
            badge_layout = QHBoxLayout(badge_wrap)
            badge_layout.setContentsMargins(4, 2, 4, 2)
            tone = "success" if status == FARM else "accent"
            badge_layout.addWidget(make_badge(status.upper(), tone=tone))
            badge_layout.addStretch()
            self.pull_table.setCellWidget(row, len(PULL_COLUMNS) - 1, badge_wrap)

    @staticmethod
    def _build_range_card(group: dict) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        label = QLabel(group["label"].upper())
        label.setProperty("class", "muted")
        label.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        layout.addWidget(label)

        value = QLabel(f"{group['kills']} kill / {group['pulls']} pulls")
        value.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(value)

        return card
