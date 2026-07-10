"""Tests for guild search, verification, and sync service."""
import pytest

from ascend.data.database import Database
from ascend.data.repositories import SettingsRepository
from ascend.services.guild_service import (
    clear_guild,
    get_guild_summary,
    realm_to_slug,
    save_verified_guild,
    verify_guild,
)


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    d.initialize()
    try:
        yield d
    finally:
        d.close()


@pytest.fixture
def settings(db):
    return SettingsRepository(db)


SAMPLE_GUILD = {
    "id": 12345,
    "name": "Example Guild",
    "server_name": "Stormrage",
    "server_slug": "stormrage",
    "region_slug": "us",
    "region_name": "United States",
    "faction_id": 1,
    "faction_name": "Alliance",
}


# ---------------------------------------------------------------------------
# realm_to_slug
# ---------------------------------------------------------------------------

def test_realm_to_slug_simple():
    assert realm_to_slug("Stormrage") == "stormrage"


def test_realm_to_slug_spaces_to_hyphens():
    assert realm_to_slug("Area 52") == "area-52"


def test_realm_to_slug_apostrophes_removed():
    assert realm_to_slug("Ner'zhul") == "nerzhul"


def test_realm_to_slug_already_slug():
    assert realm_to_slug("stormrage") == "stormrage"


def test_realm_to_slug_strips_whitespace():
    assert realm_to_slug("  Stormrage  ") == "stormrage"


# ---------------------------------------------------------------------------
# save_verified_guild / get_guild_summary
# ---------------------------------------------------------------------------

def test_save_verified_guild_persists_all_fields(settings):
    save_verified_guild(settings, SAMPLE_GUILD)
    summary = get_guild_summary(settings)
    assert summary["name"] == "Example Guild"
    assert summary["realm"] == "Stormrage"
    assert summary["region"] == "us"
    assert summary["wcl_id"] == 12345
    assert summary["faction"] == "Alliance"
    assert summary["verified"] is True
    assert summary["last_sync_at"] is not None
    assert summary["last_sync_status"] == "ok"


def test_get_guild_summary_defaults_when_nothing_saved(settings):
    summary = get_guild_summary(settings)
    assert summary["name"] == ""
    assert summary["verified"] is False
    assert summary["wcl_id"] is None


# ---------------------------------------------------------------------------
# clear_guild
# ---------------------------------------------------------------------------

def test_clear_guild_removes_active_context(settings):
    save_verified_guild(settings, SAMPLE_GUILD)
    clear_guild(settings)
    summary = get_guild_summary(settings)
    assert summary["name"] == ""
    assert summary["verified"] is False
    assert summary["wcl_id"] is None


def test_clear_guild_preserves_reports(db, settings):
    save_verified_guild(settings, SAMPLE_GUILD)
    db.execute(
        "INSERT INTO reports (report_code, analysis_status) VALUES ('XYZ999', 'not_analyzed')"
    )
    clear_guild(settings)
    reports = db.query_all("SELECT * FROM reports")
    assert len(reports) == 1


# ---------------------------------------------------------------------------
# verify_guild with mock client
# ---------------------------------------------------------------------------

class MockClientFound:
    def fetch_guild(self, name, server_slug, region):
        return {**SAMPLE_GUILD, "name": name}


class MockClientNotFound:
    def fetch_guild(self, name, server_slug, region):
        return None


def test_verify_guild_returns_guild_on_match():
    result = verify_guild(MockClientFound(), "Example Guild", "Stormrage", "US")
    assert result is not None
    assert result["name"] == "Example Guild"


def test_verify_guild_returns_none_when_not_found():
    result = verify_guild(MockClientNotFound(), "Unknown Guild", "Stormrage", "US")
    assert result is None


def test_verify_guild_normalizes_realm_slug():
    """Realm sent to client must be slugified."""
    captured = {}

    class CapturingClient:
        def fetch_guild(self, name, server_slug, region):
            captured["server_slug"] = server_slug
            return None

    verify_guild(CapturingClient(), "Guild", "Area 52", "US")
    assert captured["server_slug"] == "area-52"


def test_verify_guild_normalizes_region_lower():
    """Region must be lowercased when sent to WCL."""
    captured = {}

    class CapturingClient:
        def fetch_guild(self, name, server_slug, region):
            captured["region"] = region
            return None

    verify_guild(CapturingClient(), "Guild", "Stormrage", "US")
    assert captured["region"] == "us"


# ---------------------------------------------------------------------------
# Unverified text is never treated as verified
# ---------------------------------------------------------------------------

def test_unverified_name_does_not_set_verified_flag(settings):
    settings.set("guild_name", "Manually Typed Guild")
    summary = get_guild_summary(settings)
    assert summary["verified"] is False


# ---------------------------------------------------------------------------
# Sync disabled without verified guild (state checks)
# ---------------------------------------------------------------------------

def test_guild_summary_not_verified_without_save(settings):
    settings.set("guild_name", "Some Guild")
    summary = get_guild_summary(settings)
    assert not summary["verified"]


def test_guild_summary_verified_after_save(settings):
    save_verified_guild(settings, SAMPLE_GUILD)
    summary = get_guild_summary(settings)
    assert summary["verified"]
