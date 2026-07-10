"""First-run setup wizard shell.

Walks a new user through configuring Ascend without touching the command
line, source code, YAML, or JSON. Every step writes to the same
repositories/secure storage the rest of the app uses, so nothing here is
fake - it's just a guided path through real settings.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from ascend import metadata
from ascend.api.client import WCLClient
from ascend.api.url_parser import InvalidReportReferenceError, parse_report_reference
from ascend.data.database import (
    Database,
    default_app_data_root,
    load_bootstrap_config,
    save_bootstrap_config,
)
from ascend.data.repositories import SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.sync_service import sync_report_by_code
from ascend.ui.dialogs import CharacterDialog, show_error, show_info
from ascend.ui.widgets import BackgroundTaskPanel


class PlayerProfilePage(QWizardPage):
    def __init__(self, settings_repo: SettingsRepository):
        super().__init__()
        self.settings_repo = settings_repo
        self.setTitle("Your Profile")

        form = QFormLayout(self)
        self.display_name_edit = QLineEdit(self.settings_repo.get("player_display_name", ""))
        self.display_name_edit.setPlaceholderText("e.g. Aeloria, or your guild nickname")
        form.addRow("Your name:", self.display_name_edit)

        from PySide6.QtWidgets import QComboBox
        self.region_combo = QComboBox()
        self.region_combo.addItems(["US", "EU", "KR", "TW", "CN"])
        preferred = self.settings_repo.get("preferred_region", "US")
        if preferred in ["US", "EU", "KR", "TW", "CN"]:
            self.region_combo.setCurrentText(preferred)
        form.addRow("Your region:", self.region_combo)

        note = QLabel(
            "This is used to pre-fill character fields and personalise the app. "
            "You can change it any time in Settings."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        form.addRow("", note)

    def validatePage(self) -> bool:
        name = self.display_name_edit.text().strip()
        if name:
            self.settings_repo.set("player_display_name", name)
        self.settings_repo.set("preferred_region", self.region_combo.currentText())
        return True


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle(f"Welcome to {metadata.APP_NAME}")
        layout = QVBoxLayout(self)
        label = QLabel(
            f"<b>{metadata.APP_NAME}</b> - {metadata.APP_TAGLINE}<br><br>"
            "This short setup walks through connecting your Warcraft Logs account, "
            "adding characters, and configuring how Ascend scores your performance. "
            "You can change anything here later in Settings."
        )
        label.setWordWrap(True)
        layout.addWidget(label)


class LocalFirstPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Local-first, private by default")
        layout = QVBoxLayout(self)
        label = QLabel(
            "Ascend stores your Warcraft Logs data, analysis results, and settings on "
            "your own computer. Nothing is uploaded anywhere unless you explicitly export "
            "a report or post a summary to Discord yourself.\n\n"
            "Your Warcraft Logs client secret and Discord webhook are stored using Windows "
            "Credential Manager (or a clearly-flagged encrypted fallback) - never in plain "
            "text, never in the database."
        )
        label.setWordWrap(True)
        layout.addWidget(label)


class CredentialsPage(QWizardPage):
    def __init__(self, settings_repo: SettingsRepository, secure_storage: SecureStorage):
        super().__init__()
        self.settings_repo = settings_repo
        self.secure_storage = secure_storage
        self.setTitle("Warcraft Logs Credentials")

        form = QFormLayout(self)
        self.client_id_edit = QLineEdit(self.settings_repo.get("wcl_client_id", ""))
        form.addRow("Client ID:", self.client_id_edit)

        self.client_secret_edit = QLineEdit(self.secure_storage.get_client_secret() or "")
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Client Secret:", self.client_secret_edit)

        note = QLabel(
            "Create a client at warcraftlogs.com/api/clients/ if you don't have one yet."
        )
        note.setProperty("class", "muted")
        form.addRow("", note)

    def validatePage(self) -> bool:
        self.settings_repo.set("wcl_client_id", self.client_id_edit.text().strip())
        self.secure_storage.set_client_secret(self.client_secret_edit.text().strip() or None)
        return True


class TestConnectionPage(QWizardPage):
    def __init__(
        self,
        settings_repo: SettingsRepository,
        secure_storage: SecureStorage,
        task_manager: BackgroundTaskManager,
    ):
        super().__init__()
        self.settings_repo = settings_repo
        self.secure_storage = secure_storage
        self.task_manager = task_manager
        self.setTitle("Test Your Connection")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Click below to verify Ascend can authenticate with Warcraft Logs."))

        self.test_button = QPushButton("Test Warcraft Logs Connection")
        self.test_button.clicked.connect(self._on_test)
        layout.addWidget(self.test_button)

        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.setVisible(False)
        layout.addWidget(self.task_panel)

    def _on_test(self) -> None:
        client_id = self.settings_repo.get("wcl_client_id", "")
        client_secret = self.secure_storage.get_client_secret() or ""
        if not client_id or not client_secret:
            show_error(self, "Missing credentials", "Go back and enter your credentials first.")
            return

        def _run(progress_cb, _cancel_token):
            progress_cb(50, "Contacting Warcraft Logs...")
            client = WCLClient(client_id, client_secret)
            return client.test_connection()

        self.task_panel.start("Testing...")
        task = self.task_manager.submit(_run)
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_finished)
        task.signals.error.connect(lambda msg: show_error(self, "Connection failed", msg))

    def _on_finished(self, result) -> None:
        self.task_panel.finish("Done.")
        if result.ok:
            show_info(self, "Connected", result.message)
        else:
            show_error(self, "Connection failed", result.message)


class CharactersSetupPage(QWizardPage):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setTitle("Add Your Characters")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Add the characters you play to get started. "
            "Ascend uses character information to match you in imported Warcraft Logs reports.\n\n"
            "You can add more characters or edit them any time from the Characters page."
        ))

        self._char_list_layout = QVBoxLayout()
        layout.addLayout(self._char_list_layout)
        self._refresh_char_list(db)

        add_button = QPushButton("Add a Character")
        add_button.clicked.connect(self._on_add)
        layout.addWidget(add_button)
        layout.addStretch()

    def _refresh_char_list(self, db) -> None:
        from ascend.data.repositories import CharacterRepository
        while self._char_list_layout.count():
            item = self._char_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for character in CharacterRepository(db).list_all():
            label = QLabel(f"  • {character.display_name} ({character.character_class or 'Unknown class'}) — {character.server or ''} [{character.region or ''}]")
            self._char_list_layout.addWidget(label)

    def _on_add(self) -> None:
        from ascend.data.repositories import CharacterRepository, SettingsRepository

        preferred_region = SettingsRepository(self.db).get("preferred_region", "US")
        dialog = CharacterDialog(self, default_region=preferred_region)
        if dialog.exec():
            CharacterRepository(self.db).create(dialog.result_character())
            self._refresh_char_list(self.db)


class TierAndRankPage(QWizardPage):
    def __init__(self, settings_repo: SettingsRepository):
        super().__init__()
        self.settings_repo = settings_repo
        self.setTitle("Raid Context")

        from PySide6.QtWidgets import QComboBox
        from ascend.data.wow_data import WOW_RAID_TIERS

        form = QFormLayout(self)
        self.tier_combo = QComboBox()
        self.tier_combo.setEditable(True)
        self.tier_combo.addItems(WOW_RAID_TIERS)
        saved_tier = self.settings_repo.get("current_tier", "")
        if saved_tier in WOW_RAID_TIERS:
            self.tier_combo.setCurrentText(saved_tier)
        elif saved_tier:
            self.tier_combo.setCurrentText(saved_tier)
        form.addRow("Current Raid Tier:", self.tier_combo)

        self.rank_edit = QLineEdit(self.settings_repo.get("guild_us_rank", ""))
        self.rank_edit.setPlaceholderText("e.g. 42")
        form.addRow("Guild Rank:", self.rank_edit)

    def validatePage(self) -> bool:
        self.settings_repo.set("current_tier", self.tier_combo.currentText().strip())
        self.settings_repo.set("guild_us_rank", self.rank_edit.text().strip())
        return True


class ScoringPreferencesPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Scoring Preferences")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Ascend uses these default category weights (attendance 15, survival & first "
            "deaths 20, mechanic execution 20, damage & priority damage 15, consistency 10, "
            "learning speed 10, utility & defensives 5, preparation & consumables 5).\n\n"
            "You can fine-tune every weight, plus classification thresholds and minimum "
            "sample sizes, later in Settings."
        ))


class DiscordPage(QWizardPage):
    def __init__(self, secure_storage: SecureStorage, task_manager: BackgroundTaskManager):
        super().__init__()
        self.secure_storage = secure_storage
        self.task_manager = task_manager
        self.setTitle("Optional: Discord Webhook")

        form = QFormLayout(self)
        self.webhook_edit = QLineEdit(self.secure_storage.get_discord_webhook() or "")
        self.webhook_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.webhook_edit.setPlaceholderText("https://discord.com/api/webhooks/... (optional)")
        form.addRow("Webhook URL:", self.webhook_edit)

        note = QLabel("Weekly summary posting arrives in Phase 4. This just saves the webhook now.")
        note.setProperty("class", "muted")
        form.addRow("", note)

    def validatePage(self) -> bool:
        self.secure_storage.set_discord_webhook(self.webhook_edit.text().strip() or None)
        return True


class DataDirectoryPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Local Data Folder")
        layout = QVBoxLayout(self)

        app_root = default_app_data_root()
        config = load_bootstrap_config(app_root)
        self.data_dir_label = QLabel(config.get("data_dir", str(app_root)))
        layout.addWidget(QLabel("Ascend will store its database and logs here:"))
        layout.addWidget(self.data_dir_label)

        change_button = QPushButton("Change...")
        change_button.clicked.connect(self._on_change)
        layout.addWidget(change_button)

    def _on_change(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        chosen = QFileDialog.getExistingDirectory(self, "Choose data folder", self.data_dir_label.text())
        if not chosen:
            return
        app_root = default_app_data_root()
        config = load_bootstrap_config(app_root)
        config["data_dir"] = chosen
        save_bootstrap_config(app_root, config)
        self.data_dir_label.setText(chosen)
        show_info(self, "Restart required", "This takes effect the next time Ascend starts.")


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
        self.setMinimumSize(600, 420)
        # QWizard's native styles (Aero/Vista/Mac) paint their own banner/background
        # using OS chrome that ignores our application-wide dark stylesheet, which
        # can render text invisible. ClassicStyle is plain QWidget-based and respects it.
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setStyleSheet("QWizard, QWizardPage { background-color: #1e1f22; color: #e6e6e6; }")

        settings_repo = SettingsRepository(db)

        self.addPage(WelcomePage())
        self.addPage(PlayerProfilePage(settings_repo))
        self.addPage(LocalFirstPage())
        self.addPage(CredentialsPage(settings_repo, secure_storage))
        self.addPage(TestConnectionPage(settings_repo, secure_storage, task_manager))
        self.addPage(CharactersSetupPage(db))
        self.addPage(TierAndRankPage(settings_repo))
        self.addPage(ScoringPreferencesPage())
        self.addPage(DiscordPage(secure_storage, task_manager))
        self.addPage(DataDirectoryPage())
        self.addPage(FirstAnalysisPage(db, settings_repo, secure_storage, task_manager))
