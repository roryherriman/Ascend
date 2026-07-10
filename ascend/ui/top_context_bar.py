"""Compact top context bar: page title/subtitle on the left, a character
selector, guild context, and a Settings shortcut on the right.

Replaces the old large Character/Guild cards that used to live inside the
Dashboard body - this is persistent context, not Dashboard content.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ascend.data.database import Database
from ascend.data.repositories import CharacterRepository, SettingsRepository
from ascend.services.guild_icon_service import get_guild_badge_pixmap
from ascend.ui.class_icons import class_color, class_icon
from ascend.ui.icons import icon


class _ClickableFrame(QFrame):
    """A QFrame that emits a signal on click - used so the guild context chip
    can hold an arbitrary child layout (icon + two text rows) while still
    being clickable, which a QPushButton with embedded child widgets can't
    reliably do (child widgets would fight the button for mouse events)."""

    def __init__(self, signal, parent: QWidget | None = None):
        super().__init__(parent)
        self._signal = signal

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        self._signal.emit()
        super().mousePressEvent(event)


class TopContextBar(QWidget):
    settings_requested = Signal()
    character_changed = Signal(object)  # emits the selected Character (or None)

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self._characters: list = []
        self.setObjectName("topContextBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self.title_label = QLabel("")
        self.title_label.setObjectName("pageTitle")
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("pageDescription")
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)
        layout.addLayout(title_col, stretch=1)

        layout.addWidget(self._build_character_selector())
        layout.addWidget(self._build_guild_context())

        settings_button = QPushButton()
        settings_button.setIcon(icon("settings"))
        settings_button.setToolTip("Settings")
        settings_button.setFixedSize(32, 32)
        settings_button.clicked.connect(self.settings_requested.emit)
        layout.addWidget(settings_button)

        self.refresh()

    def set_title(self, title: str, subtitle: str = "") -> None:
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))

    def _build_character_selector(self) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("contextChip")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(8, 4, 10, 4)
        layout.setSpacing(6)

        self.character_icon_label = QLabel()
        layout.addWidget(self.character_icon_label)

        self.character_combo = QComboBox()
        self.character_combo.setMinimumWidth(150)
        self.character_combo.currentIndexChanged.connect(self._on_character_selected)
        layout.addWidget(self.character_combo)

        return wrap

    def _build_guild_context(self) -> QWidget:
        chip = _ClickableFrame(self.settings_requested)
        chip.setObjectName("contextChip")
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setToolTip("Open guild settings")
        layout = QHBoxLayout(chip)
        layout.setContentsMargins(8, 4, 10, 4)
        layout.setSpacing(6)

        self.guild_icon_label = QLabel()
        layout.addWidget(self.guild_icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        self.guild_name_label = QLabel("No guild set")
        self.guild_name_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        text_col.addWidget(self.guild_name_label)
        self.guild_rank_label = QLabel("")
        self.guild_rank_label.setProperty("class", "caption")
        text_col.addWidget(self.guild_rank_label)
        layout.addLayout(text_col)

        return chip

    def refresh(self) -> None:
        self._refresh_characters()
        self._refresh_guild()

    def _refresh_characters(self) -> None:
        self.character_combo.blockSignals(True)
        self.character_combo.clear()
        self._characters = CharacterRepository(self.db).list_all(enabled_only=True)
        for character in self._characters:
            self.character_combo.addItem(character.display_name)
        self.character_combo.blockSignals(False)

        primary_index = next(
            (i for i, c in enumerate(self._characters) if c.character_role == "primary"), 0
        )
        if self._characters:
            self.character_combo.setCurrentIndex(primary_index)
            self._apply_character_icon(self._characters[primary_index])
        else:
            self.character_icon_label.setPixmap(class_icon(None).pixmap(20, 20))

    def _on_character_selected(self, index: int) -> None:
        if 0 <= index < len(self._characters):
            character = self._characters[index]
            self._apply_character_icon(character)
            self.character_changed.emit(character)

    def _apply_character_icon(self, character) -> None:
        self.character_icon_label.setPixmap(class_icon(character.character_class).pixmap(20, 20))
        accent = class_color(character.character_class)
        self.character_combo.setStyleSheet(f"color: {accent};")

    def _refresh_guild(self) -> None:
        settings_repo = SettingsRepository(self.db)
        guild_name = settings_repo.get("guild_name", "")
        guild_rank = settings_repo.get("guild_us_rank", "")

        primary = next(
            (c for c in self._characters if c.character_role == "primary"),
            self._characters[0] if self._characters else None,
        )
        region = primary.region if primary else ""
        realm = primary.server if primary else ""

        pixmap = get_guild_badge_pixmap(self.db, region, realm, guild_name, size=20)
        self.guild_icon_label.setPixmap(pixmap)
        self.guild_name_label.setText(guild_name or "No guild set")
        self.guild_rank_label.setText(f"Rank {guild_rank}" if guild_rank else "Set in Settings")
