"""Data Quality - makes sure Ascend never silently ignores missing or
uncertain data: sync success/failure history, character-identity
confidence, and small-sample warnings.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ascend.data.database import Database
from ascend.data.repositories import SyncHistoryRepository
from ascend.services.data_quality import DETECTED, NO_DATA, character_identity_confidence, small_sample_warnings
from ascend.theme import apply_card_elevation
from ascend.ui.widgets import make_badge

SYNC_COLUMNS = ["Started", "Type", "Status", "Reports", "Pulls", "Error"]
CONFIDENCE_COLUMNS = ["Character", "Raid Nights", "Participations", "Status"]

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

        self.confidence_table = QTableWidget(0, len(CONFIDENCE_COLUMNS))
        self.confidence_table.setHorizontalHeaderLabels(CONFIDENCE_COLUMNS)
        self.confidence_table.verticalHeader().setVisible(False)
        self.confidence_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.confidence_table.setMaximumHeight(160)
        layout.addWidget(self.confidence_table)

        return card

    def _refresh_confidence(self) -> None:
        entries = character_identity_confidence(self.db)
        self.confidence_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.confidence_table.setItem(row, 0, QTableWidgetItem(entry.display_name))
            self.confidence_table.setItem(row, 1, QTableWidgetItem(str(entry.raid_nights)))
            self.confidence_table.setItem(row, 2, QTableWidgetItem(str(entry.participations)))

            status_text = {
                DETECTED: "Detected", NO_DATA: "No Data Yet",
            }.get(entry.status, "Not Yet Detected")
            tone = _STATUS_TONE.get(entry.status, "warning")
            badge_wrap = QWidget()
            badge_layout = QHBoxLayout(badge_wrap)
            badge_layout.setContentsMargins(4, 2, 4, 2)
            badge_layout.addWidget(make_badge(status_text.upper(), tone=tone))
            badge_layout.addStretch()
            self.confidence_table.setCellWidget(row, 3, badge_wrap)

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
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Sync History")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        self.sync_table = QTableWidget(0, len(SYNC_COLUMNS))
        self.sync_table.setHorizontalHeaderLabels(SYNC_COLUMNS)
        self.sync_table.verticalHeader().setVisible(False)
        self.sync_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sync_table.setAlternatingRowColors(True)
        layout.addWidget(self.sync_table)

        return card

    def _refresh_sync_history(self) -> None:
        entries = SyncHistoryRepository(self.db).recent(limit=20)
        self.sync_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                _format_timestamp(entry.started_at),
                entry.operation_type,
                entry.status,
                str(entry.reports_processed),
                str(entry.pulls_processed),
                entry.error_message or "",
            ]
            for col, value in enumerate(values):
                self.sync_table.setItem(row, col, QTableWidgetItem(value))

    def reload(self) -> None:
        self._refresh_confidence()
        self._refresh_warnings()
        self._refresh_sync_history()
