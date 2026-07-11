"""Roster Comparison - basic attendance-based comparison against the players
you actually raid with.

Same-spec/same-class performance comparison and roster percentiles need
event-level performance data Ascend doesn't ingest yet (Phase 3) - this page
shows attendance (raid nights and pulls together) only, which is honestly
derivable from what's already synced, rather than padding itself out with
empty performance columns.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.services.roster import roster_summary
from ascend.theme import PALETTE, apply_card_elevation
from ascend.ui.components import AscendEmptyState
from ascend.ui.widgets import make_badge


def _header_row() -> QFrame:
    row = QFrame()
    row.setStyleSheet(
        f"background: {PALETTE.bg_card}; border-bottom: 1px solid {PALETTE.border};"
    )
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 4, 10, 4)
    layout.setSpacing(8)
    for text, stretch in [("Name", 3), ("Server", 2), ("Class", 2), ("Raid Nights", 1), ("Pulls", 1), ("", 1)]:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.5px; color: {PALETTE.text_muted};"
        )
        layout.addWidget(lbl, stretch)
    return row


def _member_row(member, alt: bool) -> QFrame:
    row = QFrame()
    bg = PALETTE.bg_card_hover if alt else "transparent"
    row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(8)

    name_lbl = QLabel(member.name)
    name_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
    layout.addWidget(name_lbl, 3)

    for text, stretch in [
        (member.server or "--", 2),
        (member.class_name or "--", 2),
        (str(member.raid_nights), 1),
        (str(member.pulls), 1),
    ]:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 12px; color: {PALETTE.text_secondary};")
        layout.addWidget(lbl, stretch)

    badge_wrap = QWidget()
    badge_layout = QHBoxLayout(badge_wrap)
    badge_layout.setContentsMargins(0, 0, 0, 0)
    if member.character_id is not None:
        badge_layout.addWidget(make_badge("TRACKED", tone="accent"))
    badge_layout.addStretch()
    layout.addWidget(badge_wrap, 1)

    return row


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

        self._card = QFrame()
        self._card.setProperty("class", "card")
        apply_card_elevation(self._card)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        card_layout.addWidget(_header_row())

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._rows_container)
        card_layout.addWidget(scroll, stretch=1)

        self._layout.addWidget(self._card, stretch=1)

        self.empty_state: AscendEmptyState | None = None

        self.reload()

    def reload(self) -> None:
        members = roster_summary(self.db)

        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        self._card.setVisible(bool(members))
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

        sorted_members = sorted(members, key=lambda m: (-m.pulls, m.name.lower()))
        for i, member in enumerate(sorted_members):
            self._rows_layout.addWidget(_member_row(member, alt=i % 2 == 1))
