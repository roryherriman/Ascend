"""Roster Comparison - basic attendance-based comparison against the players
you actually raid with.

Same-spec/same-class performance comparison and roster percentiles need
event-level performance data Ascend doesn't ingest yet (Phase 3) - this page
shows attendance (raid nights and pulls together) only, which is honestly
derivable from what's already synced, rather than padding itself out with
empty performance columns.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ascend.data.database import Database
from ascend.services.roster import roster_summary
from ascend.ui.components import AscendEmptyState
from ascend.ui.widgets import make_badge

COLUMNS = ["Name", "Server", "Class", "Raid Nights", "Pulls", "Tracked"]


class RosterComparisonPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(14)

        title = QLabel("Roster Comparison")
        title.setObjectName("pageTitle")
        self._layout.addWidget(title)

        subtitle = QLabel(
            "Attendance across the players you actually raid with. Performance comparison "
            "(damage, roster percentile) arrives once event-level data is analyzed."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        self._layout.addWidget(subtitle)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self._layout.addWidget(self.table, stretch=1)

        self.empty_state: AscendEmptyState | None = None

        self.reload()

    def reload(self) -> None:
        members = roster_summary(self.db)
        self.table.setVisible(bool(members))
        if self.empty_state is not None:
            self.empty_state.setVisible(not members)
        elif not members:
            self.empty_state = AscendEmptyState(
                title="No Roster Data Yet",
                description="Analyze a Warcraft Logs report to see who you raid with and how "
                "often, here.",
                icon_name="roster",
            )
            self._layout.addWidget(self.empty_state, stretch=1)
        if not members:
            return

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(members))
        for row, member in enumerate(members):
            values = [
                member.name,
                member.server or "--",
                member.class_name or "--",
                str(member.raid_nights),
                str(member.pulls),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
            # Numeric DisplayRole data so column sorting compares as numbers, not strings.
            self.table.item(row, 3).setData(Qt.ItemDataRole.DisplayRole, member.raid_nights)
            self.table.item(row, 4).setData(Qt.ItemDataRole.DisplayRole, member.pulls)

            badge_wrap = QWidget()
            badge_layout = QHBoxLayout(badge_wrap)
            badge_layout.setContentsMargins(4, 2, 4, 2)
            if member.character_id is not None:
                badge_layout.addWidget(make_badge("TRACKED", tone="accent"))
            badge_layout.addStretch()
            self.table.setCellWidget(row, len(COLUMNS) - 1, badge_wrap)
        self.table.setSortingEnabled(True)
