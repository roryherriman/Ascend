"""PR 3 tests: Blizzard guild crest pipeline, SecureStorage BNET keys, slug helpers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ascend.services.guild_icon_service import (
    _guild_to_bnet_slug,
    _realm_to_bnet_slug,
    _bnet_region_namespace,
    guild_cache_key,
    make_guild_badge_pixmap,
)


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def test_realm_slug_simple():
    assert _realm_to_bnet_slug("Proudmoore") == "proudmoore"


def test_realm_slug_spaces():
    assert _realm_to_bnet_slug("Moon Guard") == "moon-guard"


def test_realm_slug_apostrophe():
    assert _realm_to_bnet_slug("Kil'jaeden") == "kiljaeden"


def test_realm_slug_mixed():
    assert _realm_to_bnet_slug("Kel'Thuzad") == "kelthuzad"


def test_guild_slug_simple():
    assert _guild_to_bnet_slug("Warcraft") == "warcraft"


def test_guild_slug_spaces():
    assert _guild_to_bnet_slug("Death and Taxes") == "death-and-taxes"


def test_guild_slug_special_chars():
    assert _guild_to_bnet_slug("<It's Raid Time>") == "its-raid-time"


# ---------------------------------------------------------------------------
# Region namespace
# ---------------------------------------------------------------------------

def test_region_namespace_us():
    base, ns = _bnet_region_namespace("US")
    assert "us.api.blizzard.com" in base
    assert ns == "profile-us"


def test_region_namespace_eu():
    base, ns = _bnet_region_namespace("eu")
    assert "eu.api.blizzard.com" in base
    assert ns == "profile-eu"


def test_region_namespace_defaults_to_us():
    base, ns = _bnet_region_namespace("XX")
    assert "us.api.blizzard.com" in base
    assert ns == "profile-us"


# ---------------------------------------------------------------------------
# guild_cache_key
# ---------------------------------------------------------------------------

def test_cache_key_stable():
    k1 = guild_cache_key("US", "Proudmoore", "My Guild")
    k2 = guild_cache_key("US", "Proudmoore", "My Guild")
    assert k1 == k2
    assert len(k1) == 16


def test_cache_key_case_insensitive():
    k1 = guild_cache_key("us", "proudmoore", "my guild")
    k2 = guild_cache_key("US", "Proudmoore", "My Guild")
    assert k1 == k2


def test_cache_key_different_guilds_differ():
    k1 = guild_cache_key("US", "Proudmoore", "Alpha")
    k2 = guild_cache_key("US", "Proudmoore", "Beta")
    assert k1 != k2


# ---------------------------------------------------------------------------
# make_guild_badge_pixmap
# ---------------------------------------------------------------------------

def test_make_guild_badge_pixmap_returns_pixmap(qtbot):
    from PySide6.QtGui import QPixmap
    pm = make_guild_badge_pixmap("Warcraft", size=48)
    assert isinstance(pm, QPixmap)
    assert pm.width() == 48
    assert pm.height() == 48


def test_make_guild_badge_pixmap_empty_name(qtbot):
    from PySide6.QtGui import QPixmap
    pm = make_guild_badge_pixmap("", size=32)
    assert isinstance(pm, QPixmap)


# ---------------------------------------------------------------------------
# try_fetch_blizzard_guild_crest — mocked network
# ---------------------------------------------------------------------------

def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_try_fetch_returns_none_without_credentials(tmp_path):
    from ascend.services.guild_icon_service import try_fetch_blizzard_guild_crest
    db = _make_db(tmp_path)
    result = try_fetch_blizzard_guild_crest(db, "US", "Proudmoore", "My Guild", "", "")
    assert result is None


def test_try_fetch_returns_none_on_oauth_failure(tmp_path):
    from ascend.services.guild_icon_service import try_fetch_blizzard_guild_crest
    db = _make_db(tmp_path)
    with patch("ascend.services.guild_icon_service._get_bnet_access_token", side_effect=Exception("401")):
        result = try_fetch_blizzard_guild_crest(db, "US", "Proudmoore", "My Guild", "id", "secret")
    assert result is None


def test_try_fetch_returns_none_on_404(tmp_path):
    from ascend.services.guild_icon_service import try_fetch_blizzard_guild_crest
    import requests as req
    db = _make_db(tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("ascend.services.guild_icon_service._get_bnet_access_token", return_value="token"):
        with patch("requests.get", return_value=mock_resp):
            result = try_fetch_blizzard_guild_crest(db, "US", "Proudmoore", "My Guild", "id", "secret")
    assert result is None


def test_try_fetch_returns_none_when_no_emblem_asset(tmp_path):
    from ascend.services.guild_icon_service import try_fetch_blizzard_guild_crest
    db = _make_db(tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"assets": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("ascend.services.guild_icon_service._get_bnet_access_token", return_value="token"):
        with patch("requests.get", return_value=mock_resp):
            result = try_fetch_blizzard_guild_crest(db, "US", "Proudmoore", "My Guild", "id", "secret")
    assert result is None


def test_try_fetch_downloads_and_caches_emblem(tmp_path):
    from ascend.services.guild_icon_service import try_fetch_blizzard_guild_crest
    db = _make_db(tmp_path)

    api_resp = MagicMock()
    api_resp.status_code = 200
    api_resp.json.return_value = {"assets": [{"key": "emblem", "value": "https://example.com/guild.png"}]}
    api_resp.raise_for_status = MagicMock()

    img_resp = MagicMock()
    img_resp.status_code = 200
    img_resp.content = b"fakepng"
    img_resp.raise_for_status = MagicMock()

    call_count = {"n": 0}
    def fake_get(url, **kwargs):
        call_count["n"] += 1
        if "api.blizzard" in url:
            return api_resp
        return img_resp

    with patch("ascend.services.guild_icon_service._get_bnet_access_token", return_value="token"):
        with patch("requests.get", side_effect=fake_get):
            with patch("ascend.services.guild_icon_service._cache_dir", return_value=tmp_path):
                result = try_fetch_blizzard_guild_crest(
                    db, "US", "Proudmoore", "My Guild", "id", "secret"
                )

    assert result is not None
    assert result.get("source_type") == "official_api"
    assert result.get("retrieval_status") == "ok"
    # File should exist on disk
    cache_file = result.get("cache_file_path")
    assert cache_file and Path(cache_file).exists()


# ---------------------------------------------------------------------------
# SecureStorage BNET keys
# ---------------------------------------------------------------------------

def test_secure_storage_bnet_secret_roundtrip(tmp_path):
    from ascend.data.secure_storage import SecureStorage
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    assert storage.get_bnet_client_secret() is None
    storage.set_bnet_client_secret("test_bnet_secret")
    assert storage.get_bnet_client_secret() == "test_bnet_secret"
    storage.set_bnet_client_secret(None)
    assert storage.get_bnet_client_secret() is None


def test_secure_storage_bnet_secret_independent_of_wcl(tmp_path):
    from ascend.data.secure_storage import SecureStorage
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    storage.set_client_secret("wcl_secret")
    storage.set_bnet_client_secret("bnet_secret")
    assert storage.get_client_secret() == "wcl_secret"
    assert storage.get_bnet_client_secret() == "bnet_secret"


# ---------------------------------------------------------------------------
# Settings page has BNET fields
# ---------------------------------------------------------------------------

def test_settings_page_has_bnet_fields(qtbot, tmp_path):
    from ascend.ui.settings_page import SettingsPage
    from ascend.data.database import Database
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    db = _make_db(tmp_path)
    storage = SecureStorage(tmp_path, keyring_module=None, dpapi_module=None)
    mgr = BackgroundTaskManager()
    page = SettingsPage(db, storage, mgr)
    qtbot.addWidget(page)
    assert hasattr(page, "bnet_client_id_edit")
    assert hasattr(page, "bnet_client_secret_edit")
    assert hasattr(page, "_bnet_crest_btn")
