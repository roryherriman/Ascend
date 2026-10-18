"""Settings page — credentials, raid context, guild, scoring, cache, data management.

Secrets (WCL client secret, Discord webhook URL) are stored via SecureStorage
(Windows Credential Manager, or a clearly-flagged encrypted fallback) and are
never written to SQLite.
"""
from __future__ import annotations

from pathlib import Path

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
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


def _run_connection_test(progress_cb, cancel_token, client_id: str, client_secret: str, timeout: float):
    progress_cb(30, "Requesting an access token...")
    client = WCLClient(client_id, client_secret, timeout_seconds=timeout)
    progress_cb(70, "Querying the Warcraft Logs API...")
    return client.test_connection()


def _run_discord_summary(progress_cb, cancel_token, db, webhook_url: str):
    from ascend.services.discord_service import post_weekly_summary
    progress_cb(40, "Building weekly summary...")
    return post_weekly_summary(db, webhook_url)


def _run_discord_test(progress_cb, cancel_token, webhook_url: str):
    from ascend.services.discord_service import (
        INVALID_WEBHOOK_MESSAGE,
        is_discord_webhook_url,
        redact_webhook,
    )
    if not is_discord_webhook_url(webhook_url):
        return False, INVALID_WEBHOOK_MESSAGE
    progress_cb(40, "Sending test message to Discord...")
    try:
        response = requests.post(
            webhook_url,
            json={"content": "Ascend: test message - your webhook is configured correctly."},
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        return False, redact_webhook(str(exc), webhook_url)
    return response.status_code in (200, 204), response.status_code


def _run_zone_refresh(progress_cb, cancel_token, client_id: str, client_secret: str, timeout: float):
    progress_cb(20, "Connecting to Warcraft Logs...")
    client = WCLClient(client_id, client_secret, timeout_seconds=timeout)
    progress_cb(60, "Fetching raid zones...")
    return client.fetch_zones()


def _run_guild_verify(progress_cb, cancel_token, client_id: str, client_secret: str,
                      timeout: float, name: str, server_slug: str, region: str):
    progress_cb(30, "Connecting to Warcraft Logs...")
    client = WCLClient(client_id, client_secret, timeout_seconds=timeout)
    progress_cb(70, f"Looking up {name}...")
    return client.fetch_guild(name, server_slug, region)


def _run_bnet_guild_crest(
    progress_cb, cancel_token,
    db, region: str, realm: str, guild_name: str,
    bnet_client_id: str, bnet_client_secret: str, timeout: float,
):
    from ascend.services.guild_icon_service import try_fetch_blizzard_guild_crest
    progress_cb(20, "Authenticating with Battle.net...")
    result = try_fetch_blizzard_guild_crest(
        db, region, realm, guild_name, bnet_client_id, bnet_client_secret, timeout=timeout
    )
    progress_cb(100, "Done.")
    return result


class SettingsPage(QWidget):
    restart_wizard_requested = Signal()

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
        self._cached_zones: list[dict] = []
        self._cached_at: str | None = None

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

        form_layout.addWidget(self._build_profile_group())
        form_layout.addWidget(self._build_credentials_group())
        form_layout.addWidget(self._build_bnet_credentials_group())
        form_layout.addWidget(self._build_raid_context_group())
        form_layout.addWidget(self._build_guild_group())
        form_layout.addWidget(self._build_combat_log_group())
        form_layout.addWidget(self._build_network_group())
        form_layout.addWidget(self._build_discord_group())
        form_layout.addWidget(self._build_theme_group())
        form_layout.addWidget(self._build_data_location_group())
        form_layout.addWidget(self._build_data_management_group())
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

    def _build_profile_group(self) -> QGroupBox:
        group = QGroupBox("Player Profile")
        form = QFormLayout(group)
        self.player_display_name_edit = QLineEdit()
        self.player_display_name_edit.setPlaceholderText("e.g. your in-game name or guild nickname")
        form.addRow("Your name:", self.player_display_name_edit)
        self.preferred_region_combo = QComboBox()
        self.preferred_region_combo.addItems(["US", "EU", "KR", "TW", "CN"])
        form.addRow("Preferred region:", self.preferred_region_combo)
        return group

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

    def _build_bnet_credentials_group(self) -> QGroupBox:
        group = QGroupBox("Battle.net Credentials (optional — for guild crests)")
        form = QFormLayout(group)

        self.bnet_client_id_edit = QLineEdit()
        self.bnet_client_id_edit.setPlaceholderText("Battle.net client ID")
        form.addRow("Client ID:", self.bnet_client_id_edit)

        self.bnet_client_secret_edit = QLineEdit()
        self.bnet_client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.bnet_client_secret_edit.setPlaceholderText("Battle.net client secret")
        form.addRow("Client Secret:", self.bnet_client_secret_edit)

        note = QLabel(
            "Register a client at develop.battle.net to enable guild crest fetching. "
            "The secret is stored in Windows Credential Manager, never in plain text."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        form.addRow("", note)

        return group

    def _build_raid_context_group(self) -> QGroupBox:
        """Raid tier dropdown with Refresh from Warcraft Logs."""
        group = QGroupBox("Raid Context")
        layout = QVBoxLayout(group)

        tier_row = QHBoxLayout()
        self.current_tier_combo = QComboBox()
        self.current_tier_combo.setEditable(True)
        self.current_tier_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.current_tier_combo.setMinimumWidth(300)

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QCompleter
        self._tier_completer = QCompleter([], self.current_tier_combo)
        self._tier_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._tier_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._tier_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.current_tier_combo.setCompleter(self._tier_completer)

        tier_row.addWidget(self.current_tier_combo, stretch=1)

        self._tier_refresh_btn = QPushButton("Refresh")
        self._tier_refresh_btn.setToolTip(
            "Fetch the current raid tier list from Warcraft Logs.\n"
            "Requires saved Warcraft Logs credentials."
        )
        self._tier_refresh_btn.clicked.connect(self._on_refresh_tiers)
        tier_row.addWidget(self._tier_refresh_btn)
        layout.addLayout(tier_row)

        self._tier_sync_label = QLabel()
        self._tier_sync_label.setProperty("class", "muted")
        self._tier_sync_label.setWordWrap(True)
        layout.addWidget(self._tier_sync_label)

        return group

    def _build_guild_group(self) -> QGroupBox:
        """Full guild search, verification, and sync panel."""
        group = QGroupBox("Guild")
        layout = QVBoxLayout(group)

        search_form = QFormLayout()

        self.guild_search_region_combo = QComboBox()
        self.guild_search_region_combo.addItems(["US", "EU", "KR", "TW", "CN"])
        search_form.addRow("Region:", self.guild_search_region_combo)

        from ascend.data.wow_data import WOW_US_REALMS, realms_for_region
        self.guild_realm_edit = QLineEdit()
        self.guild_realm_edit.setPlaceholderText("Start typing realm name…")
        from PySide6.QtWidgets import QCompleter as _QCompleter
        from PySide6.QtCore import Qt as _Qt
        self._realm_completer = _QCompleter(WOW_US_REALMS, self.guild_realm_edit)
        self._realm_completer.setCaseSensitivity(_Qt.CaseSensitivity.CaseInsensitive)
        self._realm_completer.setFilterMode(_Qt.MatchFlag.MatchContains)
        self.guild_realm_edit.setCompleter(self._realm_completer)
        self.guild_search_region_combo.currentTextChanged.connect(self._update_realm_completer)
        search_form.addRow("Realm:", self.guild_realm_edit)

        self.guild_name_edit = QLineEdit()
        self.guild_name_edit.setPlaceholderText("Guild name (case-insensitive)")
        search_form.addRow("Guild Name:", self.guild_name_edit)

        layout.addLayout(search_form)

        btn_row = QHBoxLayout()
        self._guild_verify_btn = QPushButton("Verify Guild")
        self._guild_verify_btn.clicked.connect(self._on_verify_guild)
        btn_row.addWidget(self._guild_verify_btn)

        self._guild_sync_btn = QPushButton("Sync")
        self._guild_sync_btn.setEnabled(False)
        self._guild_sync_btn.setToolTip("Sync requires a verified guild.")
        self._guild_sync_btn.clicked.connect(self._on_sync_guild)
        btn_row.addWidget(self._guild_sync_btn)

        self._guild_clear_btn = QPushButton("Clear")
        self._guild_clear_btn.clicked.connect(self._on_clear_guild)
        btn_row.addWidget(self._guild_clear_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._guild_status_label = QLabel("Not Configured")
        self._guild_status_label.setWordWrap(True)
        layout.addWidget(self._guild_status_label)

        self._guild_detail_label = QLabel()
        self._guild_detail_label.setProperty("class", "muted")
        self._guild_detail_label.setWordWrap(True)
        layout.addWidget(self._guild_detail_label)

        icon_form = QFormLayout()
        icon_row = QWidget()
        self._bnet_crest_btn = QPushButton("Fetch Blizzard Crest")
        self._bnet_crest_btn.setToolTip(
            "Download the guild emblem from the Blizzard Game Data API.\n"
            "Requires Battle.net credentials saved above."
        )
        self._bnet_crest_btn.clicked.connect(self._on_fetch_blizzard_crest)
        icon_row_layout = _horizontal(
            self._build_button("Refresh Guild Icon", self._on_refresh_guild_icon),
            self._bnet_crest_btn,
            self._build_button("Choose Custom Image...", self._on_choose_custom_guild_icon),
            self._build_button("Clear Cached Icon", self._on_clear_guild_icon),
            self._build_button("Reset to Automatic", self._on_reset_guild_icon),
        )
        icon_row.setLayout(icon_row_layout)
        icon_form.addRow("Guild Icon:", icon_row)
        note = QLabel(
            "Ascend can fetch your guild's emblem from the Blizzard Game Data API when "
            "Battle.net credentials are configured above. Without credentials, a badge is "
            "generated from the guild initials. Custom local images are never uploaded."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        icon_form.addRow("", note)

        layout.addLayout(icon_form)
        return group

    def _update_realm_completer(self, region: str) -> None:
        from ascend.data.wow_data import realms_for_region
        from PySide6.QtWidgets import QCompleter as _QCompleter
        from PySide6.QtCore import Qt as _Qt
        realms = realms_for_region(region)
        self._realm_completer = _QCompleter(realms, self.guild_realm_edit)
        self._realm_completer.setCaseSensitivity(_Qt.CaseSensitivity.CaseInsensitive)
        self._realm_completer.setFilterMode(_Qt.MatchFlag.MatchContains)
        self.guild_realm_edit.setCompleter(self._realm_completer)

    def _build_combat_log_group(self) -> QGroupBox:
        group = QGroupBox("WoW Combat Log")
        layout = QVBoxLayout(group)

        self._combat_log_status_label = QLabel("Scanning…")
        self._combat_log_status_label.setWordWrap(True)
        layout.addWidget(self._combat_log_status_label)

        self._combat_log_path_label = QLabel()
        self._combat_log_path_label.setProperty("class", "muted")
        self._combat_log_path_label.setWordWrap(True)
        self._combat_log_path_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._combat_log_path_label)

        btn_row = QHBoxLayout()
        rescan_btn = QPushButton("Rescan")
        rescan_btn.setToolTip("Scan again for WoWCombatLog.txt in common installation paths.")
        rescan_btn.clicked.connect(self._on_rescan_combat_log)
        btn_row.addWidget(rescan_btn)

        open_wcl_btn = QPushButton("Open Warcraft Logs Upload")
        open_wcl_btn.setToolTip(
            "Opens warcraftlogs.com/upload in your browser so you can upload your combat log. "
            "Once uploaded, paste the report code into the Reports page."
        )
        open_wcl_btn.clicked.connect(self._on_open_wcl_upload)
        btn_row.addWidget(open_wcl_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        upload_note = QLabel(
            "Ascend reads report data from Warcraft Logs — it does not parse raw combat logs directly. "
            "To analyze a raid night: upload WoWCombatLog.txt to warcraftlogs.com, then paste "
            "the resulting report code into the Reports page."
        )
        upload_note.setProperty("class", "muted")
        upload_note.setWordWrap(True)
        upload_note.setStyleSheet("font-size: 11px;")
        layout.addWidget(upload_note)

        self._refresh_combat_log_status()
        return group

    def _refresh_combat_log_status(self) -> None:
        from ascend.services.combat_log import detect_combat_logs
        logs = detect_combat_logs()
        if not logs:
            self._combat_log_status_label.setText("No WoW combat log detected.")
            self._combat_log_path_label.setText(
                "Searched common installation paths (C:/Program Files (x86)/World of Warcraft, etc.)."
            )
            return
        primary = logs[0]
        flavor_label = {
            "_retail_": "Retail",
            "_classic_era_": "Classic Era",
            "_classic_": "Classic / Cataclysm",
        }.get(primary.flavor, primary.flavor)
        size_text = f"{primary.size_mb():.1f} MB" if primary.size_bytes >= 1024 else f"{primary.size_bytes} B"
        self._combat_log_status_label.setText(
            f"Combat log detected ({flavor_label}) — {size_text}, last modified {primary.last_modified_str()}"
        )
        self._combat_log_path_label.setText(str(primary.path))
        if len(logs) > 1:
            others = ", ".join(
                f"{l.flavor}" for l in logs[1:]
            )
            self._combat_log_path_label.setText(
                str(primary.path) + f"\n(also found: {others})"
            )

    def _on_rescan_combat_log(self) -> None:
        self._combat_log_status_label.setText("Scanning…")
        self._combat_log_path_label.setText("")
        self._refresh_combat_log_status()

    def _on_open_wcl_upload(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl("https://www.warcraftlogs.com/upload/select-client"))

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

        summary_button = QPushButton("Post Weekly Summary Now")
        summary_button.setToolTip(
            "Post a summary of the last 7 days of raid data to the configured Discord webhook."
        )
        summary_button.clicked.connect(self._on_post_discord_summary)
        form.addRow("", summary_button)

        note = QLabel(
            "Weekly summary includes raid nights, total pulls, kills, and encounter list "
            "from the last 7 days. Post it any time using the button above."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
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
        data_row.setLayout(_horizontal(self.data_dir_edit, change_data_button))
        form.addRow("Data folder:", data_row)

        self.export_dir_edit = QLineEdit()
        self.export_dir_edit.setReadOnly(True)
        change_export_button = QPushButton("Change...")
        change_export_button.clicked.connect(self._on_change_export_dir)
        export_row = QWidget()
        export_row.setLayout(_horizontal(self.export_dir_edit, change_export_button))
        form.addRow("Export folder:", export_row)

        return group

    def _build_data_management_group(self) -> QGroupBox:
        group = QGroupBox("Data Management")
        layout = QVBoxLayout(group)

        open_button = QPushButton("Open Data Folder")
        open_button.clicked.connect(self._on_open_data_folder)
        layout.addWidget(open_button)

        self.db_size_label = QLabel()
        self.db_size_label.setProperty("class", "muted")
        layout.addWidget(self.db_size_label)

        note = QLabel(
            "Your data is stored locally and never uploaded. "
            "Use File > Back Up Ascend Data to save a timestamped copy."
        )
        note.setProperty("class", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        restart_btn = QPushButton("Restart Setup Wizard")
        restart_btn.setToolTip(
            "Reopen initial configuration to review credentials, characters, "
            "raid tier, and guild. Your imported reports and analysis history "
            "will not be deleted."
        )
        restart_btn.clicked.connect(self._on_restart_wizard)
        layout.addWidget(restart_btn)

        reset_btn = QPushButton("Reset Ascend")
        reset_btn.setToolTip(
            "Remove all local profile data, characters, reports, analysis history, "
            "and settings. This cannot be undone."
        )
        reset_btn.setStyleSheet("color: #e05555; font-weight: 600;")
        reset_btn.clicked.connect(self._on_reset_ascend)
        layout.addWidget(reset_btn)

        return group

    def _on_open_data_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        folder = default_app_data_root()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _build_demo_mode_group(self) -> QGroupBox:
        group = QGroupBox("Demo Mode")
        form = QFormLayout(group)

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

    def _populate_tier_combo(self, zones: list[dict], cached_at: str | None, is_cache: bool) -> None:
        from ascend.services.raid_tier_service import format_cached_at, zone_display_name
        self._cached_zones = zones
        self._cached_at = cached_at

        saved_tier = self.settings_repo.get("current_tier", "")
        self.current_tier_combo.blockSignals(True)
        self.current_tier_combo.clear()
        names = [zone_display_name(z) for z in zones]
        self.current_tier_combo.addItems(names)
        from PySide6.QtWidgets import QCompleter as _QC
        from PySide6.QtCore import Qt as _Qt
        self._tier_completer = _QC(names, self.current_tier_combo)
        self._tier_completer.setCaseSensitivity(_Qt.CaseSensitivity.CaseInsensitive)
        self._tier_completer.setFilterMode(_Qt.MatchFlag.MatchContains)
        self._tier_completer.setCompletionMode(_QC.CompletionMode.PopupCompletion)
        self.current_tier_combo.setCompleter(self._tier_completer)

        if saved_tier and saved_tier in names:
            self.current_tier_combo.setCurrentText(saved_tier)
        elif names:
            self.current_tier_combo.setCurrentIndex(0)
        self.current_tier_combo.blockSignals(False)

        source = "Warcraft Logs (cached)" if is_cache else "Warcraft Logs static list (click Refresh)"
        sync_text = format_cached_at(cached_at) if is_cache and cached_at else \
            "Static tier list — click Refresh to load current tiers from Warcraft Logs"
        self._tier_sync_label.setText(f"Data source: {source}\n{sync_text}")

    def _load_values(self) -> None:
        from ascend.services.raid_tier_service import get_zones_for_display
        from ascend.services.guild_service import get_guild_summary

        self.player_display_name_edit.setText(self.settings_repo.get("player_display_name", ""))
        preferred_region = self.settings_repo.get("preferred_region", "US")
        if preferred_region in ["US", "EU", "KR", "TW", "CN"]:
            self.preferred_region_combo.setCurrentText(preferred_region)
        self.client_id_edit.setText(self.settings_repo.get("wcl_client_id", ""))
        self.client_secret_edit.setText(self.secure_storage.get_client_secret() or "")
        self.bnet_client_id_edit.setText(self.settings_repo.get("bnet_client_id", ""))
        self.bnet_client_secret_edit.setText(self.secure_storage.get_bnet_client_secret() or "")

        zones, cached_at, is_cache = get_zones_for_display(self.db)
        self._populate_tier_combo(zones, cached_at, is_cache)

        guild = get_guild_summary(self.settings_repo)
        self.guild_name_edit.setText(guild["name"])
        self.guild_realm_edit.setText(guild["realm"])
        region_val = (guild["region"] or "").upper()
        if region_val in ["US", "EU", "KR", "TW", "CN"]:
            self.guild_search_region_combo.setCurrentText(region_val)
        self._refresh_guild_status_display(guild)

        self.cache_duration_spin.setValue(self.settings_repo.get("cache_duration_minutes", 60))
        self.api_timeout_spin.setValue(self.settings_repo.get("api_timeout_seconds", 15))
        self.discord_webhook_edit.setText(self.secure_storage.get_discord_webhook() or "")

        app_root = default_app_data_root()
        config = load_bootstrap_config(app_root)
        self.data_dir_edit.setText(config.get("data_dir", str(app_root)))
        self.export_dir_edit.setText(config.get("export_dir", str(app_root / "exports")))
        self.demo_mode_checkbox.setChecked(bool(config.get("demo_mode", False)))

        db_path = Path(config.get("data_dir", str(app_root))) / (
            "ascend_demo.db" if config.get("demo_mode") else "ascend.db"
        )
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            self.db_size_label.setText(f"Database: {size_kb:.1f} KB  ({db_path.name})")
        else:
            self.db_size_label.setText("Database: not yet created")

        self._refresh_security_banner()

    def _refresh_guild_status_display(self, guild: dict | None = None) -> None:
        from ascend.services.guild_service import get_guild_summary
        if guild is None:
            guild = get_guild_summary(self.settings_repo)

        if not guild["name"]:
            self._guild_status_label.setText("Status: Not Configured")
            self._guild_detail_label.setText("")
            self._guild_sync_btn.setEnabled(False)
            return

        if guild["verified"]:
            self._guild_status_label.setText(
                f"Status: Verified  ·  {guild['name']} — {guild['realm']} [{guild['region'].upper()}]"
                + (f"  ·  {guild['faction']}" if guild["faction"] else "")
                + (f"  ·  WCL ID: {guild['wcl_id']}" if guild["wcl_id"] else "")
            )
            self._guild_sync_btn.setEnabled(True)
            sync_ts = guild["last_sync_at"] or ""
            if sync_ts:
                try:
                    from datetime import datetime, timezone
                    dt = datetime.fromisoformat(sync_ts.replace("Z", "+00:00")).astimezone()
                    sync_ts = dt.strftime("Last synchronized: %B %-d, %Y at %-I:%M %p")
                except (ValueError, AttributeError):
                    pass
            self._guild_detail_label.setText(sync_ts)
        else:
            self._guild_status_label.setText(
                f"Status: Unverified  ·  {guild['name']} (not yet confirmed with Warcraft Logs)"
            )
            self._guild_sync_btn.setEnabled(False)
            self._guild_detail_label.setText("")

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
        self.settings_repo.set("player_display_name", self.player_display_name_edit.text().strip())
        self.settings_repo.set("preferred_region", self.preferred_region_combo.currentText())
        self.settings_repo.set("wcl_client_id", self.client_id_edit.text().strip())
        self.secure_storage.set_client_secret(self.client_secret_edit.text().strip() or None)
        self.settings_repo.set("bnet_client_id", self.bnet_client_id_edit.text().strip())
        self.secure_storage.set_bnet_client_secret(self.bnet_client_secret_edit.text().strip() or None)

        tier_name = self.current_tier_combo.currentText().strip()
        self.settings_repo.set("current_tier", tier_name)
        matching = [z for z in self._cached_zones if z.get("name") == tier_name]
        if matching and matching[0].get("id") is not None:
            self.settings_repo.set("current_tier_zone_id", matching[0]["id"])

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

    # -- raid tier refresh ------------------------------------------------

    def _on_refresh_tiers(self) -> None:
        client_id = self.client_id_edit.text().strip() or self.settings_repo.get("wcl_client_id", "")
        client_secret = (
            self.client_secret_edit.text().strip() or self.secure_storage.get_client_secret() or ""
        )
        if not client_id or not client_secret:
            show_error(
                self, "Credentials required",
                "Enter Warcraft Logs credentials (Client ID and Secret) above, then click Refresh.",
            )
            return

        self._tier_refresh_btn.setText("Refreshing…")
        self._tier_refresh_btn.setEnabled(False)
        timeout = float(self.api_timeout_spin.value())

        self.task_panel.start("Fetching raid tiers from Warcraft Logs...")
        task = self.task_manager.submit(_run_zone_refresh, client_id, client_secret, timeout)
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_tiers_refreshed)
        task.signals.error.connect(self._on_tiers_refresh_failed)

    def _on_tiers_refreshed(self, raw_zones: list) -> None:
        from ascend.services.raid_tier_service import save_zones_to_cache, sort_zones, format_cached_at
        from datetime import datetime, timezone

        self._tier_refresh_btn.setText("Refresh")
        self._tier_refresh_btn.setEnabled(True)
        self.task_panel.finish("Raid tiers updated.")

        sorted_zones = sort_zones(raw_zones)
        save_zones_to_cache(self.db, sorted_zones)
        now = datetime.now(timezone.utc).isoformat()
        self._populate_tier_combo(sorted_zones, now, is_cache=True)

    def _on_tiers_refresh_failed(self, message: str) -> None:
        self._tier_refresh_btn.setText("Retry")
        self._tier_refresh_btn.setEnabled(True)
        self.task_panel.reset()
        show_error(
            self, "Refresh failed",
            f"Could not fetch raid tiers from Warcraft Logs.\n\n{message}\n\n"
            "The previous list is still shown.",
        )

    # -- guild verification -----------------------------------------------

    def _on_verify_guild(self) -> None:
        name = self.guild_name_edit.text().strip()
        realm = self.guild_realm_edit.text().strip()
        region = self.guild_search_region_combo.currentText().strip()

        if not name:
            show_error(self, "Guild name required", "Enter a guild name to search.")
            return
        if not realm:
            show_error(self, "Realm required", "Enter a realm name to search.")
            return

        from ascend.services.guild_service import realm_to_slug
        server_slug = realm_to_slug(realm)
        region_lower = region.lower()

        client_id = self.client_id_edit.text().strip() or self.settings_repo.get("wcl_client_id", "")
        client_secret = (
            self.client_secret_edit.text().strip() or self.secure_storage.get_client_secret() or ""
        )
        if not client_id or not client_secret:
            show_error(
                self, "Credentials required",
                "Enter Warcraft Logs credentials before verifying a guild.",
            )
            return

        self._guild_verify_btn.setText("Verifying…")
        self._guild_verify_btn.setEnabled(False)
        self._guild_status_label.setText("Status: Verifying…")
        timeout = float(self.api_timeout_spin.value())

        self.task_panel.start(f"Looking up {name} on {realm} [{region}]...")
        task = self.task_manager.submit(
            _run_guild_verify, client_id, client_secret, timeout,
            name, server_slug, region_lower,
        )
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_guild_verified)
        task.signals.error.connect(self._on_guild_verify_failed)

    def _on_guild_verified(self, guild: dict | None) -> None:
        from ascend.services.guild_service import save_verified_guild, clear_guild

        self._guild_verify_btn.setText("Verify Guild")
        self._guild_verify_btn.setEnabled(True)
        self.task_panel.finish("Guild lookup complete.")

        if not guild:
            self._guild_status_label.setText(
                "Status: Guild Not Found\n\n"
                "Ascend could not verify this guild using the selected region, realm, and name.\n"
                "Check the spelling and realm, then try again."
            )
            self._guild_sync_btn.setEnabled(False)
            return

        save_verified_guild(self.settings_repo, guild)
        self.guild_name_edit.setText(guild.get("name", ""))
        self.guild_realm_edit.setText(guild.get("server_name", ""))
        region_slug = (guild.get("region_slug") or "").upper()
        if region_slug in ["US", "EU", "KR", "TW", "CN"]:
            self.guild_search_region_combo.setCurrentText(region_slug)
        self._refresh_guild_status_display()

    def _on_guild_verify_failed(self, message: str) -> None:
        self._guild_verify_btn.setText("Verify Guild")
        self._guild_verify_btn.setEnabled(True)
        self.task_panel.reset()
        self._guild_status_label.setText("Status: Verification Failed")
        show_error(
            self, "Guild verification failed",
            f"Warcraft Logs returned an error:\n\n{message}\n\nCheck your credentials and try again.",
        )

    def _on_sync_guild(self) -> None:
        from ascend.services.guild_service import get_guild_summary, save_verified_guild
        guild = get_guild_summary(self.settings_repo)
        if not guild["verified"] or not guild["wcl_id"]:
            show_error(self, "No verified guild", "Verify a guild before syncing.")
            return

        client_id = self.client_id_edit.text().strip() or self.settings_repo.get("wcl_client_id", "")
        client_secret = (
            self.client_secret_edit.text().strip() or self.secure_storage.get_client_secret() or ""
        )
        if not client_id or not client_secret:
            show_error(self, "Credentials required", "Enter Warcraft Logs credentials to sync.")
            return

        name = guild["name"]
        realm_slug = guild["realm_slug"] or guild["realm"]
        region = guild["region"]
        timeout = float(self.api_timeout_spin.value())

        self._guild_sync_btn.setText("Syncing…")
        self._guild_sync_btn.setEnabled(False)
        self.task_panel.start(f"Syncing {name}...")
        task = self.task_manager.submit(
            _run_guild_verify, client_id, client_secret, timeout,
            name, realm_slug, region,
        )
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_guild_synced)
        task.signals.error.connect(self._on_guild_sync_failed)

    def _on_guild_synced(self, guild: dict | None) -> None:
        from ascend.services.guild_service import save_verified_guild
        self._guild_sync_btn.setText("Sync")
        self._guild_sync_btn.setEnabled(True)
        self.task_panel.finish("Guild synced.")

        if guild:
            save_verified_guild(self.settings_repo, guild)
            self._refresh_guild_status_display()
        else:
            self._guild_status_label.setText("Status: Sync — guild not found at current coordinates")

    def _on_guild_sync_failed(self, message: str) -> None:
        self._guild_sync_btn.setText("Retry Sync")
        self._guild_sync_btn.setEnabled(True)
        self.task_panel.reset()
        show_error(
            self, "Sync failed",
            f"Could not sync guild data:\n\n{message}\n\nPrevious data is preserved.",
        )

    def _on_clear_guild(self) -> None:
        from ascend.services.guild_service import clear_guild
        from PySide6.QtWidgets import QMessageBox
        name = self.guild_name_edit.text().strip() or "this guild"
        reply = QMessageBox.question(
            self, "Clear Guild",
            f"Remove the active guild configuration for {name}?\n\n"
            "Your imported reports and analysis history will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        clear_guild(self.settings_repo)
        self.guild_name_edit.clear()
        self.guild_realm_edit.clear()
        self._refresh_guild_status_display()

    # -- wizard restart + reset -------------------------------------------

    def _on_restart_wizard(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Restart Setup Wizard?",
            "This will reopen initial configuration so you can review your Warcraft Logs "
            "connection, characters, raid tier, and guild.\n\n"
            "Your imported reports and analysis history will not be deleted.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return
        self.db.execute(
            "UPDATE app_state SET setup_state = 'not_started' WHERE id = 1"
        )
        self.settings_repo.set("first_run_completed", False)
        self.restart_wizard_requested.emit()

    def _on_reset_ascend(self) -> None:
        dlg = _ResetDialog(self.db, self.secure_storage, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            from PySide6.QtWidgets import QApplication
            QApplication.quit()

    # -- data location ----------------------------------------------------

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

    def _on_post_discord_summary(self) -> None:
        webhook_url = self.discord_webhook_edit.text().strip()
        if not webhook_url:
            show_error(self, "Missing webhook", "Enter a Discord webhook URL first.")
            return
        self.task_panel.start("Posting weekly summary to Discord...")
        task = self.task_manager.submit(_run_discord_summary, self.db, webhook_url)
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_discord_summary_finished)
        task.signals.error.connect(lambda msg: self._on_discord_summary_failed(msg))

    def _on_discord_summary_finished(self, result) -> None:
        self.task_panel.finish("Done.")
        ok, detail = result
        if ok:
            show_info(self, "Summary posted", detail)
        else:
            show_error(self, "Discord post failed", detail)

    def _on_discord_summary_failed(self, message: str) -> None:
        self.task_panel.reset()
        show_error(self, "Discord post failed", message)

    # -- guild icon management -------------------------------------------

    @staticmethod
    def _build_button(label: str, handler) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(handler)
        return button

    def _guild_region_realm(self) -> tuple[str, str]:
        from ascend.services.guild_service import get_guild_summary
        guild = get_guild_summary(self.settings_repo)
        if guild["verified"] and guild["realm"] and guild["region"]:
            return guild["region"], guild["realm"]
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

    def _on_fetch_blizzard_crest(self) -> None:
        identity = self._current_guild_identity()
        if identity is None:
            return
        region, realm, guild_name = identity
        bnet_id = self.bnet_client_id_edit.text().strip() or self.settings_repo.get("bnet_client_id", "")
        bnet_secret = self.bnet_client_secret_edit.text().strip() or self.secure_storage.get_bnet_client_secret() or ""
        if not bnet_id or not bnet_secret:
            show_error(
                self, "Battle.net credentials required",
                "Enter Battle.net Client ID and Secret in the Battle.net Credentials section above, "
                "then save settings before fetching the guild crest.",
            )
            return

        self._bnet_crest_btn.setText("Fetching…")
        self._bnet_crest_btn.setEnabled(False)
        timeout = float(self.api_timeout_spin.value())
        self.task_panel.start(f"Fetching guild crest for {guild_name} from Blizzard API...")
        task = self.task_manager.submit(
            _run_bnet_guild_crest,
            self.db, region, realm, guild_name, bnet_id, bnet_secret, timeout,
        )
        self._active_task = task
        task.signals.progress.connect(self.task_panel.update_progress)
        task.signals.finished.connect(self._on_bnet_crest_fetched)
        task.signals.error.connect(self._on_bnet_crest_failed)

    def _on_bnet_crest_fetched(self, record) -> None:
        self._bnet_crest_btn.setText("Fetch Blizzard Crest")
        self._bnet_crest_btn.setEnabled(True)
        self.task_panel.finish("Guild crest fetch complete.")
        if record:
            show_info(self, "Guild crest fetched", "The Blizzard guild emblem has been saved to your local cache.")
        else:
            show_info(
                self, "No emblem available",
                "Blizzard returned no emblem for this guild. "
                "The generated initials badge will be used instead.",
            )

    def _on_bnet_crest_failed(self, message: str) -> None:
        self._bnet_crest_btn.setText("Fetch Blizzard Crest")
        self._bnet_crest_btn.setEnabled(True)
        self.task_panel.reset()
        show_error(self, "Crest fetch failed", f"Could not fetch guild crest:\n\n{message}")

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


class _ResetDialog(QDialog):
    """Two-step confirmation dialog for Reset Ascend."""

    def __init__(self, db: Database, secure_storage: SecureStorage, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.secure_storage = secure_storage
        self.setWindowTitle("Reset Ascend")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())
        self._stack.setCurrentIndex(0)

    def _build_step1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        warning = QLabel(
            "<h3>Reset Ascend?</h3>"
            "<p>This will remove all local Ascend data:</p>"
            "<ul>"
            "<li>Profile and configuration</li>"
            "<li>Characters</li>"
            "<li>Imported reports and analysis history</li>"
            "<li>Guild configuration and verification data</li>"
            "<li>Raid tier selection</li>"
            "<li>Insights, annotations, and goals</li>"
            "<li>Application preferences</li>"
            "<li>Setup completion state</li>"
            "</ul>"
            "<p><b>This action cannot be undone unless you create a backup first.</b></p>"
        )
        warning.setWordWrap(True)
        warning.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(warning)

        buttons = QHBoxLayout()
        backup_btn = QPushButton("Create Backup First")
        backup_btn.clicked.connect(self._on_backup)
        buttons.addWidget(backup_btn)
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        continue_btn = QPushButton("Continue →")
        continue_btn.setStyleSheet("color: #e05555; font-weight: 600;")
        continue_btn.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        buttons.addWidget(continue_btn)
        layout.addLayout(buttons)
        return page

    def _build_step2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        instruction = QLabel(
            "<b>Type RESET to confirm:</b>"
        )
        instruction.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(instruction)

        self._confirm_edit = QLineEdit()
        self._confirm_edit.setPlaceholderText("Type RESET here")
        layout.addWidget(self._confirm_edit)

        self._clear_wcl_check = QCheckBox(
            "Clear Warcraft Logs credentials from Windows Credential Manager"
        )
        self._clear_discord_check = QCheckBox(
            "Clear Discord webhook from Windows Credential Manager"
        )
        layout.addWidget(self._clear_wcl_check)
        layout.addWidget(self._clear_discord_check)

        buttons = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        buttons.addWidget(back_btn)
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        self._reset_btn = QPushButton("Reset Ascend")
        self._reset_btn.setStyleSheet("color: #e05555; font-weight: 600;")
        self._reset_btn.clicked.connect(self._on_execute_reset)
        buttons.addWidget(self._reset_btn)
        layout.addLayout(buttons)
        return page

    def _on_backup(self) -> None:
        from ascend.data.database import default_app_data_root
        import shutil
        from datetime import datetime, timezone
        app_root = default_app_data_root()
        db_path = app_root / "ascend.db"
        if not db_path.exists():
            show_info(self, "No backup needed", "No database file exists yet.")
            return
        backup_dir = app_root / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"ascend_backup_{stamp}.db"
        shutil.copy2(db_path, dest)
        show_info(self, "Backup created", f"Backup saved to:\n{dest}")

    def _on_execute_reset(self) -> None:
        if self._confirm_edit.text().strip() != "RESET":
            show_error(self, "Confirmation required", 'Type the word RESET exactly to proceed.')
            return

        try:
            self._do_reset()
        except Exception as exc:
            show_error(
                self, "Reset failed",
                f"The reset could not complete:\n\n{exc}\n\n"
                "Your original data may still be intact. Check the data folder.",
            )
            return

        show_info(
            self, "Ascend has been reset",
            "Ascend will now close. Relaunch to start fresh.",
        )
        self.accept()

    def _do_reset(self) -> None:
        from ascend.data.database import default_app_data_root
        import shutil

        if self._clear_wcl_check.isChecked():
            try:
                self.secure_storage.set_client_secret(None)
            except Exception:
                pass
        if self._clear_discord_check.isChecked():
            try:
                self.secure_storage.set_discord_webhook(None)
            except Exception:
                pass

        self.db.close()

        app_root = default_app_data_root()
        db_path = app_root / "ascend.db"
        if db_path.exists():
            db_path.unlink()

        icons_dir = app_root / "guild_icons"
        if icons_dir.exists():
            shutil.rmtree(icons_dir, ignore_errors=True)

        config_path = app_root / "config.json"
        if config_path.exists():
            config_path.unlink()


def _horizontal(*widgets: QWidget):
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return layout
