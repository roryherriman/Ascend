"""Settings page - credentials, scoring configuration, cache/network, and data locations.

Secrets (Warcraft Logs client secret, Discord webhook URL) are stored via
SecureStorage (Windows Credential Manager, or an encrypted/obfuscated local
fallback with a visible warning) and are never written to SQLite.
"""
from __future__ import annotations

import requests
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ascend.api.client import WCLClient
from ascend.data.database import (
    Database,
    default_app_data_root,
    load_bootstrap_config,
    save_bootstrap_config,
)
from ascend.data.repositories import CharacterRepository, SettingsRepository
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.services.guild_icon_service import (
    clear_guild_icon,
    get_or_create_guild_icon,
    reset_to_automatic_guild_icon,
    set_custom_guild_icon,
)
from ascend.ui.dialogs import show_error, show_info
from ascend.ui.widgets import BackgroundTaskPanel

DEFAULT_SCORING_WEIGHTS = {
    "attendance": 15,
    "survival_and_first_deaths": 20,
    "mechanic_execution": 20,
    "damage_and_priority_damage": 15,
    "consistency": 10,
    "learning_speed": 10,
    "utility_and_defensives": 5,
    "preparation_and_consumables": 5,
}

DEFAULT_THRESHOLDS = {
    "standout": 90,
    "strong": 80,
    "above_average": 70,
    "average": 55,
    "below_average": 40,
}


def _run_connection_test(progress_cb, cancel_token, client_id: str, client_secret: str, timeout: float):
    progress_cb(30, "Requesting an access token...")
    client = WCLClient(client_id, client_secret, timeout_seconds=timeout)
    progress_cb(70, "Querying the Warcraft Logs API...")
    return client.test_connection()


def _run_discord_test(progress_cb, cancel_token, webhook_url: str):
    progress_cb(40, "Sending test message to Discord...")
    try:
        response = requests.post(
            webhook_url,
            json={"content": "Ascend: test message - your webhook is configured correctly."},
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        return False, str(exc)
    return response.status_code in (200, 204), response.status_code


class SettingsPage(QWidget):
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
        self.settings_repo = SettingsRepository(db)
        self._active_task = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        outer.addWidget(title)

        self.security_banner = QLabel()
        self.security_banner.setWordWrap(True)
        outer.addWidget(self.security_banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        content = QWidget()
        form_layout = QVBoxLayout(content)

        form_layout.addWidget(self._build_credentials_group())
        form_layout.addWidget(self._build_guild_group())
        form_layout.addWidget(self._build_scoring_weights_group())
        form_layout.addWidget(self._build_thresholds_group())
        form_layout.addWidget(self._build_sample_size_group())
        form_layout.addWidget(self._build_network_group())
        form_layout.addWidget(self._build_discord_group())
        form_layout.addWidget(self._build_theme_group())
        form_layout.addWidget(self._build_data_location_group())
        form_layout.addWidget(self._build_demo_mode_group())
        form_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        self.task_panel = BackgroundTaskPanel()
        self.task_panel.cancel_button.setVisible(False)
        outer.addWidget(self.task_panel)

        save_button = QPushButton("Save Settings")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._on_save)
        outer.addWidget(save_button)

        self._load_values()

    # -- groups ---------------------------------------------------------

    def _build_credentials_group(self) -> QGroupBox:
        group = QGroupBox("Warcraft Logs Credentials")
        form = QFormLayout(group)

        self.client_id_edit = QLineEdit()
        form.addRow("Client ID:", self.client_id_edit)

        self.client_secret_edit = QLineEdit()
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Client Secret:", self.client_secret_edit)

        test_button = QPushButton("Test Warcraft Logs Connection")
        test_button.clicked.connect(self._on_test_connection)
        form.addRow("", test_button)

        return group

    def _build_guild_group(self) -> QGroupBox:
        group = QGroupBox("Guild && Tier")
        form = QFormLayout(group)
        self.guild_name_edit = QLineEdit()
        self.guild_name_edit.setPlaceholderText("e.g. Ascend Raiders")
        form.addRow("Guild Name:", self.guild_name_edit)

        self.current_tier_edit = QLineEdit()
        self.current_tier_edit.setPlaceholderText("e.g. Liberation of Undermine")
        form.addRow("Current Raid Tier:", self.current_tier_edit)

        self.guild_rank_edit = QLineEdit()
        self.guild_rank_edit.setPlaceholderText("e.g. Officer, Raider, Rank 3")
        form.addRow("Guild US Rank:", self.guild_rank_edit)

        icon_row = QWidget()
        icon_row_layout = _horizontal(
            self._build_button("Refresh Guild Icon", self._on_refresh_guild_icon),
            self._build_button("Choose Custom Image...", self._on_choose_custom_guild_icon),
            self._build_button("Clear Cached Icon", self._on_clear_guild_icon),
            self._build_button("Reset to Automatic", self._on_reset_guild_icon),
        )
        icon_row.setLayout(icon_row_layout)
        form.addRow("Guild Icon:", icon_row)

        note = QLabel(
            "Warcraft Logs does not expose a guild emblem, so Ascend generates a badge "
            "from the guild name unless you choose a custom local image (never uploaded)."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        form.addRow("", note)

        self.progression_weight_spin = QDoubleSpinBox()
        self.progression_weight_spin.setRange(0.0, 10.0)
        self.progression_weight_spin.setSingleStep(0.1)
        form.addRow("Progression Weighting:", self.progression_weight_spin)

        self.farm_weight_spin = QDoubleSpinBox()
        self.farm_weight_spin.setRange(0.0, 10.0)
        self.farm_weight_spin.setSingleStep(0.1)
        form.addRow("Farm Weighting:", self.farm_weight_spin)

        return group

    def _build_scoring_weights_group(self) -> QGroupBox:
        group = QGroupBox("Scoring Weights (0-100 score composition)")
        form = QFormLayout(group)
        self.scoring_weight_spins: dict[str, QSpinBox] = {}
        labels = {
            "attendance": "Attendance",
            "survival_and_first_deaths": "Survival & First Deaths",
            "mechanic_execution": "Mechanic Execution",
            "damage_and_priority_damage": "Damage & Priority Damage",
            "consistency": "Consistency",
            "learning_speed": "Learning Speed",
            "utility_and_defensives": "Utility & Defensives",
            "preparation_and_consumables": "Preparation & Consumables",
        }
        for key, label in labels.items():
            spin = QSpinBox()
            spin.setRange(0, 100)
            self.scoring_weight_spins[key] = spin
            form.addRow(f"{label}:", spin)
        return group

    def _build_thresholds_group(self) -> QGroupBox:
        group = QGroupBox("Classification Thresholds (minimum score)")
        form = QFormLayout(group)
        self.threshold_spins: dict[str, QSpinBox] = {}
        labels = {
            "standout": "Standout",
            "strong": "Strong",
            "above_average": "Above Average",
            "average": "Average",
            "below_average": "Below Average",
        }
        for key, label in labels.items():
            spin = QSpinBox()
            spin.setRange(0, 100)
            self.threshold_spins[key] = spin
            form.addRow(f"{label}:", spin)
        return group

    def _build_sample_size_group(self) -> QGroupBox:
        group = QGroupBox("Minimum Sample Sizes")
        form = QFormLayout(group)
        self.min_pulls_spin = QSpinBox()
        self.min_pulls_spin.setRange(1, 500)
        form.addRow("Minimum pulls for high confidence:", self.min_pulls_spin)

        self.min_deaths_spin = QSpinBox()
        self.min_deaths_spin.setRange(1, 500)
        form.addRow("Minimum deaths for high confidence:", self.min_deaths_spin)
        return group

    def _build_network_group(self) -> QGroupBox:
        group = QGroupBox("Cache && Network")
        form = QFormLayout(group)
        self.cache_duration_spin = QSpinBox()
        self.cache_duration_spin.setRange(1, 1440)
        self.cache_duration_spin.setSuffix(" minutes")
        form.addRow("Cache duration:", self.cache_duration_spin)

        self.api_timeout_spin = QSpinBox()
        self.api_timeout_spin.setRange(1, 120)
        self.api_timeout_spin.setSuffix(" seconds")
        form.addRow("API request timeout:", self.api_timeout_spin)
        return group

    def _build_discord_group(self) -> QGroupBox:
        group = QGroupBox("Discord Output")
        form = QFormLayout(group)
        self.discord_webhook_edit = QLineEdit()
        self.discord_webhook_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.discord_webhook_edit.setPlaceholderText("https://discord.com/api/webhooks/...")
        form.addRow("Discord Webhook URL:", self.discord_webhook_edit)

        test_button = QPushButton("Test Discord Webhook")
        test_button.clicked.connect(self._on_test_discord)
        form.addRow("", test_button)

        note = QLabel("Automatic weekly summary posting is available in Phase 4.")
        note.setProperty("class", "muted")
        form.addRow("", note)
        return group

    def _build_theme_group(self) -> QGroupBox:
        group = QGroupBox("Appearance")
        form = QFormLayout(group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark (default)"])
        form.addRow("Theme:", self.theme_combo)
        return group

    def _build_data_location_group(self) -> QGroupBox:
        group = QGroupBox("Data && Export Locations")
        form = QFormLayout(group)

        self.data_dir_edit = QLineEdit()
        self.data_dir_edit.setReadOnly(True)
        change_data_button = QPushButton("Change...")
        change_data_button.clicked.connect(self._on_change_data_dir)
        data_row = QWidget()
        data_row_layout = _horizontal(self.data_dir_edit, change_data_button)
        data_row.setLayout(data_row_layout)
        form.addRow("Data folder:", data_row)

        self.export_dir_edit = QLineEdit()
        self.export_dir_edit.setReadOnly(True)
        change_export_button = QPushButton("Change...")
        change_export_button.clicked.connect(self._on_change_export_dir)
        export_row = QWidget()
        export_row_layout = _horizontal(self.export_dir_edit, change_export_button)
        export_row.setLayout(export_row_layout)
        form.addRow("Export folder:", export_row)

        return group

    def _build_demo_mode_group(self) -> QGroupBox:
        group = QGroupBox("Demo Mode")
        form = QFormLayout(group)

        from PySide6.QtWidgets import QCheckBox

        self.demo_mode_checkbox = QCheckBox("Use Demo Mode (sanitized sample data)")
        form.addRow("", self.demo_mode_checkbox)

        note = QLabel(
            "Demo Mode uses a completely separate local database seeded with sanitized "
            "sample data, so it never mixes with your real data. Toggling this requires "
            "restarting Ascend."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        form.addRow("", note)
        return group

    # -- load / save ------------------------------------------------------

    def _load_values(self) -> None:
        self.client_id_edit.setText(self.settings_repo.get("wcl_client_id", ""))
        self.client_secret_edit.setText(self.secure_storage.get_client_secret() or "")
        self.guild_name_edit.setText(self.settings_repo.get("guild_name", ""))
        self.current_tier_edit.setText(self.settings_repo.get("current_tier", ""))
        self.guild_rank_edit.setText(self.settings_repo.get("guild_us_rank", ""))
        self.progression_weight_spin.setValue(self.settings_repo.get("progression_weight_multiplier", 1.0))
        self.farm_weight_spin.setValue(self.settings_repo.get("farm_weight_multiplier", 0.4))

        weights = self.settings_repo.get("scoring_weights", DEFAULT_SCORING_WEIGHTS)
        for key, spin in self.scoring_weight_spins.items():
            spin.setValue(weights.get(key, DEFAULT_SCORING_WEIGHTS[key]))

        thresholds = self.settings_repo.get("classification_thresholds", DEFAULT_THRESHOLDS)
        for key, spin in self.threshold_spins.items():
            spin.setValue(thresholds.get(key, DEFAULT_THRESHOLDS[key]))

        self.min_pulls_spin.setValue(self.settings_repo.get("min_sample_pulls", 10))
        self.min_deaths_spin.setValue(self.settings_repo.get("min_sample_deaths", 5))
        self.cache_duration_spin.setValue(self.settings_repo.get("cache_duration_minutes", 60))
        self.api_timeout_spin.setValue(self.settings_repo.get("api_timeout_seconds", 15))
        self.discord_webhook_edit.setText(self.secure_storage.get_discord_webhook() or "")

        app_root = default_app_data_root()
        config = load_bootstrap_config(app_root)
        self.data_dir_edit.setText(config.get("data_dir", str(app_root)))
        self.export_dir_edit.setText(config.get("export_dir", str(app_root / "exports")))
        self.demo_mode_checkbox.setChecked(bool(config.get("demo_mode", False)))

        self._refresh_security_banner()

    def _refresh_security_banner(self) -> None:
        status = self.secure_storage.status()
        if not status["using_fallback"]:
            self.security_banner.setText(f"Secrets are stored in: {status['backend']}.")
            self.security_banner.setStyleSheet("color: #4caf7d;")
        elif status["insecure"]:
            self.security_banner.setText(
                "WARNING: Windows Credential Manager and the encrypted DPAPI fallback are both "
                f"unavailable ({status['reason']}). Secrets are stored using weak local "
                "obfuscation only, NOT strong encryption. Consider fixing your keyring/pywin32 "
                "installation."
            )
            self.security_banner.setStyleSheet("color: #e0545c; font-weight: 600;")
        else:
            self.security_banner.setText(
                f"NOTE: Windows Credential Manager is unavailable ({status['reason']}). "
                "Secrets are stored in an encrypted local fallback tied to your Windows login "
                "(DPAPI) instead."
            )
            self.security_banner.setStyleSheet("color: #e0a83e; font-weight: 600;")

    def _on_save(self) -> None:
        self.settings_repo.set("wcl_client_id", self.client_id_edit.text().strip())
        self.secure_storage.set_client_secret(self.client_secret_edit.text().strip() or None)
        self.settings_repo.set("guild_name", self.guild_name_edit.text().strip())
        self.settings_repo.set("current_tier", self.current_tier_edit.text().strip())
        self.settings_repo.set("guild_us_rank", self.guild_rank_edit.text().strip())
        self.settings_repo.set("progression_weight_multiplier", self.progression_weight_spin.value())
        self.settings_repo.set("farm_weight_multiplier", self.farm_weight_spin.value())

        self.settings_repo.set(
            "scoring_weights", {k: s.value() for k, s in self.scoring_weight_spins.items()}
        )
        self.settings_repo.set(
            "classification_thresholds", {k: s.value() for k, s in self.threshold_spins.items()}
        )
        self.settings_repo.set("min_sample_pulls", self.min_pulls_spin.value())
        self.settings_repo.set("min_sample_deaths", self.min_deaths_spin.value())
        self.settings_repo.set("cache_duration_minutes", self.cache_duration_spin.value())
        self.settings_repo.set("api_timeout_seconds", self.api_timeout_spin.value())
        self.secure_storage.set_discord_webhook(self.discord_webhook_edit.text().strip() or None)
        self.settings_repo.set("theme_preference", "dark")

        app_root = default_app_data_root()
        config = load_bootstrap_config(app_root)
        demo_mode_changed = bool(config.get("demo_mode", False)) != self.demo_mode_checkbox.isChecked()
        config["demo_mode"] = self.demo_mode_checkbox.isChecked()
        save_bootstrap_config(app_root, config)

        self._refresh_security_banner()
        if demo_mode_changed:
            show_info(
                self, "Restart required",
                "Demo Mode will take effect after you restart Ascend.",
            )
        else:
            show_info(self, "Settings saved", "Your settings have been saved.")

    def _on_change_data_dir(self) -> None:
        show_info(
            self, "Restart required",
            "Changing the data folder requires restarting the application after the change, "
            "so your existing database can be found in its current location until you migrate it.",
        )
        chosen = QFileDialog.getExistingDirectory(self, "Choose data folder", self.data_dir_edit.text())
        if not chosen:
            return
        app_root = default_app_data_root()
        config = load_bootstrap_config(app_root)
        config["data_dir"] = chosen
        save_bootstrap_config(app_root, config)
        self.data_dir_edit.setText(chosen)

    def _on_change_export_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose export folder", self.export_dir_edit.text())
        if not chosen:
            return
        app_root = default_app_data_root()
        config = load_bootstrap_config(app_root)
        config["export_dir"] = chosen
        save_bootstrap_config(app_root, config)
        self.export_dir_edit.setText(chosen)

    # -- connection tests --------------------------------------------------

    def _on_test_connection(self) -> None:
        client_id = self.client_id_edit.text().strip()
        client_secret = self.client_secret_edit.text().strip()
        if not client_id or not client_secret:
            show_error(self, "Missing credentials", "Enter both a client ID and client secret first.")
            return

        self.task_panel.start("Testing Warcraft Logs connection...")
        task = self.task_manager.submit(
            _run_connection_test, client_id, client_secret, float(self.api_timeout_spin.value())
        )
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_connection_test_finished)
        task.signals.error.connect(lambda msg: self._on_connection_test_failed(msg))

    def _on_connection_test_finished(self, result) -> None:
        self.task_panel.finish("Connection test complete.")
        if result.ok:
            details = ""
            if result.limit_per_hour is not None:
                details = (
                    f"\n\nRate limit: {result.points_spent_this_hour:.1f} / "
                    f"{result.limit_per_hour} points used this hour."
                )
            show_info(self, "Connection successful", result.message + details)
        else:
            show_error(self, "Connection failed", result.message)

    def _on_connection_test_failed(self, message: str) -> None:
        self.task_panel.reset()
        show_error(self, "Connection test failed", message)

    def _on_test_discord(self) -> None:
        webhook_url = self.discord_webhook_edit.text().strip()
        if not webhook_url:
            show_error(self, "Missing webhook", "Enter a Discord webhook URL first.")
            return

        self.task_panel.start("Testing Discord webhook...")
        task = self.task_manager.submit(_run_discord_test, webhook_url)
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_discord_test_finished)
        task.signals.error.connect(lambda msg: self._on_discord_test_failed(msg))

    def _on_discord_test_finished(self, result) -> None:
        self.task_panel.finish("Discord test complete.")
        ok, detail = result
        if ok:
            show_info(self, "Discord webhook works", "A test message was posted successfully.")
        else:
            show_error(self, "Discord webhook failed", f"Discord responded with: {detail}")

    def _on_discord_test_failed(self, message: str) -> None:
        self.task_panel.reset()
        show_error(self, "Discord test failed", message)

    # -- guild icon management -------------------------------------------

    @staticmethod
    def _build_button(label: str, handler) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(handler)
        return button

    def _guild_region_realm(self) -> tuple[str, str]:
        characters = CharacterRepository(self.db).list_all(enabled_only=True)
        primary = next((c for c in characters if c.character_role == "primary"), None)
        primary = primary or (characters[0] if characters else None)
        if primary is None:
            return "", ""
        return primary.region, primary.server

    def _current_guild_identity(self) -> tuple[str, str, str] | None:
        guild_name = self.guild_name_edit.text().strip()
        if not guild_name:
            show_error(self, "No guild name set", "Enter a guild name above first.")
            return None
        region, realm = self._guild_region_realm()
        return region, realm, guild_name

    def _on_refresh_guild_icon(self) -> None:
        identity = self._current_guild_identity()
        if identity is None:
            return
        get_or_create_guild_icon(self.db, *identity)
        show_info(self, "Guild icon refreshed", "The guild icon cache has been refreshed.")

    def _on_choose_custom_guild_icon(self) -> None:
        identity = self._current_guild_identity()
        if identity is None:
            return
        path, _filter = QFileDialog.getOpenFileName(
            self, "Choose a local guild image", "", "Images (*.png *.jpg *.jpeg *.bmp *.svg)"
        )
        if not path:
            return
        set_custom_guild_icon(self.db, *identity, image_path=path)
        show_info(
            self, "Custom guild icon set",
            "This image stays local and is never uploaded or committed automatically.",
        )

    def _on_clear_guild_icon(self) -> None:
        identity = self._current_guild_identity()
        if identity is None:
            return
        clear_guild_icon(self.db, *identity)
        show_info(self, "Guild icon cleared", "The cached guild icon has been removed.")

    def _on_reset_guild_icon(self) -> None:
        identity = self._current_guild_identity()
        if identity is None:
            return
        reset_to_automatic_guild_icon(self.db, *identity)
        show_info(self, "Guild icon reset", "Ascend will generate a fresh automatic badge.")


def _horizontal(*widgets: QWidget):
    from PySide6.QtWidgets import QHBoxLayout

    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return layout
