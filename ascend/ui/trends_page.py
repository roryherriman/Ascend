"""Trends - pull-range kill-rate curves and raid-night kill rate over time.

Shows what is honestly derivable from the data already ingested:
  - Per-encounter kill-rate across pull-range buckets (1-10 / 11-25 / 26-50 / 51+)
    - This is the "learning curve" view: did the raid improve as pull count grew?
  - Kill rate per raid night (how many kills per night, trending over time)

What requires event data (and therefore isn't shown yet):
  - DPS consistency trends
  - Mechanic correction speed
  - Defensive usage trends
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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
from ascend.services.encounter_classification import classify_pulls, group_by_pull_range
from ascend.theme import apply_card_elevation
from ascend.ui.components import AscendEmptyState
from ascend.ui.widgets import make_badge

_BAR_MAX_WIDTH = 160
_BAR_HEIGHT = 14


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return "--"
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return "--"


def _rate_tone(rate: int) -> str:
    if rate >= 80:
        return "success"
    if rate >= 50:
        return "info"
    return "warning"


class _BarWidget(QWidget):
    """A simple horizontal proportional fill bar."""

    def __init__(self, fill: float, color: QColor, parent: QWidget | None = None):
        super().__init__(parent)
        self._fill = max(0.0, min(1.0, fill))
        self._color = color
        self.setFixedSize(_BAR_MAX_WIDTH, _BAR_HEIGHT)

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.fillRect(0, 0, self.width(), self.height(), QColor("#2a2f3a"))
        filled_w = int(self._fill * self.width())
        if filled_w > 0:
            painter.fillRect(0, 0, filled_w, self.height(), self._color)
        painter.end()


BUCKET_COLUMNS = ["Pull Range", "Pulls", "Kills", "Wipes", "Kill Rate", "Trend"]
RAID_NIGHT_COLUMNS = ["Raid Night", "Encounters Attempted", "Pulls", "Kills", "Kill Rate"]


class TrendsPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.reports_repo = ReportRepository(db)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(16)

        title = QLabel("Learning & Trends")
        title.setObjectName("pageTitle")
        self._layout.addWidget(title)

        subtitle = QLabel(
            "Kill-rate curves show how quickly your raid improved on each boss as pulls accumulated. "
            "Performance trends (DPS, mechanic correction, defensive usage) require event-level "
            "data that isn't ingested yet."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        self._layout.addWidget(subtitle)

        self._body = QVBoxLayout()
        self._body.setSpacing(16)
        self._layout.addLayout(self._body)
        self._layout.addStretch()

        self.empty_state: AscendEmptyState | None = None
        self.reload()

    def reload(self) -> None:
        self._clear_body()

        encounters = self.reports_repo.distinct_encounters()
        if not encounters:
            self._show_empty()
            return

        # -- Per-encounter learning curves -----------------------------------
        curves_card = QFrame()
        curves_card.setProperty("class", "card")
        apply_card_elevation(curves_card)
        cl = QVBoxLayout(curves_card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(12)

        curves_title = QLabel("Kill Rate by Pull Range")
        curves_title.setStyleSheet("font-size: 13px; font-weight: 600;")
        cl.addWidget(curves_title)

        curves_note = QLabel("Per boss, progression pulls only — shows improvement as pull count grew.")
        curves_note.setProperty("class", "muted")
        curves_note.setStyleSheet("font-size: 11px;")
        curves_note.setWordWrap(True)
        cl.addWidget(curves_note)

        for encounter_id, encounter_name in encounters:
            pairs = self.reports_repo.fights_for_encounter(encounter_id)
            fights = [fight for _report, fight in pairs]
            groups = group_by_pull_range(fights)
            if not groups:
                continue

            enc_label = QLabel(encounter_name)
            enc_label.setStyleSheet("font-size: 12px; font-weight: 600; margin-top: 6px;")
            cl.addWidget(enc_label)

            table = QTableWidget(len(groups), len(BUCKET_COLUMNS))
            table.setHorizontalHeaderLabels(BUCKET_COLUMNS)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
            table.setAlternatingRowColors(True)
            table.setMaximumHeight(36 + 36 * len(groups))

            prev_rate: int | None = None
            for row, group in enumerate(groups):
                pulls, kills = group["pulls"], group["kills"]
                wipes = pulls - kills
                rate = round(100 * kills / pulls) if pulls else 0

                if prev_rate is not None:
                    if rate > prev_rate:
                        trend = f"+{rate - prev_rate}%  ▲"
                        trend_color = QColor("#2d8a4e")
                    elif rate < prev_rate:
                        trend = f"{rate - prev_rate}%  ▼"
                        trend_color = QColor("#c0392b")
                    else:
                        trend = "— (no change)"
                        trend_color = QColor("#6b7280")
                else:
                    trend = "baseline"
                    trend_color = QColor("#6b7280")
                prev_rate = rate

                def cell(text: str) -> QTableWidgetItem:
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    return item

                table.setItem(row, 0, cell(group["label"]))
                table.setItem(row, 1, cell(str(pulls)))
                table.setItem(row, 2, cell(str(kills)))
                table.setItem(row, 3, cell(str(wipes)))
                table.setItem(row, 4, cell(f"{rate}%"))

                trend_item = QTableWidgetItem(trend)
                trend_item.setFlags(trend_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                trend_item.setForeground(trend_color)
                trend_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 5, trend_item)

            cl.addWidget(table)

        self._body.addWidget(curves_card)

        # -- Raid night kill rates ------------------------------------------
        night_card = QFrame()
        night_card.setProperty("class", "card")
        apply_card_elevation(night_card)
        nl = QVBoxLayout(night_card)
        nl.setContentsMargins(16, 14, 16, 14)
        nl.setSpacing(10)

        night_title = QLabel("Kill Rate by Raid Night")
        night_title.setStyleSheet("font-size: 13px; font-weight: 600;")
        nl.addWidget(night_title)

        night_note = QLabel("All encounters combined, per raid night (report), chronological.")
        night_note.setProperty("class", "muted")
        night_note.setStyleSheet("font-size: 11px;")
        nl.addWidget(night_note)

        night_rows = self._compute_raid_night_kill_rates()
        if night_rows:
            table = QTableWidget(len(night_rows), len(RAID_NIGHT_COLUMNS))
            table.setHorizontalHeaderLabels(RAID_NIGHT_COLUMNS)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for col in range(1, len(RAID_NIGHT_COLUMNS)):
                table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            table.setAlternatingRowColors(True)
            table.setMaximumHeight(36 + 36 * min(len(night_rows), 15))

            for row, (date, title, enc_count, pulls, kills) in enumerate(night_rows):
                rate = round(100 * kills / pulls) if pulls else 0

                def cell(text: str) -> QTableWidgetItem:
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    return item

                table.setItem(row, 0, cell(f"{date} — {title}"))
                table.setItem(row, 1, cell(str(enc_count)))
                table.setItem(row, 2, cell(str(pulls)))
                table.setItem(row, 3, cell(str(kills)))
                rate_item = QTableWidgetItem(f"{rate}%")
                rate_item.setFlags(rate_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                rate_item.setForeground(QColor("#2d8a4e") if rate >= 60 else QColor("#e0a020"))
                table.setItem(row, 4, rate_item)

            nl.addWidget(table)
        else:
            no_data = QLabel("No raid nights with kill data yet.")
            no_data.setProperty("class", "muted")
            nl.addWidget(no_data)

        self._body.addWidget(night_card)

        # -- Unavailable data note ------------------------------------------
        unavail_card = QFrame()
        unavail_card.setProperty("class", "card")
        ul = QHBoxLayout(unavail_card)
        ul.setContentsMargins(16, 12, 16, 12)
        ul.addWidget(make_badge("NOT YET AVAILABLE", tone="neutral"))
        note = QLabel(
            "DPS consistency trends, mechanic correction speed, and defensive usage trends "
            "require ingested event-level data (Phase 3/4). They will appear here once "
            "event data is parsed from a verified Warcraft Logs payload."
        )
        note.setWordWrap(True)
        note.setProperty("class", "muted")
        note.setStyleSheet("font-size: 11px;")
        ul.addWidget(note, stretch=1)
        self._body.addWidget(unavail_card)

    def _compute_raid_night_kill_rates(self) -> list[tuple[str, str, int, int, int]]:
        """Returns (date_str, title, encounter_count, total_pulls, total_kills) per report, chronological."""
        reports = self.reports_repo.list_all()
        rows: list[tuple[float, str, str, int, int, int]] = []
        for report in reports:
            if report.id is None:
                continue
            report_fights = self.reports_repo.fights_for_report(report.id)
            if not report_fights:
                continue
            enc_ids = {f.encounter_id for f in report_fights if f.encounter_id}
            pulls = len(report_fights)
            kills = sum(1 for f in report_fights if f.kill)
            if pulls == 0:
                continue
            sort_key = report.start_time or 0.0
            date_str = _format_date(report.start_time)
            title = report.title or report.report_code or "--"
            rows.append((sort_key, date_str, title, len(enc_ids), pulls, kills))
        rows.sort(key=lambda r: r[0])
        return [(date, title, enc, pulls, kills) for _sort, date, title, enc, pulls, kills in rows]

    def _clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if self.empty_state is not None:
            self.empty_state.setVisible(False)

    def _show_empty(self) -> None:
        if self.empty_state is None:
            self.empty_state = AscendEmptyState(
                title="No Data Yet",
                description="Analyze a Warcraft Logs report to see kill-rate trends here.",
                icon_name="trends",
            )
            self._layout.insertWidget(self._layout.count() - 1, self.empty_state)
        self.empty_state.setVisible(True)
