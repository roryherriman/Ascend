# Data Model

SQLite database (`ascend.db` / `ascend_demo.db` in Demo Mode), versioned via
`ascend/data/migrations.py`'s `schema_version` table. Each migration is
additive (`CREATE TABLE IF NOT EXISTS`) so existing installs upgrade in
place; new phases add new migrations rather than editing old ones.

## Phase 1 schema (migrations 1-2)

| Table | Purpose |
|---|---|
| `characters` | User-managed roster of tracked characters (never hardcoded) |
| `reports` | One row per Warcraft Logs report, keyed uniquely by `report_code` |
| `fights` | One row per fight/pull, unique on `(report_id, fight_id)` - prevents duplicate pull ingestion |
| `settings` | Non-secret key/value settings (JSON-encoded values) |
| `sync_history` | Per-sync-operation audit log (status, counts, errors) |
| `api_cache` | Raw Warcraft Logs API responses, keyed by cache key (e.g. `report:<code>`) |
| `session_operations` | App-lifecycle tracking for crash/unclean-shutdown detection |
| `analysis_runs` | Which app/analysis-engine/scoring-model version produced an analysis (schema only until Phase 2/3's engine exists) |

## Phase 2 schema (migration 4)

| Table | Purpose |
|---|---|
| `fight_participants` | One row per player actor present in a fight (from `ReportMasterData.actors`, matched against `Fight.friendlyPlayers`), unique on `(fight_id, actor_id)`. `character_id` is set when the actor's name+server matches a tracked Character - see `ascend/services/character_detection.py` - and is `NULL` otherwise (an untracked raid-team member). |

Secrets are deliberately **not** in this list - see `docs/SECURITY.md`.

## Duplicate prevention

- `reports.report_code` is `UNIQUE`; `ReportRepository.upsert_report` updates
  the existing row instead of inserting a new one.
- `fights` has a `UNIQUE(report_id, fight_id)` constraint;
  `ReportRepository.upsert_fight` uses `ON CONFLICT ... DO UPDATE`.

## Raw data preservation and reanalysis

`ApiCacheRepository` stores the exact raw GraphQL response for each fetched
report before any normalization happens. This is what "raw-data
preservation" means in Phase 1: even though only a normalized subset (title,
zone, fights, etc.) is written into `reports`/`fights` today, the full
response is retained so a smarter Phase 2/3 analysis engine can be re-run
against already-downloaded data without an extra API call.

`analysis_runs` (empty until Phase 2/3 ships an analysis engine) is where
each analysis will record the `app_version` / `analysis_engine_version` /
`scoring_model_version` / `encounter_rule_version` that produced it, per
`ascend/metadata.py`. When any of those versions bump, Ascend will be able to
detect stale analyses and offer "Reanalyze Using Local Data" instead of
redownloading.

## Bootstrap config (outside SQLite)

`%LOCALAPPDATA%\Ascend\config.json` holds `data_dir`, `export_dir`, and
`demo_mode` - these must be known *before* SQLite can be opened, so they
can't live inside the database itself.
