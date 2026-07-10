"""Entry point for Ascend.

Launch with: python app.py
Or via run_app.bat / the built Ascend.exe on Windows.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv is an optional dev convenience, not a hard requirement


def _seed_dev_env_credentials(settings_repo, secure_storage) -> None:
    """Optional developer convenience: pre-fill Settings from a local .env,
    but never overwrite a value the user (or a previous run) already set."""
    env_client_id = os.environ.get("ASCEND_WCL_CLIENT_ID")
    if env_client_id and not settings_repo.get("wcl_client_id"):
        settings_repo.set("wcl_client_id", env_client_id)

    env_client_secret = os.environ.get("ASCEND_WCL_CLIENT_SECRET")
    if env_client_secret and not secure_storage.get_client_secret():
        secure_storage.set_client_secret(env_client_secret)

    env_webhook = os.environ.get("ASCEND_DISCORD_WEBHOOK")
    if env_webhook and not secure_storage.get_discord_webhook():
        secure_storage.set_discord_webhook(env_webhook)


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("Ascend")
    app.setOrganizationName("Ascend")

    try:
        from ascend import metadata
        from ascend.data.database import Database, default_app_data_root, load_bootstrap_config
        from ascend.data.repositories import SettingsRepository
        from ascend.data.secure_storage import SecureStorage
        from ascend.logging_setup import get_logger, setup_logging
        from ascend.main_window import MainWindow
        from ascend.services.background_worker import BackgroundTaskManager
        from ascend.services.demo_data import ensure_demo_report_seeded
        from ascend.theme import DARK_STYLESHEET
        from ascend.ui.first_run_wizard import FirstRunWizard

        app.setStyleSheet(DARK_STYLESHEET)

        app_root = default_app_data_root()
        bootstrap_config = load_bootstrap_config(app_root)
        # `--demo` forces Demo Mode for this run only (not persisted to config.json) -
        # a quick way to preview the Dashboard with realistic sanitized data before
        # the real analysis engine exists. See docs/ARCHITECTURE.md - Demo Mode.
        cli_demo_flag = "--demo" in sys.argv[1:]
        is_demo = bool(bootstrap_config.get("demo_mode", False)) or cli_demo_flag

        log_dir = app_root / "logs"
        logger = setup_logging(log_dir)
        logger.info(
            "Starting %s v%s (build %s), demo_mode=%s",
            metadata.APP_NAME, metadata.APP_VERSION, metadata.BUILD_NUMBER, is_demo,
        )

        db = Database.default_path_instance(demo_override=is_demo if cli_demo_flag else None)
        db.initialize()

        settings_repo = SettingsRepository(db)
        secure_storage = SecureStorage.default_instance()
        task_manager = BackgroundTaskManager()

        _seed_dev_env_credentials(settings_repo, secure_storage)

        if is_demo:
            from ascend.ui.characters_page import seed_initial_characters

            seed_initial_characters(db)
            ensure_demo_report_seeded(db)

        if not settings_repo.get("first_run_completed", False) and not is_demo:
            wizard = FirstRunWizard(db, secure_storage, task_manager)
            wizard.exec()
            settings_repo.set("first_run_completed", True)

        window = MainWindow(db, secure_storage=secure_storage, is_demo=is_demo)
        window.show()
    except Exception as exc:  # noqa: BLE001 - top-level guard so the app never crashes silently
        traceback.print_exc()
        try:
            get_logger().exception("Fatal startup error: %s", type(exc).__name__)
        except Exception:  # noqa: BLE001 - logging must never mask the real startup error
            pass
        QMessageBox.critical(
            None,
            "Ascend - Startup Error",
            "The application failed to start.\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            "See the console log for full details.",
        )
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
