# Architecture

## Layers

```
ui/          PySide6 pages and dialogs - no direct SQL, no direct HTTP calls
services/    Orchestration: background workers, sync, (later) analysis/export/discord
api/         Warcraft Logs OAuth + GraphQL client, URL parsing
data/        SQLite access: database, migrations, repositories, models, secure storage
analysis/    (Phase 2+) metrics, scoring, comparisons, insights, readiness
reports/     (Phase 3+) HTML/CSV/JSON/PDF export and charts
```

`ui/` pages depend on `services/` and `data/repositories`, never on raw SQL or
`requests` directly. `services/sync_service.py` is the only place that turns
a Warcraft Logs API response into database rows.

## Application startup (`app.py`)

1. Load `.env` if present (optional dev convenience only - see `.env.example`).
2. Read the bootstrap config (`%LOCALAPPDATA%\Ascend\config.json`) to find the
   data directory and whether Demo Mode is active.
3. Set up rotating file logging.
4. Open the SQLite database (`ascend.db`, or `ascend_demo.db` in Demo Mode)
   and apply any pending migrations.
5. If Demo Mode is active, seed the bundled sanitized sample report.
6. If this is the first run, show the setup wizard.
7. Show `MainWindow`.

## Background work

All API calls and (later) analysis run through
`services/background_worker.py`'s `BackgroundTaskManager`, built on
`QThreadPool`/`QRunnable`. Each `BackgroundTask` carries its own
`CancellationToken` and a `WorkerSignals` object (`started`, `progress`,
`finished`, `error`, `cancelled`). Worker functions take the shape:

```python
def worker(progress_callback, cancel_token, *args, **kwargs) -> Any: ...
```

They should check `cancel_token.is_cancelled` between database-committing
units of work (e.g. per fight) so cancellation never leaves a half-written
row - and should return normally (not raise) when cancelled, letting the
caller emit the `cancelled` signal.

Each `BackgroundTaskManager` owns its own `QThreadPool` (not Qt's
process-wide global one) so unrelated background work never contends with
it, and so tests stay isolated from each other.

## Session recovery

`data/repositories.py::SessionOperationRepository` records an `app_session`
row with status `started` at launch. On the *next* launch, before starting a
new one, Ascend marks any still-`started` row as `interrupted` - that's how
an unclean shutdown (crash, force-quit) gets surfaced (status bar +
Diagnostics page) instead of silently ignored. `MainWindow.closeEvent` marks
the current session `completed` and is idempotent (guarded so a repeated
`close()` - e.g. in tests - never double-writes to an already-closed
connection).

Full workflow-level session recovery (resuming a partially-completed sync)
is a Phase 2/3 concern once there's a multi-step sync workflow to resume.

## Demo Mode

Demo Mode never shares a database with real data: `Database.default_path_instance()`
picks `ascend_demo.db` instead of `ascend.db` based on a `demo_mode` flag in
the bootstrap config (needed before SQLite can even be opened, so it can't
live in the database itself). Toggling it in Settings requires a restart. A
persistent "DEMO DATA" banner is shown across the whole window while active.

## Data provenance and raw-data preservation

`services/sync_service.py` stores the *raw* Warcraft Logs GraphQL response in
the `api_cache` table (via `ApiCacheRepository`) before normalizing it into
`reports`/`fights` rows. This means future analysis-engine improvements can
reprocess a report from its cached raw response instead of re-hitting the
API - see [DATA_MODEL.md](DATA_MODEL.md).

## GUI structure

`navigation.py` defines the 18 sidebar sections. `main_window.py` builds one
page per section; sections without Phase 1 functionality get a
`PlaceholderPage` stating which phase implements them (see
`MainWindow.PLACEHOLDER_NOTES`). This keeps the full information architecture
visible and navigable from day one without pretending unbuilt features work.
