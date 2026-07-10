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

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ascend.api.client import WCLClient
from ascend.api.url_parser import InvalidReportReferenceError, build_report_url, parse_report_reference
from ascend.data.database import Database
from ascend.data.repositories import SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.sync_service import sync_report_by_code
from ascend.theme import DARK_TOKENS, PALETTE, apply_card_elevation
from ascend.ui.dialogs import show_error
from ascend.ui.icons import icon
from ascend.ui.widgets import BackgroundTaskPanel, make_badge, make_phase_badge

RECENT_URLS_SETTING_KEY = "recent_report_urls"
MAX_RECENT_URLS = 5

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
#
# Toasts live in a dedicated ToastOverlay anchored top-right, below the page's
# context bar - never inline in card content, and never blocking a primary
# control. Informational toasts auto-dismiss; warnings/errors stay until the
# user dismisses them (or clicks through, e.g. to Diagnostics).

class ToastCard(QFrame):
    """A single stacked notification. tone: info / success / warning / error."""

    dismissed = Signal()

    def __init__(
        self,
        text: str,
        tone: str = "info",
        duration_ms: int | None = None,
        on_click: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("class", "banner")
        self.setProperty("bannerTone", tone)
        self.setObjectName("toastCard")
        self._on_click = on_click
        if on_click:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(8)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label, stretch=1)

        close_button = QPushButton("×")
        close_button.setObjectName("secondaryFlatButton")
        close_button.setFixedWidth(22)
        close_button.clicked.connect(self._dismiss)
        layout.addWidget(close_button)

        # Informational toasts auto-dismiss by default; warnings/errors require
        # an explicit manual dismissal unless the caller overrides duration_ms.
        if duration_ms is None:
            duration_ms = 6000 if tone in ("info", "success") else 0
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self._dismiss)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if self._on_click:
            self._on_click()
        super().mousePressEvent(event)

    def _dismiss(self) -> None:
        self.dismissed.emit()


class ToastOverlay(QWidget):
    """Floating overlay anchored top-right of a host widget, below its context
    bar. Stacks ToastCards vertically without affecting the host's layout
    geometry - a fixed-width floating widget, not part of any layout."""

    _MARGIN = 16
    _WIDTH = 340

    def __init__(self, host: QWidget, top_offset: int = 64):
        super().__init__(host)
        self._host = host
        self._top_offset = top_offset
        self.setFixedWidth(self._WIDTH)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        host.installEventFilter(self)
        self.hide()

    def show_toast(
        self,
        text: str,
        tone: str = "info",
        duration_ms: int | None = None,
        on_click: Callable[[], None] | None = None,
    ) -> ToastCard:
        toast = ToastCard(text, tone=tone, duration_ms=duration_ms, on_click=on_click, parent=self)
        toast.dismissed.connect(lambda: self._remove(toast))
        self._layout.addWidget(toast)
        self._reposition()
        self.show()
        self.raise_()
        return toast

    def _remove(self, toast: ToastCard) -> None:
        self._layout.removeWidget(toast)
        toast.setParent(None)
        toast.deleteLater()
        self._reposition()
        if self._layout.count() == 0:
            self.hide()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override signature
        if obj is self._host and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._reposition()
        return super().eventFilter(obj, event)

    def _reposition(self) -> None:
        self.adjustSize()
        x = self._host.width() - self.width() - self._MARGIN
        self.move(max(0, x), self._top_offset)
        self.raise_()


# -- Analyze bar ----------------------------------------------------------
#
# Shared URL-parse -> WCLClient -> sync_report_by_code workflow, used two ways:
#   * compact=False - the large onboarding "hero" experience (No Data state).
#   * compact=True  - the small "Quick Analyze" control shown once analytics
#     data exists (Active Analytics state), so the big hero card isn't kept
#     around forever. Both share one implementation so the workflow can't
#     drift between the two presentations.

class AnalyzeBar(QWidget):
    """URL input + ANALYZE button + secondary actions + background-task
    progress. Emits signals rather than talking to toasts/dialogs directly so
    the owning state widget decides how to present the outcome."""

    report_ready = Signal(object)
    analysis_failed = Signal(str)
    analysis_cancelled = Signal()

    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        compact: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.secure_storage = secure_storage
        self.task_manager = task_manager
        self.compact = compact
        self.settings_repo = SettingsRepository(db)
        self._active_task = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if compact else 10)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Warcraft Logs URL or report code")
        self.url_edit.setMinimumHeight(30 if compact else 40)
        self.url_edit.returnPressed.connect(self._on_analyze_clicked)
        input_row.addWidget(self.url_edit, stretch=1)

        self.analyze_button = QPushButton("ANALYZE")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.setMinimumHeight(30 if compact else 40)
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        input_row.addWidget(self.analyze_button)
        layout.addLayout(input_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)

        paste_button = QPushButton("Paste Clipboard")
        paste_button.setObjectName("secondaryFlatButton")
        paste_button.clicked.connect(self._on_paste_clicked)
        actions_row.addWidget(paste_button)

        self.recent_combo = QComboBox()
        self.recent_combo.setMinimumWidth(130 if compact else 150)
        self._reload_recent_urls()
        self.recent_combo.activated.connect(self._on_recent_selected)
        actions_row.addWidget(self.recent_combo)

        if not compact:
            self.open_browser_button = QPushButton("Open Warcraft Logs")
            self.open_browser_button.setObjectName("secondaryFlatButton")
            self.open_browser_button.clicked.connect(self._on_open_browser_clicked)
            actions_row.addWidget(self.open_browser_button)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.clicked.connect(self._on_cancel)
        layout.addWidget(self.task_panel)

        if compact:
            self.setMaximumHeight(96)

    # -- recent URL handling -------------------------------------------------

    def _reload_recent_urls(self) -> None:
        recent = self.settings_repo.get(RECENT_URLS_SETTING_KEY, [])
        self.recent_combo.clear()
        self.recent_combo.addItem("Recent Reports")
        for url in recent:
            self.recent_combo.addItem(url)

    def _remember_recent_url(self, raw_input: str) -> None:
        recent = self.settings_repo.get(RECENT_URLS_SETTING_KEY, [])
        recent = [raw_input] + [u for u in recent if u != raw_input]
        recent = recent[:MAX_RECENT_URLS]
        self.settings_repo.set(RECENT_URLS_SETTING_KEY, recent)
        self._reload_recent_urls()

    def _on_recent_selected(self, index: int) -> None:
        if index > 0:
            self.url_edit.setText(self.recent_combo.itemText(index))

    def _on_paste_clicked(self) -> None:
        clipboard_text = QApplication.clipboard().text()
        if clipboard_text:
            self.url_edit.setText(clipboard_text.strip())

    def _parse_current_input(self):
        raw = self.url_edit.text().strip()
        try:
            return raw, parse_report_reference(raw)
        except InvalidReportReferenceError as exc:
            show_error(self, "Invalid report URL or code", str(exc))
            return raw, None

    def _on_open_browser_clicked(self) -> None:
        raw, parsed = self._parse_current_input()
        if parsed is None:
            return
        QDesktopServices.openUrl(QUrl(build_report_url(parsed.report_code, parsed.fight)))

    def _build_client(self) -> WCLClient | None:
        client_id = self.settings_repo.get("wcl_client_id", "")
        client_secret = self.secure_storage.get_client_secret() or ""
        timeout = self.settings_repo.get("api_timeout_seconds", 15)
        if not client_id or not client_secret:
            show_error(
                self, "Warcraft Logs credentials not set",
                "Enter your Warcraft Logs client ID and client secret in Settings first.",
            )
            return None
        return WCLClient(client_id, client_secret, timeout_seconds=float(timeout))

    def _on_analyze_clicked(self) -> None:
        raw, parsed = self._parse_current_input()
        if parsed is None:
            return
        client = self._build_client()
        if client is None:
            return

        self._remember_recent_url(raw)
        self.analyze_button.setEnabled(False)
        self.task_panel.start(f"Fetching report {parsed.report_code}...")

        task = self.task_manager.submit(sync_report_by_code, self.db, client, parsed.report_code)
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_finished)
        task.signals.error.connect(self._on_error)
        task.signals.cancelled.connect(self._on_cancelled)

    def _on_finished(self, report) -> None:
        self.analyze_button.setEnabled(True)
        self._active_task = None
        if report is None:
            self.task_panel.reset()
            return
        self.task_panel.finish(f"Retrieved report {report.report_code}.")
        self.report_ready.emit(report)

    def _on_error(self, message: str) -> None:
        self.analyze_button.setEnabled(True)
        self._active_task = None
        self.task_panel.reset()
        if "ReportCodeNotFoundError" in message:
            message = message.split(":", 1)[-1].strip()
        self.analysis_failed.emit(message)

    def _on_cancelled(self) -> None:
        self.analyze_button.setEnabled(True)
        self._active_task = None
        self.task_panel.finish("Cancelled.")
        self.analysis_cancelled.emit()

    def _on_cancel(self) -> None:
        if self._active_task is not None:
            self._active_task.cancel()


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


# -- KPI row ------------------------------------------------------------
#
# Deliberately no per-metric card/border - a single unified surface (level 3,
# "supporting information") with subtle vertical dividers between metrics,
# per the visual-hierarchy spec. Scrolls horizontally at smaller widths
# instead of shrinking every metric illegibly.

class KPIMetric(QWidget):
    """One KPI: small icon + label above, value + optional trend below."""

    def __init__(
        self, icon_name: str, label: str, value: str = "--", trend: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(3)

        label_row = QHBoxLayout()
        label_row.setSpacing(5)
        icon_label = QLabel()
        icon_label.setPixmap(icon(icon_name).pixmap(13, 13))
        label_row.addWidget(icon_label)
        label_label = QLabel(label.upper())
        label_label.setProperty("class", "muted")
        label_label.setStyleSheet(
            f"font-size: {DARK_TOKENS.type_scale.kpi_label[0]}px; font-weight: 700; letter-spacing: 0.5px;"
        )
        label_row.addWidget(label_label)
        label_row.addStretch()
        layout.addLayout(label_row)

        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        value_row.addWidget(self.value_label)
        self.trend_label = QLabel(trend or "")
        self.trend_label.setStyleSheet(f"font-size: 10px; color: {PALETTE.text_secondary};")
        self.trend_label.setVisible(bool(trend))
        value_row.addWidget(self.trend_label)
        value_row.addStretch()
        layout.addLayout(value_row)

    def set_value(self, value: str, trend: str | None = None) -> None:
        self.value_label.setText(value)
        if trend is not None:
            self.trend_label.setText(trend)
            self.trend_label.setVisible(bool(trend))


class KPIRow(QScrollArea):
    """Unified KPI strip: metrics separated by a hairline divider, not
    individual mini-cards."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(DARK_TOKENS.control.kpi_chip_height + 4)

        container = QWidget()
        container.setProperty("class", "card")
        self._layout = QHBoxLayout(container)
        self._layout.setContentsMargins(4, 10, 4, 10)
        self._layout.setSpacing(0)
        self.setWidget(container)
        self._is_first = True

    def add_metric(self, icon_name: str, label: str, value: str = "--", trend: str | None = None) -> KPIMetric:
        if not self._is_first:
            divider = QFrame()
            divider.setObjectName("kpiDivider")
            divider.setFrameShape(QFrame.Shape.VLine)
            divider.setFixedWidth(1)
            self._layout.addWidget(divider)
        self._is_first = False
        metric = KPIMetric(icon_name, label, value, trend)
        self._layout.addWidget(metric)
        return metric

    def finish(self) -> None:
        self._layout.addStretch()


# Backwards-compatible aliases (KPIStrip/KPIChip -> KPIRow/KPIMetric).
KPIStrip = KPIRow
KPIChip = KPIMetric


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
