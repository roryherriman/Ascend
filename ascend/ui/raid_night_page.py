"""Raid Night Summary - brings together everything Ascend knows about one
raid night: overview, pull-by-pull table, and the roster detected in it.

Score/classification and participation/survival breakdowns need the scoring
engine and event-level data (Phase 3) and are intentionally not shown here
yet - see the Empty Component Rule (docs/ARCHITECTURE.md) for why this page
doesn't pad itself out with empty placeholders for that.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ascend.api.url_parser import build_report_url
from ascend.data.database import Database
from ascend.data.models import Fight, Report
from ascend.data.repositories import ReportRepository
from ascend.services.zone_data import label_for_difficulty
from ascend.theme import PALETTE, apply_card_elevation
from ascend.ui.components import AscendEmptyState
from ascend.ui.widgets import make_badge

PULL_COLUMNS = ["Pull #", "Boss", "Difficulty", "Result", "Duration"]
ROSTER_COLUMNS = ["Name", "Server", "Class", "Tracked"]


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return "--"
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (OSError, OverflowError, ValueError):
        return "--"


def _format_duration(start: float | None, end: float | None) -> str:
    if start is None or end is None or end < start:
        return "--"
    total_seconds = int((end - start) / 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


class PullDetailDialog(QDialog):
    """Drill-down for a single pull: what we objectively know about it
    (boss, difficulty, result, timing, participants) plus a direct link to
    the fight on Warcraft Logs as the evidence - Ascend doesn't yet ingest
    event-level data (deaths, damage, etc.), so it doesn't fabricate a local
    evidence panel; the authoritative source is one click away instead."""

    def __init__(
        self,
        db: Database,
        report: Report,
        fight: Fight,
        pull_number: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Pull {pull_number} - {fight.name or 'Unknown Encounter'}")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel(fight.name or "Unknown Encounter")
        header.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(header)

        difficulty_label = label_for_difficulty(db, report.zone_id, fight.difficulty)
        result = "Kill" if fight.kill else ("Wipe" if fight.kill is False else "--")
        for caption, value in [
            ("Pull #", str(pull_number)),
            ("Difficulty", difficulty_label),
            ("Result", result),
            ("Duration", _format_duration(fight.start_time, fight.end_time)),
        ]:
            row = QHBoxLayout()
            caption_label = QLabel(caption)
            caption_label.setProperty("class", "muted")
            row.addWidget(caption_label)
            row.addStretch()
            value_label = QLabel(value)
            value_label.setStyleSheet("font-weight: 600;")
            row.addWidget(value_label)
            layout.addLayout(row)

        participants_title = QLabel("Participants")
        participants_title.setStyleSheet("font-size: 12px; font-weight: 600; margin-top: 6px;")
        layout.addWidget(participants_title)

        reports_repo = ReportRepository(db)
        participants = reports_repo.participants_for_fight(fight.id) if fight.id else []
        self.participants_table = QTableWidget(len(participants), 3)
        self.participants_table.setHorizontalHeaderLabels(["Name", "Server", "Class"])
        self.participants_table.verticalHeader().setVisible(False)
        self.participants_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.participants_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, participant in enumerate(sorted(participants, key=lambda p: (p.name or "").lower())):
            self.participants_table.setItem(row, 0, QTableWidgetItem(participant.name or "--"))
            self.participants_table.setItem(row, 1, QTableWidgetItem(participant.server or "--"))
            self.participants_table.setItem(row, 2, QTableWidgetItem(participant.class_name or "--"))
        layout.addWidget(self.participants_table)

        self.evidence_button = QPushButton("Open This Pull on Warcraft Logs")
        self.evidence_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(build_report_url(report.report_code, fight.fight_id)))
        )
        layout.addWidget(self.evidence_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)


class RaidNightSummaryPage(QWidget):
    view_reports_requested = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.reports_repo = ReportRepository(db)
        self._reports: list[Report] = []
        self._current_fights: list[Fight] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(14)

        title = QLabel("Raid Night Summary")
        title.setObjectName("pageTitle")
        self._layout.addWidget(title)

        self._picker_row = QHBoxLayout()
        picker_label = QLabel("Raid Night:")
        picker_label.setProperty("class", "muted")
        self._picker_row.addWidget(picker_label)
        self.report_combo = QComboBox()
        self.report_combo.setMinimumWidth(320)
        self.report_combo.currentIndexChanged.connect(self._on_report_selected)
        self._picker_row.addWidget(self.report_combo)
        self._picker_row.addStretch()
        self._layout.addLayout(self._picker_row)

        self.empty_state: AscendEmptyState | None = None
        self.detail_container = QWidget()
        detail_layout = QVBoxLayout(self.detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(14)

        self.overview_row = self._build_overview_row()
        detail_layout.addLayout(self.overview_row)

        content_row = QHBoxLayout()
        content_row.setSpacing(14)
        content_row.addWidget(self._build_pull_table_panel(), stretch=7)
        content_row.addWidget(self._build_roster_panel(), stretch=5)
        detail_layout.addLayout(content_row, stretch=1)

        detail_layout.addWidget(self._build_notes_panel())

        self._layout.addWidget(self.detail_container, stretch=1)

        self.reload()

    # -- Overview -----------------------------------------------------------

    def _build_overview_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(24)
        self._overview_labels: dict[str, QLabel] = {}
        for key, caption in [
            ("date", "Date"), ("guild", "Guild"), ("pulls", "Pulls"),
            ("kills", "Kills / Wipes"), ("duration", "Total Duration"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(2)
            caption_label = QLabel(caption.upper())
            caption_label.setProperty("class", "muted")
            caption_label.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
            col.addWidget(caption_label)
            value_label = QLabel("--")
            value_label.setStyleSheet("font-size: 15px; font-weight: 600;")
            col.addWidget(value_label)
            self._overview_labels[key] = value_label
            row.addLayout(col)
        row.addStretch()
        return row

    # -- Pull table -----------------------------------------------------------

    def _build_pull_table_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Pulls")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        self.pull_table = QTableWidget(0, len(PULL_COLUMNS))
        self.pull_table.setHorizontalHeaderLabels(PULL_COLUMNS)
        self.pull_table.verticalHeader().setVisible(False)
        self.pull_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pull_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pull_table.setAlternatingRowColors(True)
        self.pull_table.cellDoubleClicked.connect(self._on_pull_double_clicked)
        layout.addWidget(self.pull_table)

        hint = QLabel("Double-click a pull to view its detail and roster.")
        hint.setProperty("class", "muted")
        hint.setStyleSheet("font-size: 10px;")
        layout.addWidget(hint)

        return card

    # -- Roster -----------------------------------------------------------

    def _build_roster_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Roster")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        self.roster_table = QTableWidget(0, len(ROSTER_COLUMNS))
        self.roster_table.setHorizontalHeaderLabels(ROSTER_COLUMNS)
        self.roster_table.verticalHeader().setVisible(False)
        self.roster_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.roster_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.roster_table.setAlternatingRowColors(True)
        layout.addWidget(self.roster_table)

        return card

    # -- Notes (manual annotation) -------------------------------------------

    def _build_notes_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel("Notes")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        header_row.addWidget(title)
        header_row.addStretch()
        self.save_notes_button = QPushButton("Save Notes")
        self.save_notes_button.setObjectName("secondaryFlatButton")
        self.save_notes_button.clicked.connect(self._on_save_notes)
        header_row.addWidget(self.save_notes_button)
        layout.addLayout(header_row)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText(
            "Add a manual note for this raid night - e.g. why a pull was skipped, "
            "who was on standby, anything worth remembering later."
        )
        self.notes_edit.setFixedHeight(70)
        layout.addWidget(self.notes_edit)

        return card

    def _on_save_notes(self) -> None:
        report = self._current_report()
        if report is None or report.id is None:
            return
        self.reports_repo.update_notes(report.id, self.notes_edit.toPlainText())
        report.notes = self.notes_edit.toPlainText()

    # -- Data -----------------------------------------------------------

    def reload(self) -> None:
        self._reports = self.reports_repo.list_all()
        self._show_empty_state(not self._reports)
        if not self._reports:
            return

        self.report_combo.blockSignals(True)
        self.report_combo.clear()
        for report in self._reports:
            label = f"{_format_date(report.start_time)} - {report.title or report.report_code}"
            self.report_combo.addItem(label, userData=report.id)
        self.report_combo.blockSignals(False)
        self._refresh_detail()

    def select_report(self, report_id: int) -> None:
        """External navigation hook, e.g. from Reports page's 'View Raid Night
        Summary' action."""
        self.reload()
        for i in range(self.report_combo.count()):
            if self.report_combo.itemData(i) == report_id:
                self.report_combo.setCurrentIndex(i)
                return

    def _show_empty_state(self, empty: bool) -> None:
        self.detail_container.setVisible(not empty)
        for i in range(self._picker_row.count()):
            widget = self._picker_row.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(not empty)
        if empty and self.empty_state is None:
            self.empty_state = AscendEmptyState(
                title="No Raid Nights Yet",
                description="Analyze a Warcraft Logs report from the Dashboard or Reports page "
                "to see its pull-by-pull summary and roster here.",
                icon_name="raid_night",
                primary_action=("Go to Reports", self.view_reports_requested.emit),
            )
            self._layout.addWidget(self.empty_state, stretch=1)
        if self.empty_state is not None:
            self.empty_state.setVisible(empty)

    def _on_report_selected(self, _index: int) -> None:
        self._refresh_detail()

    def _current_report(self) -> Report | None:
        report_id = self.report_combo.currentData()
        return next((r for r in self._reports if r.id == report_id), None)

    def _on_pull_double_clicked(self, row: int, _column: int) -> None:
        report = self._current_report()
        if report is None or row >= len(self._current_fights):
            return
        fight = self._current_fights[row]
        dialog = PullDetailDialog(self.db, report, fight, pull_number=row + 1, parent=self)
        dialog.exec()

    def _refresh_detail(self) -> None:
        report = self._current_report()
        if report is None:
            return

        fights = self.reports_repo.fights_for_report(report.id)
        self._current_fights = fights
        kills = sum(1 for f in fights if f.kill)
        wipes = sum(1 for f in fights if f.kill is False)
        total_ms = sum(
            (f.end_time - f.start_time) for f in fights
            if f.start_time is not None and f.end_time is not None and f.end_time >= f.start_time
        )

        self._overview_labels["date"].setText(_format_date(report.start_time))
        self._overview_labels["guild"].setText(report.guild_name or report.owner_name or "--")
        self._overview_labels["pulls"].setText(str(len(fights)))
        self._overview_labels["kills"].setText(f"{kills} / {wipes}")
        self._overview_labels["duration"].setText(_format_duration(0, total_ms) if fights else "--")
        self.notes_edit.setPlainText(report.notes)

        self.pull_table.setRowCount(len(fights))
        for row, fight in enumerate(fights):
            difficulty_label = label_for_difficulty(self.db, report.zone_id, fight.difficulty)
            result = "Kill" if fight.kill else ("Wipe" if fight.kill is False else "--")
            values = [
                str(row + 1),
                fight.name or "--",
                difficulty_label,
                result,
                _format_duration(fight.start_time, fight.end_time),
            ]
            for col, value in enumerate(values):
                self.pull_table.setItem(row, col, QTableWidgetItem(value))

        roster: dict[tuple[str, str], dict] = {}
        for fight in fights:
            for participant in self.reports_repo.participants_for_fight(fight.id):
                key = (participant.name or "", participant.server or "")
                roster[key] = {
                    "name": participant.name or "--",
                    "server": participant.server or "--",
                    "class_name": participant.class_name or "--",
                    "tracked": participant.character_id is not None,
                }

        roster_rows = sorted(roster.values(), key=lambda r: r["name"].lower())
        self.roster_table.setRowCount(len(roster_rows))
        for row, entry in enumerate(roster_rows):
            self.roster_table.setItem(row, 0, QTableWidgetItem(entry["name"]))
            self.roster_table.setItem(row, 1, QTableWidgetItem(entry["server"]))
            self.roster_table.setItem(row, 2, QTableWidgetItem(entry["class_name"]))
            badge_wrap = QWidget()
            badge_layout = QHBoxLayout(badge_wrap)
            badge_layout.setContentsMargins(4, 2, 4, 2)
            if entry["tracked"]:
                badge_layout.addWidget(make_badge("TRACKED", tone="accent"))
            badge_layout.addStretch()
            self.roster_table.setCellWidget(row, 3, badge_wrap)
