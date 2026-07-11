"""PR 4 tests: wizard reduced to 5 steps, guild_rank removed, tier auto-detect."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


# ---------------------------------------------------------------------------
# Wizard structure
# ---------------------------------------------------------------------------

def test_wizard_has_five_pages(qtbot, tmp_path):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.first_run_wizard import FirstRunWizard
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    wizard = FirstRunWizard(db, storage, mgr)
    qtbot.addWidget(wizard)
    assert len(wizard.pageIds()) == 5


def test_wizard_page_order(qtbot, tmp_path):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.first_run_wizard import (
        CharactersSetupPage,
        CredentialsPage,
        FirstAnalysisPage,
        FirstRunWizard,
        TierPage,
        WelcomePage,
    )
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    wizard = FirstRunWizard(db, storage, mgr)
    qtbot.addWidget(wizard)
    page_types = [type(wizard.page(pid)) for pid in wizard.pageIds()]
    assert page_types == [WelcomePage, CredentialsPage, CharactersSetupPage, TierPage, FirstAnalysisPage]


# ---------------------------------------------------------------------------
# WelcomePage — merged privacy content
# ---------------------------------------------------------------------------

def test_welcome_page_contains_privacy_text(qtbot):
    from ascend.ui.first_run_wizard import WelcomePage
    page = WelcomePage()
    qtbot.addWidget(page)
    # Check that some privacy-related text exists in labels
    labels = page.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)
    all_text = " ".join(lbl.text() for lbl in labels).lower()
    assert "local" in all_text or "machine" in all_text or "private" in all_text


# ---------------------------------------------------------------------------
# CredentialsPage — merged profile fields
# ---------------------------------------------------------------------------

def test_credentials_page_has_profile_fields(qtbot, tmp_path):
    from ascend.data.database import Database
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import CredentialsPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    page = CredentialsPage(SettingsRepository(db), storage)
    qtbot.addWidget(page)
    assert hasattr(page, "display_name_edit")
    assert hasattr(page, "region_combo")
    assert hasattr(page, "client_id_edit")
    assert hasattr(page, "client_secret_edit")


def test_credentials_page_saves_all_fields(qtbot, tmp_path):
    from ascend.data.database import Database
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import CredentialsPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    repo = SettingsRepository(db)
    page = CredentialsPage(repo, storage)
    qtbot.addWidget(page)
    page.display_name_edit.setText("Aeloria")
    page.region_combo.setCurrentText("EU")
    page.client_id_edit.setText("my_client_id")
    page.client_secret_edit.setText("my_client_secret")
    page.validatePage()
    assert repo.get("player_display_name") == "Aeloria"
    assert repo.get("preferred_region") == "EU"
    assert repo.get("wcl_client_id") == "my_client_id"
    assert storage.get_client_secret() == "my_client_secret"


# ---------------------------------------------------------------------------
# TierPage — no guild_rank, has tier_combo
# ---------------------------------------------------------------------------

def test_tier_page_has_no_rank_field(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import TierPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    page = TierPage(SettingsRepository(db), storage)
    qtbot.addWidget(page)
    assert not hasattr(page, "rank_edit"), "guild_rank field must be removed"


def test_tier_page_has_tier_combo(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import TierPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    page = TierPage(SettingsRepository(db), storage)
    qtbot.addWidget(page)
    assert hasattr(page, "tier_combo")


def test_tier_page_saves_tier(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import TierPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    repo = SettingsRepository(db)
    page = TierPage(repo, storage)
    qtbot.addWidget(page)
    page.tier_combo.setCurrentText("Nerub-ar Palace")
    page.validatePage()
    assert repo.get("current_tier") == "Nerub-ar Palace"


def test_tier_page_does_not_save_guild_rank(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import TierPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    repo = SettingsRepository(db)
    page = TierPage(repo, storage)
    qtbot.addWidget(page)
    page.validatePage()
    assert repo.get("guild_us_rank", None) is None


# ---------------------------------------------------------------------------
# TierPage — auto-detect via WCL zones
# ---------------------------------------------------------------------------

def test_tier_autodetect_sets_combo_on_success(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import TierPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    repo = SettingsRepository(db)
    repo.set("wcl_client_id", "id123")
    storage.set_client_secret("secret123")
    page = TierPage(repo, storage)
    qtbot.addWidget(page)
    # Simulate detection signal
    page._on_detected("Liberation of Undermine")
    assert page.tier_combo.currentText() == "Liberation of Undermine"
    assert "Detected" in page._status_label.text()


def test_tier_autodetect_shows_fallback_message_on_failure(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import TierPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    page = TierPage(SettingsRepository(db), storage)
    qtbot.addWidget(page)
    page._on_failed()
    assert "manually" in page._status_label.text().lower()


def test_tier_autodetect_no_credentials_shows_manual_message(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.data.secure_storage import SecureStorage
    from ascend.ui.first_run_wizard import TierPage
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    page = TierPage(SettingsRepository(db), storage)
    qtbot.addWidget(page)
    page.initializePage()  # no creds → immediate fallback message
    assert "manually" in page._status_label.text().lower() or "credential" in page._status_label.text().lower()


# ---------------------------------------------------------------------------
# TierAndRankPage (legacy compat) — still importable, no guild_rank
# ---------------------------------------------------------------------------

def test_legacy_tier_and_rank_page_no_rank_edit(qtbot, tmp_path):
    from ascend.data.repositories import SettingsRepository
    from ascend.ui.first_run_wizard import TierAndRankPage
    db = _make_db(tmp_path)
    page = TierAndRankPage(SettingsRepository(db))
    qtbot.addWidget(page)
    assert not hasattr(page, "rank_edit")


# ---------------------------------------------------------------------------
# Removed pages not in wizard (structural guarantee)
# ---------------------------------------------------------------------------

def test_removed_pages_not_in_wizard(qtbot, tmp_path):
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.first_run_wizard import (
        FirstRunWizard,
        LocalFirstPage,
        PlayerProfilePage,
        TierAndRankPage,
    )
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    wizard = FirstRunWizard(db, storage, mgr)
    qtbot.addWidget(wizard)
    page_types = {type(wizard.page(pid)) for pid in wizard.pageIds()}
    assert LocalFirstPage not in page_types
    assert PlayerProfilePage not in page_types
    assert TierAndRankPage not in page_types
