"""Report Library — card-based view of all synced Warcraft Logs reports.

PR 6 replaces the dense QTableWidget with a scrollable card grid:
each report card shows title, zone, date, pull stats, and inline
action buttons (View Raid Night, Open on WCL, Delete).

The toolbar keeps Discover Reports / Add Report Code / task panel.
A zone filter dropdown + search bar narrow the visible cards.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from ascend.api.client import WCLClient
from ascend.data.database import Database
from ascend.data.models import Report
from ascend.data.repositories import ReportRepository, SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.sync_service import sync_new_guild_reports, sync_report_by_code
from ascend.services.zone_data import label_for_difficulty
from ascend.ui.dialogs import ReportCodeDialog, confirm, show_error, show_info
from ascend.ui.styles.tokens import DARK_TOKENS
from ascend.ui.widgets import BackgroundTaskPanel, make_badge

_ALL_ZONES = "All Zones"


def _format_date(epoch_ms: float | None) -> str:
    if not epoch_ms:
        return ""
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return ""


def _pull_stats(fights) -> str:
    if not fights:
        return "No pulls"
    kills = sum(1 for f in fights if f.kill)
    wipes = sum(1 for f in fights if f.kill is False)
    parts = [f"{len(fights)} pull{'s' if len(fights) != 1 else ''}"]
    if kills:
        parts.append(f"{kills} kill{'s' if kills != 1 else ''}")
    if wipes:
        parts.append(f"{wipes} wipe{'s' if wipes != 1 else ''}")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Report card widget
# ---------------------------------------------------------------------------

class _ReportCard(QFrame):
    """Single report entry in the library grid."""

    def __init__(
        self,
        report: Report,
        fights: list,
        difficulty_label: str,
        on_view: "Callable[[Report], None]",
        on_open_wcl: "Callable[[Report], None]",
        on_delete: "Callable[[Report], None]",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.report = report
        self.setObjectName("reportCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            #reportCard {{
                background: {DARK_TOKENS.palette.bg_card};
                border: 1px solid {DARK_TOKENS.palette.border};
                border-radius: 6px;
            }}
            #reportCard:hover {{
                border-color: {DARK_TOKENS.palette.accent_muted};
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(4)

        # ── Top row: zone · date + status badge ──────────────────────────
        top = QHBoxLayout()
        top.setSpacing(6)

        zone_date = QLabel()
        zone_name = report.zone_name or ""
        date_str = _format_date(report.start_time)
        zone_date_parts = [p for p in [zone_name, date_str] if p]
        zone_date.setText(" · ".join(zone_date_parts) if zone_date_parts else "Unknown zone")
        zone_date.setStyleSheet(
            f"font-size: 11px; color: {DARK_TOKENS.palette.text_muted};"
        )
        top.addWidget(zone_date)
        top.addStretch()

        if report.report_source == "guild_discovery":
            source_badge = make_badge("GUILD SYNC", tone="accent")
            top.addWidget(source_badge)

        status_tone = "success" if report.analysis_status == "analyzed" else "neutral"
        badge = make_badge(report.analysis_status.replace("_", " ").upper(), tone=status_tone)
        top.addWidget(badge)
        outer.addLayout(top)

        # ── Title ─────────────────────────────────────────────────────────
        title_text = report.title or report.report_code
        title = QLabel(title_text)
        title.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {DARK_TOKENS.palette.text_primary};"
        )
        title.setWordWrap(True)
        outer.addWidget(title)

        # ── Stats row ─────────────────────────────────────────────────────
        stats_parts = [_pull_stats(fights)]
        if difficulty_label and difficulty_label != "--":
            stats_parts.append(difficulty_label)
        guild_or_owner = report.guild_name or report.owner_name or ""
        if guild_or_owner:
            stats_parts.append(guild_or_owner)

        stats = QLabel(" · ".join(stats_parts))
        stats.setStyleSheet(
            f"font-size: 11px; color: {DARK_TOKENS.palette.text_secondary};"
        )
        outer.addWidget(stats)

        # ── Action buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()

        view_btn = QPushButton("View Raid Night")
        view_btn.setFixedHeight(26)
        view_btn.clicked.connect(lambda: on_view(report))
        btn_row.addWidget(view_btn)

        wcl_btn = QPushButton("Open WCL")
        wcl_btn.setFixedHeight(26)
        wcl_btn.clicked.connect(lambda: on_open_wcl(report))
        btn_row.addWidget(wcl_btn)

        del_btn = QPushButton("Delete")
        del_btn.setObjectName("dangerButton")
        del_btn.setFixedHeight(26)
        del_btn.clicked.connect(lambda: on_delete(report))
        btn_row.addWidget(del_btn)

        outer.addLayout(btn_row)


# ---------------------------------------------------------------------------
# Reports page
# ---------------------------------------------------------------------------

class ReportsPage(QWidget):
    view_raid_night_requested = Signal(int)

    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.secure_storage = secure_storage
        self.task_manager = task_manager
        self.repo = ReportRepository(db)
        self.settings_repo = SettingsRepository(db)
        self._reports: list[Report] = []
        self._active_task = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Report Library")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by title, code, or guild…")
        self.search_edit.textChanged.connect(self._rebuild_cards)
        toolbar.addWidget(self.search_edit, stretch=1)

        self.zone_filter = QComboBox()
        self.zone_filter.setMinimumWidth(180)
        self.zone_filter.currentTextChanged.connect(self._rebuild_cards)
        toolbar.addWidget(self.zone_filter)

        self.discover_button = QPushButton("Discover Reports")
        self.discover_button.setToolTip(
            "Fetch all new guild reports from Warcraft Logs not yet in your local library."
        )
        self.discover_button.clicked.connect(self._on_discover)
        toolbar.addWidget(self.discover_button)

        self.add_code_button = QPushButton("Add Report Code")
        self.add_code_button.setObjectName("primaryButton")
        self.add_code_button.clicked.connect(self._on_add_report_code)
        toolbar.addWidget(self.add_code_button)

        layout.addLayout(toolbar)

        # ── Card scroll area ──────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 8, 0, 8)
        self._cards_layout.setSpacing(8)
        self._scroll.setWidget(self._cards_container)
        layout.addWidget(self._scroll, stretch=1)

        # ── Task panel ────────────────────────────────────────────────────
        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.clicked.connect(self._on_cancel_sync)
        layout.addWidget(self.task_panel)

        self.reload()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def reload(self) -> None:
        self._reports = self.repo.list_all()
        self._refresh_zone_filter()
        self._refresh_discover_button()
        self._rebuild_cards()

    def _refresh_zone_filter(self) -> None:
        current = self.zone_filter.currentText()
        zones = sorted({r.zone_name for r in self._reports if r.zone_name})
        self.zone_filter.blockSignals(True)
        self.zone_filter.clear()
        self.zone_filter.addItem(_ALL_ZONES)
        self.zone_filter.addItems(zones)
        if current in zones:
            self.zone_filter.setCurrentText(current)
        self.zone_filter.blockSignals(False)

    def _filtered_reports(self) -> list[Report]:
        text = self.search_edit.text().strip().lower()
        zone = self.zone_filter.currentText()
        result = self._reports
        if zone and zone != _ALL_ZONES:
            result = [r for r in result if (r.zone_name or "") == zone]
        if text:
            result = [
                r for r in result
                if text in (r.title or "").lower()
                or text in r.report_code.lower()
                or text in (r.guild_name or "").lower()
                or text in (r.owner_name or "").lower()
            ]
        return result

    def _rebuild_cards(self) -> None:
        # Remove old cards
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        reports = self._filtered_reports()

        if not self._reports:
            self._cards_layout.addWidget(self._empty_state(
                "No reports yet",
                "Use 'Add Report Code' to import a report, or 'Discover Reports' to pull"
                " all guild reports from Warcraft Logs.",
            ))
            self._cards_layout.addStretch()
            return

        if not reports:
            self._cards_layout.addWidget(self._empty_state(
                "No matching reports",
                "Try a different search term or clear the zone filter.",
            ))
            self._cards_layout.addStretch()
            return

        for report in reports:
            fights = self.repo.fights_for_report(report.id) if report.id else []
            difficulty_labels = sorted({
                label_for_difficulty(self.db, report.zone_id, f.difficulty)
                for f in fights if f.difficulty is not None
            } - {"--"})
            difficulty_label = difficulty_labels[0] if difficulty_labels else ""

            card = _ReportCard(
                report=report,
                fights=fights,
                difficulty_label=difficulty_label,
                on_view=self._on_view_raid_night,
                on_open_wcl=self._on_open_on_wcl,
                on_delete=self._on_delete,
            )
            self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()

    def _empty_state(self, heading: str, body: str) -> QLabel:
        label = QLabel(f"<b>{heading}</b><br><span style='color:{DARK_TOKENS.palette.text_muted}'>{body}</span>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet(f"padding: 40px; color: {DARK_TOKENS.palette.text_secondary};")
        return label

    # ------------------------------------------------------------------
    # Discover / guild sync
    # ------------------------------------------------------------------

    def _refresh_discover_button(self) -> None:
        guild_id = self.settings_repo.get("guild_wcl_id", None)
        enabled = bool(guild_id)
        self.discover_button.setEnabled(enabled)
        if not enabled:
            self.discover_button.setToolTip(
                "Set a guild in Settings to enable automatic report discovery."
            )

    def _on_discover(self) -> None:
        guild_id_raw = self.settings_repo.get("guild_wcl_id", None)
        if not guild_id_raw:
            show_error(self, "No guild configured", "Set a guild in Settings > Raid Context first.")
            return
        try:
            guild_id = int(guild_id_raw)
        except (TypeError, ValueError):
            show_error(self, "Invalid guild ID", "The stored guild ID is not a valid integer.")
            return

        client = self._build_client()
        if client is None:
            return

        self.discover_button.setEnabled(False)
        self.add_code_button.setEnabled(False)
        self.task_panel.start("Discovering new guild reports…")

        task = self.task_manager.submit(sync_new_guild_reports, self.db, client, guild_id)
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_discover_finished)
        task.signals.error.connect(self._on_discover_error)
        task.signals.cancelled.connect(self._on_discover_cancelled)

    def _on_discover_finished(self, new_reports: list) -> None:
        self._active_task = None
        self.discover_button.setEnabled(True)
        self.add_code_button.setEnabled(True)
        count = len(new_reports) if new_reports else 0
        if count == 0:
            self.task_panel.finish("No new reports found.")
            show_info(self, "Up to date", "No new reports were found for your guild.")
        else:
            self.task_panel.finish(f"Synced {count} new report{'s' if count != 1 else ''}.")
            self.reload()
            titles = "\n".join(
                f"  • {r.title or r.report_code}" for r in (new_reports or [])[:5]
            )
            suffix = f"\n  … and {count - 5} more" if count > 5 else ""
            show_info(
                self,
                f"{count} new report{'s' if count != 1 else ''} found",
                f"The following reports were synced from Warcraft Logs:\n{titles}{suffix}",
            )

    def _on_discover_error(self, message: str) -> None:
        self._active_task = None
        self.discover_button.setEnabled(True)
        self.add_code_button.setEnabled(True)
        self.task_panel.reset()
        show_error(self, "Report discovery failed", message)

    def _on_discover_cancelled(self) -> None:
        self._active_task = None
        self.discover_button.setEnabled(True)
        self.add_code_button.setEnabled(True)
        self.task_panel.finish("Discovery cancelled.")

    # ------------------------------------------------------------------
    # Add report by code
    # ------------------------------------------------------------------

    def _on_add_report_code(self) -> None:
        dialog = ReportCodeDialog(self)
        if not dialog.exec():
            return
        code = dialog.report_code()
        client = self._build_client()
        if client is None:
            return

        self.add_code_button.setEnabled(False)
        self.task_panel.start(f"Fetching report {code}...")

        task = self.task_manager.submit(sync_report_by_code, self.db, client, code)
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(lambda result: self._on_sync_finished(result))
        task.signals.error.connect(self._on_sync_error)
        task.signals.cancelled.connect(self._on_sync_cancelled)

    def _on_sync_finished(self, report: Report | None) -> None:
        self.add_code_button.setEnabled(True)
        self._active_task = None
        if report is None:
            self.task_panel.reset()
            return
        self.task_panel.finish(f"Synced report {report.report_code}.")
        self.reload()
        show_info(self, "Report synced", f"'{report.title or report.report_code}' was synced successfully.")

    def _on_sync_error(self, message: str) -> None:
        self.add_code_button.setEnabled(True)
        self._active_task = None
        self.task_panel.reset()
        if "ReportCodeNotFoundError" in message:
            message = message.split(":", 1)[-1].strip()
        show_error(self, "Could not sync report", message)

    def _on_sync_cancelled(self) -> None:
        self.add_code_button.setEnabled(True)
        self._active_task = None
        self.task_panel.finish("Sync cancelled.")

    def _on_cancel_sync(self) -> None:
        if self._active_task is not None:
            self._active_task.cancel()

    # ------------------------------------------------------------------
    # Per-card actions
    # ------------------------------------------------------------------

    def _on_view_raid_night(self, report: Report) -> None:
        if report.id is not None:
            self.view_raid_night_requested.emit(report.id)

    def _on_open_on_wcl(self, report: Report) -> None:
        QDesktopServices.openUrl(
            QUrl(f"https://www.warcraftlogs.com/reports/{report.report_code}")
        )

    def _on_delete(self, report: Report) -> None:
        if not confirm(
            self, "Delete local data",
            f"Delete all locally stored data for report '{report.title or report.report_code}'? "
            "This only removes local data; nothing is changed on Warcraft Logs.",
        ):
            return
        self.repo.delete_report(report.id)
        self.reload()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

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
