"""Tests for PR 1: navigation restructure, hidden pages, and global context bar."""
from __future__ import annotations

import pytest

from ascend.navigation import ALL_PAGES, HIDDEN_PAGES, NAV_ITEMS, FULL_TITLES


def test_primary_nav_has_exactly_eight_items():
    assert len(NAV_ITEMS) == 8


def test_primary_nav_keys():
    keys = [k for k, _ in NAV_ITEMS]
    assert keys == [
        "dashboard",
        "reports",
        "raid_night",
        "encounter_progression",
        "roster",
        "trends",
        "insights",
        "settings",
    ]


def test_hidden_pages_not_in_nav_items():
    nav_keys = {k for k, _ in NAV_ITEMS}
    for key, _ in HIDDEN_PAGES:
        assert key not in nav_keys, f"Hidden page '{key}' must not be in NAV_ITEMS"


def test_all_pages_covers_nav_and_hidden():
    all_keys = {k for k, _ in ALL_PAGES}
    nav_keys = {k for k, _ in NAV_ITEMS}
    hidden_keys = {k for k, _ in HIDDEN_PAGES}
    assert all_keys == nav_keys | hidden_keys


def test_full_titles_covers_all_pages():
    for key, _ in ALL_PAGES:
        assert key in FULL_TITLES, f"FULL_TITLES missing entry for '{key}'"


def test_removed_pages_absent_from_primary_nav():
    nav_keys = {k for k, _ in NAV_ITEMS}
    removed = {"readiness", "goals", "rules", "raid_night_comparison",
               "data_quality", "export", "diagnostics", "characters"}
    for key in removed:
        assert key not in nav_keys, f"'{key}' should not be in primary nav"


def test_all_nav_pages_reachable_in_main_window(tmp_path, qtbot):
    from ascend.data.database import Database
    from ascend.main_window import MainWindow

    db = Database(tmp_path / "nav_test.db")
    db.initialize()
    window = MainWindow(db)
    qtbot.addWidget(window)
    try:
        for key, _ in NAV_ITEMS:
            assert key in window._page_indices, f"Nav page '{key}' missing from page stack"
            window.sidebar.select_section(key)
            assert window.stack.currentIndex() == window._page_indices[key]
    finally:
        db.close()


def test_hidden_pages_reachable_programmatically(tmp_path, qtbot):
    from ascend.data.database import Database
    from ascend.main_window import MainWindow

    db = Database(tmp_path / "hidden_test.db")
    db.initialize()
    window = MainWindow(db)
    qtbot.addWidget(window)
    try:
        for key, _ in HIDDEN_PAGES:
            assert key in window._page_indices, f"Hidden page '{key}' missing from page stack"
    finally:
        db.close()


def test_sidebar_count_matches_nav_items(tmp_path, qtbot):
    from ascend.data.database import Database
    from ascend.main_window import MainWindow

    db = Database(tmp_path / "sidebar_test.db")
    db.initialize()
    window = MainWindow(db)
    qtbot.addWidget(window)
    try:
        assert window.sidebar.selectable_section_count == len(NAV_ITEMS)
    finally:
        db.close()


def test_global_context_bar_present(tmp_path, qtbot):
    from ascend.data.database import Database
    from ascend.main_window import MainWindow
    from ascend.ui.global_context_bar import GlobalContextBar

    db = Database(tmp_path / "gcb_test.db")
    db.initialize()
    window = MainWindow(db)
    qtbot.addWidget(window)
    try:
        assert hasattr(window, "global_context_bar")
        assert isinstance(window.global_context_bar, GlobalContextBar)
    finally:
        db.close()


def test_global_context_bar_no_character_shows_fallback(tmp_path, qtbot):
    from ascend.data.database import Database
    from ascend.ui.global_context_bar import GlobalContextBar

    db = Database(tmp_path / "gcb_nochar.db")
    db.initialize()
    bar = GlobalContextBar(db)
    qtbot.addWidget(bar)
    assert "No Character" in bar._char_name.text()
    db.close()


def test_global_context_bar_reflects_settings(tmp_path, qtbot):
    from ascend.data.database import Database
    from ascend.data.repositories import SettingsRepository
    from ascend.ui.global_context_bar import GlobalContextBar

    db = Database(tmp_path / "gcb_char.db")
    db.initialize()
    repo = SettingsRepository(db)
    repo.set("player_display_name", "Kysarra")
    repo.set("character_class", "Mage")
    repo.set("guild_name", "Serenity")
    repo.set("current_tier", "Liberation of Undermine")

    bar = GlobalContextBar(db)
    qtbot.addWidget(bar)
    assert bar._char_name.text() == "Kysarra"
    assert bar._guild_name.text() == "Serenity"
    assert bar._tier_name.text() == "Liberation of Undermine"
    db.close()
