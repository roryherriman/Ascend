"""Reusable themed components shared across pages.

Every widget here reads its colors/spacing from ascend/ui/styles/tokens.py
(directly, or indirectly via the QSS classes defined in ascend/ui/styles/) -
none of them hardcode a color inline, so retheming stays centralized.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ascend.theme import PALETTE, apply_card_elevation
from ascend.ui.icons import icon

# -- Badges -----------------------------------------------------------------

_BADGE_TONES = {"neutral", "accent", "success", "warning", "error", "info"}


def make_badge(text: str, tone: str = "neutral") -> QLabel:
    """A small pill badge. ``tone`` matches a QSS selector in ui/styles/cards.py."""
    assert tone in _BADGE_TONES, f"unknown badge tone: {tone}"
    label = QLabel(text)
    label.setProperty("class", "badge")
    label.setProperty("badgeTone", tone)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def make_phase_badge(phase: int) -> QLabel:
    return make_badge(f"PHASE {phase}", tone="accent")


_CONFIDENCE_TONES = {
    "high": "success",
    "medium": "warning",
    "low": "error",
    "insufficient": "neutral",
}


def make_confidence_badge(level: str) -> QLabel:
    tone = _CONFIDENCE_TONES.get(level.lower(), "neutral")
    return make_badge(f"{level.upper()} CONFIDENCE", tone=tone)


_TREND_COLORS = {"up": PALETTE.success, "down": PALETTE.error, "flat": PALETTE.text_secondary}
_TREND_GLYPHS = {"up": "▲", "down": "▼", "flat": "–"}


def make_trend_label(direction: str, text: str = "") -> QLabel:
    """Small colored trend indicator, e.g. '▲ 4.2%'. direction: up/down/flat."""
    direction = direction.lower()
    glyph = _TREND_GLYPHS.get(direction, "–")
    color = _TREND_COLORS.get(direction, PALETTE.text_secondary)
    label = QLabel(f"{glyph} {text}".strip())
    label.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 11px;")
    return label


# -- Cards --------------------------------------------------------------

class MetricCard(QFrame):
    """Dashboard metric card: label, big value, optional comparison/trend/confidence hint."""

    def __init__(
        self,
        title: str,
        value: str = "--",
        subtext: str = "",
        tooltip: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setObjectName("metricCard")
        self.setMinimumHeight(108)
        apply_card_elevation(self)
        if tooltip:
            self.setToolTip(tooltip)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setProperty("class", "muted")
        self.title_label.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.6px;")
        self.title_label.setWordWrap(True)

        value_row = QHBoxLayout()
        value_row.setSpacing(8)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 26px; font-weight: 700;")
        value_row.addWidget(self.value_label)
        self.trend_label = make_trend_label("flat", "")
        self.trend_label.setVisible(False)
        value_row.addWidget(self.trend_label)
        value_row.addStretch()

        self.subtext_label = QLabel(subtext)
        self.subtext_label.setProperty("class", "muted")
        self.subtext_label.setStyleSheet("font-size: 11px;")
        self.subtext_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addLayout(value_row)
        layout.addWidget(self.subtext_label)
        layout.addStretch()

    def set_value(self, value: str, subtext: str | None = None) -> None:
        self.value_label.setText(value)
        if subtext is not None:
            self.subtext_label.setText(subtext)

    def set_trend(self, direction: str, text: str) -> None:
        self.trend_label.setText(f"{_TREND_GLYPHS.get(direction, '-')} {text}".strip())
        self.trend_label.setStyleSheet(
            f"color: {_TREND_COLORS.get(direction, PALETTE.text_secondary)}; "
            "font-weight: 600; font-size: 11px;"
        )
        self.trend_label.setVisible(True)


# Backwards-compatible alias used by earlier Phase 1 code.
StatCard = MetricCard


class InfoCard(QFrame):
    """A card for freeform content (e.g. character summary, strengths list) with a title."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        apply_card_elevation(self)

        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(16, 14, 16, 14)
        self.layout_.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.layout_.addWidget(title_label)

        self.body_layout = QVBoxLayout()
        self.body_layout.setSpacing(4)
        self.layout_.addLayout(self.body_layout)

    def add_widget(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)


# -- Banners --------------------------------------------------------------

class Banner(QFrame):
    """A dismissable-looking (but not necessarily dismissable) inline banner.
    tone: success / warning / error / info."""

    def __init__(self, text: str, tone: str = "info", parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "banner")
        self.setProperty("bannerTone", tone)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        layout.addWidget(self.label, stretch=1)

    def set_text(self, text: str) -> None:
        self.label.setText(text)


class DemoBanner(Banner):
    """Persistent banner shown across the whole app while Demo Mode is active,
    so demo data is never mistaken for a real analysis."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(
            "DEMO DATA — this is sanitized sample data, not a real Warcraft Logs report",
            tone="warning",
            parent=parent,
        )
        self.setObjectName("demoBanner")
        self.label.setStyleSheet("font-weight: 700;")


# -- Empty states -----------------------------------------------------------
#
# The full AscendEmptyState component (icon, phase badge, planned list, and
# action buttons) lives in ascend/ui/components.py. PlaceholderPage wraps it
# with a page title for full-page use by main_window.py.

class PlaceholderPage(QWidget):
    """Full-page designed empty state shown for sections not yet implemented
    in the current development phase."""

    def __init__(
        self,
        title: str,
        phase_note: str,
        phase: int | None = None,
        planned: list[str] | None = None,
        icon_name: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        from ascend.ui.components import AscendEmptyState  # local import: avoids a circular import

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)

        panel = AscendEmptyState(
            title=title,
            description=phase_note,
            icon_name=icon_name,
            phase=phase,
            planned=planned,
            secondary_action=("View Roadmap", self._open_roadmap),
        )
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout.addWidget(panel)
        layout.addStretch()

    @staticmethod
    def _open_roadmap() -> None:
        from pathlib import Path

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        roadmap_path = Path(__file__).resolve().parent.parent.parent / "docs" / "ROADMAP.md"
        if roadmap_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(roadmap_path)))


# -- Background task panel ---------------------------------------------------

class BackgroundTaskPanel(QFrame):
    """Progress bar + status message + cancel button for the active background task."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

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
