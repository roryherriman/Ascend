# Security

## Secrets

Ascend handles two secrets: the Warcraft Logs **client secret** and an
optional **Discord webhook URL**.

Rules, enforced in `ascend/data/secure_storage.py`:

- Never stored in SQLite, YAML, or source code.
- Never logged, printed, or included in exports.
- Stored via the Windows Credential Manager (`keyring` package), verified at
  startup with a real set/get/delete round-trip - not just a successful
  `import keyring`, since the package can be installed without a working
  backend.
- If Credential Manager is unavailable, fall back to a DPAPI-encrypted local
  file (`secure_fallback.dat`, tied to the current Windows login via
  `pywin32`'s `win32crypt`). The Settings page shows a visible warning
  banner whenever this fallback is active, explaining why.
- If even DPAPI is unavailable, an obfuscated (NOT encrypted) last-resort
  fallback is used so the app doesn't crash, with a loud "INSECURE" warning -
  this should not be reachable on a normal Windows installation.

## OAuth tokens

`ascend/api/auth.py`'s `OAuthClient` caches the access token in memory only,
with an expiry safety margin, and refreshes automatically. The token is
never written to disk, never logged, and never displayed in the UI.

## Logging

`ascend/logging_setup.py` writes rotating logs to
`%LOCALAPPDATA%\Ascend\logs\ascend.log`. Logged: startup, sync status,
GraphQL errors, rate limits, and (later) analysis/export/background-worker
failures. **Never logged:** client secret, OAuth access token, Discord
webhook URL, GitHub credentials, or Credential Manager contents - see
`tests/test_logging_redaction.py`, which asserts secret values never appear
in log output even when an error path is triggered.

## GitHub / repository hygiene

- `.gitignore` excludes `.env`, all local databases (`ascend.db`,
  `ascend_demo.db`), the DPAPI fallback file, exports, logs, and build
  output.
- `.env.example` contains placeholders only.
- Before every push: inspect the staged diff for client secrets, tokens,
  webhooks, `.env`, and local databases.

## Threat model notes

Ascend is a single-user local desktop tool; it does not run a server and
does not accept inbound network connections. The primary risks are (1)
accidental secret leakage into git history or logs, and (2) mishandling the
Warcraft Logs OAuth token - both addressed above.
