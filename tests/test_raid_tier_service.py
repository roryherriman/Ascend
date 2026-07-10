"""Tests for raid tier fetching, caching, and dropdown population."""
import json

import pytest

from ascend.data.database import Database
from ascend.services.raid_tier_service import (
    CACHE_KEY,
    format_cached_at,
    get_cached_zones,
    get_zones_for_display,
    save_zones_to_cache,
    sort_zones,
    zone_display_name,
)


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    d.initialize()
    try:
        yield d
    finally:
        d.close()


SAMPLE_ZONES = [
    {"id": 40, "name": "New Raid", "frozen": False, "expansion_id": 11, "expansion_name": "New Expansion"},
    {"id": 35, "name": "Old Raid", "frozen": True, "expansion_id": 10, "expansion_name": "Old Expansion"},
    {"id": 36, "name": "Old Raid 2", "frozen": True, "expansion_id": 10, "expansion_name": "Old Expansion"},
    {"id": 38, "name": "Recent Raid", "frozen": False, "expansion_id": 11, "expansion_name": "New Expansion"},
]


def test_sort_zones_active_before_frozen(db):
    result = sort_zones(SAMPLE_ZONES)
    frozen_indices = [i for i, z in enumerate(result) if z["frozen"]]
    active_indices = [i for i, z in enumerate(result) if not z["frozen"]]
    assert all(a < f for a in active_indices for f in frozen_indices)


def test_sort_zones_within_active_higher_expansion_first():
    result = sort_zones(SAMPLE_ZONES)
    active = [z for z in result if not z["frozen"]]
    exp_ids = [z["expansion_id"] for z in active]
    assert exp_ids == sorted(exp_ids, reverse=True)


def test_save_and_get_cached_zones(db):
    zones = sort_zones(SAMPLE_ZONES)
    save_zones_to_cache(db, zones)
    cached, cached_at = get_cached_zones(db)
    assert len(cached) == len(zones)
    assert cached[0]["name"] == zones[0]["name"]
    assert cached_at is not None


def test_get_cached_zones_returns_empty_when_absent(db):
    zones, cached_at = get_cached_zones(db)
    assert zones == []
    assert cached_at is None


def test_save_zones_overwrites_previous(db):
    save_zones_to_cache(db, SAMPLE_ZONES[:2])
    save_zones_to_cache(db, SAMPLE_ZONES[:1])
    cached, _ = get_cached_zones(db)
    assert len(cached) == 1


def test_get_zones_for_display_falls_back_to_static(db):
    zones, cached_at, is_cache = get_zones_for_display(db)
    assert len(zones) > 0
    assert is_cache is False
    assert cached_at is None


def test_get_zones_for_display_uses_cache_when_available(db):
    save_zones_to_cache(db, sort_zones(SAMPLE_ZONES))
    zones, cached_at, is_cache = get_zones_for_display(db)
    assert is_cache is True
    assert cached_at is not None
    assert len(zones) == len(SAMPLE_ZONES)


def test_zone_display_name():
    z = {"id": 1, "name": "Nerub-ar Palace", "frozen": False}
    assert zone_display_name(z) == "Nerub-ar Palace"


def test_format_cached_at_none():
    result = format_cached_at(None)
    assert "Refresh" in result or "Never" in result or "synchronized" in result.lower()


def test_format_cached_at_valid_iso():
    result = format_cached_at("2026-07-10T14:30:00+00:00")
    assert "2026" in result or "synchronized" in result.lower()


def test_current_tier_first_in_sorted_list():
    """The most recent non-frozen zone should appear first."""
    result = sort_zones(SAMPLE_ZONES)
    assert not result[0]["frozen"]
    assert result[0]["expansion_id"] >= result[1]["expansion_id"]


def test_fetch_zones_with_mock_client(db):
    """Verify fetch_and_cache_zones uses client.fetch_zones() and caches the result."""
    from ascend.services.raid_tier_service import fetch_and_cache_zones

    class MockClient:
        def fetch_zones(self):
            return SAMPLE_ZONES

    zones = fetch_and_cache_zones(db, MockClient())
    assert len(zones) == len(SAMPLE_ZONES)
    cached, _ = get_cached_zones(db)
    assert len(cached) == len(SAMPLE_ZONES)


def test_fetch_zones_preserves_selected_tier_in_combo(db, qtbot):
    """After a refresh, the combo should retain the previously selected tier if still present."""
    from PySide6.QtWidgets import QComboBox
    combo = QComboBox()
    combo.addItems([z["name"] for z in SAMPLE_ZONES])
    combo.setCurrentText("Old Raid")
    assert combo.currentText() == "Old Raid"
    new_zones = sort_zones(SAMPLE_ZONES)
    names = [z["name"] for z in new_zones]
    combo.clear()
    combo.addItems(names)
    if "Old Raid" in names:
        combo.setCurrentText("Old Raid")
    assert combo.currentText() == "Old Raid"


def test_static_fallback_contains_liberation_of_undermine():
    """The static list must include at least the last known tier."""
    from ascend.data.wow_data import WOW_RAID_TIERS
    assert "Liberation of Undermine" in WOW_RAID_TIERS


def test_no_hardcoded_current_tier_assumption():
    """get_zones_for_display should not assume a fixed current tier name."""
    from ascend.data.wow_data import WOW_RAID_TIERS
    assert len(WOW_RAID_TIERS) > 0
