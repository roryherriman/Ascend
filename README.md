# Ascend

**Progression Performance Intelligence** for competitive World of Warcraft raiders.

Ascend is a local-first Windows desktop application that analyzes your raid
performance using the official [Warcraft Logs API v2](https://www.warcraftlogs.com/api/docs)
(OAuth client-credentials + GraphQL). It does not scrape Warcraft Logs web
pages, and it is not another parse-color viewer - the goal is evidence-based
answers to questions like *am I improving during progression?*, *how quickly
do I correct mistakes?*, and *is there real evidence I'm a standout player?*

> Ascend is an independent, unofficial tool. It is not affiliated with,
> endorsed by, or sponsored by Blizzard Entertainment or Warcraft Logs.

## Development status: Phase 1 (Foundation)

This drop delivers the application shell and the plumbing everything else
builds on. It does **not** yet compute scores, insights, or readiness - see
[docs/ROADMAP.md](docs/ROADMAP.md) for what's implemented vs. planned.

**Implemented in Phase 1:**
- Ascend branding, dark-themed PySide6 shell, sidebar navigation (18 sections)
- Centralized theme + reusable widgets (stat cards, banners, progress panels)
- Settings page: Warcraft Logs credentials, scoring weights, thresholds,
  sample-size minimums, cache/timeout, Discord webhook, data/export locations,
  Demo Mode toggle
- Secure credential storage via Windows Credential Manager, with a clearly
  flagged encrypted (DPAPI) local fallback
- Character management (add/edit/remove/enable), stored in SQLite - never
  hardcoded
- Warcraft Logs OAuth client-credentials authentication + Test Connection
- A Warcraft Logs report URL/code parser (`ascend/api/url_parser.py`)
- Basic report retrieval: paste a URL or report code, fetch report + fight
  metadata, store it, with duplicate-safe upserts
- SQLite storage with versioned migrations, raw-API-response preservation,
  and an analysis-versioning schema for future reanalysis
- Background worker infrastructure (`QThreadPool`/`QRunnable`) so API calls
  never freeze the GUI, with progress + cancellation
- Session-operation tracking (detects an unclean previous shutdown)
- Rotating local logging and a Diagnostics page (never logs or displays
  secrets)
- Demo Mode architecture (a fully separate database seeded with sanitized
  sample data)
- A first-run setup wizard shell
- Unit tests (56 passing) using sanitized mock API responses - no live API
  calls during tests

**In progress / planned:** see [docs/ROADMAP.md](docs/ROADMAP.md).

## Local-first architecture

Warcraft Logs data, analysis results, settings, encounter rules, and history
stay on your computer. Nothing is uploaded anywhere except the report codes
you explicitly fetch from Warcraft Logs, and summaries you explicitly post to
Discord (Phase 4).

## Stack

Python 3.11+, PySide6, SQLite, Warcraft Logs API v2 (OAuth client-credentials
+ GraphQL), Plotly (for later charts), PyInstaller, pytest, keyring/pywin32
for secure storage.

## Getting started (Windows)

1. Install Python 3.11+ (check "Add python.exe to PATH" during install).
2. Double-click **`setup.bat`** - creates a virtual environment, installs
   dependencies, and runs the test suite.
3. Double-click **`run_app.bat`** to launch Ascend.
4. On first launch, the setup wizard walks you through Warcraft Logs
   credentials, characters, and preferences. You can also configure
   everything later from **Settings**.

No command line is required after the initial `setup.bat` run. After a
Phase 4 build, you'll be able to just double-click `Ascend.exe`.

## Security and privacy

- Your Warcraft Logs client secret and Discord webhook URL are **never**
  stored in plain text in SQLite, YAML, or source code.
- They're stored via the Windows Credential Manager (through the `keyring`
  package). If that's unavailable, Ascend falls back to a DPAPI-encrypted
  local file tied to your Windows login, and clearly warns you in Settings
  when this fallback is active.
- Access tokens are cached in memory only - never logged, displayed, or
  exported.
- See [docs/SECURITY.md](docs/SECURITY.md) for details.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - app structure, data flow, session recovery
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) - SQLite schema and versioning
- [docs/WCL_API.md](docs/WCL_API.md) - verified Warcraft Logs API v2 usage
- [docs/SECURITY.md](docs/SECURITY.md) - credential storage and logging policy
- [docs/ROADMAP.md](docs/ROADMAP.md) - phase-by-phase feature plan
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - dev setup, testing, branching

## Known limitations (Phase 1)

- No scoring, classification, insights, readiness, or roster comparison yet -
  Dashboard cards are placeholders until Phase 2/3.
- "Analyze a Raid Night" currently performs URL parsing + basic report/fight
  retrieval only; full character detection, metrics, and summaries land in
  Phase 2.
- Most sidebar sections (Raid Night Summary, Encounter Analysis, Death
  Review, Roster Comparison, Learning and Trends, Insights, Readiness, Goals,
  Raid Night Comparison, Encounter Progression, Encounter Rules, Data
  Quality, Export and Discord) are placeholders that state which phase they
  arrive in.
- The Windows executable build (`build_windows.bat`) works but isn't yet
  polished with icons/portable packaging - that's Phase 4.

## Testing

```
setup.bat
```

runs the full suite automatically. To re-run manually:

```
call .venv\Scripts\activate.bat
pytest -q
```

All tests use sanitized mock API responses; no live Warcraft Logs API calls
are made during the test suite.
