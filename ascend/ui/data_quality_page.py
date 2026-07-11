"""Data Quality - makes sure Ascend never silently ignores missing or
uncertain data: sync success/failure history, character-identity
confidence, and small-sample warnings.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ascend.theme import PALETTE

from ascend.data.database import Database
from ascend.data.repositories import SyncHistoryRepository
from ascend.services.data_quality import DETECTED, NO_DATA, character_identity_confidence, small_sample_warnings
from ascend.theme import apply_card_elevation
from ascend.ui.widgets import make_badge

_CONF_COLS = [("Character", 3), ("Raid Nights", 1), ("Participations", 1), ("Status", 2)]
_SYNC_COLS = [("Started", 2), ("Type", 1), ("Status", 1), ("Reports", 1), ("Pulls", 1), ("Error", 3)]

_STATUS_TONE = {DETECTED: "success", NO_DATA: "neutral"}  # NOT_DETECTED falls through to "warning"


def _format_timestamp(iso_string: str | None) -> str:
    if not iso_string:
        return "--"
    try:
        return datetime.fromisoformat(iso_string).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_string


class DataQualityPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Data Quality")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addWidget(self._build_confidence_panel())
        layout.addWidget(self._build_warnings_panel())
        layout.addWidget(self._build_sync_history_panel(), stretch=1)

        self.reload()

    # -- Character identity confidence ---------------------------------------

    def _build_confidence_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Character Identity Confidence")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Whether each tracked character has actually been detected in a synced report - "
            "'Not Yet Detected' usually means the character name or server on file doesn't "
            "exactly match what Warcraft Logs reports."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 11px;")
        layout.addWidget(subtitle)

        self._confidence_rows_layout = QVBoxLayout()
        self._confidence_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._confidence_rows_layout.setSpacing(0)
        layout.addLayout(self._confidence_rows_layout)

        return card

    def _col_header(self, cols: list) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            f"background: {PALETTE.bg_card}; border-bottom: 1px solid {PALETTE.border};"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(8)
        for text, stretch in cols:
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(
                f"font-size: 10px; font-weight: 700; letter-spacing: 0.4px; color: {PALETTE.text_muted};"
            )
            h.addWidget(lbl, stretch)
        return row

    def _refresh_confidence(self) -> None:
        while self._confidence_rows_layout.count():
            item = self._confidence_rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        entries = character_identity_confidence(self.db)
        if not entries:
            lbl = QLabel("No tracked characters yet.")
            lbl.setProperty("class", "muted")
            lbl.setStyleSheet("font-size: 11px; padding: 6px 10px;")
            self._confidence_rows_layout.addWidget(lbl)
            return

        self._confidence_rows_layout.addWidget(self._col_header(_CONF_COLS))
        for i, entry in enumerate(entries):
            row = QFrame()
            bg = PALETTE.bg_card_hover if i % 2 == 1 else "transparent"
            row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
            h = QHBoxLayout(row)
            h.setContentsMargins(10, 5, 10, 5)
            h.setSpacing(8)

            for text, stretch in [(entry.display_name, 3), (str(entry.raid_nights), 1), (str(entry.participations), 1)]:
                lbl = QLabel(text)
                lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE.text_secondary};")
                h.addWidget(lbl, stretch)

            status_text = {DETECTED: "Detected", NO_DATA: "No Data Yet"}.get(entry.status, "Not Yet Detected")
            tone = _STATUS_TONE.get(entry.status, "warning")
            badge_wrap = QWidget()
            badge_layout = QHBoxLayout(badge_wrap)
            badge_layout.setContentsMargins(0, 0, 0, 0)
            badge_layout.addWidget(make_badge(status_text.upper(), tone=tone))
            badge_layout.addStretch()
            h.addWidget(badge_wrap, 2)
            self._confidence_rows_layout.addWidget(row)

    # -- Small-sample warnings -------------------------------------------------

    def _build_warnings_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title = QLabel("Small-Sample Warnings")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        self.warnings_container = QVBoxLayout()
        self.warnings_container.setSpacing(4)
        layout.addLayout(self.warnings_container)

        self.no_warnings_label = QLabel("No small-sample reports or encounters right now.")
        self.no_warnings_label.setProperty("class", "muted")
        self.no_warnings_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.no_warnings_label)

        return card

    def _refresh_warnings(self) -> None:
        while self.warnings_container.count():
            item = self.warnings_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        warnings = small_sample_warnings(self.db)
        self.no_warnings_label.setVisible(not warnings)
        for warning in warnings:
            kind_label = "report" if warning.kind == "report" else "encounter"
            label = QLabel(f"⚠ {warning.subject} - only {warning.pulls} pull(s) logged ({kind_label})")
            label.setStyleSheet("font-size: 11px;")
            self.warnings_container.addWidget(label)

    # -- Sync history -----------------------------------------------------

    def _build_sync_history_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        apply_card_elevation(card)
        self._sync_card_layout = QVBoxLayout(card)
        self._sync_card_layout.setContentsMargins(16, 14, 16, 14)
        self._sync_card_layout.setSpacing(8)

        title = QLabel("Sync History")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        self._sync_card_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(220)
        self._sync_rows_container = QWidget()
        self._sync_rows_layout = QVBoxLayout(self._sync_rows_container)
        self._sync_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._sync_rows_layout.setSpacing(0)
        scroll.setWidget(self._sync_rows_container)
        self._sync_card_layout.addWidget(scroll, stretch=1)

        return card

    def _refresh_sync_history(self) -> None:
        while self._sync_rows_layout.count():
            item = self._sync_rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        entries = SyncHistoryRepository(self.db).recent(limit=20)
        if not entries:
            lbl = QLabel("No sync history yet.")
            lbl.setProperty("class", "muted")
            lbl.setStyleSheet("font-size: 11px; padding: 6px 10px;")
            self._sync_rows_layout.addWidget(lbl)
            return

        self._sync_rows_layout.addWidget(self._col_header(_SYNC_COLS))
        for i, entry in enumerate(entries):
            row = QFrame()
            bg = PALETTE.bg_card_hover if i % 2 == 1 else "transparent"
            row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
            h = QHBoxLayout(row)
            h.setContentsMargins(10, 5, 10, 5)
            h.setSpacing(8)
            values = [
                (_format_timestamp(entry.started_at), 2),
                (entry.operation_type, 1),
                (entry.status, 1),
                (str(entry.reports_processed), 1),
                (str(entry.pulls_processed), 1),
                (entry.error_message or "", 3),
            ]
            for text, stretch in values:
                lbl = QLabel(text)
                lbl.setStyleSheet(f"font-size: 11px; color: {PALETTE.text_secondary};")
                lbl.setWordWrap(False)
                h.addWidget(lbl, stretch)
            self._sync_rows_layout.addWidget(row)

    def reload(self) -> None:
        self._refresh_confidence()
        self._refresh_warnings()
        self._refresh_sync_history()
