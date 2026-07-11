"""Dashboard page - a thin state orchestrator, not a fixed layout.

Ascend has fundamentally different Dashboard compositions depending on how
much analyzed data exists, not one layout with values swapped for "--":

  NO_DATA              -> NoDataState (onboarding hero)
  IMPORTED_INCOMPLETE   -> ImportedIncompleteState (profile-is-building panel)
  ACTIVE                -> ActiveAnalyticsState (full analytics dashboard)

State is recomputed whenever a report finishes importing, whenever analysis
completes, and whenever the selected character changes (see _compute_state).
Real per-character filtering of reports isn't possible yet - Report rows
don't carry a character_id until character detection lands - so today the
computed state is the same regardless of which character is selected; the
hook is wired now so that becomes true automatically once that mapping
exists, without another Dashboard rewrite.

Development-phase information (this being a Phase 1 build, what's coming in
Phase 2/3) deliberately does not appear anywhere in this file - see
About/Roadmap/Diagnostics instead.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from ascend.data.database import Database
from ascend.data.repositories import AnalysisRunRepository, ReportRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.ui.components import ToastOverlay
from ascend.ui.dashboard_states import ActiveAnalyticsState, ImportedIncompleteState, NoDataState
from ascend.ui.top_context_bar import TopContextBar

NO_DATA = "no_data"
IMPORTED_INCOMPLETE = "imported_incomplete"
ACTIVE = "active"


class DashboardPage(QWidget):
    open_reports_requested = Signal()
    settings_requested = Signal()

    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        is_demo: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.secure_storage = secure_storage
        self.task_manager = task_manager
        self.is_demo = is_demo
        self.reports_repo = ReportRepository(db)
        self.analysis_repo = AnalysisRunRepository(db)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(20, 14, 20, 0)
        outer_layout.setSpacing(10)

        self.context_bar = TopContextBar(db)
        self.context_bar.set_title(
            "Dashboard", "Progression overview and actionable performance intelligence"
        )
        self.context_bar.settings_requested.connect(self.settings_requested.emit)
        self.context_bar.character_changed.connect(self._on_character_changed)
        outer_layout.addWidget(self.context_bar)

        separator = QFrame()
        separator.setObjectName("separator")
        outer_layout.addWidget(separator)

        self.stack = QStackedWidget()
        outer_layout.addWidget(self.stack, stretch=1)

        self._state_indices: dict[str, int] = {}
        self._state_widgets: dict[str, QWidget] = {}
        self._current_state: str | None = None

        # Anchored to this page so toasts sit top-right, below the context
        # bar, and never overlap primary panel content.
        self.toast_overlay = ToastOverlay(self, top_offset=self.context_bar.height() + 24)

        self._build_states()
        self._apply_state(self._compute_state())

    # -- State computation ---------------------------------------------------

    def _compute_state(self) -> str:
        if self.is_demo:
            return ACTIVE
        reports = self.reports_repo.list_all()
        if not reports:
            return NO_DATA
        has_analysis = any(
            report.id is not None and self.analysis_repo.latest_for_report(report.id) is not None
            for report in reports
        )
        return ACTIVE if has_analysis else IMPORTED_INCOMPLETE

    def _on_character_changed(self, _character) -> None:
        # Reports aren't yet linked to a specific character (see module
        # docstring), so this recomputes the same overall state today - but
        # it means switching characters already re-evaluates state correctly
        # once that per-character link exists.
        self._apply_state(self._compute_state())

    def _apply_state(self, state: str) -> None:
        if state == self._current_state:
            return
        self._current_state = state
        self.stack.setCurrentIndex(self._state_indices[state])

    def refresh_state(self) -> None:
        """Re-derive and (if needed) switch composition - called after an
        import completes or analysis finishes."""
        self._apply_state(self._compute_state())
        widget = self._state_widgets.get(self._current_state)
        if hasattr(widget, "refresh"):
            widget.refresh()

    # -- Building the three state widgets -------------------------------------

    def _build_states(self) -> None:
        no_data = NoDataState(self.db, self.open_reports_requested.emit)
        self._register_state(NO_DATA, no_data)

        imported = ImportedIncompleteState(self.db, self.open_reports_requested.emit)
        self._register_state(IMPORTED_INCOMPLETE, imported)

        active = ActiveAnalyticsState(self.db, self.open_reports_requested)
        if self.is_demo:
            active.apply_demo_data()
        self._register_state(ACTIVE, active)

    def _register_state(self, key: str, widget: QWidget) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(widget)
        index = self.stack.addWidget(scroll)
        self._state_indices[key] = index
        self._state_widgets[key] = widget

