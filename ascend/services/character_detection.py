"""Matches a Warcraft Logs report actor to one of the user's tracked
Characters.

ReportActor (see ascend/api/graphql_queries.py) exposes only ``name`` and
``server`` - a "normalized server name" - with no region field. Matching is
therefore name+server only (case-insensitive, whitespace-trimmed), not
region-qualified. For a personal-scale tracker (a handful of tracked
characters) the realistic ambiguity this introduces - the same character
name on a same-named realm in two different regions - is treated as an
accepted limitation rather than something worth an extra API round-trip to
resolve; it can be revisited if it ever causes a real mismatch.
"""
from __future__ import annotations

from ascend.data.models import Character


def _normalize(value: str | None) -> str:
    return (value or "").strip().casefold()


def match_character(name: str | None, server: str | None, characters: list[Character]) -> Character | None:
    """Returns the tracked Character matching this actor's name+server, or
    None if no enabled tracked character matches."""
    target_name = _normalize(name)
    target_server = _normalize(server)
    if not target_name:
        return None
    for character in characters:
        if not character.enabled:
            continue
        if _normalize(character.character_name) == target_name and _normalize(character.server) == target_server:
            return character
    return None
