# Roadmap

Ascend is built as a stable vertical slice first, then expanded. Do not
assume anything not listed as "Implemented" actually works yet.

## Phase 1 - Foundation (this drop)

Implemented: Ascend branding, PySide6 shell, sidebar nav (18 sections), dark
theme, Settings, secure credentials, character management, Warcraft Logs
OAuth + Test Connection, report-code entry, Dashboard URL input, URL parser,
basic report retrieval, SQLite storage + migrations, analysis-versioning
schema, raw-data preservation, background-worker infrastructure, Dashboard
placeholders, first-run wizard shell, Demo Mode architecture, logging,
Diagnostics, session-operation tracking, setup/run scripts, tests, GitHub
repo/issues/labels/milestones, this documentation.

## Phase 2 - Raid Night Analysis

Report discovery, fight ingestion, character detection, the full "Analyze
Raid Night" vertical slice, objective pull metrics, Reports table, Raid
Night Summary, pull table + pull detail + evidence panels, Encounter
Analysis page, progression vs. farm classification, basic roster
comparisons, a functional Dashboard, basic Insights, Data Quality
indicators, manual annotations, baseline architecture, local-data
reanalysis.

## Phase 3 - Performance Intelligence

Event ingestion, Death Review, defensive/consumable usage, damage
consistency, learning-speed analysis, advanced Insights, explainable
scoring, Goals, Raid Night Comparison, Encounter Progression timeline,
guild-rank history, Readiness assessment, analysis-engine migrations,
reanalysis workflow, HTML/CSV/JSON export.

## Phase 4 - Release

Encounter-rule editor, priority-target scoring, advanced mechanic
classification, Discord summaries, PDF export, polished Windows executable,
portable release packaging, About Ascend dialog, update-check placeholder,
complete documentation, release validation.

## Non-goals (for now)

- Web/cloud version - Ascend is a local Windows desktop app by design.
- Scraping warcraftlogs.com - only the official API is used.
- Guaranteeing recruitment outcomes - Readiness (Phase 3) evaluates whether
  data *supports* a classification; it never promises results.
