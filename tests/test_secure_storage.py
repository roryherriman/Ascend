from ascend.data.secure_storage import SecureStorage


class FakeKeyring:
    """In-memory stand-in for the real `keyring` package."""

    def __init__(self, fail: bool = False):
        self._store: dict[tuple[str, str], str] = {}
        self.fail = fail

    def set_password(self, service, key, value):
        if self.fail:
            raise RuntimeError("Credential Manager unavailable")
        self._store[(service, key)] = value

    def get_password(self, service, key):
        if self.fail:
            raise RuntimeError("Credential Manager unavailable")
        return self._store.get((service, key))

    def delete_password(self, service, key):
        if self.fail:
            raise RuntimeError("Credential Manager unavailable")
        self._store.pop((service, key), None)


class FakeDPAPI:
    """Deterministic stand-in for win32crypt, reversible but obviously not plaintext."""

    def CryptProtectData(self, data, _description, *_args):
        return b"ENC:" + data

    def CryptUnprotectData(self, data, *_args):
        assert data.startswith(b"ENC:")
        return (None, data[len(b"ENC:"):])


def test_uses_keyring_when_available(tmp_path):
    storage = SecureStorage(tmp_path, keyring_module=FakeKeyring())
    assert storage.using_fallback is False

    storage.set_client_secret("super-secret-value")
    assert storage.get_client_secret() == "super-secret-value"
    assert storage.status()["backend"] == "Windows Credential Manager"


def test_falls_back_to_dpapi_when_keyring_unavailable(tmp_path):
    storage = SecureStorage(
        tmp_path, keyring_module=FakeKeyring(fail=True), dpapi_module=FakeDPAPI()
    )
    assert storage.using_fallback is True
    assert storage.insecure_plaintext_fallback is False

    storage.set_client_secret("super-secret-value")
    assert storage.get_client_secret() == "super-secret-value"

    fallback_file = tmp_path / "secure_fallback.dat"
    assert fallback_file.exists()
    assert "super-secret-value" not in fallback_file.read_text(encoding="utf-8")


def test_insecure_last_resort_when_no_dpapi_available(tmp_path):
    storage = SecureStorage(tmp_path, keyring_module=FakeKeyring(fail=True), dpapi_module=None)
    assert storage.using_fallback is True
    assert storage.insecure_plaintext_fallback is True
    assert storage.status()["insecure"] is True


def test_delete_secret_removes_value(tmp_path):
    storage = SecureStorage(tmp_path, keyring_module=FakeKeyring())
    storage.set_discord_webhook("https://discord.com/api/webhooks/test")
    assert storage.get_discord_webhook() is not None

    storage.set_discord_webhook(None)
    assert storage.get_discord_webhook() is None


def test_empty_string_is_treated_as_delete(tmp_path):
    storage = SecureStorage(
        tmp_path, keyring_module=FakeKeyring(fail=True), dpapi_module=FakeDPAPI()
    )
    storage.set_client_secret("value")
    storage.set_client_secret("")
    assert storage.get_client_secret() is None
