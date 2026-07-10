"""Per-pull progression/farm weighting: progression pulls count fully
toward a score, the exact first-kill pull counts at reduced weight, and
farm (post-first-kill) pulls count much less - per the scoring direction's
"progression performance is primary, farm has substantially reduced
weight" principle.

Deliberately a separate module from ascend/services/encounter_classification.py
rather than a modification of it: that module's classify_pulls() has an
existing 2-value (progression/farm) contract already used by the Encounter
Analysis page and covered by its own tests, and changing its return shape
to add a distinct first-kill bucket would be a breaking change for no
benefit to that page. This module reimplements the same first-kill-index
algorithm to produce the 3-tier numeric weight the scoring engine needs.
"""
from __future__ import annotations

from ascend.data.models import Fight

PROGRESSION_WEIGHT = 1.00
FIRST_KILL_WEIGHT = 0.80
FARM_WEIGHT = 0.25


def pull_weights(fights: list[Fight]) -> dict[int, float]:
    """``fights`` must already be in chronological order (see
    ReportRepository.fights_for_encounter) and all belong to the same
    encounter. Returns {fight.id: weight}, computed independently per
    difficulty - a first Heroic kill doesn't turn ongoing Mythic pulls of
    the same boss into farm, matching encounter_classification.py's
    per-difficulty rule."""
    first_kill_index_by_difficulty: dict[int | None, int] = {}
    for i, fight in enumerate(fights):
        if fight.kill and fight.difficulty not in first_kill_index_by_difficulty:
            first_kill_index_by_difficulty[fight.difficulty] = i

    weights: dict[int, float] = {}
    for i, fight in enumerate(fights):
        first_kill_index = first_kill_index_by_difficulty.get(fight.difficulty)
        if first_kill_index is None or i < first_kill_index:
            weights[fight.id] = PROGRESSION_WEIGHT
        elif i == first_kill_index:
            weights[fight.id] = FIRST_KILL_WEIGHT
        else:
            weights[fight.id] = FARM_WEIGHT
    return weights
