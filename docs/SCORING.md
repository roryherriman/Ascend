# Ascend Scoring v1.0

Ascend assigns every tracked character a score from 0–100 derived entirely
from data that has been imported and verified within the application. No
user-configured weights or tunable knobs exist in v1 — the methodology is
fixed and documented here so it can be inspected and challenged.

## Design principles

1. **Missing data reduces confidence, not score.** A category that cannot be
   computed from available data is marked `UNAVAILABLE`. It contributes zero
   weight to the overall score rather than pulling the number down. The
   overall confidence level reflects how much of the possible scoring weight
   is actually backed by data.

2. **All categories and their weights are fixed.** They are not adjustable
   in the UI. A future Scoring v2 may revise the weights, but doing so will
   be visible in the changelog and will produce a new version number.

3. **Every number is explainable.** The UI shows the full evidence trail:
   raw metric value → normalized score → confidence modifier → sample size
   modifier → final contribution. Nothing is aggregated silently.

4. **Standout requires everything.** The top classification (`Standout`)
   requires High confidence, a minimum progression sample of 50 pulls, and
   all survival/damage/consistency/execution categories to be AVAILABLE with
   no single category below 70. This cannot be awarded today because those
   categories require event-level data not yet ingested.

---

## Category weights

| Category      | Weight |
|---------------|--------|
| Survival      | 22     |
| Execution     | 20     |
| Damage        | 18     |
| Consistency   | 14     |
| Learning      | 10     |
| Utility       | 8      |
| Participation | 8      |
| **Total**     | **100**|

---

## Overall score formula

```
overall_score = sum(category.score × category.weight for available categories)
              / sum(category.weight for available categories)
```

Only categories in `AVAILABLE` or `PARTIAL` status with a non-`None` score
are included. `UNAVAILABLE` categories are excluded from both numerator and
denominator.

---

## Classification thresholds

| Score range | Classification       |
|-------------|----------------------|
| ≥ 90        | Standout ★           |
| ≥ 80        | Strong               |
| ≥ 70        | Above Average        |
| ≥ 55        | Average              |
| ≥ 40        | Below Average        |
| < 40        | Significant Concerns |
| —           | Insufficient Data    |

`Insufficient Data` is used when:
- Overall confidence is `INSUFFICIENT_DATA`, **or**
- Less than 50% of the total scoring weight is backed by available data
  (`MIN_COVERAGE_RATIO_FOR_CLASSIFICATION = 0.5`).

---

## Confidence levels

Confidence is derived from sample size (participated pulls):

| Pulls | Confidence level  |
|-------|-------------------|
| < 5   | Insufficient Data |
| 5–19  | Low               |
| 20–49 | Moderate          |
| ≥ 50  | High              |

Data completeness modifiers can downgrade confidence further:
- Missing encounter rules → step down one level
- Partial event ingestion → step down one level
- Unknown character identity → force to Insufficient Data

---

## Current availability (v1.0)

| Category      | Status      | Reason                                    |
|---------------|-------------|-------------------------------------------|
| Participation | AVAILABLE   | Computed from fight_participants counts   |
| Learning      | PARTIAL     | Pull-count improvement curve available    |
| Survival      | UNAVAILABLE | Requires event-level death data           |
| Execution     | UNAVAILABLE | Requires mechanic rule definitions        |
| Damage        | UNAVAILABLE | Requires parsed DPS/HPS event data        |
| Consistency   | UNAVAILABLE | Requires performance variance across pulls|
| Utility       | UNAVAILABLE | Requires parsed interrupt/cooldown data   |

As a result, no character can currently be awarded `Standout` (correct by
design — the data required to justify that classification does not yet exist
in Ascend).

---

## Version history

| Version | Date       | Change                                      |
|---------|------------|---------------------------------------------|
| 1.0     | 2026-07-11 | Initial fixed-weight scoring specification  |
