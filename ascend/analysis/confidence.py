"""Confidence and sample-size handling, kept entirely separate from score
computation - per the scoring direction, missing data reduces confidence,
never score. See docs/SCORING.md for the full confidence rules.
"""
from __future__ import annotations

from ascend.analysis.scoring_models import ConfidenceLevel

_LEVEL_ORDER = [
    ConfidenceLevel.INSUFFICIENT_DATA,
    ConfidenceLevel.LOW,
    ConfidenceLevel.MODERATE,
    ConfidenceLevel.HIGH,
]

# Sample-size thresholds (relevant progression pulls), as specified.
_INSUFFICIENT_MAX = 9
_LOW_MAX = 24
_MODERATE_MAX = 49


def confidence_from_sample_size(pull_count: int) -> ConfidenceLevel:
    if pull_count <= _INSUFFICIENT_MAX:
        return ConfidenceLevel.INSUFFICIENT_DATA
    if pull_count <= _LOW_MAX:
        return ConfidenceLevel.LOW
    if pull_count <= _MODERATE_MAX:
        return ConfidenceLevel.MODERATE
    return ConfidenceLevel.HIGH


def downgrade(level: ConfidenceLevel, steps: int = 1) -> ConfidenceLevel:
    """Moves a confidence level down (never below INSUFFICIENT_DATA)."""
    index = _LEVEL_ORDER.index(level)
    return _LEVEL_ORDER[max(0, index - steps)]


def apply_data_completeness_modifiers(
    level: ConfidenceLevel,
    *,
    missing_roster_data: bool = False,
    missing_encounter_rules: bool = False,
    partial_event_ingestion: bool = False,
    unknown_character_identity: bool = False,
) -> ConfidenceLevel:
    """Each true flag downgrades confidence by one tier, per the scoring
    direction's confidence rules. Order doesn't matter - this is a simple
    step count, not a weighted formula, since the spec gives no relative
    weighting between these four factors."""
    steps = sum([
        missing_roster_data,
        missing_encounter_rules,
        partial_event_ingestion,
        unknown_character_identity,
    ])
    return downgrade(level, steps)


# Discrete multiplier used as MetricEvidence.confidence_modifier - how much
# a metric's contribution is trusted given its confidence tier.
CONFIDENCE_MODIFIER_VALUES: dict[ConfidenceLevel, float] = {
    ConfidenceLevel.INSUFFICIENT_DATA: 0.0,
    ConfidenceLevel.LOW: 0.5,
    ConfidenceLevel.MODERATE: 0.75,
    ConfidenceLevel.HIGH: 1.0,
}


def confidence_modifier_value(level: ConfidenceLevel) -> float:
    return CONFIDENCE_MODIFIER_VALUES[level]


def sample_size_modifier(pull_count: int) -> float:
    """Continuous 0-1 scaling used as MetricEvidence.sample_size_modifier -
    reaches 1.0 at the same 50-pull threshold that yields High confidence,
    kept separate from the discrete confidence tier (which gates
    classification/display) so a metric's contribution scales smoothly
    with sample size rather than jumping between four fixed values."""
    return min(1.0, max(0.0, pull_count / 50))
