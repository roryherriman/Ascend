"""Secure storage for the Warcraft Logs client secret and Discord webhook URL.

Preference order:
1. Windows Credential Manager, via the ``keyring`` package. Verified working
   with a real set/get/delete round-trip probe at startup (not just a
   successful import) since ``keyring`` can be installed without a usable
   backend.
2. DPAPI-encrypted local file (``pywin32``'s ``win32crypt``), tied to the
   current Windows user login. Used only if Credential Manager is
   unavailable, and the caller (Settings page) is expected to warn the user
   clearly when this fallback is active.
3. As an absolute last resort, if neither is available, an obfuscated
   (NOT secure) local fallback so the app does not crash - flagged loudly via
   ``insecure_plaintext_fallback`` so the UI can refuse to hide the warning.

Secrets are never written to SQLite, YAML, or source code, and this module
never logs secret values.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

SERVICE_NAME = "Ascend"
CLIENT_SECRET_KEY = "wcl_client_secret"
DISCORD_WEBHOOK_KEY = "discord_webhook_url"
BNET_CLIENT_SECRET_KEY = "bnet_client_secret"

_PROBE_KEY = "__ascend_probe__"

_UNSET = object()  # distinguishes "not provided, auto-detect" from an explicit None in tests


class SecureStorage:
    def __init__(self, fallback_dir: Path, keyring_module: Any = _UNSET, dpapi_module: Any = _UNSET):
        self._fallback_path = Path(fallback_dir) / "secure_fallback.dat"
        self.using_fallback = False
        self.fallback_reason: str | None = None
        self.insecure_plaintext_fallback = False

        self._keyring = keyring_module
        if self._keyring is _UNSET:
            try:
                import keyring as kr

                self._keyring = kr
            except ImportError as exc:
                self._keyring = None
                self.using_fallback = True
                self.fallback_reason = f"The 'keyring' package is unavailable ({exc})."

        if self._keyring is not None and not self.using_fallback and not self._probe_keyring():
            self.using_fallback = True
            self.fallback_reason = (
                "Windows Credential Manager could not be reached or written to on this system."
            )

        self._dpapi = dpapi_module
        if self._dpapi is _UNSET:
            self._dpapi = None
            if self.using_fallback:
                try:
                    import win32crypt

                    self._dpapi = win32crypt
                except ImportError:
                    self._dpapi = None

        if self.using_fallback and self._dpapi is None:
            self.insecure_plaintext_fallback = True

    @classmethod
    def default_instance(cls) -> "SecureStorage":
        from ascend.data.database import default_app_data_root

        return cls(default_app_data_root())

    def _probe_keyring(self) -> bool:
        try:
            self._keyring.set_password(SERVICE_NAME, _PROBE_KEY, "probe")
            value = self._keyring.get_password(SERVICE_NAME, _PROBE_KEY)
            self._keyring.delete_password(SERVICE_NAME, _PROBE_KEY)
            return value == "probe"
        except Exception:
            return False

    # -- public API ---------------------------------------------------

    def status(self) -> dict:
        if not self.using_fallback:
            backend = "Windows Credential Manager"
        elif self.insecure_plaintext_fallback:
            backend = "INSECURE local fallback (obfuscated only, not encrypted)"
        else:
            backend = "Encrypted local fallback (Windows DPAPI)"
        return {
            "backend": backend,
            "using_fallback": self.using_fallback,
            "insecure": self.insecure_plaintext_fallback,
            "reason": self.fallback_reason,
        }

    def set_secret(self, key: str, value: str | None) -> None:
        if not value:
            self.delete_secret(key)
            return
        if not self.using_fallback:
            try:
                self._keyring.set_password(SERVICE_NAME, key, value)
                return
            except Exception:
                self.using_fallback = True
                self.fallback_reason = "Windows Credential Manager write failed at runtime."
        self._set_fallback(key, value)

    def get_secret(self, key: str) -> str | None:
        if not self.using_fallback:
            try:
                return self._keyring.get_password(SERVICE_NAME, key)
            except Exception:
                self.using_fallback = True
                self.fallback_reason = "Windows Credential Manager read failed at runtime."
        return self._get_fallback(key)

    def delete_secret(self, key: str) -> None:
        if not self.using_fallback:
            try:
                self._keyring.delete_password(SERVICE_NAME, key)
            except Exception:
                pass
        self._delete_fallback(key)

    def get_client_secret(self) -> str | None:
        return self.get_secret(CLIENT_SECRET_KEY)

    def set_client_secret(self, value: str | None) -> None:
        self.set_secret(CLIENT_SECRET_KEY, value)

    def get_discord_webhook(self) -> str | None:
        return self.get_secret(DISCORD_WEBHOOK_KEY)

    def set_discord_webhook(self, value: str | None) -> None:
        self.set_secret(DISCORD_WEBHOOK_KEY, value)

    def get_bnet_client_secret(self) -> str | None:
        return self.get_secret(BNET_CLIENT_SECRET_KEY)

    def set_bnet_client_secret(self, value: str | None) -> None:
        self.set_secret(BNET_CLIENT_SECRET_KEY, value)

    # -- fallback file storage -----------------------------------------

    def _load_fallback_file(self) -> dict:
        if not self._fallback_path.exists():
            return {}
        try:
            return json.loads(self._fallback_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_fallback_file(self, data: dict) -> None:
        self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback_path.write_text(json.dumps(data), encoding="utf-8")

    def _set_fallback(self, key: str, value: str) -> None:
        data = self._load_fallback_file()
        raw = value.encode("utf-8")
        if self._dpapi is not None:
            encrypted = self._dpapi.CryptProtectData(raw, SERVICE_NAME, None, None, None, 0)
            data[key] = {"enc": "dpapi", "value": base64.b64encode(encrypted).decode("ascii")}
        else:
            # Last-resort obfuscation only - never treat this as secure.
            data[key] = {"enc": "b64", "value": base64.b64encode(raw).decode("ascii")}
        self._write_fallback_file(data)

    def _get_fallback(self, key: str) -> str | None:
        data = self._load_fallback_file()
        entry = data.get(key)
        if not entry:
            return None
        raw = base64.b64decode(entry["value"])
        if entry.get("enc") == "dpapi" and self._dpapi is not None:
            _description, decrypted = self._dpapi.CryptUnprotectData(raw, None, None, None, 0)
            return decrypted.decode("utf-8")
        return raw.decode("utf-8")

    def _delete_fallback(self, key: str) -> None:
        data = self._load_fallback_file()
        if key in data:
            del data[key]
            self._write_fallback_file(data)
