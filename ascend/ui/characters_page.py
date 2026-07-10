"""Characters page - add/edit/remove/enable characters, all persisted in SQLite."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.data.models import Character
from ascend.data.repositories import CharacterRepository
from ascend.ui.class_icons import class_color, class_icon
from ascend.ui.dialogs import CharacterDialog, confirm, show_error
from ascend.ui.widgets import make_badge

COLUMNS = [
    "Display Name", "Character Name", "Region", "Server", "WCL ID",
    "Class", "Role", "Enabled", "Notes",
]

INITIAL_CHARACTERS: list[Character] = [
    Character(
        display_name="Kysarra",
        character_name="Kysarra",
        region="US",
        server="Stormrage",
        wcl_character_id=108832382,
        character_class="Mage",
        character_role="primary",
        enabled=True,
        notes="",
    ),
    Character(
        display_name="Kyssandra",
        character_name="Kyssandra",
        region="US",
        server="Stormrage",
        wcl_character_id=110023835,
        character_class="Warlock",
        character_role="primary",
        enabled=True,
        notes="",
    ),
]


def seed_initial_characters(db: Database) -> None:
    """Insert the starter roster into SQLite on first run only. Not hardcoded into logic
    elsewhere - once seeded, all further changes go through the GUI and the database."""
    repo = CharacterRepository(db)
    if repo.list_all():
        return
    for character in INITIAL_CHARACTERS:
        repo.create(character)


class CharactersPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.repo = CharacterRepository(db)
        self._characters: list[Character] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Characters")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter characters...")
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_edit, stretch=1)

        self.add_button = QPushButton("Add Character")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self._on_add)
        toolbar.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._on_edit)
        toolbar.addWidget(self.edit_button)

        self.toggle_button = QPushButton("Enable / Disable")
        self.toggle_button.clicked.connect(self._on_toggle_enabled)
        toolbar.addWidget(self.toggle_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setObjectName("dangerButton")
        self.remove_button.clicked.connect(self._on_remove)
        toolbar.addWidget(self.remove_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, stretch=1)

        self.reload()

    def reload(self) -> None:
        self._characters = self.repo.list_all()
        self._populate_table(self._characters)

    def _populate_table(self, characters: list[Character]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(characters))
        for row, character in enumerate(characters):
            values = [
                character.display_name,
                character.character_name,
                character.region,
                character.server,
                str(character.wcl_character_id) if character.wcl_character_id else "",
                "",  # Class - rendered as an icon + text widget below
                character.character_role,
                "",  # Enabled - rendered as a badge widget below
                character.notes or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, character.id)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

            class_wrap = QWidget()
            class_layout = QHBoxLayout(class_wrap)
            class_layout.setContentsMargins(6, 2, 4, 2)
            class_layout.setSpacing(6)
            class_icon_label = QLabel()
            class_icon_label.setPixmap(class_icon(character.character_class).pixmap(18, 18))
            class_layout.addWidget(class_icon_label)
            class_text = QLabel(character.character_class or "Unknown")
            class_text.setStyleSheet(f"color: {class_color(character.character_class)};")
            class_layout.addWidget(class_text)
            class_layout.addStretch()
            self.table.setCellWidget(row, 5, class_wrap)

            badge = make_badge("ENABLED" if character.enabled else "DISABLED",
                                tone="success" if character.enabled else "neutral")
            badge_wrap = QWidget()
            badge_layout = QHBoxLayout(badge_wrap)
            badge_layout.setContentsMargins(4, 2, 4, 2)
            badge_layout.addWidget(badge)
            badge_layout.addStretch()
            self.table.setCellWidget(row, 7, badge_wrap)
        self.table.setSortingEnabled(True)

    def _apply_filter(self, text: str) -> None:
        text = text.strip().lower()
        if not text:
            self._populate_table(self._characters)
            return
        filtered = [
            c for c in self._characters
            if text in c.display_name.lower()
            or text in c.character_name.lower()
            or text in (c.character_class or "").lower()
            or text in c.server.lower()
        ]
        self._populate_table(filtered)

    def _selected_character(self) -> Character | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        character_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return self.repo.get(character_id)

    def _on_add(self) -> None:
        dialog = CharacterDialog(self)
        if dialog.exec():
            character = dialog.result_character()
            try:
                self.repo.create(character)
            except Exception as exc:  # noqa: BLE001
                show_error(self, "Could not add character", str(exc))
                return
            self.reload()

    def _on_edit(self) -> None:
        character = self._selected_character()
        if character is None:
            show_error(self, "No selection", "Select a character to edit first.")
            return
        dialog = CharacterDialog(self, character=character)
        if dialog.exec():
            updated = dialog.result_character()
            try:
                self.repo.update(updated)
            except Exception as exc:  # noqa: BLE001
                show_error(self, "Could not update character", str(exc))
                return
            self.reload()

    def _on_toggle_enabled(self) -> None:
        character = self._selected_character()
        if character is None:
            show_error(self, "No selection", "Select a character to enable/disable first.")
            return
        self.repo.set_enabled(character.id, not character.enabled)
        self.reload()

    def _on_remove(self) -> None:
        character = self._selected_character()
        if character is None:
            show_error(self, "No selection", "Select a character to remove first.")
            return
        if confirm(
            self, "Remove character",
            f"Remove '{character.display_name}' from the local database? "
            "This does not affect anything on Warcraft Logs.",
        ):
            self.repo.delete(character.id)
            self.reload()
