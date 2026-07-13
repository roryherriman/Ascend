"""Encounter Rules page — annotate encounters with mechanic labels and notes."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
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
from ascend.data.repositories import ReportRepository
from ascend.services.encounter_rules_service import EncounterRule, EncounterRulesRepository
from ascend.theme import PALETTE, apply_card_elevation
from ascend.ui.components import AscendEmptyState


def _rule_row(rule: EncounterRule, on_delete, alt: bool) -> QFrame:
    row = QFrame()
    bg = PALETTE.bg_card_hover if alt else "transparent"
    row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
    h = QHBoxLayout(row)
    h.setContentsMargins(12, 7, 12, 7)
    h.setSpacing(10)

    enc_lbl = QLabel(rule.encounter_name)
    enc_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
    h.addWidget(enc_lbl, 2)

    label_lbl = QLabel(rule.mechanic_label or "—")
    label_lbl.setStyleSheet(f"font-size: 11px; color: {PALETTE.text_secondary};")
    h.addWidget(label_lbl, 2)

    note_lbl = QLabel(rule.note or "—")
    note_lbl.setStyleSheet(f"font-size: 11px; color: {PALETTE.text_muted};")
    note_lbl.setWordWrap(True)
    h.addWidget(note_lbl, 4)

    del_btn = QPushButton("Delete")
    del_btn.setFixedWidth(60)
    del_btn.setStyleSheet(f"color: {PALETTE.error if hasattr(PALETTE, 'error') else '#c0392b'};")
    del_btn.clicked.connect(lambda: on_delete(rule))
    h.addWidget(del_btn)

    return row


def _col_header() -> QFrame:
    row = QFrame()
    row.setStyleSheet(
        f"background: {PALETTE.bg_card}; border-bottom: 1px solid {PALETTE.border};"
    )
    h = QHBoxLayout(row)
    h.setContentsMargins(12, 4, 12, 4)
    h.setSpacing(10)
    for text, stretch in [("Encounter", 2), ("Mechanic Label", 2), ("Note", 4), ("", 1)]:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.4px; color: {PALETTE.text_muted};"
        )
        h.addWidget(lbl, stretch)
    return row


class _AddRuleDialog(QDialog):
    def __init__(self, encounter_names: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Encounter Rule")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.encounter_combo = QComboBox()
        self.encounter_combo.setEditable(True)
        self.encounter_combo.addItems(sorted(encounter_names))
        self.encounter_combo.setInsertPolicy(QComboBox.InsertPolicy.InsertAlphabetically)
        form.addRow("Encounter:", self.encounter_combo)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("e.g. Soak, Stack, Dispel")
        form.addRow("Mechanic Label:", self.label_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Notes about this mechanic or expectation")
        form.addRow("Note:", self.note_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_rule(self) -> EncounterRule | None:
        enc = self.encounter_combo.currentText().strip()
        if not enc:
            return None
        return EncounterRule(
            id=None,
            encounter_name=enc,
            mechanic_label=self.label_edit.text().strip(),
            note=self.note_edit.text().strip(),
        )


class EncounterRulesPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self._repo = EncounterRulesRepository(db)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        hdr = QHBoxLayout()
        title = QLabel("Encounter Rules")
        title.setObjectName("pageTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ Add Rule")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._on_add)
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        subtitle = QLabel(
            "Annotate encounter bosses with mechanic labels and notes. "
            "Rules help you document expectations and tag important mechanics "
            "for your raid team without requiring event-level data."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._card = QFrame()
        self._card.setProperty("class", "card")
        apply_card_elevation(self._card)
        card_inner = QVBoxLayout(self._card)
        card_inner.setContentsMargins(0, 0, 0, 0)
        card_inner.setSpacing(0)

        self._header_added = False
        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._rows_container)
        card_inner.addWidget(scroll, stretch=1)
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

        rules = self._repo.list_all()
        self._card.setVisible(bool(rules))
        if self.empty_state is not None:
            self.empty_state.setVisible(not bool(rules))
        elif not rules:
            self.empty_state = AscendEmptyState(
                title="No Rules Yet",
                description="Click '+ Add Rule' to annotate an encounter with mechanic labels or notes.",
                icon_name="encounter",
            )
            self.layout().addWidget(self.empty_state)
            return

        self._rows_layout.addWidget(_col_header())
        for i, rule in enumerate(rules):
            self._rows_layout.addWidget(_rule_row(rule, self._on_delete, alt=i % 2 == 1))

    def _known_encounters(self) -> list[str]:
        repo = ReportRepository(self.db)
        encounters = repo.distinct_encounters()
        return [name for _, name in encounters]

    def _on_add(self) -> None:
        dlg = _AddRuleDialog(self._known_encounters(), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        rule = dlg.result_rule()
        if rule:
            self._repo.create(rule)
            self.reload()

    def _on_delete(self, rule: EncounterRule) -> None:
        self._repo.delete(rule.id)
        self.reload()
