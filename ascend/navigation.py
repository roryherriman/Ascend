"""Sidebar navigation: compact Ascend mark + grouped section list + footer.

``NAV_ITEMS`` stays a flat, ordered list of the real selectable sections (the
source of truth other code and tests rely on); ``NAV_GROUPS`` only controls
how they're visually grouped with headers in the sidebar. Labels here are
the short sidebar labels - pages can still show their full title internally.
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
from ascend.theme import DARK_TOKENS
from ascend.ui.icons import icon

NAV_ITEMS: list[tuple[str, str]] = [
    ("dashboard", "Dashboard"),
    ("characters", "Characters"),
    ("reports", "Reports"),
    ("raid_night", "Raid Nights"),
    ("encounter", "Encounters"),
    ("deaths", "Death Review"),
    ("roster", "Roster"),
    ("trends", "Trends"),
    ("raid_night_comparison", "Night Comparison"),
    ("encounter_progression", "Progression"),
    ("insights", "Insights"),
    ("readiness", "Readiness"),
    ("goals", "Goals"),
    ("rules", "Rules"),
    ("data_quality", "Data Quality"),
    ("export", "Export"),
    ("settings", "Settings"),
    ("diagnostics", "Diagnostics"),
]

# Full titles shown inside the page itself (top context bar / page header),
# since the sidebar label is deliberately shortened for density.
FULL_TITLES: dict[str, str] = {
    "dashboard": "Dashboard",
    "characters": "Characters",
    "reports": "Reports",
    "raid_night": "Raid Night Summary",
    "encounter": "Encounter Analysis",
    "deaths": "Death Review",
    "roster": "Roster Comparison",
    "trends": "Learning and Trends",
    "raid_night_comparison": "Raid Night Comparison",
    "encounter_progression": "Encounter Progression",
    "insights": "Insights",
    "readiness": "Readiness",
    "goals": "Goals",
    "rules": "Encounter Rules",
    "data_quality": "Data Quality",
    "export": "Export and Discord",
    "settings": "Settings",
    "diagnostics": "Diagnostics",
}

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
        self.setFixedWidth(DARK_TOKENS.control.sidebar_width)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("navList")
        self.list_widget.setIconSize(QSize(16, 16))
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
        outer.setContentsMargins(14, 12, 14, 10)
        outer.setSpacing(1)

        mark_row = QHBoxLayout()
        mark_row.setSpacing(7)
        mark_label = QLabel()
        mark_label.setPixmap(icon("logo_mark").pixmap(18, 18))
        mark_row.addWidget(mark_label)

        name_label = QLabel(metadata.APP_NAME)
        name_label.setObjectName("appTitle")
        mark_row.addWidget(name_label)
        mark_row.addStretch()
        outer.addLayout(mark_row)

        tagline_label = QLabel("Progression Intelligence")
        tagline_label.setProperty("class", "muted")
        tagline_label.setStyleSheet("font-size: 9px;")
        outer.addWidget(tagline_label)

        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("sidebarFooter")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        version_label = QLabel(f"v{metadata.APP_VERSION}")
        version_label.setProperty("class", "caption")
        top_row.addWidget(version_label)

        phase_label = QLabel("PHASE 1")
        phase_label.setProperty("class", "caption")
        phase_label.setStyleSheet(
            f"color: {DARK_TOKENS.palette.accent_hover}; font-weight: 700;"
        )
        top_row.addWidget(phase_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.connection_dot = QLabel("●")
        self.connection_dot.setStyleSheet(f"color: {DARK_TOKENS.palette.text_muted}; font-size: 9px;")
        status_row.addWidget(self.connection_dot)
        status_text = QLabel("Local-first")
        status_text.setProperty("class", "caption")
        status_row.addWidget(status_text)
        status_row.addStretch()
        layout.addLayout(status_row)

        return footer

    def set_connection_status(self, connected: bool | None) -> None:
        """None = not yet tested, True/False = last test result."""
        color = {
            None: DARK_TOKENS.palette.text_muted,
            True: DARK_TOKENS.palette.success,
            False: DARK_TOKENS.palette.error,
        }[connected]
        self.connection_dot.setStyleSheet(f"color: {color}; font-size: 9px;")

    def _populate_items(self) -> None:
        labels = dict(NAV_ITEMS)
        for group_label, keys in NAV_GROUPS:
            header_item = QListWidgetItem("")
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            header_item.setSizeHint(QSize(0, 20))
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
