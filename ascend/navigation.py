"""Sidebar navigation: Ascend logo/tagline header + the main section list."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ascend.metadata import APP_NAME, APP_TAGLINE

NAV_ITEMS: list[tuple[str, str]] = [
    ("dashboard", "Dashboard"),
    ("characters", "Characters"),
    ("reports", "Reports"),
    ("raid_night", "Raid Night Summary"),
    ("encounter", "Encounter Analysis"),
    ("deaths", "Death Review"),
    ("roster", "Roster Comparison"),
    ("trends", "Learning and Trends"),
    ("insights", "Insights"),
    ("readiness", "Readiness"),
    ("goals", "Goals"),
    ("raid_night_comparison", "Raid Night Comparison"),
    ("encounter_progression", "Encounter Progression"),
    ("rules", "Encounter Rules"),
    ("data_quality", "Data Quality"),
    ("export", "Export and Discord"),
    ("settings", "Settings"),
    ("diagnostics", "Diagnostics"),
]


class Sidebar(QWidget):
    section_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(0)

        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 4, 16, 12)
        header_layout.setSpacing(2)

        name_label = QLabel(APP_NAME)
        name_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        tagline_label = QLabel(APP_TAGLINE)
        tagline_label.setProperty("class", "muted")
        tagline_label.setStyleSheet("font-size: 10px;")
        tagline_label.setWordWrap(True)
        tagline_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        header_layout.addWidget(name_label)
        header_layout.addWidget(tagline_label)
        layout.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("navList")

        for key, label in NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setData(1000, key)
            self.list_widget.addItem(item)

        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget, stretch=1)

        self.list_widget.setCurrentRow(0)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < self.list_widget.count():
            key = self.list_widget.item(row).data(1000)
            self.section_selected.emit(key)

    def select_section(self, key: str) -> None:
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(1000) == key:
                self.list_widget.setCurrentRow(i)
                return
