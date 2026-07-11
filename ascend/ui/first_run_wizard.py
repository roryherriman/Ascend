"""First-run setup wizard — 5 steps from zero to first report.

Walks a new user through Ascend's one-time configuration without touching
the command line or config files. All writes go to the same repositories
and secure storage that the rest of the app uses, so nothing here is fake.

Step 1 — Welcome + privacy summary
Step 2 — Profile + Warcraft Logs credentials
Step 3 — Add characters
Step 4 — Raid tier (auto-detected from WCL zones)
Step 5 — Optional first report import
"""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from ascend import metadata
from ascend.api.client import WCLClient
from ascend.api.url_parser import InvalidReportReferenceError, parse_report_reference
from ascend.data.database import Database
from ascend.data.repositories import SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.data.wow_data import WOW_RAID_TIERS
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.sync_service import sync_report_by_code
from ascend.ui.dialogs import CharacterDialog, show_error, show_info
from ascend.ui.widgets import BackgroundTaskPanel


# ---------------------------------------------------------------------------
# Step 1 — Welcome (merged with local-first privacy note)
# ---------------------------------------------------------------------------

class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle(f"Welcome to {metadata.APP_NAME}")
        layout = QVBoxLayout(self)

        intro = QLabel(
            f"<b>{metadata.APP_NAME}</b> — {metadata.APP_TAGLINE}<br><br>"
            "This short setup connects your Warcraft Logs account, adds your characters, "
            "and detects your current raid tier. You can change anything later in Settings."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addSpacing(12)

        privacy = QLabel(
            "<b>Your data stays on your machine.</b> Ascend stores analysis results "
            "and settings locally — nothing is uploaded unless you explicitly export "
            "or post to Discord yourself. Secrets (WCL client secret, Discord webhook) "
            "are stored via Windows Credential Manager, never in plain text or the database."
        )
        privacy.setWordWrap(True)
        privacy.setProperty("class", "muted")
        layout.addWidget(privacy)


# ---------------------------------------------------------------------------
# Step 2 — Profile + credentials (merged)
# ---------------------------------------------------------------------------

class CredentialsPage(QWizardPage):
    def __init__(self, settings_repo: SettingsRepository, secure_storage: SecureStorage):
        super().__init__()
        self.settings_repo = settings_repo
        self.secure_storage = secure_storage
        self.setTitle("Your Profile & Warcraft Logs Credentials")

        form = QFormLayout(self)

        self.display_name_edit = QLineEdit(self.settings_repo.get("player_display_name", ""))
        self.display_name_edit.setPlaceholderText("e.g. Aeloria, or your guild nickname")
        form.addRow("Your name:", self.display_name_edit)

        self.region_combo = QComboBox()
        self.region_combo.addItems(["US", "EU", "KR", "TW", "CN"])
        preferred = self.settings_repo.get("preferred_region", "US")
        if preferred in ["US", "EU", "KR", "TW", "CN"]:
            self.region_combo.setCurrentText(preferred)
        form.addRow("Region:", self.region_combo)

        form.addRow(QLabel(""))  # spacer row

        self.client_id_edit = QLineEdit(self.settings_repo.get("wcl_client_id", ""))
        self.client_id_edit.setPlaceholderText("Paste your WCL OAuth2 client ID")
        form.addRow("WCL Client ID:", self.client_id_edit)

        self.client_secret_edit = QLineEdit(self.secure_storage.get_client_secret() or "")
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_secret_edit.setPlaceholderText("Paste your WCL OAuth2 client secret")
        form.addRow("WCL Client Secret:", self.client_secret_edit)

        note = QLabel("Create a client at warcraftlogs.com/api/clients/ if you don't have one yet.")
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        form.addRow("", note)

    def validatePage(self) -> bool:
        name = self.display_name_edit.text().strip()
        if name:
            self.settings_repo.set("player_display_name", name)
        self.settings_repo.set("preferred_region", self.region_combo.currentText())
        self.settings_repo.set("wcl_client_id", self.client_id_edit.text().strip())
        self.secure_storage.set_client_secret(self.client_secret_edit.text().strip() or None)
        return True


# ---------------------------------------------------------------------------
# Step 3 — Characters (unchanged)
# ---------------------------------------------------------------------------

class CharactersSetupPage(QWizardPage):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setTitle("Your Characters")

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Add the characters you play. Ascend matches you automatically in imported "
            "Warcraft Logs reports — class and spec are detected on first import."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(240)
        inner = QWidget()
        self._char_list_layout = QVBoxLayout(inner)
        self._char_list_layout.setSpacing(6)
        self._char_list_layout.setContentsMargins(0, 4, 0, 4)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._empty_label = QLabel("No characters added yet.")
        self._empty_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self._empty_label)

        add_button = QPushButton("+ Add a Character")
        add_button.clicked.connect(self._on_add)
        layout.addWidget(add_button)
        layout.addStretch()

        self._refresh_char_list()

    def _refresh_char_list(self) -> None:
        from ascend.data.repositories import CharacterRepository
        from ascend.ui.class_icons import class_icon_pixmap, class_color
        from ascend.theme import PALETTE

        while self._char_list_layout.count():
            item = self._char_list_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()

        characters = CharacterRepository(self.db).list_all()
        self._empty_label.setVisible(not characters)

        for char in characters:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: {PALETTE.bg_card}; border: 1px solid {PALETTE.border}; border-radius: 5px; }}"
            )
            row = QHBoxLayout(card)
            row.setContentsMargins(10, 6, 10, 6)
            row.setSpacing(10)

            icon_lbl = QLabel()
            pm = class_icon_pixmap(char.character_class, 24)
            if not pm.isNull():
                icon_lbl.setPixmap(pm)
            icon_lbl.setFixedSize(24, 24)
            row.addWidget(icon_lbl)

            info = QVBoxLayout()
            info.setSpacing(1)
            name_lbl = QLabel(char.display_name)
            name_lbl.setStyleSheet("font-weight: 600; font-size: 12px;")
            info.addWidget(name_lbl)

            if char.character_class:
                color = class_color(char.character_class)
                cls_lbl = QLabel(char.character_class)
                cls_lbl.setStyleSheet(f"font-size: 11px; color: {color};")
            else:
                cls_lbl = QLabel(f"{char.character_name} · {char.server}-{char.region}")
                cls_lbl.setStyleSheet(f"font-size: 11px; color: {PALETTE.text_muted};")
            info.addWidget(cls_lbl)
            row.addLayout(info, stretch=1)

            edit_btn = QPushButton("Edit")
            edit_btn.setFixedWidth(48)
            edit_btn.clicked.connect(lambda checked=False, c=char: self._on_edit(c))
            row.addWidget(edit_btn)

            remove_btn = QPushButton("Remove")
            remove_btn.setFixedWidth(60)
            remove_btn.setStyleSheet("color: #e05555;")
            remove_btn.clicked.connect(lambda checked=False, c=char: self._on_remove(c))
            row.addWidget(remove_btn)

            self._char_list_layout.addWidget(card)

    def _on_add(self) -> None:
        from ascend.data.repositories import CharacterRepository, SettingsRepository
        preferred_region = SettingsRepository(self.db).get("preferred_region", "US")
        dialog = CharacterDialog(self, default_region=preferred_region)
        if dialog.exec():
            CharacterRepository(self.db).create(dialog.result_character())
            self._refresh_char_list()

    def _on_edit(self, character) -> None:
        from ascend.data.repositories import CharacterRepository
        dialog = CharacterDialog(self, character=character)
        if dialog.exec():
            updated = dialog.result_character()
            updated.id = character.id
            CharacterRepository(self.db).update(updated)
            self._refresh_char_list()

    def _on_remove(self, character) -> None:
        from ascend.data.repositories import CharacterRepository
        CharacterRepository(self.db).delete(character.id)
        self._refresh_char_list()


# ---------------------------------------------------------------------------
# Internal signal bridge for tier auto-detect (must be QObject)
# ---------------------------------------------------------------------------

class _TierSignals(QObject):
    detected = Signal(str)   # emits zone name when found
    failed = Signal()        # emits when zones fetch fails / no result


# ---------------------------------------------------------------------------
# Step 4 — Raid tier (auto-detected from WCL; user can override)
# ---------------------------------------------------------------------------

class TierPage(QWizardPage):
    """Auto-detects the current raid tier from WCL worldData.zones on entry.

    When WCL credentials are available (saved by CredentialsPage), a background
    thread fetches all zones and picks the most recently added non-frozen tier.
    The combo is pre-filled with the detected value; the user can override it.
    If detection fails (no credentials, network error), the combo defaults to
    the first entry in WOW_RAID_TIERS.
    """

    def __init__(self, settings_repo: SettingsRepository, secure_storage: SecureStorage):
        super().__init__()
        self.settings_repo = settings_repo
        self.secure_storage = secure_storage
        self.setTitle("Current Raid Tier")
        self._signals = _TierSignals()
        self._signals.detected.connect(self._on_detected)
        self._signals.failed.connect(self._on_failed)

        form = QFormLayout(self)

        self.tier_combo = QComboBox()
        self.tier_combo.setEditable(True)
        self.tier_combo.addItems(WOW_RAID_TIERS)
        saved_tier = self.settings_repo.get("current_tier", "")
        if saved_tier:
            self.tier_combo.setCurrentText(saved_tier)
        form.addRow("Current Raid Tier:", self.tier_combo)

        self._status_label = QLabel("Enter your Warcraft Logs credentials on the previous step to auto-detect.")
        self._status_label.setProperty("class", "muted")
        self._status_label.setWordWrap(True)
        form.addRow("", self._status_label)

    def initializePage(self) -> None:
        client_id = self.settings_repo.get("wcl_client_id", "")
        client_secret = self.secure_storage.get_client_secret() or ""
        if not client_id or not client_secret:
            self._status_label.setText("No WCL credentials — select your tier manually.")
            return

        self._status_label.setText("Detecting current tier from Warcraft Logs…")

        signals = self._signals

        def _fetch():
            try:
                client = WCLClient(client_id, client_secret)
                zones = client.fetch_zones()
                # Pick the most recently added active zone: highest id, not frozen
                active = [z for z in zones if not z.get("frozen")]
                if not active:
                    active = zones  # fallback: any zone
                if not active:
                    signals.failed.emit()
                    return
                best = max(active, key=lambda z: z.get("id") or 0)
                signals.detected.emit(best["name"])
            except Exception:  # noqa: BLE001
                signals.failed.emit()

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_detected(self, name: str) -> None:
        self._status_label.setText(f"Detected: {name}")
        self.tier_combo.setCurrentText(name)

    def _on_failed(self) -> None:
        self._status_label.setText("Could not detect — select your tier manually.")

    def validatePage(self) -> bool:
        self.settings_repo.set("current_tier", self.tier_combo.currentText().strip())
        return True


# ---------------------------------------------------------------------------
# Step 5 — Optional first report import (unchanged)
# ---------------------------------------------------------------------------

class FirstAnalysisPage(QWizardPage):
    def __init__(
        self,
        db: Database,
        settings_repo: SettingsRepository,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
    ):
        super().__init__()
        self.db = db
        self.settings_repo = settings_repo
        self.secure_storage = secure_storage
        self.task_manager = task_manager
        self.setTitle("Analyze Your First Report (optional)")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Paste a Warcraft Logs report URL or code to retrieve it now, or skip this and "
            "do it later from the Dashboard."
        ))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste a Warcraft Logs report URL or report code...")
        layout.addWidget(self.url_edit)

        self.fetch_button = QPushButton("Fetch Report Data Now")
        self.fetch_button.clicked.connect(self._on_fetch)
        layout.addWidget(self.fetch_button)

        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.setVisible(False)
        layout.addWidget(self.task_panel)

    def _on_fetch(self) -> None:
        raw = self.url_edit.text().strip()
        try:
            parsed = parse_report_reference(raw)
        except InvalidReportReferenceError as exc:
            show_error(self, "Invalid report URL or code", str(exc))
            return

        client_id = self.settings_repo.get("wcl_client_id", "")
        client_secret = self.secure_storage.get_client_secret() or ""
        if not client_id or not client_secret:
            show_error(self, "Missing credentials", "Go back and enter your Warcraft Logs credentials first.")
            return

        client = WCLClient(client_id, client_secret)
        self.task_panel.start(f"Fetching report {parsed.report_code}...")
        task = self.task_manager.submit(sync_report_by_code, self.db, client, parsed.report_code)
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(lambda report: self._on_finished(report))
        task.signals.error.connect(lambda msg: self._on_error(msg))

    def _on_finished(self, report) -> None:
        if report is None:
            self.task_panel.reset()
            return
        self.task_panel.finish(f"Retrieved {report.report_code}.")
        show_info(self, "Report retrieved", "Open the Reports page after finishing setup to view it.")

    def _on_error(self, message: str) -> None:
        self.task_panel.reset()
        if "ReportCodeNotFoundError" in message:
            message = message.split(":", 1)[-1].strip()
        show_error(self, "Could not retrieve report", message)


# ---------------------------------------------------------------------------
# Wizard shell — 5 pages
# ---------------------------------------------------------------------------

class FirstRunWizard(QWizard):
    def __init__(
        self,
        db: Database,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"{metadata.APP_NAME} Setup")
        self.setMinimumSize(600, 440)
        # ClassicStyle uses plain QWidget painting that respects our dark stylesheet.
        # The native Aero/Vista/Mac styles paint their own chrome and ignore it.
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setStyleSheet("QWizard, QWizardPage { background-color: #1e1f22; color: #e6e6e6; }")

        settings_repo = SettingsRepository(db)

        self.addPage(WelcomePage())
        self.addPage(CredentialsPage(settings_repo, secure_storage))
        self.addPage(CharactersSetupPage(db))
        self.addPage(TierPage(settings_repo, secure_storage))
        self.addPage(FirstAnalysisPage(db, settings_repo, secure_storage, task_manager))


# ---------------------------------------------------------------------------
# Legacy page classes kept for import compatibility (not added to wizard)
# ---------------------------------------------------------------------------

class PlayerProfilePage(QWizardPage):
    """Merged into CredentialsPage in PR 4. Kept for test imports only."""
    def __init__(self, settings_repo: SettingsRepository):
        super().__init__()
        self.settings_repo = settings_repo
        self.setTitle("Your Profile")
        form = QFormLayout(self)
        self.display_name_edit = QLineEdit(self.settings_repo.get("player_display_name", ""))
        form.addRow("Your name:", self.display_name_edit)
        self.region_combo = QComboBox()
        self.region_combo.addItems(["US", "EU", "KR", "TW", "CN"])
        form.addRow("Your region:", self.region_combo)


class LocalFirstPage(QWizardPage):
    """Merged into WelcomePage in PR 4. Kept for import compatibility."""
    def __init__(self):
        super().__init__()
        self.setTitle("Local-first, private by default")


class TierAndRankPage(QWizardPage):
    """Replaced by TierPage in PR 4. Kept for import compatibility.

    guild_rank / guild_us_rank removed — auto-detected via Blizzard API in future PRs.
    """
    def __init__(self, settings_repo: SettingsRepository):
        super().__init__()
        self.settings_repo = settings_repo
        self.setTitle("Raid Context")
        form = QFormLayout(self)
        self.tier_combo = QComboBox()
        self.tier_combo.setEditable(True)
        self.tier_combo.addItems(WOW_RAID_TIERS)
        saved_tier = self.settings_repo.get("current_tier", "")
        if saved_tier:
            self.tier_combo.setCurrentText(saved_tier)
        form.addRow("Current Raid Tier:", self.tier_combo)

    def validatePage(self) -> bool:
        self.settings_repo.set("current_tier", self.tier_combo.currentText().strip())
        return True
