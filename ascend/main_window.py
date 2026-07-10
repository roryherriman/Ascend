"""Main application window: sidebar navigation + stacked pages."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.data.repositories import SessionOperationRepository
from ascend.data.secure_storage import SecureStorage
from ascend.navigation import FULL_TITLES, NAV_ITEMS, Sidebar
from ascend.services.background_worker import BackgroundTaskManager
from ascend.ui.characters_page import CharactersPage, seed_initial_characters
from ascend.ui.components import ToastOverlay
from ascend.ui.dashboard_page import DashboardPage
from ascend.ui.data_quality_page import DataQualityPage
from ascend.ui.death_review_page import DeathReviewPage
from ascend.ui.diagnostics import DiagnosticsPage
from ascend.ui.encounter_page import EncounterAnalysisPage
from ascend.ui.encounter_progression_page import EncounterProgressionPage
from ascend.ui.export_page import ExportPage
from ascend.ui.insights_page import InsightsPage
from ascend.ui.trends_page import TrendsPage
from ascend.ui.raid_night_page import RaidNightSummaryPage
from ascend.ui.reports_page import ReportsPage
from ascend.ui.roster_page import RosterComparisonPage
from ascend.ui.settings_page import SettingsPage
from ascend.ui.widgets import DemoBanner, PlaceholderPage

# key -> (development phase, note, planned capabilities, icon name)
PLACEHOLDER_META: dict[str, dict] = {
    "raid_night_comparison": dict(
        phase=3,
        note="Raid Night Comparison will let you compare two or more nights side by side.",
        planned=[
            "Compare 2+ raid nights at once",
            "Improved / Declined / Unchanged classification",
            "Category-score deltas",
        ],
        icon="raid_night_comparison",
    ),
    "readiness": dict(
        phase=3,
        note="Readiness will evaluate whether your data supports moving to a more competitive environment.",
        planned=[
            "Readiness classification with evidence",
            "Guild-rank history",
            "Largest performance gaps, not just a score",
        ],
        icon="readiness",
    ),
    "goals": dict(
        phase=3,
        note="Goals will let you set measurable targets that update automatically as you analyze reports.",
        planned=[
            "Measurable goals with start/target/current value",
            "Automatic progress updates on new analysis",
            "Not Started / In Progress / Achieved / Missed status",
        ],
        icon="goals",
    ),
    "rules": dict(
        phase=4,
        note="The Encounter Rules editor will let you configure mechanic rules without touching YAML by hand.",
        planned=[
            "Priority targets and avoidable-damage rules",
            "YAML import/export",
            "Severity, weight, and confidence per rule",
        ],
        icon="rules",
    ),
    "export": dict(
        phase=4,
        note="Discord Export will let you share a Raid Night Summary to your guild's Discord.",
        planned=[
            "Discord weekly summary",
            "PDF export",
        ],
        icon="export",
    ),
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage | None = None,
        is_demo: bool = False,
    ):
        super().__init__()
        self.db = db
        self.secure_storage = secure_storage or SecureStorage.default_instance()
        self.task_manager = BackgroundTaskManager()
        self.is_demo = is_demo
        self._settings = QSettings()

        session_ops = SessionOperationRepository(db)
        interrupted_count = session_ops.mark_unclosed_as_interrupted("app_session")
        self._session_operation_id = session_ops.start("app_session")
        self._had_unclean_previous_shutdown = interrupted_count > 0

        seed_initial_characters(db)

        self.setWindowTitle("Ascend")
        self._restore_geometry()

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        if self.is_demo:
            outer_layout.addWidget(DemoBanner())

        body = QWidget()
        root_layout = QHBoxLayout(body)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        outer_layout.addWidget(body, stretch=1)

        self.sidebar = Sidebar()
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("pageContainer")
        root_layout.addWidget(self.stack, stretch=1)

        # Global toasts (e.g. unclean-shutdown warning) - a dedicated overlay
        # anchored top-right of the page area, below any per-page context bar,
        # so it never obscures Dashboard (or any other page's) content.
        self.toast_overlay = ToastOverlay(self.stack, top_offset=16)

        self._page_indices: dict[str, int] = {}
        self._nav_labels = dict(NAV_ITEMS)
        self._build_pages()
        self._wire_cross_page_navigation()

        # A full-width status bar isn't used for messaging (see navigation/visual
        # spec) - Qt still creates one lazily via statusBar(), so keep it hidden.
        self.statusBar().setVisible(False)

        self._build_menu_bar()

        self.sidebar.section_selected.connect(self._on_section_selected)
        self._restore_last_page()

        if self._had_unclean_previous_shutdown:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(
                400,
                lambda: self.toast_overlay.show_toast(
                    "Ascend did not shut down cleanly last time - see Diagnostics for details.",
                    tone="warning",
                ),
            )

    def _build_menu_bar(self) -> None:
        from ascend.data.database import default_app_data_root
        from ascend import metadata

        mb = self.menuBar()

        file_menu = mb.addMenu("&File")

        open_data = QAction("Open Data Folder", self)
        open_data.setStatusTip("Open the folder where Ascend stores your database and exports")
        open_data.triggered.connect(self._open_data_folder)
        file_menu.addAction(open_data)

        file_menu.addSeparator()

        backup_action = QAction("Back Up Ascend Data…", self)
        backup_action.setStatusTip("Save a timestamped copy of your database to the backups folder")
        backup_action.triggered.connect(self._backup_data)
        file_menu.addAction(backup_action)

        restore_action = QAction("Restore Ascend Data…", self)
        restore_action.setStatusTip("Replace the current database with a backup (requires restart)")
        restore_action.triggered.connect(self._restore_data)
        file_menu.addAction(restore_action)

        help_menu = mb.addMenu("&Help")

        about_action = QAction("About Ascend", self)
        about_action.triggered.connect(lambda: QMessageBox.about(
            self,
            "About Ascend",
            f"<b>Ascend</b> — {metadata.APP_TAGLINE}<br><br>"
            f"Version {metadata.APP_VERSION} (build {metadata.BUILD_NUMBER})<br>"
            f"{metadata.COPYRIGHT}<br><br>"
            f"{metadata.DISCLAIMER}",
        ))
        help_menu.addAction(about_action)

        updates_action = QAction("Check for Updates", self)
        updates_action.setStatusTip("Visit the Ascend releases page")
        updates_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"https://github.com/{metadata.GITHUB_REPO}/releases"))
        )
        help_menu.addAction(updates_action)

    def _open_data_folder(self) -> None:
        from ascend.data.database import default_app_data_root
        folder = default_app_data_root()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _backup_data(self) -> None:
        from ascend.data.database import default_app_data_root
        app_root = default_app_data_root()
        db_path = self.db.db_path
        if not db_path.exists():
            QMessageBox.warning(self, "Back Up Data", "No database file found to back up.")
            return

        backups_dir = app_root / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = backups_dir / f"ascend_backup_{stamp}.db"
        try:
            shutil.copy2(str(db_path), str(dest))
            QMessageBox.information(
                self, "Back Up Data",
                f"Backup saved to:\n{dest}\n\nYour data is unchanged."
            )
        except OSError as exc:
            QMessageBox.critical(self, "Back Up Data", f"Backup failed:\n{exc}")

    def _restore_data(self) -> None:
        from ascend.data.database import default_app_data_root
        app_root = default_app_data_root()
        backups_dir = app_root / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Backup to Restore",
            str(backups_dir), "Database files (*.db)"
        )
        if not path:
            return

        confirm = QMessageBox.warning(
            self, "Restore Ascend Data",
            "This will replace your current database with the selected backup.\n\n"
            "Your current data will be backed up first, then Ascend will close.\n"
            "Restart Ascend after the restore completes.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        db_path = self.db.db_path
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        pre_backup = app_root / "backups" / f"ascend_pre_restore_{stamp}.db"
        try:
            if db_path.exists():
                shutil.copy2(str(db_path), str(pre_backup))
            self.db.close()
            shutil.copy2(path, str(db_path))
            QMessageBox.information(
                self, "Restore Complete",
                f"Restore complete. Previous data saved to:\n{pre_backup}\n\n"
                "Please restart Ascend."
            )
            self.close()
        except OSError as exc:
            QMessageBox.critical(self, "Restore Failed", f"Restore failed:\n{exc}\n\nYour original data is intact.")

    def _restore_geometry(self) -> None:
        geometry = self._settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(1400, 900)
        self.setMinimumSize(1024, 700)

    def _restore_last_page(self) -> None:
        last_key = self._settings.value("window/last_page")
        if last_key in self._page_indices:
            self.sidebar.select_section(last_key)

    def _build_pages(self) -> None:
        for key, _label in NAV_ITEMS:
            if key == "dashboard":
                page = DashboardPage(self.db, self.secure_storage, self.task_manager, is_demo=self.is_demo)
                page.open_reports_requested.connect(lambda: self.sidebar.select_section("reports"))
                page.settings_requested.connect(lambda: self.sidebar.select_section("settings"))
            elif key == "characters":
                page = CharactersPage(self.db)
            elif key == "reports":
                page = ReportsPage(self.db, self.secure_storage, self.task_manager)
                self.reports_page = page
            elif key == "raid_night":
                page = RaidNightSummaryPage(self.db)
                self.raid_night_page = page
            elif key == "encounter":
                page = EncounterAnalysisPage(self.db)
            elif key == "roster":
                page = RosterComparisonPage(self.db)
            elif key == "data_quality":
                page = DataQualityPage(self.db)
            elif key == "deaths":
                page = DeathReviewPage(self.db, self.secure_storage, self.task_manager)
            elif key == "insights":
                page = InsightsPage(self.db)
            elif key == "trends":
                page = TrendsPage(self.db)
            elif key == "encounter_progression":
                page = EncounterProgressionPage(self.db)
            elif key == "export":
                page = ExportPage(self.db)
            elif key == "settings":
                page = SettingsPage(self.db, self.secure_storage, self.task_manager)
            elif key == "diagnostics":
                page = DiagnosticsPage(self.db, self.secure_storage)
            else:
                meta = PLACEHOLDER_META.get(key, {})
                page = PlaceholderPage(
                    FULL_TITLES.get(key, self._nav_labels[key]),
                    meta.get("note", "Coming in a later phase."),
                    phase=meta.get("phase"),
                    planned=meta.get("planned"),
                    icon_name=meta.get("icon"),
                )
            index = self.stack.addWidget(page)
            self._page_indices[key] = index

    def _wire_cross_page_navigation(self) -> None:
        if hasattr(self, "reports_page") and hasattr(self, "raid_night_page"):
            self.reports_page.view_raid_night_requested.connect(self._open_raid_night_summary)
            self.raid_night_page.view_reports_requested.connect(
                lambda: self.sidebar.select_section("reports")
            )

    def _open_raid_night_summary(self, report_id: int) -> None:
        self.sidebar.select_section("raid_night")
        self.raid_night_page.select_report(report_id)

    def _on_section_selected(self, key: str) -> None:
        index = self._page_indices.get(key)
        if index is not None:
            self.stack.setCurrentIndex(index)
            # Reports/Raid Night Summary are built once at startup, so refresh
            # their data on every visit rather than only at construction time -
            # otherwise a report synced from another page (e.g. the Dashboard)
            # wouldn't show up until the app restarted.
            page = self.stack.widget(index)
            reload_fn = getattr(page, "reload", None)
            if callable(reload_fn):
                reload_fn()
        self._settings.setValue("window/last_page", key)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        # Guard against being invoked more than once (e.g. an explicit close()
        # followed by the test harness or window manager closing again) and
        # against the database having already been closed independently.
        if not getattr(self, "_shutdown_handled", False):
            self._shutdown_handled = True
            self._settings.setValue("window/geometry", self.saveGeometry())
            self.task_manager.cancel_all()
            self.task_manager.wait_for_done(3000)
            if self.db.is_open:
                SessionOperationRepository(self.db).complete(self._session_operation_id)
                self.db.close()
        super().closeEvent(event)
