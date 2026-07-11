"""Global context bar — shows active character, guild, tier, and sync status.

Sits below the sidebar and above page content (or as a top strip inside the
main window). Future PRs wire in real character/guild/tier data; this PR
establishes the widget structure and reads from SettingsRepository.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.data.repositories import SettingsRepository
from ascend.ui.class_icons import class_icon_pixmap, class_color
from ascend.ui.styles.tokens import DARK_TOKENS


class GlobalContextBar(QWidget):
    """Compact strip showing active character → guild → current tier → sync.

    Emits ``settings_requested`` when the user clicks the settings shortcut,
    and ``sync_requested`` when they click the sync status label.
    """

    settings_requested = Signal()
    sync_requested = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.settings_repo = SettingsRepository(db)
        self.setObjectName("globalContextBar")

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.setFixedHeight(44)
        self.setStyleSheet(f"""
            #globalContextBar {{
                background: {DARK_TOKENS.palette.bg_card};
                border-bottom: 1px solid {DARK_TOKENS.palette.border};
            }}
        """)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 0, 16, 0)
        outer.setSpacing(0)

        # Character section
        self._char_icon = QLabel()
        self._char_icon.setFixedSize(20, 20)
        outer.addWidget(self._char_icon)
        outer.addSpacing(6)

        char_text = QVBoxLayout()
        char_text.setSpacing(0)
        self._char_name = QLabel()
        self._char_name.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {DARK_TOKENS.palette.text_primary};")
        self._char_sub = QLabel()
        self._char_sub.setStyleSheet(f"font-size: 10px; color: {DARK_TOKENS.palette.text_muted};")
        char_text.addWidget(self._char_name)
        char_text.addWidget(self._char_sub)
        outer.addLayout(char_text)

        outer.addSpacing(24)
        self._div1 = _divider()
        outer.addWidget(self._div1)
        outer.addSpacing(24)

        # Guild section
        self._guild_icon = QLabel()
        self._guild_icon.setFixedSize(20, 20)
        outer.addWidget(self._guild_icon)
        outer.addSpacing(6)

        guild_text = QVBoxLayout()
        guild_text.setSpacing(0)
        self._guild_name = QLabel()
        self._guild_name.setStyleSheet(f"font-size: 12px; color: {DARK_TOKENS.palette.text_secondary};")
        guild_text.addWidget(self._guild_name)
        outer.addLayout(guild_text)

        outer.addSpacing(24)
        self._div2 = _divider()
        outer.addWidget(self._div2)
        outer.addSpacing(24)

        # Tier section
        tier_text = QVBoxLayout()
        tier_text.setSpacing(0)
        tier_lbl = QLabel("Current tier")
        tier_lbl.setStyleSheet(f"font-size: 9px; color: {DARK_TOKENS.palette.text_muted};")
        self._tier_name = QLabel()
        self._tier_name.setStyleSheet(f"font-size: 12px; color: {DARK_TOKENS.palette.text_secondary};")
        tier_text.addWidget(tier_lbl)
        tier_text.addWidget(self._tier_name)
        outer.addLayout(tier_text)

        outer.addStretch()

        # Sync status (right side)
        self._sync_label = QLabel()
        self._sync_label.setStyleSheet(f"font-size: 10px; color: {DARK_TOKENS.palette.text_muted};")
        self._sync_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_label.mousePressEvent = lambda _: self.sync_requested.emit()
        outer.addWidget(self._sync_label)

        outer.addSpacing(12)

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(24, 24)
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {DARK_TOKENS.palette.text_muted};
                font-size: 13px;
            }}
            QPushButton:hover {{
                color: {DARK_TOKENS.palette.text_primary};
            }}
        """)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self.settings_requested.emit)
        outer.addWidget(settings_btn)

    def refresh(self) -> None:
        """Re-read settings and update all labels. Call after any settings change."""
        repo = self.settings_repo

        char_name = repo.get("player_display_name", "")
        char_class = repo.get("character_class", "")
        char_realm = repo.get("character_realm", "")
        char_region = repo.get("preferred_region", "")
        guild_name = repo.get("guild_name", "")
        guild_realm = repo.get("guild_realm", "")
        tier_name = repo.get("current_tier", "")
        last_sync = repo.get("last_sync_at", "")

        if char_name:
            self._char_name.setText(char_name)
            color = class_color(char_class) if char_class else DARK_TOKENS.palette.text_primary
            self._char_name.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {color};")
            parts = []
            if char_class:
                parts.append(char_class)
            if char_realm:
                suffix = f" ({char_region})" if char_region else ""
                parts.append(f"{char_realm}{suffix}")
            self._char_sub.setText(" · ".join(parts) if parts else "Character")

            if char_class:
                pm = class_icon_pixmap(char_class, 20)
                self._char_icon.setPixmap(pm)
            else:
                self._char_icon.clear()
        else:
            self._char_name.setText("No Character")
            self._char_name.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {DARK_TOKENS.palette.text_muted};")
            self._char_sub.setText("Add a character in Settings")
            self._char_icon.clear()

        if guild_name:
            self._guild_name.setText(guild_name)
            self._guild_name.setStyleSheet(f"font-size: 12px; color: {DARK_TOKENS.palette.text_secondary};")
            # Guild badge mini: colored square with initial (full badge renders in PR 3)
            self._guild_icon.setText(guild_name[:1].upper())
            self._guild_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._guild_icon.setStyleSheet(f"""
                font-size: 10px; font-weight: 600;
                color: {DARK_TOKENS.palette.text_on_accent};
                background: {DARK_TOKENS.palette.accent_muted};
                border-radius: 4px;
            """)
        else:
            self._guild_name.setText("No Guild")
            self._guild_name.setStyleSheet(f"font-size: 12px; color: {DARK_TOKENS.palette.text_disabled};")
            self._guild_icon.setText("")
            self._guild_icon.setStyleSheet(f"background: {DARK_TOKENS.palette.bg_input}; border-radius: 4px;")

        if tier_name:
            self._tier_name.setText(tier_name)
        else:
            self._tier_name.setText("Not detected")
            self._tier_name.setStyleSheet(f"font-size: 12px; color: {DARK_TOKENS.palette.text_disabled};")

        if last_sync:
            self._sync_label.setText(f"Last synced {last_sync}")
        else:
            self._sync_label.setText("Not synced")


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFixedWidth(1)
    line.setFixedHeight(28)
    line.setStyleSheet(f"background: {DARK_TOKENS.palette.border};")
    return line
