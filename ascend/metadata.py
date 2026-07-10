"""Central application identity and version metadata for Ascend.

Single source of truth for anything shown in window titles, the About
dialog (Phase 4), diagnostics, exports, and Discord summaries.
"""
from __future__ import annotations

APP_NAME = "Ascend"
APP_TAGLINE = "Progression Performance Intelligence"
APP_VERSION = "0.1.0"
BUILD_NUMBER = "1"
COPYRIGHT = "Copyright (c) 2026 Rory Herriman"

GITHUB_REPO = "roryherriman/Ascend"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
WARCRAFT_LOGS_URL = "https://www.warcraftlogs.com"

# Bumped independently of APP_VERSION when the analysis/scoring logic changes,
# so stored analyses can be flagged as needing reanalysis (see docs/DATA_MODEL.md).
ANALYSIS_ENGINE_VERSION = "0.1.0"
SCORING_MODEL_VERSION = "0.1.0"
ENCOUNTER_RULE_SCHEMA_VERSION = "0.1.0"

DISCLAIMER = (
    "Ascend is an independent, unofficial tool. It is not affiliated with, "
    "endorsed by, or sponsored by Blizzard Entertainment or Warcraft Logs."
)
