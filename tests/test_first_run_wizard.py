from ascend.data.database import Database
from ascend.data.secure_storage import SecureStorage
from ascend.services.background_worker import BackgroundTaskManager
from ascend.ui.first_run_wizard import FirstRunWizard


class FakeKeyring:
    def __init__(self):
        self._store = {}

    def set_password(self, service, key, value):
        self._store[(service, key)] = value

    def get_password(self, service, key):
        return self._store.get((service, key))

    def delete_password(self, service, key):
        self._store.pop((service, key), None)


def test_first_run_wizard_has_all_setup_steps(tmp_path, qtbot):
    db = Database(tmp_path / "wizard_test.db")
    db.initialize()
    try:
        secure_storage = SecureStorage(tmp_path, keyring_module=FakeKeyring())
        task_manager = BackgroundTaskManager()
        wizard = FirstRunWizard(db, secure_storage, task_manager)
        qtbot.addWidget(wizard)

        assert len(wizard.pageIds()) == 10
    finally:
        db.close()


def test_first_run_wizard_credentials_page_saves_on_next(tmp_path, qtbot):
    db = Database(tmp_path / "wizard_test2.db")
    db.initialize()
    try:
        secure_storage = SecureStorage(tmp_path, keyring_module=FakeKeyring())
        task_manager = BackgroundTaskManager()
        wizard = FirstRunWizard(db, secure_storage, task_manager)
        qtbot.addWidget(wizard)
        wizard.show()

        wizard.next()  # Welcome -> LocalFirst
        wizard.next()  # LocalFirst -> Credentials
        credentials_page = wizard.currentPage()
        credentials_page.client_id_edit.setText("wizard-client-id")
        credentials_page.client_secret_edit.setText("wizard-client-secret")
        wizard.next()  # triggers validatePage() -> saves

        from ascend.data.repositories import SettingsRepository

        assert SettingsRepository(db).get("wcl_client_id") == "wizard-client-id"
        assert secure_storage.get_client_secret() == "wizard-client-secret"
    finally:
        db.close()
