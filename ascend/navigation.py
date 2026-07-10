"""Sidebar navigation: Ascend mark + grouped section list + footer.

``NAV_ITEMS`` stays a flat, ordered list of the real selectable sections (the
source of truth other code and tests rely on); ``NAV_GROUPS`` only controls
how they're visually grouped with headers in the sidebar.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ascend import metadata
from ascend.ui.icons import icon

NAV_ITEMS: list[tuple[str, str]] = [
    ("dashboard", "Dashboard"),
    ("characters", "Characters"),
    ("reports", "Reports"),
    ("raid_night", "Raid Night Summary"),
    ("encounter", "Encounter Analysis"),
    ("deaths", "Death Review"),
    ("roster", "Roster Comparison"),
    ("trends", "Learning and Trends"),
    ("raid_night_comparison", "Raid Night Comparison"),
    ("encounter_progression", "Encounter Progression"),
    ("insights", "Insights"),
    ("readiness", "Readiness"),
    ("goals", "Goals"),
    ("rules", "Encounter Rules"),
    ("data_quality", "Data Quality"),
    ("export", "Export and Discord"),
    ("settings", "Settings"),
    ("diagnostics", "Diagnostics"),
]

NAV_GROUPS: list[tuple[str, list[str]]] = [
    ("Overview", ["dashboard", "characters", "reports"]),
    (
        "Analysis",
        [
            "raid_night", "encounter", "deaths", "roster", "trends",
            "raid_night_comparison", "encounter_progression",
        ],
    ),
    ("Intelligence", ["insights", "readiness", "goals", "rules"]),
    ("System", ["data_quality", "export", "settings", "diagnostics"]),
]

NAV_ICONS: dict[str, str] = {
    "dashboard": "dashboard",
    "characters": "characters",
    "reports": "reports",
    "raid_night": "raid_night",
    "encounter": "encounter",
    "deaths": "deaths",
    "roster": "roster",
    "trends": "trends",
    "raid_night_comparison": "raid_night_comparison",
    "encounter_progression": "encounter_progression",
    "insights": "insights",
    "readiness": "readiness",
    "goals": "goals",
    "rules": "rules",
    "data_quality": "data_quality",
    "export": "export",
    "settings": "settings",
    "diagnostics": "diagnostics",
}

_KEY_ROLE = Qt.ItemDataRole.UserRole + 100


class Sidebar(QWidget):
    section_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(232)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("navList")
        self.list_widget.setIconSize(QSize(18, 18))
        self.list_widget.setUniformItemSizes(False)
        self._populate_items()
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget, stretch=1)

        layout.addWidget(self._build_footer())

        self._select_first_real_row()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("sidebarHeader")
        outer = QVBoxLayout(header)
        outer.setContentsMargins(16, 18, 16, 14)
        outer.setSpacing(2)

        mark_row = QHBoxLayout()
        mark_row.setSpacing(8)
        mark_label = QLabel()
        mark_label.setPixmap(icon("logo_mark").pixmap(22, 22))
        mark_row.addWidget(mark_label)

        name_label = QLabel(metadata.APP_NAME)
        name_label.setObjectName("appTitle")
        mark_row.addWidget(name_label)
        mark_row.addStretch()
        outer.addLayout(mark_row)

        tagline_label = QLabel(metadata.APP_TAGLINE)
        tagline_label.setProperty("class", "muted")
        tagline_label.setStyleSheet("font-size: 10px;")
        tagline_label.setWordWrap(True)
        outer.addWidget(tagline_label)

        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("sidebarFooter")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(2)

        version_label = QLabel(f"v{metadata.APP_VERSION}")
        version_label.setProperty("class", "caption")
        layout.addWidget(version_label)

        mode_label = QLabel("Local-first · no cloud sync")
        mode_label.setProperty("class", "caption")
        layout.addWidget(mode_label)

        return footer

    def _populate_items(self) -> None:
        labels = dict(NAV_ITEMS)
        for group_label, keys in NAV_GROUPS:
            header_item = QListWidgetItem("")
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            header_item.setSizeHint(
                QSize(0, 26)
            )
            self.list_widget.addItem(header_item)
            header_label = QLabel(group_label.upper())
            header_label.setObjectName("navGroupLabel")
            self.list_widget.setItemWidget(header_item, header_label)

            for key in keys:
                item = QListWidgetItem(labels.get(key, key))
                icon_name = NAV_ICONS.get(key)
                if icon_name:
                    item.setIcon(icon(icon_name))
                item.setData(_KEY_ROLE, key)
                self.list_widget.addItem(item)

    def _select_first_real_row(self) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.data(_KEY_ROLE):
                self.list_widget.setCurrentRow(row)
                return

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= self.list_widget.count():
            return
        key = self.list_widget.item(row).data(_KEY_ROLE)
        if key:
            self.section_selected.emit(key)

    def select_section(self, key: str) -> None:
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(_KEY_ROLE) == key:
                self.list_widget.setCurrentRow(i)
                return

    @property
    def selectable_section_count(self) -> int:
        """Number of real, selectable nav rows (excludes group-header rows)."""
        return sum(
            1 for i in range(self.list_widget.count())
            if self.list_widget.item(i).data(_KEY_ROLE)
        )
