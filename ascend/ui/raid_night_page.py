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
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
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


def _row_header(cols: list[tuple[str, int | None]]) -> QFrame:
    """Styled column-header strip. cols = [(label, stretch_or_fixed_px), ...]"""
    header = QFrame()
    header.setStyleSheet(
        f"background: {PALETTE.bg_card}; border-bottom: 1px solid {PALETTE.border};"
    )
    layout = QHBoxLayout(header)
    layout.setContentsMargins(10, 4, 10, 4)
    layout.setSpacing(8)
    for text, size in cols:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.5px; color: {PALETTE.text_muted};"
        )
        if isinstance(size, int) and size < 10:
            layout.addWidget(lbl, size)
        elif isinstance(size, int):
            lbl.setFixedWidth(size)
            layout.addWidget(lbl)
        else:
            layout.addWidget(lbl, 1)
    return header


def _data_row(values: list[tuple[str, int | None]], *, alt: bool = False) -> QFrame:
    """Plain data row matching _row_header column layout."""
    row = QFrame()
    bg = PALETTE.bg_card_hover if alt else "transparent"
    row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(8)
    for text, size in values:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px;")
        if isinstance(size, int) and size < 10:
            layout.addWidget(lbl, size)
        elif isinstance(size, int):
            lbl.setFixedWidth(size)
            layout.addWidget(lbl)
        else:
            layout.addWidget(lbl, 1)
    return row


# ---------------------------------------------------------------------------
# Pull Detail Dialog
# ---------------------------------------------------------------------------

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
            caption_lbl = QLabel(caption)
            caption_lbl.setProperty("class", "muted")
            row.addWidget(caption_lbl)
            row.addStretch()
            value_lbl = QLabel(value)
            value_lbl.setStyleSheet("font-weight: 600;")
            row.addWidget(value_lbl)
            layout.addLayout(row)

        participants_title = QLabel("Participants")
        participants_title.setStyleSheet("font-size: 12px; font-weight: 600; margin-top: 6px;")
        layout.addWidget(participants_title)

        reports_repo = ReportRepository(db)
        participants = reports_repo.participants_for_fight(fight.id) if fight.id else []

        participant_container = QWidget()
        p_layout = QVBoxLayout(participant_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(0)
        p_layout.addWidget(_row_header([("Name", 3), ("Server", 2), ("Class", 2)]))
        for i, p in enumerate(sorted(participants, key=lambda x: (x.name or "").lower())):
            p_layout.addWidget(_data_row(
                [(p.name or "--", 3), (p.server or "--", 2), (p.class_name or "--", 2)],
                alt=i % 2 == 1,
            ))
        layout.addWidget(participant_container)

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


# ---------------------------------------------------------------------------
# Raid Night Summary Page
# ---------------------------------------------------------------------------

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

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_pull_table_panel(), "Pulls")
        self._tabs.addTab(self._build_roster_panel(), "Roster")
        self._tabs.addTab(self._build_notes_panel(), "Notes")
        detail_layout.addWidget(self._tabs, stretch=1)

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

        header_row = QHBoxLayout()
        title = QLabel("Pulls")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        header_row.addWidget(title)
        header_row.addStretch()
        hint = QLabel("Click a pull to view detail")
        hint.setProperty("class", "muted")
        hint.setStyleSheet("font-size: 10px;")
        header_row.addWidget(hint)
        layout.addLayout(header_row)

        layout.addWidget(_row_header([("#", 40), ("Boss", 3), ("Difficulty", 2), ("Result", 1), ("Duration", 1)]))

        self._pulls_container = QWidget()
        self._pulls_layout = QVBoxLayout(self._pulls_container)
        self._pulls_layout.setContentsMargins(0, 0, 0, 0)
        self._pulls_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._pulls_container)
        layout.addWidget(scroll, stretch=1)

        return card

    def _clear_pulls(self) -> None:
        while self._pulls_layout.count():
            item = self._pulls_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _build_pull_row(
        self, pull_number: int, fight: Fight, report: Report, alt: bool
    ) -> QFrame:
        difficulty_label = label_for_difficulty(self.db, report.zone_id, fight.difficulty)
        result = "Kill ✓" if fight.kill else ("Wipe" if fight.kill is False else "--")

        row = QFrame()
        bg = PALETTE.bg_card_hover if alt else "transparent"
        row.setStyleSheet(
            f"background: {bg}; border-bottom: 1px solid {PALETTE.border};"
        )
        row.setCursor(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        num_lbl = QLabel(str(pull_number))
        num_lbl.setFixedWidth(40)
        num_lbl.setProperty("class", "muted")
        layout.addWidget(num_lbl)

        boss_lbl = QLabel(fight.name or "--")
        boss_lbl.setStyleSheet("font-weight: 600;")
        layout.addWidget(boss_lbl, 3)

        diff_lbl = QLabel(difficulty_label)
        diff_lbl.setProperty("class", "muted")
        layout.addWidget(diff_lbl, 2)

        result_lbl = QLabel(result)
        if fight.kill:
            result_lbl.setStyleSheet(f"color: {PALETTE.success}; font-weight: 600;")
        layout.addWidget(result_lbl, 1)

        dur_lbl = QLabel(_format_duration(fight.start_time, fight.end_time))
        dur_lbl.setProperty("class", "muted")
        layout.addWidget(dur_lbl, 1)

        # Capture for lambda closure
        _fight = fight
        _pull = pull_number
        row.mousePressEvent = lambda _ev, f=_fight, p=_pull: self._on_pull_clicked(f, p)

        return row

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

        layout.addWidget(_row_header([("Name", 2), ("Server", 2), ("Class", 2), ("", 1)]))

        self._roster_container = QWidget()
        self._roster_layout = QVBoxLayout(self._roster_container)
        self._roster_layout.setContentsMargins(0, 0, 0, 0)
        self._roster_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._roster_container)
        layout.addWidget(scroll, stretch=1)

        return card

    def _clear_roster(self) -> None:
        while self._roster_layout.count():
            item = self._roster_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _build_roster_row(self, entry: dict, alt: bool) -> QFrame:
        row = QFrame()
        bg = PALETTE.bg_card_hover if alt else "transparent"
        row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        layout.addWidget(QLabel(entry["name"]), 2)
        srv = QLabel(entry["server"])
        srv.setProperty("class", "muted")
        layout.addWidget(srv, 2)
        cls = QLabel(entry["class_name"])
        cls.setProperty("class", "muted")
        layout.addWidget(cls, 2)

        badge_wrap = QWidget()
        badge_layout = QHBoxLayout(badge_wrap)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        if entry["tracked"]:
            badge_layout.addWidget(make_badge("TRACKED", tone="accent"))
        badge_layout.addStretch()
        layout.addWidget(badge_wrap, 1)

        return row

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
        """External navigation hook, e.g. from Reports page's 'View Raid Night' action."""
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

    def _on_pull_clicked(self, fight: Fight, pull_number: int) -> None:
        report = self._current_report()
        if report is None:
            return
        dialog = PullDetailDialog(self.db, report, fight, pull_number=pull_number, parent=self)
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

        self._clear_pulls()
        for i, fight in enumerate(fights):
            self._pulls_layout.addWidget(self._build_pull_row(i + 1, fight, report, alt=i % 2 == 1))

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

        self._clear_roster()
        for i, entry in enumerate(sorted(roster.values(), key=lambda r: r["name"].lower())):
            self._roster_layout.addWidget(self._build_roster_row(entry, alt=i % 2 == 1))


