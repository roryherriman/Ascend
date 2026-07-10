"""Domain models for Ascend's explainable, confidence-weighted scoring
engine. Every score is a composition of these types - there is no hidden
or opaque path from raw data to a number. See docs/SCORING.md for the
formulas, normalization methods, and confidence rules these types carry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CategoryStatus(str, Enum):
    """Whether a category could actually be computed from data Ascend has."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ConfidenceLevel(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class Classification(str, Enum):
    STANDOUT = "standout"
    STRONG = "strong"
    ABOVE_AVERAGE = "above_average"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    SIGNIFICANT_CONCERNS = "significant_concerns"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class MetricEvidence:
    """One line of evidence behind a category score. Every field the user
    specified as required for explainability is present - nothing is
    collapsed into just a final number."""

    metric_name: str
    raw_value: float | str | None
    normalized_value: float | None  # 0-100, or None if not computable
    comparison_baseline: str  # what the raw value is being compared against, in words
    weight: float  # this metric's share of its category, 0-1
    confidence_modifier: float  # multiplier applied due to data confidence, 0-1
    sample_size_modifier: float  # multiplier applied due to sample size, 0-1
    progression_modifier: float  # weighted average of per-pull progression/farm weights, 0-1
    final_contribution: float | None  # normalized_value * all modifiers * weight, or None
    supporting_refs: list[str] = field(default_factory=list)  # report/fight references
    note: str = ""  # why this metric is/isn't available, in plain English


@dataclass
class CategoryScore:
    """One of the 7 scoring categories (Survival, Execution, Damage,
    Consistency, Learning, Utility, Participation)."""

    name: str
    weight: int  # out of 100 - see docs/SCORING.md's category weight table
    status: CategoryStatus
    score: float | None  # 0-100, or None if UNAVAILABLE
    metrics: list[MetricEvidence] = field(default_factory=list)
    note: str = ""  # why this category is Partial/Unavailable, in plain English


@dataclass
class ScoreBreakdown:
    """The full, explainable result of scoring one character's progression
    performance. `overall_score` and `classification` are None/
    INSUFFICIENT_DATA whenever confidence doesn't support showing a normal
    classification - see docs/SCORING.md's confidence rules."""

    character_id: int
    character_name: str
    categories: dict[str, CategoryScore]
    overall_score: float | None
    confidence: ConfidenceLevel
    classification: Classification
    sample_size: int  # relevant progression pulls considered
    coverage_ratio: float  # fraction of the 100-point weight actually backed by data
    notes: list[str] = field(default_factory=list)
