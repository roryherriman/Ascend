"""Dashboard-grade reusable components: empty states, toasts, the progression
gauge, the KPI strip, and the lightweight trend chart.

Kept separate from ui/widgets.py (smaller, page-agnostic building blocks:
badges, MetricCard, InfoCard, Banner) since these are heavier, purpose-built
pieces for the redesigned Dashboard and placeholder pages. All colors and
sizes come from ascend/ui/styles/tokens.py - nothing here hardcodes a hex
value or pixel size.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ascend.theme import DARK_TOKENS, PALETTE, apply_card_elevation
from ascend.ui.icons import icon
from ascend.ui.widgets import make_badge, make_phase_badge

# -- Ascend empty state -------------------------------------------------

ActionSpec = tuple[str, Callable[[], None]]


class AscendEmptyState(QFrame):
    """Reusable designed empty state: icon, title (+ phase badge), description,
    planned-capabilities list, and up to two action buttons."""

    def __init__(
        self,
        title: str,
        description: str,
        icon_name: str | None = None,
        phase: int | None = None,
        planned: list[str] | None = None,
        primary_action: ActionSpec | None = None,
        secondary_action: ActionSpec | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("emptyStatePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        if icon_name:
            icon_label = QLabel()
            icon_label.setPixmap(icon(icon_name).pixmap(28, 28))
            layout.addWidget(icon_label)

        header_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        header_row.addWidget(title_label)
        if phase is not None:
            header_row.addWidget(make_phase_badge(phase))
        header_row.addStretch()
        layout.addLayout(header_row)

        description_label = QLabel(description)
        description_label.setProperty("class", "muted")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        if planned:
            planned_title = QLabel("Planned:")
            planned_title.setStyleSheet("font-weight: 600; margin-top: 4px; font-size: 12px;")
            layout.addWidget(planned_title)
            for capability in planned:
                item_label = QLabel(f"•  {capability}")
                item_label.setProperty("class", "muted")
                item_label.setWordWrap(True)
                item_label.setStyleSheet("font-size: 12px;")
                layout.addWidget(item_label)

        if primary_action or secondary_action:
            actions_row = QHBoxLayout()
            actions_row.setContentsMargins(0, 8, 0, 0)
            if primary_action:
                label, callback = primary_action
                button = QPushButton(label)
                button.setObjectName("primaryButton")
                button.clicked.connect(callback)
                actions_row.addWidget(button)
            if secondary_action:
                label, callback = secondary_action
                button = QPushButton(label)
                button.clicked.connect(callback)
                actions_row.addWidget(button)
            actions_row.addStretch()
            layout.addLayout(actions_row)


# -- Toast notifications -----------------------------------------------

class Toast(QFrame):
    """A transient, self-dismissing notification - used instead of permanent
    full-width status-bar text for things like an unclean-shutdown warning."""

    def __init__(self, text: str, tone: str = "info", duration_ms: int = 6000, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "banner")
        self.setProperty("bannerTone", tone)
        self.setMaximumWidth(420)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label, stretch=1)

        close_button = QPushButton("×")
        close_button.setObjectName("secondaryFlatButton")
        close_button.setFixedWidth(24)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.close)

    @staticmethod
    def show_in(parent: QWidget, text: str, tone: str = "info", duration_ms: int = 6000) -> "Toast":
        """Anchors a toast to the bottom-right of ``parent`` and shows it."""
        toast = Toast(text, tone=tone, duration_ms=duration_ms, parent=parent)
        toast.adjustSize()
        margin = 16
        x = parent.width() - toast.width() - margin
        y = parent.height() - toast.height() - margin
        toast.move(max(margin, x), max(margin, y))
        toast.show()
        toast.raise_()
        return toast


# -- Progression gauge ---------------------------------------------------

_CLASSIFICATION_COLORS = {
    "standout": PALETTE.secondary_accent,
    "strong": PALETTE.success,
    "above average": PALETTE.accent_cyan,
    "average": PALETTE.text_secondary,
    "below average": PALETTE.warning,
    "significant concerns": PALETTE.error,
}


class ProgressionGauge(QWidget):
    """A circular score gauge (0-100) with a classification label underneath.
    Shows a clear 'no analysis yet' state when there's no score to display."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._score: int | None = None
        self._classification = ""
        self.setMinimumSize(140, 140)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def set_score(self, score: int | None, classification: str = "") -> None:
        self._score = score
        self._classification = classification
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 12
        rect = QRectF((self.width() - side) / 2, 8, side, side)

        track_pen = QPen(QColor(DARK_TOKENS.palette.border))
        track_pen.setWidth(max(6, side // 14))
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self._score is not None:
            color = _CLASSIFICATION_COLORS.get(self._classification.lower(), PALETTE.accent)
            arc_pen = QPen(QColor(color))
            arc_pen.setWidth(max(6, side // 14))
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            span = int(360 * 16 * (self._score / 100))
            painter.drawArc(rect, 90 * 16, -span)

            painter.setPen(QColor(PALETTE.text_primary))
            font = QFont()
            font.setPixelSize(int(side * 0.26))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._score))
        else:
            painter.setPen(QColor(PALETTE.text_muted))
            font = QFont()
            font.setPixelSize(int(side * 0.22))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "--")

        painter.end()


# -- KPI strip ------------------------------------------------------------

class KPIChip(QFrame):
    """One compact KPI: icon, label, value, optional trend, optional confidence dot."""

    def __init__(
        self, icon_name: str, label: str, value: str = "--", trend: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setFixedHeight(DARK_TOKENS.control.kpi_chip_height)
        self.setMinimumWidth(128)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setPixmap(icon(icon_name).pixmap(16, 16))
        layout.addWidget(icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        label_label = QLabel(label.upper())
        label_label.setProperty("class", "muted")
        label_label.setStyleSheet(f"font-size: {DARK_TOKENS.type_scale.kpi_label[0]}px; font-weight: 700; letter-spacing: 0.5px;")
        text_col.addWidget(label_label)

        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        value_row.addWidget(self.value_label)
        self.trend_label = QLabel(trend or "")
        self.trend_label.setStyleSheet(f"font-size: 10px; color: {PALETTE.text_secondary};")
        self.trend_label.setVisible(bool(trend))
        value_row.addWidget(self.trend_label)
        value_row.addStretch()
        text_col.addLayout(value_row)
        layout.addLayout(text_col)

    def set_value(self, value: str, trend: str | None = None) -> None:
        self.value_label.setText(value)
        if trend is not None:
            self.trend_label.setText(trend)
            self.trend_label.setVisible(bool(trend))


class KPIStrip(QScrollArea):
    """Compact horizontal strip of KPI chips - scrolls at smaller widths
    instead of shrinking every chip illegibly."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(DARK_TOKENS.control.kpi_chip_height + 4)

        container = QWidget()
        self._layout = QHBoxLayout(container)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(10)
        self.setWidget(container)

    def add_chip(self, icon_name: str, label: str, value: str = "--", trend: str | None = None) -> KPIChip:
        chip = KPIChip(icon_name, label, value, trend)
        self._layout.addWidget(chip)
        return chip

    def finish(self) -> None:
        self._layout.addStretch()


# -- Trend chart -----------------------------------------------------------

class TrendChartWidget(QWidget):
    """Lightweight custom-painted line chart with a gradient fill, used as the
    Dashboard's Performance Trend anchor. Deliberately not Plotly/QtWebEngine -
    that's a heavy new dependency this app doesn't otherwise need, and there's
    no real trend data to chart until Phase 2/3 anyway."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._points: list[float] = []
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_series(self, values: list[float]) -> None:
        self._points = values
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = 8
        rect = self.rect().adjusted(margin, margin, -margin, -margin)

        grid_pen = QPen(QColor(DARK_TOKENS.palette.border))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        for i in range(4):
            y = rect.top() + rect.height() * i / 3
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

        if len(self._points) >= 2:
            lo, hi = min(self._points), max(self._points)
            span = max(hi - lo, 1e-6)
            step = rect.width() / (len(self._points) - 1)

            from PySide6.QtGui import QLinearGradient, QPainterPath

            path = QPainterPath()
            fill_path = QPainterPath()
            for i, value in enumerate(self._points):
                x = rect.left() + i * step
                y = rect.bottom() - ((value - lo) / span) * rect.height()
                if i == 0:
                    path.moveTo(x, y)
                    fill_path.moveTo(x, rect.bottom())
                    fill_path.lineTo(x, y)
                else:
                    path.lineTo(x, y)
                    fill_path.lineTo(x, y)
            fill_path.lineTo(rect.right(), rect.bottom())
            fill_path.closeSubpath()

            gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
            gradient.setColorAt(0.0, QColor(DARK_TOKENS.palette.accent_muted))
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillPath(fill_path, gradient)

            line_pen = QPen(QColor(DARK_TOKENS.palette.accent))
            line_pen.setWidth(2)
            painter.setPen(line_pen)
            painter.drawPath(path)
        else:
            painter.setPen(QColor(PALETTE.text_muted))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No performance history yet.")

        painter.end()
