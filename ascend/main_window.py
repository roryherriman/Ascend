"""Main application window: sidebar navigation + stacked pages."""
from __future__ import annotations

from PySide6.QtCore import QSettings
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

# key -> (development phase, note, planned capabilities, icon name)
PLACEHOLDER_META: dict[str, dict] = {
    "raid_night": dict(
        phase=2,
        note="The Raid Night Summary will bring together everything Ascend knows about one raid night.",
        planned=[
            "Overview: pulls, kills, duration, score, classification",
            "Participation and survival breakdown",
            "Pull-by-pull table with evidence",
            "Roster comparison for that night",
        ],
        icon="raid_night",
    ),
    "encounter": dict(
        phase=2,
        note="Encounter Analysis will let you drill into one boss across pulls and raid nights.",
        planned=[
            "Pull-by-pull results with filters",
            "Progression pull-range comparisons (1-10, 11-25, ...)",
            "Priority-target damage",
            "Mechanic-rule results",
        ],
        icon="encounter",
    ),
    "deaths": dict(
        phase=3,
        note="Death Review will show the evidence behind every death - never labeling one avoidable without a basis.",
        planned=[
            "Death timeline and evidence",
            "Manual classification (avoidable / assignment failure / unknown)",
            "Defensive and consumable timeline",
            "Repeated-cause tracking by ability",
        ],
        icon="deaths",
    ),
    "roster": dict(
        phase=2,
        note="Roster Comparison will show how you stack up against the players you actually raid with.",
        planned=[
            "Same-spec and same-class comparison",
            "Ranged DPS and full roster percentile",
            "Sortable tables with percentile bars",
        ],
        icon="roster",
    ),
    "trends": dict(
        phase=3,
        note="Learning and Trends will track how quickly you correct mistakes across a tier.",
        planned=[
            "Pull-range comparisons",
            "Death-rate trends",
            "Mechanic correction speed",
            "DPS consistency",
            "Defensive usage trends",
        ],
        icon="trends",
    ),
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
    "encounter_progression": dict(
        phase=3,
        note="Encounter Progression will chart your climb on one boss from first pull to farm.",
        planned=[
            "First pull to first kill timeline",
            "Repeated-failure milestones",
            "Reclear performance",
        ],
        icon="encounter_progression",
    ),
    "insights": dict(
        phase=2,
        note="Insights will surface evidence-based strengths, warnings, and improvement areas.",
        planned=[
            "Strength and improvement-area insights",
            "Every insight links back to its evidence",
            "Confidence and sample size shown alongside each insight",
        ],
        icon="insights",
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
    "data_quality": dict(
        phase=2,
        note="Data Quality will make sure Ascend never silently ignores missing or uncertain data.",
        planned=[
            "Sync success/failure tracking",
            "Small-sample warnings",
            "Character-identity confidence",
        ],
        icon="data_quality",
    ),
    "export": dict(
        phase=3,
        note="Export and Discord will let you share a Raid Night Summary outside Ascend.",
        planned=[
            "HTML, CSV, and JSON export",
            "Discord weekly summary (Phase 4)",
            "PDF export (Phase 4)",
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

        self._page_indices: dict[str, int] = {}
        self._nav_labels = dict(NAV_ITEMS)
        self._build_pages()

        self.status_bar = self.statusBar()

        self.sidebar.section_selected.connect(self._on_section_selected)
        self._restore_last_page()

        if self._had_unclean_previous_shutdown:
            self.status_bar.showMessage(
                "Ascend did not shut down cleanly last time - see Diagnostics for details."
            )
        else:
            self.status_bar.showMessage("Ready.")

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
                meta = PLACEHOLDER_META.get(key, {})
                page = PlaceholderPage(
                    self._nav_labels[key],
                    meta.get("note", "Coming in a later phase."),
                    phase=meta.get("phase"),
                    planned=meta.get("planned"),
                    icon_name=meta.get("icon"),
                )
            index = self.stack.addWidget(page)
            self._page_indices[key] = index

    def _on_section_selected(self, key: str) -> None:
        index = self._page_indices.get(key)
        if index is not None:
            self.stack.setCurrentIndex(index)
        self.status_bar.showMessage(f"Viewing {self._nav_labels.get(key, key)}")
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
