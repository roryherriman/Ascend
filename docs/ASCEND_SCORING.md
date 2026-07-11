# Ascend Scoring v1.0

**Scoring Model Version:** 1.0.0  
**Analysis Engine Version:** 1.0.0  

---

## Overview

Ascend scores raid performance for a tracked character on a 0–100 scale. The score is *explainable* — every metric links back to its raw input, the weighting applied, and the reason for any penalty or bonus.

The model is designed to be **honest about data quality**: a character with 3 pulls gets a very different confidence rating than one with 50+. Scores from small samples carry explicit uncertainty bounds rather than pretending to statistical precision they don't have.

---

## Score Structure

```
Overall Score (0–100)
├── Category: Participation         weight=0.30
├── Category: Learning Velocity     weight=0.35
├── Category: Execution (Phase 2)   weight=0.25  [UNAVAILABLE until event data]
└── Category: Survivability (Ph2)   weight=0.10  [UNAVAILABLE until event data]
```

Each category produces a category score (0–100). The overall score is a weighted sum across available categories, re-normalized to 100 if any categories are unavailable.

---

## Categories

### Participation (weight: 30%)

Measures how consistently the character shows up and contributes to progression pulls.

| Metric | Description |
|--------|-------------|
| Raid Night Attendance | Fraction of raid nights present out of all tracked nights |
| Pull Participation Rate | Fraction of pulls on progression bosses where the character was in the raid |
| Consecutive Presence | Longest streak of consecutive raid nights attended |

**Status:** AVAILABLE (uses fight participant data synced from Warcraft Logs).

---

### Learning Velocity (weight: 35%)

Measures how quickly the character improves kill rate as pull count increases.

| Metric | Description |
|--------|-------------|
| Kill Rate Improvement | Change in kill rate between pull-range buckets (1–10 → 11–25 → 26–50 → 51+) |
| Per-Encounter Curve Slope | Rate of kill-rate improvement per additional 10 pulls |
| Stagnation Penalty | Applied when kill rate fails to improve across two or more pull-range buckets |

Kill-rate curves are computed per encounter, so a character who excels on mechanically complex bosses gets credit even if farmable bosses have flat curves.

**Status:** AVAILABLE (uses fight-level kill/wipe data synced from Warcraft Logs).

---

### Execution (weight: 25%) — Phase 2

Measures DPS consistency, mechanic adherence, and cooldown usage.

| Metric | Description |
|--------|-------------|
| DPS Consistency | Variance of DPS across pulls at similar progression stages |
| Mechanic Miss Rate | Frequency of mechanics-related deaths or failed casts |
| Defensive Usage | Defensives used per threat event |

**Status:** UNAVAILABLE — requires event-level data (Phase 3 ingestion). Will become active once Warcraft Logs event payloads are parsed.

---

### Survivability (weight: 10%) — Phase 2

Measures avoidable death rate and recovery.

| Metric | Description |
|--------|-------------|
| Avoidable Death Rate | Deaths attributed to avoidable damage / total pulls |
| Wipe Contribution | Estimated contribution to wipes from positioning or avoidable damage |

**Status:** UNAVAILABLE — requires event-level data (Phase 3 ingestion).

---

## Modifiers Applied to Each Metric

Every `MetricEvidence` entry in the score breakdown carries three multipliers that adjust how much the raw value counts toward the final score.

### Confidence Modifier (0.5 – 1.0)

Reduces the weight of metrics computed from uncertain or sparse data.

| Confidence Level | Modifier |
|-----------------|---------|
| HIGH | 1.00 |
| MODERATE | 0.80 |
| LOW | 0.60 |
| INSUFFICIENT_DATA | 0.50 |

Confidence is computed from:
- **Sample size**: fewer than 5 pulls → LOW; 5–19 → MODERATE; 20+ → HIGH.
- **Character detection**: if the character's name/server doesn't exactly match WCL actor data, confidence degrades by one tier.

### Sample Size Modifier (0.5 – 1.0)

Caps how much a metric can contribute when pull count is very low.

| Pulls | Modifier |
|-------|---------|
| 0–4 | 0.50 |
| 5–14 | 0.70 |
| 15–29 | 0.85 |
| 30+ | 1.00 |

### Progression Modifier (0.7 – 1.2)

Adjusts for whether pulls are genuinely progression (new content) or farm (previously cleared).

| Context | Modifier |
|---------|---------|
| Progression (never killed) | 1.10 |
| Recent progression (first clear < 4 weeks ago) | 1.00 |
| Farm (cleared 4+ weeks ago) | 0.85 |
| Mixed / unknown | 0.95 |

Progression kills are weighted higher than farm kills because they represent genuine improvement under uncertainty.

---

## Final Contribution Calculation

```
final_contribution = normalized_value
                   × confidence_modifier
                   × sample_size_modifier
                   × progression_modifier
```

Contributions are summed within a category and normalized to a 0–100 category score using the category baseline (expected contribution for an "average" raider in that category).

---

## Classification

The overall score maps to a classification:

| Score Range | Classification |
|-------------|----------------|
| 85–100 | Standout |
| 70–84 | Strong |
| 55–69 | Above Average |
| 40–54 | Average |
| 25–39 | Below Average |
| 0–24 | Significant Concerns |
| — | Insufficient Data |

When confidence is LOW or INSUFFICIENT_DATA for the majority of active categories, the classification defaults to **Insufficient Data** regardless of numeric score.

---

## Coverage and Confidence

Two aggregate metadata fields supplement the score:

- **Coverage ratio**: fraction of the weighted score that comes from AVAILABLE (vs UNAVAILABLE) categories. A score with coverage=0.65 means 65% of the possible weight was computable from current data.
- **Confidence level**: aggregate of the per-metric confidence values. HIGH requires the majority of metrics at high confidence; MODERATE is the default for most early-progression profiles.

---

## What the Score Is Not

- **Not a DPS meter rank**: Ascend does not rank by damage output. DPS and HPS data will feed into the Execution category in Phase 2, but raid utility, mechanic adherence, and attendance are given at least equal weight.
- **Not a percentile vs. global population**: Ascend scores are self-referential — the baseline is the character's own pull history and attendance record, not a comparison against all WCL players.
- **Not final**: Scoring v1.0 covers Participation and Learning Velocity. Phase 2 will add Execution and Survivability when event-level data is ingested. The scoring model version is stored with each computed score so historical results can be recalculated when the model updates.

---

## Implementation Notes

- Source: `ascend/analysis/scoring_engine.py`, `ascend/analysis/scoring_models.py`
- Scoring is computed on-demand in `InsightsPage.reload()` — results are not persisted to SQLite in v1.0. A caching layer is planned for Phase 2.
- `ScoreBreakdown`, `CategoryScore`, and `MetricEvidence` are fully typed dataclasses with no mutable state. Safe to call from background workers.
- `SCORING_MODEL_VERSION = "1.0.0"` (see `ascend/metadata.py`) is incremented when the model changes in a way that invalidates previously computed scores.
