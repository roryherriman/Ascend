"""Small reusable widgets shared across pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StatCard(QFrame):
    """A dashboard card showing one metric: a title, a big value, and optional subtext."""

    def __init__(self, title: str, value: str = "--", subtext: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setObjectName("statCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(96)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setProperty("class", "muted")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 600; text-transform: uppercase;")

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 24px; font-weight: 700;")

        self.subtext_label = QLabel(subtext)
        self.subtext_label.setProperty("class", "muted")
        self.subtext_label.setStyleSheet("font-size: 11px;")
        self.subtext_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtext_label)

    def set_value(self, value: str, subtext: str | None = None) -> None:
        self.value_label.setText(value)
        if subtext is not None:
            self.subtext_label.setText(subtext)


class PlaceholderPage(QWidget):
    """Shown for sections not yet implemented in the current development phase."""

    def __init__(self, title: str, phase_note: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")

        note_label = QLabel(phase_note)
        note_label.setProperty("class", "muted")
        note_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(note_label)
        layout.addStretch()


class DemoBanner(QFrame):
    """Persistent banner shown across the whole app while Demo Mode is active,
    so demo data is never mistaken for a real analysis."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("demoBanner")
        self.setStyleSheet(
            "background-color: #e0a83e; color: #1e1f22; font-weight: 700;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        label = QLabel("DEMO DATA - this is sanitized sample data, not a real Warcraft Logs report")
        layout.addWidget(label)
        layout.addStretch()


class BackgroundTaskPanel(QFrame):
    """Progress bar + status message + cancel button for the active background task."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        self.status_label = QLabel("Idle")
        self.status_label.setMinimumWidth(220)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.setEnabled(False)

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar, stretch=1)
        layout.addWidget(self.cancel_button)

    def start(self, message: str) -> None:
        self.setVisible(True)
        self.status_label.setText(message)
        self.progress_bar.setValue(0)
        self.cancel_button.setEnabled(True)

    def update_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        if message:
            self.status_label.setText(message)

    def finish(self, message: str) -> None:
        self.progress_bar.setValue(100)
        self.status_label.setText(message)
        self.cancel_button.setEnabled(False)

    def reset(self) -> None:
        self.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Idle")
        self.cancel_button.setEnabled(False)
