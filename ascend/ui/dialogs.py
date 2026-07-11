"""Shared dialogs: error reporting and character / report-code entry forms."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from ascend.data.models import Character

REGIONS = ["US", "EU", "KR", "TW", "CN"]


def show_error(parent: QWidget | None, title: str, message: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(title)
    box.setText(message)
    box.exec()


def show_info(parent: QWidget | None, title: str, message: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(message)
    box.exec()


def confirm(parent: QWidget | None, title: str, message: str) -> bool:
    result = QMessageBox.question(
        parent, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    return result == QMessageBox.StandardButton.Yes


class CharacterDialog(QDialog):
    """Add or edit a character. Class and role are detected automatically from raid data."""

    def __init__(
        self,
        parent: QWidget | None = None,
        character: Character | None = None,
        default_region: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Edit Character" if character else "Add Character")
        self.setMinimumWidth(380)
        self._character = character

        self.display_name_edit = QLineEdit()
        self.character_name_edit = QLineEdit()
        self.region_combo = QComboBox()
        self.region_combo.addItems(REGIONS)
        if default_region and default_region in REGIONS:
            self.region_combo.setCurrentText(default_region)
        self.server_edit = QLineEdit()
        self._setup_realm_completer()
        self.region_combo.currentTextChanged.connect(self._update_realm_completer)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["primary", "alternate"])
        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(True)

        detected_note = QLabel("Class and spec role are detected automatically from your raid logs.")
        detected_note.setWordWrap(True)
        detected_note.setStyleSheet("color: #888; font-size: 11px;")

        form = QFormLayout()
        form.addRow("Display name:", self.display_name_edit)
        form.addRow("Character name:", self.character_name_edit)
        form.addRow("Region:", self.region_combo)
        form.addRow("Server:", self.server_edit)
        form.addRow("Primary / alternate:", self.role_combo)
        form.addRow("", self.enabled_checkbox)
        form.addRow("", detected_note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.setLayout(form)

        if character:
            self.display_name_edit.setText(character.display_name)
            self.character_name_edit.setText(character.character_name)
            if character.region in REGIONS:
                self.region_combo.setCurrentText(character.region)
            self.server_edit.setText(character.server)
            self.role_combo.setCurrentText(character.character_role)
            self.enabled_checkbox.setChecked(character.enabled)

    def _setup_realm_completer(self) -> None:
        from ascend.data.wow_data import realms_for_region
        realms = realms_for_region(self.region_combo.currentText())
        completer = QCompleter(realms, self.server_edit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.server_edit.setCompleter(completer)

    def _update_realm_completer(self, region: str) -> None:
        from ascend.data.wow_data import realms_for_region
        realms = realms_for_region(region)
        completer = QCompleter(realms, self.server_edit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.server_edit.setCompleter(completer)

    def _on_accept(self) -> None:
        if not self.display_name_edit.text().strip() or not self.character_name_edit.text().strip():
            show_error(self, "Missing information", "Display name and character name are required.")
            return
        if not self.server_edit.text().strip():
            show_error(self, "Missing information", "Server is required.")
            return
        self.accept()

    def result_character(self) -> Character:
        existing = self._character
        return Character(
            id=existing.id if existing else None,
            display_name=self.display_name_edit.text().strip(),
            character_name=self.character_name_edit.text().strip(),
            region=self.region_combo.currentText(),
            server=self.server_edit.text().strip(),
            wcl_character_id=existing.wcl_character_id if existing else None,
            character_class=existing.character_class if existing else None,
            character_role=self.role_combo.currentText(),
            spec_role=existing.spec_role if existing else None,
            enabled=self.enabled_checkbox.isChecked(),
            notes=existing.notes if existing else "",
        )


class ReportCodeDialog(QDialog):
    """Simple text-entry dialog for adding a report by its Warcraft Logs report code."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add Report Code")
        self.setMinimumWidth(360)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("e.g. AbCdEfGh123456")

        form = QFormLayout()
        form.addRow("Report code:", self.code_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.setLayout(form)

    def _on_accept(self) -> None:
        if not self.code_edit.text().strip():
            show_error(self, "Missing information", "Please enter a report code.")
            return
        self.accept()

    def report_code(self) -> str:
        return self.code_edit.text().strip()
