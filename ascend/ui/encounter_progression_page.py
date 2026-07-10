"""Encounter Progression - charts the climb on one boss from first pull to farm.

Shows the full progression arc for a selected boss: a pull-by-pull visual
timeline (green = kill, red = wipe), pull-range bucket stats, first-kill
milestone, and a detailed pull history table. Farm pulls are shown separately
from progression so the reclear performance is visible at a glance.

All data is derived from fights already ingested - no event data required.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QSizePolicy,
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

_PULL_BOX_SIZE = 10
_PULL_BOX_GAP = 3
_PULL_ARC_HEIGHT = 28


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


class _PullArcWidget(QWidget):
    """Horizontal strip of coloured squares: one per pull in order.

    Green = kill, red = wipe, grey = result unknown.
    A gold vertical line marks the first-kill boundary (end of progression).
    """

    def __init__(self, pulls: list[bool | None], first_kill_idx: int | None, parent: QWidget | None = None):
        super().__init__(parent)
        self._pulls = pulls
        self._first_kill_idx = first_kill_idx
        total_w = len(pulls) * (_PULL_BOX_SIZE + _PULL_BOX_GAP) + _PULL_BOX_GAP
        self.setFixedSize(total_w, _PULL_ARC_HEIGHT)
        self.setToolTip(f"{len(pulls)} pulls total")

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        x = _PULL_BOX_GAP
        for i, kill in enumerate(self._pulls):
            if kill is True:
                color = QColor("#2d8a4e")   # green
            elif kill is False:
                color = QColor("#c0392b")   # red
            else:
                color = QColor("#6b7280")   # grey

            y = (_PULL_ARC_HEIGHT - _PULL_BOX_SIZE) // 2
            painter.fillRect(x, y, _PULL_BOX_SIZE, _PULL_BOX_SIZE, color)

            # Gold border on first-kill square
            if i == self._first_kill_idx:
                painter.setPen(QColor("#f0c040"))
                painter.drawRect(x, y, _PULL_BOX_SIZE - 1, _PULL_BOX_SIZE - 1)
                painter.setPen(Qt.PenStyle.NoPen)

            x += _PULL_BOX_SIZE + _PULL_BOX_GAP

        painter.end()


PULL_COLUMNS = ["Pull #", "Date", "Raid Night", "Difficulty", "Result", "Duration", "Phase"]


class EncounterProgressionPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.reports_repo = ReportRepository(db)
        self._encounters: list[tuple[int, str]] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(14)

        title = QLabel("Encounter Progression")
        title.setObjectName("pageTitle")
        self._layout.addWidget(title)

        subtitle = QLabel(
            "Full climb from first pull to farm on a selected boss. "
            "Progression pulls are everything up to and including the first kill "
            "at each difficulty. Farm pulls are every reclear after that."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        self._layout.addWidget(subtitle)

        picker_row = QHBoxLayout()
        picker_label = QLabel("Boss:")
        picker_label.setProperty("class", "muted")
        picker_row.addWidget(picker_label)
        self.encounter_combo = QComboBox()
        self.encounter_combo.setMinimumWidth(280)
        self.encounter_combo.currentIndexChanged.connect(self._refresh_detail)
        picker_row.addWidget(self.encounter_combo)
        picker_row.addStretch()
        self._layout.addLayout(picker_row)

        self.empty_state: AscendEmptyState | None = None
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(12)

        # Summary card
        self.summary_card = QFrame()
        self.summary_card.setProperty("class", "card")
        apply_card_elevation(self.summary_card)
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(16, 14, 16, 14)
        summary_layout.setSpacing(10)

        self.milestone_label = QLabel()
        self.milestone_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        summary_layout.addWidget(self.milestone_label)

        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(12)
        summary_layout.addLayout(self.stats_row)

        arc_label = QLabel("Pull arc:")
        arc_label.setProperty("class", "muted")
        arc_label.setStyleSheet("font-size: 11px;")
        summary_layout.addWidget(arc_label)

        self.arc_scroll = QScrollArea()
        self.arc_scroll.setWidgetResizable(True)
        self.arc_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.arc_scroll.setFixedHeight(_PULL_ARC_HEIGHT + 4)
        self.arc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.arc_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        summary_layout.addWidget(self.arc_scroll)

        detail_layout.addWidget(self.summary_card)

        # Pull-range bucket row
        self.range_row_layout = QHBoxLayout()
        self.range_row_layout.setSpacing(12)
        detail_layout.addLayout(self.range_row_layout)

        # Pull history table
        history_card = QFrame()
        history_card.setProperty("class", "card")
        apply_card_elevation(history_card)
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(16, 14, 16, 14)
        history_layout.setSpacing(8)

        history_title = QLabel("Pull History")
        history_title.setStyleSheet("font-size: 13px; font-weight: 600;")
        history_layout.addWidget(history_title)

        self.pull_table = QTableWidget(0, len(PULL_COLUMNS))
        self.pull_table.setHorizontalHeaderLabels(PULL_COLUMNS)
        self.pull_table.verticalHeader().setVisible(False)
        self.pull_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pull_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pull_table.setAlternatingRowColors(True)
        history_layout.addWidget(self.pull_table)
        detail_layout.addWidget(history_card, stretch=1)

        self._layout.addWidget(self.detail_widget, stretch=1)

        self.reload()

    def reload(self) -> None:
        self._encounters = self.reports_repo.distinct_encounters()
        show = bool(self._encounters)
        self.detail_widget.setVisible(show)
        self.encounter_combo.setVisible(show)
        if not show:
            if self.empty_state is None:
                self.empty_state = AscendEmptyState(
                    title="No Encounters Yet",
                    description="Analyze a Warcraft Logs report to see the progression arc here.",
                    icon_name="encounter_progression",
                )
                self._layout.addWidget(self.empty_state, stretch=1)
            self.empty_state.setVisible(True)
            return
        if self.empty_state is not None:
            self.empty_state.setVisible(False)

        self.encounter_combo.blockSignals(True)
        self.encounter_combo.clear()
        for encounter_id, name in self._encounters:
            self.encounter_combo.addItem(name, userData=encounter_id)
        self.encounter_combo.blockSignals(False)
        self._refresh_detail()

    def _clear_stats_row(self) -> None:
        while self.stats_row.count():
            item = self.stats_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _clear_range_row(self) -> None:
        while self.range_row_layout.count():
            item = self.range_row_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _refresh_detail(self) -> None:
        encounter_id = self.encounter_combo.currentData()
        if encounter_id is None:
            return

        pairs = self.reports_repo.fights_for_encounter(encounter_id)
        fights = [fight for _report, fight in pairs]
        classification = classify_pulls(fights)

        progression_fights = [f for f in fights if classification[f.id] != FARM]
        farm_fights = [f for f in fights if classification[f.id] == FARM]

        # First kill index within the progression list (0-based)
        first_kill_idx: int | None = None
        first_kill_pull: int | None = None
        for i, f in enumerate(progression_fights):
            if f.kill:
                first_kill_idx = i
                first_kill_pull = i + 1  # 1-based
                break

        # Milestone label
        if first_kill_pull is not None:
            self.milestone_label.setText(
                f"First kill on pull {first_kill_pull} of {len(progression_fights)} progression pull(s)"
            )
        else:
            self.milestone_label.setText(
                f"Still progressing — {len(progression_fights)} pull(s), no kill yet"
            )

        # Stats row badges
        self._clear_stats_row()
        total_kills = sum(1 for f in fights if f.kill)
        total_wipes = sum(1 for f in fights if f.kill is False)
        kill_rate = round(100 * total_kills / len(fights)) if fights else 0
        self.stats_row.addWidget(make_badge(f"Total pulls: {len(fights)}", tone="neutral"))
        self.stats_row.addWidget(make_badge(f"Progression: {len(progression_fights)}", tone="accent"))
        self.stats_row.addWidget(make_badge(f"Farm (reclears): {len(farm_fights)}", tone="neutral"))
        self.stats_row.addWidget(make_badge(f"Kills: {total_kills}", tone="success"))
        self.stats_row.addWidget(make_badge(f"Wipes: {total_wipes}", tone="error" if total_wipes > 0 else "neutral"))
        self.stats_row.addWidget(make_badge(f"Overall kill rate: {kill_rate}%", tone="info"))
        self.stats_row.addStretch()

        # Pull arc (all pulls in order, marking first kill)
        all_results = [f.kill for f in fights]
        # First kill index in the full fight list
        full_first_kill_idx: int | None = None
        for i, f in enumerate(fights):
            if f.kill and classification[f.id] != FARM:
                full_first_kill_idx = i
                break
        arc = _PullArcWidget(all_results, full_first_kill_idx)
        self.arc_scroll.setWidget(arc)

        # Pull-range buckets (progression only)
        self._clear_range_row()
        for group in group_by_pull_range(fights):
            card = self._build_range_card(group)
            self.range_row_layout.addWidget(card)
        self.range_row_layout.addStretch()

        # Pull history table
        self.pull_table.setRowCount(len(pairs))
        for row, (report, fight) in enumerate(pairs):
            difficulty_label = label_for_difficulty(self.db, report.zone_id, fight.difficulty)
            result = "Kill ✓" if fight.kill else ("Wipe" if fight.kill is False else "--")
            phase = "Farm" if classification[fight.id] == FARM else "Progression"

            items = [
                str(row + 1),
                f"{_format_date(report.start_time)} — {report.title or report.report_code}",
                report.title or report.report_code or "--",
                difficulty_label or "--",
                result,
                _format_duration(fight.start_time, fight.end_time),
                phase,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if fight.kill:
                    item.setForeground(QColor("#2d8a4e"))
                self.pull_table.setItem(row, col, item)

    def _build_range_card(self, group: dict) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(group["label"])
        title.setStyleSheet("font-size: 12px; font-weight: 600;")
        layout.addWidget(title)

        pulls, kills = group["pulls"], group["kills"]
        wipes = pulls - kills
        rate = round(100 * kills / pulls) if pulls else 0

        layout.addWidget(QLabel(f"{pulls} pulls"))
        layout.addWidget(QLabel(f"{kills} kills · {wipes} wipes"))
        rate_lbl = QLabel(f"{rate}% kill rate")
        tone = "success" if rate >= 80 else ("info" if rate >= 50 else "warning")
        rate_badge = make_badge(f"{rate}%", tone=tone)
        layout.addWidget(rate_badge)

        card.setFixedWidth(130)
        return card
