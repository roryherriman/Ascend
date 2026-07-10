"""The 7 scoring categories. Each is computed strictly from data Ascend has
already verified and ingested (Phase 1/2's reports/fights/fight_participants)
- none of this guesses at Warcraft Logs event-payload field names. Where the
required data doesn't exist yet, the category is explicitly UNAVAILABLE
(never silently scored as 0, per "missing data reduces confidence rather
than score").

See docs/SCORING.md for the full per-category rationale.
"""
from __future__ import annotations

from ascend.analysis.confidence import (
    confidence_from_sample_size,
    confidence_modifier_value,
    sample_size_modifier,
)
from ascend.analysis.scoring_models import CategoryScore, CategoryStatus, MetricEvidence
from ascend.data.database import Database
from ascend.data.repositories import ReportRepository
from ascend.services.encounter_classification import group_by_pull_range

# Category weights out of 100 - see docs/SCORING.md.
CATEGORY_WEIGHTS: dict[str, int] = {
    "survival": 22,
    "execution": 20,
    "damage": 18,
    "consistency": 14,
    "learning": 10,
    "utility": 8,
    "participation": 8,
}


def _unavailable_category(name: str, candidate_metrics: list[str], reason: str) -> CategoryScore:
    metrics = [
        MetricEvidence(
            metric_name=metric_name,
            raw_value=None,
            normalized_value=None,
            comparison_baseline="n/a - not computable yet",
            weight=1.0 / len(candidate_metrics),
            confidence_modifier=0.0,
            sample_size_modifier=0.0,
            progression_modifier=1.0,
            final_contribution=None,
            note=reason,
        )
        for metric_name in candidate_metrics
    ]
    return CategoryScore(
        name=name, weight=CATEGORY_WEIGHTS[name], status=CategoryStatus.UNAVAILABLE,
        score=None, metrics=metrics, note=reason,
    )


# -- Participation ----------------------------------------------------------

def compute_participation_category(db: Database, character_id: int) -> CategoryScore:
    eligible, participated = ReportRepository(db).participation_counts(character_id)
    name = "participation"
    if eligible == 0:
        return CategoryScore(
            name=name, weight=CATEGORY_WEIGHTS[name], status=CategoryStatus.UNAVAILABLE,
            score=None, note="No raid nights synced yet.",
        )

    rate = participated / eligible
    normalized = rate * 100
    confidence = confidence_from_sample_size(eligible)
    conf_mod = confidence_modifier_value(confidence)
    size_mod = sample_size_modifier(eligible)
    # Attendance, not pull performance - progression/farm weighting doesn't
    # semantically apply to whether you showed up, so this stays neutral.
    progression_mod = 1.0
    final = normalized * conf_mod * size_mod * progression_mod

    metric = MetricEvidence(
        metric_name="Eligible-pull participation rate",
        raw_value=f"{participated}/{eligible}",
        normalized_value=round(normalized, 1),
        comparison_baseline="all fights logged across every synced raid night",
        weight=1.0,
        confidence_modifier=conf_mod,
        sample_size_modifier=size_mod,
        progression_modifier=progression_mod,
        final_contribution=round(final, 1),
        supporting_refs=[f"{participated} of {eligible} synced pulls"],
        note="Absence from a pull is not treated as unavailability or unreliability - "
             "it's simply not counted as participation.",
    )
    return CategoryScore(
        name=name, weight=CATEGORY_WEIGHTS[name], status=CategoryStatus.AVAILABLE,
        score=round(final, 1), metrics=[metric],
    )


# -- Learning (partial) ------------------------------------------------------

def compute_learning_category(db: Database, character_id: int) -> CategoryScore:
    name = "learning"
    reports_repo = ReportRepository(db)
    encounters = reports_repo.encounters_for_character(character_id)

    metrics: list[MetricEvidence] = []
    total_pulls_considered = 0
    for encounter_id, encounter_name in encounters:
        pairs = reports_repo.fights_for_encounter(encounter_id)
        fights = [fight for _report, fight in pairs]

        # group_by_pull_range already restricts to progression pulls (up to
        # and including the first kill at each difficulty) - see
        # ascend/services/encounter_classification.py.
        groups = group_by_pull_range(fights)
        if len(groups) < 2:
            continue  # not enough pull-range diversity to measure a trend

        first_bucket, last_bucket = groups[0], groups[-1]
        first_wipe_rate = 1 - (first_bucket["kills"] / first_bucket["pulls"])
        last_wipe_rate = 1 - (last_bucket["kills"] / last_bucket["pulls"])
        trend = first_wipe_rate - last_wipe_rate  # positive = wipe rate improved (went down)
        normalized = max(0.0, min(100.0, 50 + trend * 50))
        pulls_considered = sum(g["pulls"] for g in groups)
        total_pulls_considered += pulls_considered

        confidence = confidence_from_sample_size(pulls_considered)
        conf_mod = confidence_modifier_value(confidence)
        size_mod = sample_size_modifier(pulls_considered)
        final = normalized * conf_mod * size_mod

        metrics.append(MetricEvidence(
            metric_name=f"Wipe-rate trend: {encounter_name}",
            raw_value=f"{first_wipe_rate:.0%} -> {last_wipe_rate:.0%}",
            normalized_value=round(normalized, 1),
            comparison_baseline=f"{first_bucket['label']} vs. {last_bucket['label']} (progression pulls only)",
            weight=1.0 / max(len(encounters), 1),
            confidence_modifier=conf_mod,
            sample_size_modifier=size_mod,
            progression_modifier=1.0,  # already restricted to progression-weighted pulls
            final_contribution=round(final, 1),
            supporting_refs=[encounter_name],
            note="Whether the pull-to-pull wipe rate improved across the progression attempt - "
                 "a coarse proxy. This does not measure repeated-error correction speed on a "
                 "specific mechanic, which needs verified event data Ascend doesn't have yet.",
        ))

    if not metrics:
        return CategoryScore(
            name=name, weight=CATEGORY_WEIGHTS[name], status=CategoryStatus.UNAVAILABLE,
            score=None,
            note="No encounter has enough progression pull-range diversity yet (needs pulls "
                 "spanning at least two of the 1-10/11-25/26-50/51+ buckets) to measure a trend.",
        )

    weighted_scores = [m.final_contribution * m.weight for m in metrics if m.final_contribution is not None]
    score = sum(weighted_scores) / sum(m.weight for m in metrics) if metrics else None

    return CategoryScore(
        name=name, weight=CATEGORY_WEIGHTS[name], status=CategoryStatus.PARTIAL,
        score=round(score, 1) if score is not None else None,
        metrics=metrics,
        note="Partial: measures wipe-rate trend as a proxy for learning speed. Repeated-error "
             "correction speed and performance stabilization need verified event data that "
             "isn't ingested yet.",
    )


# -- Categories that are currently entirely unavailable ----------------------

def compute_survival_category(db: Database, character_id: int) -> CategoryScore:
    return _unavailable_category(
        "survival",
        ["Pull survival rate", "First-death rate", "Early-death rate", "Death-order percentile"],
        "Requires parsed death-event data. Ascend only has unparsed raw Warcraft Logs death "
        "evidence pending a verified payload schema - see the Death Review page and "
        "docs/SCORING.md's Death Review Parser section.",
    )


def compute_execution_category(db: Database, character_id: int) -> CategoryScore:
    return _unavailable_category(
        "execution",
        ["Confirmed mechanic success", "Confirmed mechanic failures",
         "Repeated confirmed failure rate", "Assigned mechanic success"],
        "Requires configured encounter rules (Phase 4's Encounter Rules editor) and verified "
        "event evidence, neither of which exist yet.",
    )


def compute_damage_category(db: Database, character_id: int) -> CategoryScore:
    return _unavailable_category(
        "damage",
        ["Boss-damage roster percentile", "Priority-target roster percentile",
         "Active-time-adjusted damage", "Time-alive context"],
        "Requires ingested damage/event data, which Ascend does not fetch or parse yet.",
    )


def compute_consistency_category(db: Database, character_id: int) -> CategoryScore:
    return _unavailable_category(
        "consistency",
        ["Pull-to-pull variance", "Performance floor", "Outlier failure rate",
         "Frequency of catastrophic low-performance pulls"],
        "Requires a per-pull performance metric (from Damage/Execution) that doesn't exist "
        "yet - Consistency depends on those categories being available first.",
    )


def compute_utility_category(db: Database, character_id: int) -> CategoryScore:
    return _unavailable_category(
        "utility",
        ["Personal defensive usage", "Healthstone/potion usage", "Interrupts", "Dispels",
         "Class utility", "Configured assignments"],
        "Requires ingested event data and, for assignments, configured encounter rules - "
        "neither exists yet. No opportunity data means neutral, not a penalty.",
    )
