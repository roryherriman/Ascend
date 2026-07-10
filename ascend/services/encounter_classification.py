"""Progression-vs-farm classification for an encounter's pull history.

Objective and derivable from data already ingested in Phase 1/2 (no scoring
engine needed): a pull is "progression" if it happened at or before the
first kill of that encounter *at that difficulty* - the milestone a raid
team is working toward - and "farm" for everything after. If the encounter
hasn't been killed yet at that difficulty, every pull is progression.

Difficulty matters here because a guild's first Heroic kill doesn't make
earlier Mythic pulls of the same boss "farm" - they're a different
progression milestone entirely.
"""
from __future__ import annotations

from ascend.data.models import Fight

PROGRESSION = "progression"
FARM = "farm"


def classify_pulls(fights: list[Fight]) -> dict[int, str]:
    """``fights`` must already be in chronological order (see
    ReportRepository.fights_for_encounter). Returns {fight.id: classification},
    computed independently per difficulty."""
    first_kill_index_by_difficulty: dict[int | None, int] = {}
    for i, fight in enumerate(fights):
        if fight.kill and fight.difficulty not in first_kill_index_by_difficulty:
            first_kill_index_by_difficulty[fight.difficulty] = i

    classification: dict[int, str] = {}
    for i, fight in enumerate(fights):
        first_kill_index = first_kill_index_by_difficulty.get(fight.difficulty)
        is_farm = first_kill_index is not None and i > first_kill_index
        classification[fight.id] = FARM if is_farm else PROGRESSION
    return classification


PULL_RANGES: list[tuple[int, int | None]] = [(1, 10), (11, 25), (26, 50), (51, None)]


def group_by_pull_range(fights: list[Fight]) -> list[dict]:
    """Buckets progression pulls (only) into 1-10 / 11-25 / 26-50 / 51+, each
    with pull count and kill count - the "progression pull-range comparisons"
    roadmap item."""
    classification = classify_pulls(fights)
    progression_fights = [f for f in fights if classification[f.id] == PROGRESSION]

    groups = []
    for start, end in PULL_RANGES:
        bucket = progression_fights[start - 1 : end] if end is not None else progression_fights[start - 1 :]
        if not bucket:
            continue
        label = f"Pulls {start}-{end}" if end is not None else f"Pulls {start}+"
        groups.append({
            "label": label,
            "pulls": len(bucket),
            "kills": sum(1 for f in bucket if f.kill),
        })
    return groups
