"""Shared dialogs: error reporting and character / report-code entry forms."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QWidget,
)

from ascend.data.models import Character

REGIONS = ["US", "EU", "KR", "TW", "CN"]
CLASSES = [
    "Death Knight", "Demon Hunter", "Druid", "Evoker", "Hunter", "Mage",
    "Monk", "Paladin", "Priest", "Rogue", "Shaman", "Warlock", "Warrior",
]


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
    """Add or edit a character. Characters are stored in SQLite, never hardcoded."""

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
        self.wcl_id_edit = QLineEdit()
        self.class_combo = QComboBox()
        self.class_combo.addItems(CLASSES)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["primary", "alternate"])
        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(True)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMaximumHeight(80)

        form = QFormLayout()
        form.addRow("Display name:", self.display_name_edit)
        form.addRow("Character name:", self.character_name_edit)
        form.addRow("Region:", self.region_combo)
        form.addRow("Server:", self.server_edit)
        form.addRow("Warcraft Logs character ID:", self.wcl_id_edit)
        form.addRow("Class:", self.class_combo)
        form.addRow("Primary / alternate:", self.role_combo)
        form.addRow("", self.enabled_checkbox)
        form.addRow("Notes:", self.notes_edit)

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
            if character.wcl_character_id:
                self.wcl_id_edit.setText(str(character.wcl_character_id))
            if character.character_class in CLASSES:
                self.class_combo.setCurrentText(character.character_class)
            self.role_combo.setCurrentText(character.character_role)
            self.enabled_checkbox.setChecked(character.enabled)
            self.notes_edit.setPlainText(character.notes or "")

    def _on_accept(self) -> None:
        if not self.display_name_edit.text().strip() or not self.character_name_edit.text().strip():
            show_error(self, "Missing information", "Display name and character name are required.")
            return
        if not self.server_edit.text().strip():
            show_error(self, "Missing information", "Server is required.")
            return
        wcl_id_text = self.wcl_id_edit.text().strip()
        if wcl_id_text and not wcl_id_text.isdigit():
            show_error(self, "Invalid character ID", "Warcraft Logs character ID must be numeric.")
            return
        self.accept()

    def result_character(self) -> Character:
        wcl_id_text = self.wcl_id_edit.text().strip()
        return Character(
            id=self._character.id if self._character else None,
            display_name=self.display_name_edit.text().strip(),
            character_name=self.character_name_edit.text().strip(),
            region=self.region_combo.currentText(),
            server=self.server_edit.text().strip(),
            wcl_character_id=int(wcl_id_text) if wcl_id_text else None,
            character_class=self.class_combo.currentText(),
            character_role=self.role_combo.currentText(),
            enabled=self.enabled_checkbox.isChecked(),
            notes=self.notes_edit.toPlainText().strip(),
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
