# Ascend (Ascende) public release audit

**Repository:** https://github.com/roryherriman/Ascende (public since 2026-10-18)
**Audited:** 2026-10-18, at `main` = `a8e6068`, plus every branch, all 5 tags, all 51 GitHub PR refs, and all 5 published release ZIPs
**Fixes branch:** `audit/public-release-fixes` (PR #78)

> This is an engineering audit, not legal advice. Passing automated checks doesn't make the project legally safe. Where a conclusion depends on a third party's terms, the source is cited, and anything I couldn't confirm is listed in §10.

---

## 1. Executive summary

- **No credentials are exposed.** Nothing was found in git history (113 commits across all refs, 407 unique files), in GitHub issues or PRs, or in any of the 5 published release binaries (including the compiled bytecode inside them). There is nothing to revoke or rotate.
- **The main problems are in what the published releases ship and in terms-of-service obligations, not in the source code:**
  - Every release bundles a **GPL-only Qt component** (Qt Virtual Keyboard).
  - Every release is missing the **third-party licence notices** that LGPL/MPL/Apache components require.
  - Every release was built locally with the **October 2022 Python 3.11.0 runtime**, which bundles **end-of-life OpenSSL 1.1.1q**.
- **Two terms-of-service obligations aren't met yet.** Both the RPGLogs API Terms and the Blizzard Developer API Terms **require a published privacy policy**. Ascend has none (a draft is now included). Ascend's **indefinite local caching** of API data needs clarification under RPGLogs §5d, and it conflicts with Blizzard's 30-day retention rule for the optional guild-crest feature.
- **The application code is in good shape.** SQL is parameterised. There's no shell execution or unsafe deserialisation. Tokens stay in memory and are never logged. Secrets go to Windows Credential Manager. Only public reports are accessed (client-credentials flow). The class icons are original artwork, and the demo data is synthetic.
- **One real code-level leak was found and fixed:** a Discord webhook URL, which is itself a secret, could appear in error dialogs.

## 2. Release recommendation

### **READY WITH CHANGES**

The source repository is safe to remain public. **The published v0.1.0–v1.0.0 binaries should be replaced by a rebuilt release** (H1–H3, M4), and **PRIVACY.md should be published** (H4) before Ascend is promoted further. H5 should be raised with RPGLogs.

---

## 3–7. Findings

Severity: **CRITICAL** = exposed credential or actively exploitable · **HIGH** = confirmed licensing/terms gap or significant risk · **MEDIUM** · **LOW**.
Status: **Confirmed** (evidence below) · **Potential** (depends on interpretation) · **Fixed locally** (on the fixes branch, not pushed).

### CRITICAL

None.

### HIGH

**H1. GPL-only Qt Virtual Keyboard shipped in every release** (Confirmed · Fixed in build config)
- Evidence: all 5 release ZIPs contain `_internal/PySide6/Qt6VirtualKeyboard.dll` (inspected 2026-10-18). Ascend never uses it; the PySide6 PyInstaller hook collects it automatically.
- Policy: Qt lists Qt Virtual Keyboard among the modules "not available under the GNU LGPL version 3", only GPLv3 or commercial. Sources: [Qt licensing](https://doc.qt.io/qt-6/licensing.html), [Qt Virtual Keyboard licences](https://doc.qt.io/qt-6/qtvirtualkeyboard-index.html).
- Risk: distributing a GPLv3 component without GPLv3 compliance (licence text, source offer), inside an app with no licence of its own.
- Fix applied: `Ascend.spec` now filters `qt6virtualkeyboard`/`qtvirtualkeyboard` out of `a.binaries` and `a.datas`. A test build confirmed 0 Virtual Keyboard files, and the app launched cleanly with isolated app data.
- **Still needed (approval):** rebuild and replace the published release assets.

**H2. Third-party licence notices missing from releases** (Confirmed · Fixed in build config)
- Evidence: release ZIPs include licence files only for importlib_metadata, keyring, plotly and typing_extensions, plus Ascend's own icon licences. There is nothing for Qt/PySide6 (LGPL-3.0), certifi (MPL-2.0), requests/OpenSSL 3 (Apache-2.0), OpenSSL 1.1.1 (OpenSSL/SSLeay licence), Python and pywin32 (PSF), or the others.
- Policy: LGPL-3.0 §4 requires a prominent notice and licence copies. MPL-2.0 §3.2 and Apache-2.0 §4 require licence and notice text with binary distributions.
- Fix applied: new `THIRD_PARTY_NOTICES.md` (components, versions, licences, source links, an LGPL relinking note, and data-source attribution), bundled by `Ascend.spec`. The folder-based (not one-file) build keeps the Qt DLLs replaceable, which supports LGPL compliance.
- **Still needed (approval):** rebuild the releases. Consider also bundling the full LGPL/GPL/MPL/Apache licence texts, not just links.

**H3. Every release runs an outdated Python with end-of-life OpenSSL** (Confirmed · Needs rebuild)
- Evidence (PE version resources in all 5 ZIPs): `python311.dll` 3.11.0, `libssl-1_1.dll`/`libcrypto-1_1.dll` **1.1.1q**, `sqlite3.dll` 3.38.4. Python 3.11.0's `ssl` module uses OpenSSL 1.1.1, so **all HTTPS traffic** (Warcraft Logs, Battle.net, Discord) goes through it. OpenSSL 1.1.1 has been end of life since September 2023.
- Cause: the releases were built from the local `.venv` (Python 3.11.0). The v1.0.0 tag's release workflow failed at "Upload release asset" (see M5), so the published v1.0.0 ZIP (sha256 `5a56a32c…`) matches the local `dist/` build.
- Root cause traced: OpenSSL 1.1 is linked by Python 3.11.0's own `_ssl.pyd` and `_hashlib.pyd`. The `libssl-3-x64.dll` (3.5.6) belongs to Qt's TLS plugin and is current. The 1.1 DLLs **can't be swapped in place** (different ABI), so a **full rebuild with a newer Python is required**.
- Options checked: CI's `setup-python` "3.11" currently installs **3.11.9** (the last 3.11 release with Windows binaries, April 2024; OpenSSL 3.0.x but no later 3.11 security fixes). The locally installed **Python 3.13.14** ships **OpenSSL 3.0.21**. Recommended: build releases on 3.12 or 3.13 after running the suite on that version. **Approval needed.**

**H4. No privacy policy, which both API terms require** (Confirmed · Draft created)
- Policy: [RPGLogs API ToS §3(d)](https://www.archon.gg/classic-mop/articles/help/rpg-logs-api-terms-of-service) says "You will provide and adhere to a privacy policy for your API Client…". [Blizzard Developer API ToU §2 item 15](https://www.blizzard.com/en-gb/legal/a2989b50-5f16-43b1-abec-2ae17cc09dd6/blizzard-developer-api-terms-of-use) says "You must post a privacy policy governing the use of the Data…".
- Fix applied: `PRIVACY.md`, written only from behaviour verified in the code (stored fields per table, credential storage tiers, outbound services, export contents, combat-log metadata-only check, Reset scope, deletion). The README links it.
- **Still needed (approval):** review the wording, then commit and publish it. Consider linking it in-app (About / Settings).

**H5. Indefinite local storage of Warcraft Logs API content** (Potential · Needs clarification from RPGLogs)
- Evidence: raw API responses are cached in `api_cache` with no expiry:
  - full report JSON: `ascend/services/sync_service.py:154`
  - death tables: `ascend/services/death_data.py:41`
  - zone difficulties: `ascend/services/zone_data.py:46`

  Report, fight and participant data (player name, realm, class) persist in `reports`, `fights` and `fight_participants` (`ascend/data/migrations.py:155`). Only the zone list (`raid_tier_service.py`) sets an expiry.
- Policy: [RPGLogs API ToS §5(d)](https://www.archon.gg/classic-mop/articles/help/rpg-logs-api-terms-of-service) prohibits, "unless expressly permitted by the content owner", to "build databases, or otherwise create permanent copies of such content, or keep cached copies longer than permitted by the cache header", and to "create a derivative work of… distribute, publicly display". §8(b) requires deleting cached content on termination.
- Assessment: a personal, local analytics cache is the core of the product, and much third-party WCL tooling works this way. But the clause's wording doesn't clearly exempt it. **I couldn't confirm what cache headers the API sends** (it needs live credentials). This is a risk to API access, not a confirmed violation.
- Recommended: email RPGLogs (support@rpglogs.com) describing Ascend's local-only cache and ask for confirmation. Meanwhile, consider honouring `Cache-Control` on cached raw responses, adding a "purge cached API data" action, and keeping exports and Discord output to derived aggregates (Discord already is).

### MEDIUM

**M1. Discord webhook token could leak into error dialogs** (Confirmed · Fixed)
- Evidence: on network failure `_run_discord_test` (`ascend/ui/settings_page.py:65-74`) and `post_weekly_summary` (`ascend/services/discord_service.py`) returned `str(exc)`. `requests` error messages include the request URL, and the dialog at `settings_page.py:1049` displays it. A webhook URL's last path segment is its secret token.
- Fix: new `redact_webhook()` strips the webhook URL and any `/api/webhooks/…` path from error text. Test `test_network_error_does_not_leak_webhook_token` added.

**M2. Webhook URL not validated, so summaries could go to any host** (Confirmed · Fixed)
- Fix: new `is_discord_webhook_url()` accepts only `https://` on discord.com, discordapp.com, ptb.discord.com or canary.discord.com, with an `/api/webhooks/` path. Both send paths reject anything else before any request is made. Tests cover http, wrong host, a lookalike host and a non-webhook path.

**M3. Blizzard guild crests kept indefinitely; in-app Blizzard attribution unverified** (Confirmed for retention · Needs code change)
- Evidence: `ascend/services/guild_icon_service.py:190-206` downloads the emblem and writes it to a permanent cache plus the `guild_icons` table (`migrations.py:135`), with no refresh or expiry. This only applies if the user adds Battle.net credentials.
- Policy: [Blizzard Developer API ToU §2 item 18](https://www.blizzard.com/en-gb/legal/a2989b50-5f16-43b1-abec-2ae17cc09dd6/blizzard-developer-api-terms-of-use) says "You must implement a maximum 30-day TTL… for all Data". Item 13 says "clearly and conspicuously identify Blizzard in Your Application as the source of the Data."
- Fix applied: README attribution only. **Recommended (approval):** re-fetch or delete crests older than 30 days, and add "Guild crest © Blizzard Entertainment, via Battle.net API" in the UI where crests appear.

**M4. urllib3 2.7.0 in the bundle has 3 advisories (2 HIGH)** (Confirmed · Needs rebuild)
- GHSA-8988-9cw3-xx77 (HIGH, HTTPS proxy TLS config may be ignored), GHSA-vxq7-64xx-v4gw (HIGH, unbounded chunk-size line), GHSA-gh4c-6fx4-qh6g (MODERATE, deflate infinite loop). All are fixed in **urllib3 2.8.0** (source: [OSV](https://osv.dev/vulnerability/GHSA-8988-9cw3-xx77)). Exposure is limited because Ascend only talks to trusted hosts, but a rebuild picks up the fix.
- Other bundled packages had no OSV advisories. setuptools 65.5.0 and pip have advisories but are build-time only and not bundled.

**M5. Release workflow had no `permissions`; v1.0.0 release run failed** (Confirmed · Fixed)
- Evidence: the repo's default `GITHUB_TOKEN` permission is `read`. `release.yml` declared none, yet `softprops/action-gh-release` needs `contents: write`. The v1.0.0 run (2026-07-13) failed at "Upload release asset". **The cause can't be confirmed because the run's logs have expired.**
- Fix: `release.yml` now declares `permissions: contents: write`, and `ci.yml` declares `contents: read` (least privilege).

**M6. README overstated privacy guarantees** (Confirmed · Fixed)
- `README.md` (main) line 64 said Ascend "only connects to the Warcraft Logs API (and, optionally, Battle.net)". It also posts to Discord. Line 63 said secrets "never go into… config files", but the last-resort fallback writes an obfuscated file. Line 88 cited 389 tests; the suite now has 416.
- Fix: corrected those lines, and added data-retention, attribution and RPGLogs non-affiliation wording.

**M7. No licence** (Confirmed · Approval needed)
- The public repo has no `LICENSE`, so all rights are reserved by default. `ascend/resources/{icons,class_icons}/LICENSE.txt` say "same license as the Ascend project itself", which is currently none.
- **Recommendation: MIT** (simple, permissive, compatible with every bundled dependency, and matches a free community tool). Alternative: **Apache-2.0** if you want an explicit patent grant. A licence covers the code only; it grants nothing over Blizzard or Warcraft Logs content. Ascend is largely AI-generated, and copyright protection for purely AI-generated material may be limited (US Copyright Office, *Copyright and Artificial Intelligence, Part 2*, January 2025). A licence still clearly sets the terms for the human-directed work. **Not added.**

**M8. GitHub secret scanning, push protection and Dependabot are disabled** (Confirmed · Approval needed)
- The API returned "Secret scanning is disabled on this repository" and "Dependabot alerts are disabled". Enabling them is free for public repos.

**M9. "Check for Updates" opens a 404 page in every release** (Confirmed · Approval needed)
- Evidence: `ascend/metadata.py:14` has `GITHUB_REPO = "roryherriman/Ascend"`, but the repository is `roryherriman/Ascende`. **Help → Check for Updates** (`ascend/main_window.py:186-190`) therefore opens a non-existent page.
- Fix options: (a) rename the repository to `Ascend`. GitHub redirects the old name, and this **also fixes builds already in users' hands**. (b) Change `GITHUB_REPO` to `roryherriman/Ascende`, which only fixes future builds.

### LOW

| # | Finding | Evidence | Status |
|---|---|---|---|
| L1 | Last-resort secret fallback is base64, not encryption | `ascend/data/secure_storage.py:174-175` | By design. Only used when neither Credential Manager nor DPAPI works, and the UI warns. Documented in README and PRIVACY. |
| L2 | Crest image URL from the API is fetched without a host allowlist or size cap | `guild_icon_service.py:190-199` | Recommend accepting only `*.blizzard.com`/`*.blizzard.cn`/`*.battle.net`, and capping the size (e.g. 2 MB). |
| L3 | Dependencies unpinned (`>=`); Actions pinned by tag, not SHA; `pyinstaller`/`pytest` listed in runtime `requirements.txt` | `requirements.txt:1-11`, `release.yml:55` | Recommend a lock or constraints file for release builds, and SHA-pinning `softprops/action-gh-release` (it holds a write token). |
| L4 | `CLASS_ICON_SOURCES.md` claimed releases bundle Blizzard PNGs, and linked a Blizzard ToU URL that no longer loads | `CLASS_ICON_SOURCES.md:16` (main) | **Fixed:** documents that no release includes Blizzard images, updates the link, and explains the 30-day TTL. `Ascend.spec` now also refuses to bundle `class_icons/*.png/jpg`. |
| L5 | `.gitignore` missed `dist2/` | `git status` showed it untracked | **Fixed:** added `dist*/` and `Ascend-*.zip`. |
| L6 | Exports (JSON/CSV/HTML) include other players' names, realms and classes | `ascend/ui/export_page.py:77-89` | Documented in PRIVACY.md. Consider an "anonymise names" export option. |
| L7 | Rate limits are only checked reactively (HTTP 429 → error, no retry) | `ascend/api/client.py:89-93` | Compliant with RPGLogs ToS §2(e) (no circumvention). Optional: read `rateLimitData` before bulk guild syncs. |
| L8 | Releases are unsigned | README | Already disclosed. Code signing is optional. |
| L9 | **Settings → Reset** doesn't remove the Battle.net client secret, backups, logs or exports | `ascend/ui/settings_page.py:1322-1350` | Disclosed in PRIVACY.md. Recommend adding a "clear Battle.net secret" option and an "also delete backups and logs" option. |
| L10 | Background-task race: `BackgroundTaskManager.submit()` starts the task before callers connect to its signals (`ascend/services/background_worker.py:79-90`; e.g. `settings_page.py` connects after `submit`). An instant task can finish unheard, leaving a progress panel stuck. This caused a CI failure on PR #78. | `test_background_worker.py` | **Test fixed** (workers are gated until the test connects). **UI hardened**: webhook URLs are validated before any task starts. **Recommended (approval):** let `submit()` accept callbacks and connect them before `pool.start()`. |

### Cleared (checked, no issue)

- **Secrets:** custom scanner over every blob reachable from any ref, plus commit messages: 0 real hits (2 false positives: a deliberately fake token in `tests/test_fixture_sanitizer.py:38`, and a long URL). GitHub issues and PR bodies: clean. No Actions secrets configured.
- **Release binaries:** no `.env`, credentials, user paths or webhook URLs in files, the exe, or the decompressed PYZ bytecode. The 5 UUIDs in `Ascend.exe` are the standard Windows `supportedOS` manifest GUIDs.
- **Bundled demo data** (`ascend/resources/demo_report.json`): synthetic ("Test Guild", "TestOwner", report code `AbCdEfGh123456`).
- **Commit identities:** all GitHub no-reply addresses.
- **No employer or proprietary material** found in code, docs, history or `docs/about/*`.
- **Warcraft Logs auth:** client-credentials flow against `/api/v2/client` only (`ascend/api/client.py:26`), so public reports only; RPGLogs §5(c) (non-public content consent) doesn't apply. Tokens are memory-only and never logged (`auth.py:31-36`). Each user registers their own API client, so **no developer credentials are embedded** (RPGLogs §4(b): "Developer credentials… may not be embedded in open source projects").
- **AppSec:** no SQL built from strings (the f-strings are Qt stylesheets). No `subprocess`/`os.system`/`shell=True`, no `pickle`/`eval`/`yaml.load`, no temp files. The report URL parser is a strict regex plus a host check (`url_parser.py:23-24`). Cache file names are SHA-1 hashes, so no path traversal (`guild_icon_service.py:38-40`). Logging contains only HTTP status codes, Warcraft Logs error text and startup errors.
- **Blizzard IP:** class icons are original abstract glyphs (visually reviewed), and no Blizzard raster art is in the repo or any release. Screenshots show only Ascend's own UI. The name "Ascend" contains no Blizzard trademark (Blizzard ToU §2 item 13). Boss and zone names are factual references.
- **Endorsement:** README and release notes state non-affiliation, consistent with RPGLogs ToS §6(c) and Blizzard ToU §4.
- **Commercial use:** Ascend is free with no ads or premium tier, so it doesn't trigger RPGLogs §2(a) approval or Blizzard's "premium" prohibition.

---

## 8. Changes applied (branch `audit/public-release-fixes`)

| File | Change |
|---|---|
| `ascend/services/discord_service.py` | Webhook URL allowlist (`is_discord_webhook_url`) and error-text redaction (`redact_webhook`) |
| `ascend/ui/settings_page.py` | Webhook test uses the same validation and redaction |
| `tests/test_issues_10_12_13.py` | +3 tests (non-Discord URLs rejected without sending; token never in error text; official hosts accepted) |
| `Ascend.spec` | Excludes the GPL-only Qt Virtual Keyboard; never bundles Blizzard class-icon rasters; bundles `THIRD_PARTY_NOTICES.md` |
| `.github/workflows/ci.yml` | `permissions: contents: read` |
| `.github/workflows/release.yml` | `permissions: contents: write` |
| `.gitignore` | `dist*/`, `Ascend-*.zip` |
| `README.md` | Accurate connectivity/secret/retention claims, test count, attribution, links to PRIVACY and notices |
| `CLASS_ICON_SOURCES.md` | Accurate release status, current Blizzard ToU link, 30-day TTL guidance |
| `THIRD_PARTY_NOTICES.md` | **New:** bundled component licences and attribution |
| `PRIVACY.md` | **New:** data-handling notice (verified against the code) |
| `PUBLIC_RELEASE_AUDIT.md` | **New:** this report |

**Verification:**
- **Tests:** full suite **416 passed** (baseline 413 + 3 new), offscreen Qt.
- **Build:** a test PyInstaller build to a temporary folder succeeded. It contains 0 Virtual Keyboard files, only SVGs in `class_icons`, and includes `THIRD_PARTY_NOTICES.md`.
- **Launch:** the built `Ascend.exe` launched cleanly against an isolated, throwaway `LOCALAPPDATA` (no errors logged).
- **Your data:** your real `dist/` and `%LOCALAPPDATA%\Ascend` were not touched.

## 9. Needs your approval

1. **Commit and push** the fixes branch (or merge it into `main`).
2. **Approve `PRIVACY.md`** (on the PR branch).
3. **Rebuild and replace the release** with current Python, urllib3 ≥ 2.8.0, no Virtual Keyboard, and notices included (H1–H3, M4). For example, tag v1.0.1 and let the fixed workflow build it. Decide whether to delete or annotate the older release assets that contain the GPL component.
4. **Choose a licence** (recommendation: MIT) (M7).
5. **Enable** secret scanning, push protection and Dependabot alerts (M8).
6. **Contact RPGLogs** about local caching (H5).
7. **Code change:** 30-day crest refresh and in-app Blizzard attribution (M3), plus the crest host/size checks (L2).
8. **Optional hardening:** a constraints file for release builds, SHA-pinned actions, an anonymised export option (L3, L6).

## 10. Couldn't verify

- **What cache headers the Warcraft Logs API returns**, and whether RPGLogs treats a personal local cache as a "permanent copy" (H5). This needs API access and RPGLogs' answer.
- **Attribution requirements "described in the documentation for the API"** (RPGLogs §6(b)). The API documentation (archived 2025-11-14) contains none, and the referenced "RPGLogs Brand Features Use Guidelines" couldn't be found.
- **Live RPGLogs pages:** warcraftlogs.com and archon.gg showed bot challenges, which I didn't bypass. Terms were read from Internet Archive snapshots (API ToS "Last updated April 28, 2025", captured 2026-05-08). Check that nothing has changed since.
- **Blizzard ToU wording** was read from the en-GB page (last updated October 1, 2019). The privacy-policy URL in PRIVACY.md (`blizzard.com/legal/privacy`) wasn't opened.
- **Why the v1.0.0 release workflow failed** (logs expired).
- **Whether every bundled native component** (e.g. inside `pywin32_system32`, the Qt plugins) carries further notice obligations beyond those listed. A full SBOM tool (e.g. `pip-licenses`, `cyclonedx-py`) would confirm. These weren't installed, to avoid adding dependencies without approval.
- **No dedicated secret scanner** (gitleaks/trufflehog) or SAST tool (bandit) was installed, for the same reason. The checks above used a custom scanner, targeted greps, manual review and OSV. Running gitleaks once (`gitleaks detect --log-opts="--all"`) is a recommended second opinion.
