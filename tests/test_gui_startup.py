import time

from PySide6.QtCore import QTimer

from ascend.data.database import Database
from ascend.main_window import MainWindow
from ascend.navigation import NAV_ITEMS


def _make_window(tmp_path, qtbot):
    db = Database(tmp_path / "gui_test.db")
    db.initialize()
    window = MainWindow(db)
    qtbot.addWidget(window)
    return window, db


def test_main_window_launches(tmp_path, qtbot):
    window, db = _make_window(tmp_path, qtbot)
    try:
        assert window.windowTitle() == "Ascend"
        assert window.sidebar.selectable_section_count == len(NAV_ITEMS)
    finally:
        db.close()


def test_navigation_switches_every_page_without_error(tmp_path, qtbot):
    window, db = _make_window(tmp_path, qtbot)
    try:
        for key, _label in NAV_ITEMS:
            window.sidebar.select_section(key)
            assert window.stack.currentIndex() == window._page_indices[key]
    finally:
        db.close()


def test_real_user_starts_with_no_seeded_characters(tmp_path, qtbot):
    window, db = _make_window(tmp_path, qtbot)
    try:
        from ascend.data.repositories import CharacterRepository

        characters = CharacterRepository(db).list_all()
        assert characters == [], "Real user flow should start with no pre-seeded characters"
    finally:
        db.close()


def test_settings_page_persists_values(tmp_path, qtbot, monkeypatch):
    window, db = _make_window(tmp_path, qtbot)
    try:
        # _on_save() shows a confirmation QMessageBox, which would block
        # forever in a headless test since nothing dismisses it - stub it out.
        monkeypatch.setattr("ascend.ui.settings_page.show_info", lambda *a, **k: None)

        settings_page = window.stack.widget(window._page_indices["settings"])
        settings_page.client_id_edit.setText("test-client-id")
        settings_page._on_save()

        from ascend.data.repositories import SettingsRepository

        repo = SettingsRepository(db)
        assert repo.get("wcl_client_id") == "test-client-id"
    finally:
        db.close()


def test_connection_test_runs_in_background_without_blocking_gui(tmp_path, qtbot, monkeypatch):
    """A slow (simulated) API call must not freeze the Qt event loop."""
    window, db = _make_window(tmp_path, qtbot)
    try:
        from ascend.api.client import ConnectionTestResult
        from ascend.ui import settings_page as settings_module

        def slow_connection_test(progress_cb, _cancel_token, *_args, **_kwargs):
            for _ in range(10):
                time.sleep(0.03)
            return ConnectionTestResult(ok=True, message="ok")

        monkeypatch.setattr(settings_module, "_run_connection_test", slow_connection_test)
        monkeypatch.setattr(settings_module, "show_info", lambda *a, **k: None)
        monkeypatch.setattr(settings_module, "show_error", lambda *a, **k: None)

        settings_page = window.stack.widget(window._page_indices["settings"])
        settings_page.client_id_edit.setText("id")
        settings_page.client_secret_edit.setText("secret")

        tick_count = {"n": 0}
        timer = QTimer()
        timer.setInterval(5)
        timer.timeout.connect(lambda: tick_count.__setitem__("n", tick_count["n"] + 1))
        timer.start()

        settings_page._on_test_connection()

        with qtbot.waitSignal(settings_page._active_task.signals.finished, timeout=5000):
            pass

        timer.stop()
        # If the GUI thread had been blocked during the ~300ms simulated call,
        # this timer would not have been able to tick during that window.
        assert tick_count["n"] > 5
    finally:
        db.close()
