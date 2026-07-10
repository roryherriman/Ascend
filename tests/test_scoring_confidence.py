from ascend.analysis.confidence import (
    apply_data_completeness_modifiers,
    confidence_from_sample_size,
    confidence_modifier_value,
    downgrade,
    sample_size_modifier,
)
from ascend.analysis.scoring_models import ConfidenceLevel


def test_confidence_thresholds_match_spec():
    assert confidence_from_sample_size(0) == ConfidenceLevel.INSUFFICIENT_DATA
    assert confidence_from_sample_size(9) == ConfidenceLevel.INSUFFICIENT_DATA
    assert confidence_from_sample_size(10) == ConfidenceLevel.LOW
    assert confidence_from_sample_size(24) == ConfidenceLevel.LOW
    assert confidence_from_sample_size(25) == ConfidenceLevel.MODERATE
    assert confidence_from_sample_size(49) == ConfidenceLevel.MODERATE
    assert confidence_from_sample_size(50) == ConfidenceLevel.HIGH
    assert confidence_from_sample_size(500) == ConfidenceLevel.HIGH


def test_downgrade_steps_down_one_tier():
    assert downgrade(ConfidenceLevel.HIGH) == ConfidenceLevel.MODERATE
    assert downgrade(ConfidenceLevel.MODERATE) == ConfidenceLevel.LOW
    assert downgrade(ConfidenceLevel.LOW) == ConfidenceLevel.INSUFFICIENT_DATA


def test_downgrade_never_goes_below_insufficient_data():
    assert downgrade(ConfidenceLevel.INSUFFICIENT_DATA) == ConfidenceLevel.INSUFFICIENT_DATA
    assert downgrade(ConfidenceLevel.HIGH, steps=10) == ConfidenceLevel.INSUFFICIENT_DATA


def test_data_completeness_modifiers_each_downgrade_one_tier():
    result = apply_data_completeness_modifiers(ConfidenceLevel.HIGH, missing_roster_data=True)
    assert result == ConfidenceLevel.MODERATE

    result = apply_data_completeness_modifiers(
        ConfidenceLevel.HIGH, missing_roster_data=True, missing_encounter_rules=True
    )
    assert result == ConfidenceLevel.LOW

    result = apply_data_completeness_modifiers(
        ConfidenceLevel.HIGH,
        missing_roster_data=True,
        missing_encounter_rules=True,
        partial_event_ingestion=True,
        unknown_character_identity=True,
    )
    assert result == ConfidenceLevel.INSUFFICIENT_DATA


def test_confidence_modifier_values_are_monotonic():
    values = [confidence_modifier_value(level) for level in (
        ConfidenceLevel.INSUFFICIENT_DATA, ConfidenceLevel.LOW, ConfidenceLevel.MODERATE, ConfidenceLevel.HIGH
    )]
    assert values == sorted(values)
    assert values[0] == 0.0
    assert values[-1] == 1.0


def test_sample_size_modifier_scales_to_one_at_fifty_pulls():
    assert sample_size_modifier(0) == 0.0
    assert sample_size_modifier(25) == 0.5
    assert sample_size_modifier(50) == 1.0
    assert sample_size_modifier(200) == 1.0  # clamped, not > 1.0
