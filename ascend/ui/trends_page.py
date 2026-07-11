"""Trends - pull-range kill-rate curves and raid-night kill rate over time.

Shows what is honestly derivable from the data already ingested:
  - Per-encounter kill-rate across pull-range buckets (1-10 / 11-25 / 26-50 / 51+)
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
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.data.repositories import ReportRepository
from ascend.services.encounter_classification import classify_pulls, group_by_pull_range
from ascend.theme import PALETTE, apply_card_elevation
from ascend.ui.components import AscendEmptyState
from ascend.ui.widgets import make_badge

_BAR_MAX_WIDTH = 140
_BAR_HEIGHT = 12


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return "--"
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return "--"


def _rate_color(rate: int) -> str:
    if rate >= 80:
        return PALETTE.success
    if rate >= 50:
        return PALETTE.info
    return PALETTE.warning


class _BarWidget(QWidget):
    def __init__(self, fill: float, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._fill = max(0.0, min(1.0, fill))
        self._color = QColor(color)
        self.setFixedSize(_BAR_MAX_WIDTH, _BAR_HEIGHT)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(0, 0, self.width(), self.height(), QColor(PALETTE.border))
        filled_w = int(self._fill * self.width())
        if filled_w > 0:
            painter.fillRect(0, 0, filled_w, self.height(), self._color)
        painter.end()


def _col_header(texts: list[tuple[str, int]]) -> QFrame:
    row = QFrame()
    row.setStyleSheet(
        f"background: {PALETTE.bg_card}; border-bottom: 1px solid {PALETTE.border};"
    )
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 4, 10, 4)
    layout.setSpacing(8)
    for text, stretch in texts:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.4px; color: {PALETTE.text_muted};"
        )
        layout.addWidget(lbl, stretch)
    return row


def _bucket_row(group: dict, prev_rate: int | None, alt: bool) -> QFrame:
    pulls, kills = group["pulls"], group["kills"]
    wipes = pulls - kills
    rate = round(100 * kills / pulls) if pulls else 0

    if prev_rate is not None:
        delta = rate - prev_rate
        if delta > 0:
            trend = f"+{delta}% ▲"
            trend_color = PALETTE.success
        elif delta < 0:
            trend = f"{delta}% ▼"
            trend_color = PALETTE.error if hasattr(PALETTE, "error") else "#c0392b"
        else:
            trend = "— no change"
            trend_color = PALETTE.text_muted
    else:
        trend = "baseline"
        trend_color = PALETTE.text_muted

    row = QFrame()
    bg = PALETTE.bg_card_hover if alt else "transparent"
    row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(8)

    for text, stretch in [(group["label"], 2), (str(pulls), 1), (str(kills), 1), (str(wipes), 1)]:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE.text_secondary};")
        layout.addWidget(lbl, stretch)

    rate_lbl = QLabel(f"{rate}%")
    rate_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {_rate_color(rate)};")
    layout.addWidget(rate_lbl, 1)

    bar = _BarWidget(rate / 100, _rate_color(rate))
    layout.addWidget(bar, 2)

    trend_lbl = QLabel(trend)
    trend_lbl.setStyleSheet(f"font-size: 11px; color: {trend_color};")
    layout.addWidget(trend_lbl, 2)

    return row


def _night_row(date: str, title: str, enc_count: int, pulls: int, kills: int, alt: bool) -> QFrame:
    rate = round(100 * kills / pulls) if pulls else 0
    row = QFrame()
    bg = PALETTE.bg_card_hover if alt else "transparent"
    row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(8)

    date_lbl = QLabel(date)
    date_lbl.setStyleSheet(f"font-size: 11px; color: {PALETTE.text_muted};")
    layout.addWidget(date_lbl, 1)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
    layout.addWidget(title_lbl, 3)

    for text, stretch in [(str(enc_count), 1), (str(pulls), 1), (str(kills), 1)]:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE.text_secondary};")
        layout.addWidget(lbl, stretch)

    rate_lbl = QLabel(f"{rate}%")
    rate_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {_rate_color(rate)};")
    layout.addWidget(rate_lbl, 1)

    return row


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

            bucket_container = QWidget()
            bucket_layout = QVBoxLayout(bucket_container)
            bucket_layout.setContentsMargins(0, 0, 0, 0)
            bucket_layout.setSpacing(0)
            bucket_layout.addWidget(_col_header([
                ("Pull Range", 2), ("Pulls", 1), ("Kills", 1), ("Wipes", 1),
                ("Kill Rate", 1), ("", 2), ("Trend", 2),
            ]))

            prev_rate: int | None = None
            for i, group in enumerate(groups):
                pulls = group["pulls"]
                kills = group["kills"]
                rate = round(100 * kills / pulls) if pulls else 0
                bucket_layout.addWidget(_bucket_row(group, prev_rate, alt=i % 2 == 1))
                prev_rate = rate

            cl.addWidget(bucket_container)

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
            night_container = QWidget()
            night_layout = QVBoxLayout(night_container)
            night_layout.setContentsMargins(0, 0, 0, 0)
            night_layout.setSpacing(0)
            night_layout.addWidget(_col_header([
                ("Date", 1), ("Raid Night", 3), ("Encounters", 1), ("Pulls", 1), ("Kills", 1), ("Kill Rate", 1),
            ]))
            for i, (date, title, enc_count, pulls, kills) in enumerate(night_rows):
                night_layout.addWidget(_night_row(date, title, enc_count, pulls, kills, alt=i % 2 == 1))
            nl.addWidget(night_container)
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
