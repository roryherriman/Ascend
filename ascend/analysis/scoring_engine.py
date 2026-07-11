"""Combines the 7 categories into one explainable ScoreBreakdown. See
docs/SCORING.md for the full formulas this module implements.
"""
from __future__ import annotations

SCORING_VERSION = "1.0"

from ascend.analysis.categories import (
    compute_consistency_category,
    compute_damage_category,
    compute_execution_category,
    compute_learning_category,
    compute_participation_category,
    compute_survival_category,
    compute_utility_category,
)
from ascend.analysis.confidence import apply_data_completeness_modifiers, confidence_from_sample_size
from ascend.analysis.scoring_models import (
    CategoryScore,
    CategoryStatus,
    Classification,
    ConfidenceLevel,
    ScoreBreakdown,
)
from ascend.data.database import Database
from ascend.data.repositories import CharacterRepository, ReportRepository

# score >= threshold -> classification, checked highest-first.
_CLASSIFICATION_THRESHOLDS: list[tuple[int, Classification]] = [
    (90, Classification.STANDOUT),
    (80, Classification.STRONG),
    (70, Classification.ABOVE_AVERAGE),
    (55, Classification.AVERAGE),
    (40, Classification.BELOW_AVERAGE),
    (0, Classification.SIGNIFICANT_CONCERNS),
]

# Documented extension beyond the user's explicit sample-size rule: if less
# than half the total 100-point weight is actually backed by data, showing
# a classification would overstate what Ascend actually knows, regardless
# of how many pulls were logged - so confidence is forced to
# INSUFFICIENT_DATA rather than just being based on pull count alone.
MIN_COVERAGE_RATIO_FOR_CLASSIFICATION = 0.5

# Documented choice: the spec requires "minimum progression sample size"
# for Standout but doesn't give a specific number - this reuses the same
# 50-pull threshold that separately yields High confidence, since Standout
# already requires High confidence anyway.
STANDOUT_MIN_SAMPLE_SIZE = 50

_CATEGORY_COMPUTERS = {
    "survival": compute_survival_category,
    "execution": compute_execution_category,
    "damage": compute_damage_category,
    "consistency": compute_consistency_category,
    "learning": compute_learning_category,
    "utility": compute_utility_category,
    "participation": compute_participation_category,
}


def _classify(score: float) -> Classification:
    for threshold, classification in _CLASSIFICATION_THRESHOLDS:
        if score >= threshold:
            return classification
    return Classification.SIGNIFICANT_CONCERNS  # unreachable (0 is the last threshold), kept for safety


def _meets_standout_extra_criteria(
    categories: dict[str, CategoryScore], confidence: ConfidenceLevel, sample_size: int
) -> bool:
    """Standout requires High confidence, a minimum progression sample,
    below-median first-death/failure rates, above-median damage and
    consistency, and no major category below 70. Survival/Damage/
    Consistency/Execution are all UNAVAILABLE today (no event/damage data
    ingested yet), so this can never currently return True - that's
    correct, not a bug: Ascend has no basis to award its top classification
    without the data those checks depend on."""
    if confidence != ConfidenceLevel.HIGH or sample_size < STANDOUT_MIN_SAMPLE_SIZE:
        return False
    required_available = ("survival", "damage", "consistency", "execution")
    if any(categories[name].status != CategoryStatus.AVAILABLE for name in required_available):
        return False
    if any((c.score or 0) < 70 for c in categories.values() if c.score is not None):
        return False
    # Roster-median comparisons (first-death rate, confirmed-failure rate,
    # damage, consistency vs. the rest of the roster) aren't implemented -
    # they need the above categories to exist first, which the check above
    # already guarantees never happens today.
    return True


def compute_score(db: Database, character_id: int) -> ScoreBreakdown:
    character = CharacterRepository(db).get(character_id)
    character_name = character.display_name if character else "Unknown Character"

    categories = {name: fn(db, character_id) for name, fn in _CATEGORY_COMPUTERS.items()}

    included = [c for c in categories.values() if c.status != CategoryStatus.UNAVAILABLE and c.score is not None]
    total_weight_included = sum(c.weight for c in included)
    coverage_ratio = total_weight_included / 100

    overall_score = None
    if included and total_weight_included > 0:
        overall_score = sum(c.score * c.weight for c in included) / total_weight_included

    eligible, participated = ReportRepository(db).participation_counts(character_id)
    sample_size = participated

    base_confidence = confidence_from_sample_size(sample_size)
    confidence = apply_data_completeness_modifiers(
        base_confidence,
        missing_roster_data=(eligible == 0),
        # Encounter rules (Phase 4) and parsed event data (Phase 3, pending
        # a verified payload schema) don't exist anywhere in Ascend yet -
        # this reflects current system capability, not a per-character gap.
        missing_encounter_rules=True,
        partial_event_ingestion=True,
        unknown_character_identity=(participated == 0),
    )
    if coverage_ratio < MIN_COVERAGE_RATIO_FOR_CLASSIFICATION:
        confidence = ConfidenceLevel.INSUFFICIENT_DATA

    notes = [
        f"{len([c for c in categories.values() if c.status == CategoryStatus.AVAILABLE])} of 7 categories "
        f"available, {len([c for c in categories.values() if c.status == CategoryStatus.PARTIAL])} partial, "
        f"{len([c for c in categories.values() if c.status == CategoryStatus.UNAVAILABLE])} unavailable "
        f"({coverage_ratio:.0%} of scoring weight backed by data).",
    ]
    if coverage_ratio < MIN_COVERAGE_RATIO_FOR_CLASSIFICATION:
        notes.append(
            "Confidence forced to Insufficient Data: less than half the scoring weight is "
            "backed by data yet, regardless of pull count."
        )

    if confidence == ConfidenceLevel.INSUFFICIENT_DATA or overall_score is None:
        classification = Classification.INSUFFICIENT_DATA
    else:
        classification = _classify(overall_score)
        if classification == Classification.STANDOUT and not _meets_standout_extra_criteria(
            categories, confidence, sample_size
        ):
            classification = Classification.STRONG

    return ScoreBreakdown(
        character_id=character_id,
        character_name=character_name,
        categories=categories,
        overall_score=round(overall_score, 1) if overall_score is not None else None,
        confidence=confidence,
        classification=classification,
        sample_size=sample_size,
        coverage_ratio=round(coverage_ratio, 2),
        scoring_version=SCORING_VERSION,
        notes=notes,
    )
