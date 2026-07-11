# Changelog

All notable changes to Ascend are documented here.

---

## [1.0.0] — 2026-07-11

First production-ready release. Covers the full 15-PR Ascend productization sequence.

### Added

**PR 1 — Branding, navigation restructure, global context bar**
- Renamed app from WCLTracker to Ascend throughout
- Grouped sidebar navigation (Analysis, Data, Tools, App)
- Global context bar showing active guild, tier, and character

**PR 2 — Character cards, Blizzard class icon pipeline, simplified dialog**
- Character cards with WoW class colors and custom glyph icons
- Class icon pipeline (original SVG art, no copyright-encumbered assets)
- Simplified Add Character dialog (region/realm/name)

**PR 3 — Blizzard guild crest API, Battle.net credentials, polished badge**
- Optional Battle.net credentials for guild emblem fetching
- Guild crest stored locally in guild_icons cache
- Fallback initials badge when no API credentials configured

**PR 4 — Wizard reduced to 5 steps, tier auto-detect**
- First-run wizard condensed: credentials → characters → tier → guild → done
- Tier auto-detected from Warcraft Logs zones API; manual override available
- `guild_rank` column removed (not computable from available WCL data)

**PR 5 — Guild discovery: sync reports from WCL guild roster**
- `guild_discovery` report sync: pulls recent guild reports from WCL API
- `report_source` field (`"manual"` | `"guild_discovery"`) on all Report rows
- Migration 10 adds `report_source` column with backward-compat default

**PR 6 — Zone/tier filters on Encounter and Progression pages**
- Zone filter dropdown on EncounterPage and EncounterProgressionPage
- Tier filter (active tier / all tiers) persisted across page reloads
- `distinct_encounters_for_zone()` repository query

**PR 7 — Source filter and count label on Reports page**
- "All / Manual / Guild Discovery" filter on Reports page
- Report count label ("X of N reports") updates on every filter change
- Fixed `fake_sync` test helpers missing `**kwargs` after PR 5 signature change

**PR 8 — `report_source` provenance tracking tests**
- Integration tests for source filter: manual-only and guild-discovery-only views
- Count label test with mixed sources
- Newest-first sort verified

**PR 9 — Fix encounterID=0 trash fight regression**
- WCL trash fights (`encounterID=0`) normalized to `None` during sync
- `distinct_encounters()`, `distinct_encounters_for_zone()`, `encounters_for_character()` all guard `encounter_id > 0`
- Unknown actors in `friendlyPlayers` (missing from masterData) stored as minimal `FightParticipant` rows instead of silently dropped

**PR 10 — Remove AnalyzeBar as primary Dashboard entry point**
- `NoDataState` and `ImportedIncompleteState` replaced AnalyzeBar with "Open Report Library" button
- `ActiveAnalyticsState` removed `_build_quick_analyze()` method
- DashboardPage wires `open_reports_requested` signal to sidebar navigation

**PR 11 — Raid Night Summary: QTabWidget for Pulls / Roster / Notes**
- `RaidNightSummaryPage` detail panel replaced side-by-side layout with three-tab `QTabWidget`
- Fixed mojibake: `"Kill âœ""` → `"Kill ✓"` (U+2713 check mark)

**PR 12 — Remove QTableWidget from Roster and Trends pages**
- `RosterComparisonPage`: replaced QTableWidget with `QFrame`-based scrollable row layout
- `TrendsPage`: replaced both QTableWidget instances with frame-based row containers; `_BarWidget` kept as custom paint widget

**PR 13 — Remove QTableWidget from Insights and Data Quality pages**
- `InsightsPage`: `_metric_table()` replaced with `_metric_rows_widget()` / `_metric_col_header()` / `_metric_row()` frame-based rows
- `DataQualityPage`: `confidence_table` and `sync_table` replaced with `_confidence_rows_layout` / `_sync_rows_layout` frame-based layouts
- No `QTableWidget` remains in any page UI (only QSS selector in `styles/tables.py`)

**PR 14 — Local WoW combat log detection and upload workflow**
- `ascend/services/combat_log.py`: scans all drive letters for `WoWCombatLog.txt` (Retail, Classic Era, Classic/Cataclysm variants)
- Settings page: "WoW Combat Log" group with detection status, Rescan button, and "Open Warcraft Logs Upload" button
- `ASCEND_WOW_ROOT` environment variable for test overriding

**PR 15 — Final packaging, scoring documentation, release candidate**
- Version bumped to `1.0.0`; `SCORING_MODEL_VERSION` and `ANALYSIS_ENGINE_VERSION` to `1.0.0`
- `docs/ASCEND_SCORING.md`: complete Ascend Scoring v1.0 specification (categories, modifiers, classification, data quality)
- `CHANGELOG.md`: this file

### Architecture highlights

- **Zero QTableWidget**: all data tables replaced with `QFrame`-based row layouts for consistent theming and scroll performance
- **No AnalyzeBar on Dashboard**: entry point is Report Library navigation; dashboard shows state-appropriate guidance
- **Card-first UI**: every list-like surface (roster, trends, reports, encounters, data quality) uses the shared `QFrame` card pattern with `PALETTE` tokens
- **Scoring explainability**: every metric carries `raw_value`, `normalized_value`, `confidence_modifier`, `sample_size_modifier`, `progression_modifier`, `final_contribution`, and `note`
- **Secrets policy**: Battle.net and WCL client secrets stored only in Windows Credential Manager (or DPAPI fallback); never in SQLite, config files, logs, exports, or the built binary

### Test coverage

389 tests (pytest) covering data layer, API layer, sync service, scoring engine, and all UI pages.

---

## [0.2.0] — 2026-06

Phase 2 completion: character detection, reports/encounter/roster/data-quality pages, scoring engine foundation.

## [0.1.0] — 2026-05

Phase 1: SQLite data layer, WCL API client, background worker, basic GUI shell.
