"""PR 14: WoW combat log detection service and Settings UI integration."""
from __future__ import annotations

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------

def test_detect_returns_empty_when_no_wow_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(tmp_path / "nonexistent"))
    from ascend.services.combat_log import detect_combat_logs
    assert detect_combat_logs() == []


def test_detect_finds_retail_log(tmp_path, monkeypatch):
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(tmp_path))
    log_path = tmp_path / "_retail_" / "Logs" / "WoWCombatLog.txt"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("COMBAT_LOG_VERSION,20")

    from ascend.services.combat_log import detect_combat_logs
    logs = detect_combat_logs()
    assert len(logs) == 1
    assert logs[0].path == log_path
    assert logs[0].flavor == "_retail_"
    assert logs[0].size_bytes > 0


def test_detect_finds_multiple_flavors(tmp_path, monkeypatch):
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(tmp_path))
    for flavor in ("_retail_", "_classic_era_"):
        p = tmp_path / flavor / "Logs" / "WoWCombatLog.txt"
        p.parent.mkdir(parents=True)
        p.write_text("data")

    from ascend.services.combat_log import detect_combat_logs
    logs = detect_combat_logs()
    assert len(logs) == 2


def test_detect_primary_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(tmp_path / "nope"))
    from ascend.services.combat_log import detect_primary_combat_log
    assert detect_primary_combat_log() is None


def test_detect_primary_returns_newest(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(tmp_path))
    old_path = tmp_path / "_classic_era_" / "Logs" / "WoWCombatLog.txt"
    old_path.parent.mkdir(parents=True)
    old_path.write_text("old")
    time.sleep(0.05)
    new_path = tmp_path / "_retail_" / "Logs" / "WoWCombatLog.txt"
    new_path.parent.mkdir(parents=True)
    new_path.write_text("new")

    from ascend.services.combat_log import detect_primary_combat_log
    result = detect_primary_combat_log()
    assert result is not None
    assert result.path == new_path


def test_combat_log_info_size_mb(tmp_path, monkeypatch):
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(tmp_path))
    log_path = tmp_path / "_retail_" / "Logs" / "WoWCombatLog.txt"
    log_path.parent.mkdir(parents=True)
    log_path.write_bytes(b"x" * (2 * 1024 * 1024))

    from ascend.services.combat_log import detect_primary_combat_log
    info = detect_primary_combat_log()
    assert info is not None
    assert abs(info.size_mb() - 2.0) < 0.01


# ---------------------------------------------------------------------------
# Settings UI integration test
# ---------------------------------------------------------------------------

def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_settings_page_has_combat_log_group(tmp_path, qtbot, monkeypatch):
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(tmp_path / "nope"))
    db = _make_db(tmp_path)
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.settings_page import SettingsPage
    storage = SecureStorage(tmp_path / "sec")
    mgr = BackgroundTaskManager()
    page = SettingsPage(db, storage, mgr)
    qtbot.addWidget(page)
    assert hasattr(page, "_combat_log_status_label")
    assert hasattr(page, "_combat_log_path_label")
    db.close()


def test_settings_page_combat_log_no_log_found_message(tmp_path, qtbot, monkeypatch):
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(tmp_path / "nope"))
    db = _make_db(tmp_path)
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.settings_page import SettingsPage
    storage = SecureStorage(tmp_path / "sec")
    mgr = BackgroundTaskManager()
    page = SettingsPage(db, storage, mgr)
    qtbot.addWidget(page)
    assert "No WoW combat log detected" in page._combat_log_status_label.text()
    db.close()


def test_settings_page_combat_log_detected_message(tmp_path, qtbot, monkeypatch):
    wow_root = tmp_path / "wow"
    log_path = wow_root / "_retail_" / "Logs" / "WoWCombatLog.txt"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("COMBAT_LOG_VERSION,20")
    monkeypatch.setenv("ASCEND_WOW_ROOT", str(wow_root))

    db = _make_db(tmp_path)
    from ascend.data.secure_storage import SecureStorage
    from ascend.services.background_worker import BackgroundTaskManager
    from ascend.ui.settings_page import SettingsPage
    storage = SecureStorage(tmp_path / "sec")
    mgr = BackgroundTaskManager()
    page = SettingsPage(db, storage, mgr)
    qtbot.addWidget(page)
    assert "Retail" in page._combat_log_status_label.text()
    assert str(log_path) in page._combat_log_path_label.text()
    db.close()
