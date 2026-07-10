"""Main application window: sidebar navigation + stacked pages."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from ascend.data.database import Database
from ascend.data.repositories import SessionOperationRepository
from ascend.data.secure_storage import SecureStorage
from ascend.navigation import NAV_ITEMS, Sidebar
from ascend.services.background_worker import BackgroundTaskManager
from ascend.ui.characters_page import CharactersPage, seed_initial_characters
from ascend.ui.dashboard_page import DashboardPage
from ascend.ui.diagnostics import DiagnosticsPage
from ascend.ui.reports_page import ReportsPage
from ascend.ui.settings_page import SettingsPage
from ascend.ui.widgets import DemoBanner, PlaceholderPage

PLACEHOLDER_NOTES = {
    "raid_night": "The Raid Night Summary arrives in Phase 2.",
    "encounter": "Pull-by-pull encounter analysis arrives in Phase 2.",
    "deaths": "Death review with manual classification arrives in Phase 3.",
    "roster": "Roster comparison arrives in Phase 2.",
    "trends": "Learning-speed and trend analysis arrives in Phase 3.",
    "insights": "The evidence-based Insights engine arrives in Phase 2/3.",
    "readiness": "Readiness assessment arrives in Phase 3.",
    "goals": "Goal tracking arrives in Phase 3.",
    "raid_night_comparison": "Raid night comparison arrives in Phase 3.",
    "encounter_progression": "Encounter progression timelines arrive in Phase 3.",
    "rules": "The encounter-rule editor arrives in Phase 4.",
    "data_quality": "Data Quality indicators arrive in Phase 2.",
    "export": "HTML/CSV/JSON/PDF export and Discord posting arrive in Phase 3/4.",
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

        session_ops = SessionOperationRepository(db)
        interrupted_count = session_ops.mark_unclosed_as_interrupted("app_session")
        self._session_operation_id = session_ops.start("app_session")
        self._had_unclean_previous_shutdown = interrupted_count > 0

        seed_initial_characters(db)

        self.setWindowTitle("Ascend")
        self.resize(1400, 900)
        self.setMinimumSize(1024, 700)

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

        self._page_indices: dict[str, int] = {}
        self._nav_labels = dict(NAV_ITEMS)
        self._build_pages()

        self.sidebar.section_selected.connect(self._on_section_selected)

        self.status_bar = self.statusBar()
        if self._had_unclean_previous_shutdown:
            self.status_bar.showMessage(
                "Ascend did not shut down cleanly last time - see Diagnostics for details."
            )
        else:
            self.status_bar.showMessage("Ready.")

    def _build_pages(self) -> None:
        for key, _label in NAV_ITEMS:
            if key == "dashboard":
                page = DashboardPage(self.db, self.secure_storage, self.task_manager)
                page.open_reports_requested.connect(lambda: self.sidebar.select_section("reports"))
            elif key == "characters":
                page = CharactersPage(self.db)
            elif key == "reports":
                page = ReportsPage(self.db, self.secure_storage, self.task_manager)
            elif key == "settings":
                page = SettingsPage(self.db, self.secure_storage, self.task_manager)
            elif key == "diagnostics":
                page = DiagnosticsPage(self.db, self.secure_storage)
            else:
                page = PlaceholderPage(
                    self._nav_labels[key], PLACEHOLDER_NOTES.get(key, "Coming in a later phase.")
                )
            index = self.stack.addWidget(page)
            self._page_indices[key] = index

    def _on_section_selected(self, key: str) -> None:
        index = self._page_indices.get(key)
        if index is not None:
            self.stack.setCurrentIndex(index)
        self.status_bar.showMessage(f"Viewing {self._nav_labels.get(key, key)}")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        # Guard against being invoked more than once (e.g. an explicit close()
        # followed by the test harness or window manager closing again) and
        # against the database having already been closed independently.
        if not getattr(self, "_shutdown_handled", False):
            self._shutdown_handled = True
            self.task_manager.cancel_all()
            self.task_manager.wait_for_done(3000)
            if self.db.is_open:
                SessionOperationRepository(self.db).complete(self._session_operation_id)
                self.db.close()
        super().closeEvent(event)
