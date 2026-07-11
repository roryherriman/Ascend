"""PR 2 tests: class icon fallback chain, simplified dialog, card-based characters page."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ascend.data.database import Database
from ascend.data.models import Character
from ascend.data.repositories import CharacterRepository
from ascend.ui.class_icons import class_color, class_icon, class_icon_pixmap, _slug, _resolve_icon_path


# ---------------------------------------------------------------------------
# class_icons.py — slug + fallback chain
# ---------------------------------------------------------------------------

def test_slug_known_class():
    assert _slug("Death Knight") == "death_knight"
    assert _slug("Demon Hunter") == "demon_hunter"
    assert _slug("Mage") == "mage"


def test_slug_unknown_returns_raw_slug():
    assert _slug("Goblin") == "goblin"


def test_slug_none_returns_unknown():
    assert _slug(None) == "unknown"


def test_resolve_icon_path_prefers_png_over_svg(tmp_path):
    svg_file = tmp_path / "warrior.svg"
    png_file = tmp_path / "warrior.png"
    svg_file.write_text("<svg/>")
    png_file.write_bytes(b"fakepng")

    with patch("ascend.ui.class_icons._ICONS_DIR", tmp_path):
        result = _resolve_icon_path("warrior")
    assert result == str(png_file)


def test_resolve_icon_path_falls_back_to_svg(tmp_path):
    svg_file = tmp_path / "warrior.svg"
    svg_file.write_text("<svg/>")

    with patch("ascend.ui.class_icons._ICONS_DIR", tmp_path):
        result = _resolve_icon_path("warrior")
    assert result == str(svg_file)


def test_resolve_icon_path_unknown_falls_back_to_unknown_svg(tmp_path):
    unknown_svg = tmp_path / "unknown.svg"
    unknown_svg.write_text("<svg/>")

    with patch("ascend.ui.class_icons._ICONS_DIR", tmp_path):
        result = _resolve_icon_path("goblin")
    assert result == str(unknown_svg)


def test_resolve_icon_path_none_when_nothing_exists(tmp_path):
    with patch("ascend.ui.class_icons._ICONS_DIR", tmp_path):
        result = _resolve_icon_path("goblin")
    assert result is None


def test_class_color_known():
    assert class_color("Mage") == "#69CCF0"
    assert class_color("Death Knight") == "#C41F3B"


def test_class_color_unknown():
    from ascend.ui.class_icons import UNKNOWN_COLOR
    assert class_color(None) == UNKNOWN_COLOR
    assert class_color("Goblin") == UNKNOWN_COLOR


def test_class_color_case_insensitive():
    assert class_color("mage") == class_color("Mage")


def test_class_icon_returns_qicon(qtbot):
    ico = class_icon("Warrior")
    from PySide6.QtGui import QIcon
    assert isinstance(ico, QIcon)


def test_class_icon_pixmap_returns_pixmap(qtbot):
    from PySide6.QtGui import QPixmap
    pm = class_icon_pixmap("Mage", 20)
    assert isinstance(pm, QPixmap)


# ---------------------------------------------------------------------------
# CharacterDialog — simplified (no class/spec_role/wcl_id fields)
# ---------------------------------------------------------------------------

def test_character_dialog_has_no_class_combo(qtbot):
    from ascend.ui.dialogs import CharacterDialog
    dlg = CharacterDialog()
    qtbot.addWidget(dlg)
    assert not hasattr(dlg, "class_combo")


def test_character_dialog_has_no_spec_role_combo(qtbot):
    from ascend.ui.dialogs import CharacterDialog
    dlg = CharacterDialog()
    qtbot.addWidget(dlg)
    assert not hasattr(dlg, "spec_role_combo")


def test_character_dialog_has_no_wcl_id_edit(qtbot):
    from ascend.ui.dialogs import CharacterDialog
    dlg = CharacterDialog()
    qtbot.addWidget(dlg)
    assert not hasattr(dlg, "wcl_id_edit")


def test_character_dialog_preserves_detected_fields_on_edit(qtbot):
    from ascend.ui.dialogs import CharacterDialog
    existing = Character(
        display_name="Raidchar",
        character_name="Raidchar",
        region="US",
        server="Proudmoore",
        wcl_character_id=42,
        character_class="Paladin",
        character_role="primary",
        spec_role="healer",
        enabled=True,
        id=1,
    )
    dlg = CharacterDialog(character=existing)
    qtbot.addWidget(dlg)
    result = dlg.result_character()
    assert result.wcl_character_id == 42
    assert result.character_class == "Paladin"
    assert result.spec_role == "healer"


def test_character_dialog_result_new_character_has_no_class(qtbot):
    from ascend.ui.dialogs import CharacterDialog
    dlg = CharacterDialog()
    qtbot.addWidget(dlg)
    dlg.display_name_edit.setText("New")
    dlg.character_name_edit.setText("New")
    dlg.server_edit.setText("Stormrage")
    result = dlg.result_character()
    assert result.character_class is None
    assert result.spec_role is None
    assert result.wcl_character_id is None


# ---------------------------------------------------------------------------
# CharactersPage — card layout
# ---------------------------------------------------------------------------

def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_characters_page_loads(qtbot, tmp_path):
    from ascend.ui.characters_page import CharactersPage
    db = _make_db(tmp_path)
    page = CharactersPage(db)
    qtbot.addWidget(page)
    assert page is not None


def test_characters_page_shows_empty_state(qtbot, tmp_path):
    from ascend.ui.characters_page import CharactersPage
    from PySide6.QtWidgets import QLabel
    db = _make_db(tmp_path)
    page = CharactersPage(db)
    qtbot.addWidget(page)
    labels = page.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]
    assert any("No characters yet" in t for t in texts)


def test_characters_page_shows_cards_for_characters(qtbot, tmp_path):
    from ascend.ui.characters_page import CharactersPage, _CharacterCard
    db = _make_db(tmp_path)
    repo = CharacterRepository(db)
    repo.create(Character(display_name="Alpha", character_name="Alpha", region="US", server="Moon Guard"))
    repo.create(Character(display_name="Beta", character_name="Beta", region="US", server="Moon Guard"))
    page = CharactersPage(db)
    qtbot.addWidget(page)
    cards = page.findChildren(_CharacterCard)
    assert len(cards) == 2


def test_characters_page_search_filters_cards(qtbot, tmp_path):
    from ascend.ui.characters_page import CharactersPage, _CharacterCard
    db = _make_db(tmp_path)
    repo = CharacterRepository(db)
    repo.create(Character(display_name="Alpharius", character_name="Alpharius", region="US", server="Stormrage"))
    repo.create(Character(display_name="Betarix", character_name="Betarix", region="US", server="Stormrage"))
    page = CharactersPage(db)
    qtbot.addWidget(page)
    page.search_edit.setText("alpha")
    cards = page.findChildren(_CharacterCard)
    assert len(cards) == 1
    assert cards[0].character.display_name == "Alpharius"


def test_characters_page_no_table_widget(qtbot, tmp_path):
    from ascend.ui.characters_page import CharactersPage
    from PySide6.QtWidgets import QTableWidget
    db = _make_db(tmp_path)
    page = CharactersPage(db)
    qtbot.addWidget(page)
    assert len(page.findChildren(QTableWidget)) == 0


# ---------------------------------------------------------------------------
# fetch_assets.py — script structure (no network calls)
# ---------------------------------------------------------------------------

def test_fetch_assets_script_exists():
    script = Path(__file__).parent.parent / "scripts" / "fetch_assets.py"
    assert script.exists()


def test_fetch_assets_has_all_class_ids():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "fetch_assets",
        Path(__file__).parent.parent / "scripts" / "fetch_assets.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # Don't execute (would import requests) — just read the source for the constant
    source = (Path(__file__).parent.parent / "scripts" / "fetch_assets.py").read_text()
    for slug in ["warrior", "paladin", "hunter", "rogue", "priest",
                 "death_knight", "shaman", "mage", "warlock", "monk",
                 "druid", "demon_hunter", "evoker"]:
        assert slug in source


def test_fetch_assets_never_hardcodes_secret():
    source = (Path(__file__).parent.parent / "scripts" / "fetch_assets.py").read_text()
    assert "BNET_CLIENT_SECRET" in source
    assert '= "' not in source.split("BNET_CLIENT_SECRET")[1].split("\n")[0]


def test_class_icon_sources_md_exists():
    doc = Path(__file__).parent.parent / "CLASS_ICON_SOURCES.md"
    assert doc.exists()
