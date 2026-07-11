"""Characters page — add/edit/remove/enable characters, persisted in SQLite.

Displays each character as a compact card showing class icon, name, realm, role badge,
and detected class. Class and spec role are detected automatically from raid log data
and shown read-only; they cannot be edited manually.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from ascend.data.models import Character
from ascend.data.repositories import CharacterRepository
from ascend.ui.class_icons import class_color, class_icon_pixmap
from ascend.ui.dialogs import CharacterDialog, confirm, show_error
from ascend.ui.styles.tokens import DARK_TOKENS
from ascend.ui.widgets import make_badge

# Fictional demo roster — used only in Demo Mode, never seeded into real user databases.
DEMO_CHARACTERS: list[Character] = [
    Character(
        display_name="Aeloria",
        character_name="Aeloria",
        region="US",
        server="Proudmoore",
        wcl_character_id=None,
        character_class="Mage",
        character_role="primary",
        enabled=True,
        notes="Demo character",
    ),
    Character(
        display_name="Thornveil",
        character_name="Thornveil",
        region="US",
        server="Proudmoore",
        wcl_character_id=None,
        character_class="Warlock",
        character_role="primary",
        enabled=True,
        notes="Demo character",
    ),
    Character(
        display_name="Kaelric",
        character_name="Kaelric",
        region="US",
        server="Proudmoore",
        wcl_character_id=None,
        character_class="Warrior",
        character_role="primary",
        enabled=True,
        notes="Demo character",
    ),
    Character(
        display_name="Seraphyne",
        character_name="Seraphyne",
        region="US",
        server="Proudmoore",
        wcl_character_id=None,
        character_class="Priest",
        character_role="primary",
        enabled=True,
        notes="Demo character",
    ),
]


def seed_initial_characters(db: Database) -> None:
    """No-op for real users — kept for backwards compatibility with call sites."""


def seed_demo_characters(db: Database) -> None:
    """Seed fictional demo characters for Demo Mode. Only called in demo builds."""
    repo = CharacterRepository(db)
    if repo.list_all():
        return
    for character in DEMO_CHARACTERS:
        repo.create(character)


class _CharacterCard(QFrame):
    """Compact card for one character row."""

    def __init__(
        self,
        character: Character,
        on_edit,
        on_toggle,
        on_remove,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.character = character
        self.setObjectName("characterCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            #characterCard {{
                background: {DARK_TOKENS.palette.bg_card};
                border: 1px solid {DARK_TOKENS.palette.border};
                border-radius: 6px;
            }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)

        # Class icon
        icon_label = QLabel()
        pm = class_icon_pixmap(character.character_class, 28)
        if not pm.isNull():
            icon_label.setPixmap(pm)
        else:
            icon_label.setFixedSize(28, 28)
        icon_label.setFixedSize(28, 28)
        row.addWidget(icon_label)

        # Name + realm
        name_col = QVBoxLayout()
        name_col.setSpacing(1)

        name_lbl = QLabel(character.display_name)
        name_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {DARK_TOKENS.palette.text_primary};")
        name_col.addWidget(name_lbl)

        realm_parts = [character.character_name]
        if character.server:
            realm_parts.append(f"{character.server}-{character.region}")
        realm_lbl = QLabel(" · ".join(realm_parts))
        realm_lbl.setStyleSheet(f"font-size: 11px; color: {DARK_TOKENS.palette.text_muted};")
        name_col.addWidget(realm_lbl)

        row.addLayout(name_col, stretch=1)

        # Class + spec role (auto-detected, read-only)
        class_col = QVBoxLayout()
        class_col.setSpacing(1)

        if character.character_class:
            color = class_color(character.character_class)
            class_lbl = QLabel(character.character_class)
            class_lbl.setStyleSheet(f"font-size: 12px; color: {color};")
        else:
            class_lbl = QLabel("Class not yet detected")
            class_lbl.setStyleSheet(f"font-size: 11px; color: {DARK_TOKENS.palette.text_disabled};")
        class_col.addWidget(class_lbl)

        if character.spec_role:
            spec_lbl = QLabel(character.spec_role.capitalize())
            spec_lbl.setStyleSheet(f"font-size: 11px; color: {DARK_TOKENS.palette.text_muted};")
            class_col.addWidget(spec_lbl)

        row.addLayout(class_col)
        row.addSpacing(12)

        # Role + enabled badges
        badge_col = QVBoxLayout()
        badge_col.setSpacing(4)
        badge_col.addWidget(make_badge(
            character.character_role.upper(),
            tone="info" if character.character_role == "primary" else "neutral",
        ))
        badge_col.addWidget(make_badge(
            "ENABLED" if character.enabled else "DISABLED",
            tone="success" if character.enabled else "neutral",
        ))
        row.addLayout(badge_col)
        row.addSpacing(8)

        # Action buttons
        edit_btn = QPushButton("Edit")
        edit_btn.setFixedWidth(52)
        edit_btn.clicked.connect(lambda: on_edit(character))
        row.addWidget(edit_btn)

        toggle_btn = QPushButton("Disable" if character.enabled else "Enable")
        toggle_btn.setFixedWidth(60)
        toggle_btn.clicked.connect(lambda: on_toggle(character))
        row.addWidget(toggle_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("dangerButton")
        remove_btn.setFixedWidth(68)
        remove_btn.clicked.connect(lambda: on_remove(character))
        row.addWidget(remove_btn)


class CharactersPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.repo = CharacterRepository(db)
        self._characters: list[Character] = []
        self._filter_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Characters")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Characters are matched to raid log actors automatically. "
            "Class and spec role are detected from your reports — no manual entry needed."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {DARK_TOKENS.palette.text_muted}; font-size: 12px;")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search characters...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_edit, stretch=1)

        self.add_button = QPushButton("Add Character")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self._on_add)
        toolbar.addWidget(self.add_button)

        layout.addLayout(toolbar)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch()

        scroll.setWidget(self._cards_container)
        layout.addWidget(scroll, stretch=1)

        self.reload()

    def reload(self) -> None:
        self._characters = self.repo.list_all()
        self._rebuild_cards()

    def _on_search_changed(self, text: str) -> None:
        self._filter_text = text.strip().lower()
        self._rebuild_cards()

    def _filtered(self) -> list[Character]:
        text = self._filter_text
        if not text:
            return self._characters
        return [
            c for c in self._characters
            if text in c.display_name.lower()
            or text in c.character_name.lower()
            or text in (c.character_class or "").lower()
            or text in c.server.lower()
        ]

    def _rebuild_cards(self) -> None:
        # Remove all existing cards (everything before the trailing stretch)
        layout = self._cards_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()

        characters = self._filtered()

        if not characters:
            empty = QLabel("No characters match your search." if self._filter_text else "No characters yet. Click Add Character to get started.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {DARK_TOKENS.palette.text_muted}; padding: 32px;")
            layout.insertWidget(0, empty)
            return

        for i, character in enumerate(characters):
            card = _CharacterCard(
                character,
                on_edit=self._on_edit,
                on_toggle=self._on_toggle_enabled,
                on_remove=self._on_remove,
            )
            layout.insertWidget(i, card)

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

    def _on_edit(self, character: Character) -> None:
        fresh = self.repo.get(character.id)
        if fresh is None:
            show_error(self, "Not found", "Character no longer exists.")
            self.reload()
            return
        dialog = CharacterDialog(self, character=fresh)
        if dialog.exec():
            updated = dialog.result_character()
            try:
                self.repo.update(updated)
            except Exception as exc:  # noqa: BLE001
                show_error(self, "Could not update character", str(exc))
                return
            self.reload()

    def _on_toggle_enabled(self, character: Character) -> None:
        self.repo.set_enabled(character.id, not character.enabled)
        self.reload()

    def _on_remove(self, character: Character) -> None:
        if confirm(
            self, "Remove character",
            f"Remove '{character.display_name}' from the local database? "
            "This does not affect anything on Warcraft Logs.",
        ):
            self.repo.delete(character.id)
            self.reload()
