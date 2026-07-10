from pathlib import Path

from ascend.data.database import Database
from ascend.data.repositories import GuildIconRepository
from ascend.services.guild_icon_service import (
    clear_guild_icon,
    get_guild_badge_pixmap,
    get_or_create_guild_icon,
    guild_cache_key,
    make_guild_badge_pixmap,
    reset_to_automatic_guild_icon,
    set_custom_guild_icon,
)


def _db(tmp_path):
    database = Database(tmp_path / "guild_test.db")
    database.initialize()
    return database


def test_guild_cache_key_is_stable_and_unique(qtbot):
    key1 = guild_cache_key("US", "Stormrage", "Ascend Raiders")
    key2 = guild_cache_key("US", "Stormrage", "Ascend Raiders")
    key3 = guild_cache_key("US", "Stormrage", "A Different Guild")
    assert key1 == key2
    assert key1 != key3


def test_make_guild_badge_pixmap_never_null(qtbot):
    pixmap = make_guild_badge_pixmap("Ascend Raiders", size=48)
    assert not pixmap.isNull()
    assert pixmap.width() == 48


def test_make_guild_badge_pixmap_handles_empty_name(qtbot):
    pixmap = make_guild_badge_pixmap("", size=32)
    assert not pixmap.isNull()


def test_get_or_create_guild_icon_creates_cache_entry(tmp_path, qtbot, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    db = _db(tmp_path)
    try:
        record = get_or_create_guild_icon(db, "US", "Stormrage", "Ascend Raiders")
        assert record["source_type"] == "generated_fallback"
        assert record["retrieval_status"] == "ok"
        assert Path(record["cache_file_path"]).exists()
    finally:
        db.close()


def test_get_or_create_guild_icon_is_idempotent(tmp_path, qtbot, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    db = _db(tmp_path)
    try:
        first = get_or_create_guild_icon(db, "US", "Stormrage", "Ascend Raiders")
        second = get_or_create_guild_icon(db, "US", "Stormrage", "Ascend Raiders")
        assert first["cache_file_path"] == second["cache_file_path"]
        assert first["last_retrieved_at"] == second["last_retrieved_at"]
    finally:
        db.close()


def test_get_guild_badge_pixmap_never_raises_without_guild_name(tmp_path, qtbot, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    db = _db(tmp_path)
    try:
        pixmap = get_guild_badge_pixmap(db, "US", "Stormrage", "")
        assert not pixmap.isNull()
    finally:
        db.close()


def test_custom_guild_icon_roundtrip(tmp_path, qtbot, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    db = _db(tmp_path)
    try:
        source_image = tmp_path / "my_logo.png"
        make_guild_badge_pixmap("Custom", size=32).save(str(source_image), "PNG")

        record = set_custom_guild_icon(db, "US", "Stormrage", "Ascend Raiders", str(source_image))
        assert record["source_type"] == "custom_local"
        assert Path(record["cache_file_path"]).exists()

        clear_guild_icon(db, "US", "Stormrage", "Ascend Raiders")
        key = guild_cache_key("US", "Stormrage", "Ascend Raiders")
        assert GuildIconRepository(db).get(key) is None

        restored = reset_to_automatic_guild_icon(db, "US", "Stormrage", "Ascend Raiders")
        assert restored["source_type"] == "generated_fallback"
    finally:
        db.close()
