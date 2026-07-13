"""Goals page — track raid performance goals and mark them achieved."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.services.goals_service import Goal, GoalsRepository
from ascend.theme import PALETTE, apply_card_elevation
from ascend.ui.components import AscendEmptyState
from ascend.ui.widgets import make_badge


def _goal_row(goal: Goal, on_toggle, on_delete, alt: bool) -> QFrame:
    row = QFrame()
    bg = PALETTE.bg_card_hover if alt else "transparent"
    row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
    h = QHBoxLayout(row)
    h.setContentsMargins(12, 8, 12, 8)
    h.setSpacing(10)

    title_lbl = QLabel(goal.title)
    title_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
    h.addWidget(title_lbl, 3)

    if goal.description:
        desc_lbl = QLabel(goal.description)
        desc_lbl.setStyleSheet(f"font-size: 11px; color: {PALETTE.text_muted};")
        desc_lbl.setWordWrap(True)
        h.addWidget(desc_lbl, 3)

    if goal.target_date:
        days = goal.days_remaining()
        if goal.achieved_at:
            date_text = "Achieved"
            tone = "success"
        elif days is None:
            date_text = goal.target_date
            tone = "neutral"
        elif days < 0:
            date_text = f"{abs(days)}d overdue"
            tone = "error" if hasattr(PALETTE, "error") else "warning"
        elif days == 0:
            date_text = "Due today"
            tone = "warning"
        else:
            date_text = f"{days}d left"
            tone = "info"
        h.addWidget(make_badge(date_text, tone=tone), 1)

    status_tone = "success" if goal.achieved_at else "neutral"
    status_text = "ACHIEVED" if goal.achieved_at else "PENDING"
    h.addWidget(make_badge(status_text, tone=status_tone))

    toggle_btn = QPushButton("Unmark" if goal.achieved_at else "Mark Done")
    toggle_btn.setFixedWidth(90)
    toggle_btn.clicked.connect(lambda: on_toggle(goal))
    h.addWidget(toggle_btn)

    del_btn = QPushButton("Delete")
    del_btn.setFixedWidth(60)
    del_btn.setStyleSheet(f"color: {PALETTE.error if hasattr(PALETTE, 'error') else '#c0392b'};")
    del_btn.clicked.connect(lambda: on_delete(goal))
    h.addWidget(del_btn)

    return row


class _AddGoalDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Goal")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Kill Mythic Sark this tier")
        form.addRow("Title:", self.title_edit)

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional notes")
        form.addRow("Description:", self.desc_edit)

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYY-MM-DD (optional)")
        form.addRow("Target Date:", self.date_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_goal(self) -> Goal | None:
        title = self.title_edit.text().strip()
        if not title:
            return None
        date_str = self.date_edit.text().strip() or None
        return Goal(
            id=None,
            title=title,
            description=self.desc_edit.text().strip(),
            metric_key="manual",
            target_value=1.0,
            target_date=date_str,
        )


class GoalsPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self._repo = GoalsRepository(db)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel("Goals")
        title.setObjectName("pageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Add Goal")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._on_add)
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        subtitle = QLabel(
            "Track raid performance goals — boss kills, attendance targets, or anything else. "
            "Mark them achieved when done."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._card = QFrame()
        self._card.setProperty("class", "card")
        apply_card_elevation(self._card)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._rows_container)
        card_layout.addWidget(scroll, stretch=1)
        layout.addWidget(self._card, stretch=1)

        self.empty_state: AscendEmptyState | None = None
        self.reload()

    def reload(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        goals = self._repo.list_all()
        self._card.setVisible(bool(goals))
        if self.empty_state is not None:
            self.empty_state.setVisible(not bool(goals))
        elif not goals:
            self.empty_state = AscendEmptyState(
                title="No Goals Yet",
                description="Click '+ Add Goal' to set a raid performance goal.",
                icon_name="insights",
            )
            self.layout().addWidget(self.empty_state)
            return

        for i, goal in enumerate(goals):
            self._rows_layout.addWidget(
                _goal_row(goal, self._on_toggle, self._on_delete, alt=i % 2 == 1)
            )

    def _on_add(self) -> None:
        dlg = _AddGoalDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        goal = dlg.result_goal()
        if goal:
            self._repo.create(goal)
            self.reload()

    def _on_toggle(self, goal: Goal) -> None:
        if goal.achieved_at:
            self._repo.unmark_achieved(goal.id)
        else:
            self._repo.mark_achieved(goal.id)
        self.reload()

    def _on_delete(self, goal: Goal) -> None:
        self._repo.delete(goal.id)
        self.reload()
