"""Data Quality: makes sure Ascend never silently ignores missing or
uncertain data - character-identity confidence and small-sample warnings,
computed directly from what's already been synced (no scoring engine
needed).
"""
from __future__ import annotations

from dataclasses import dataclass

from ascend.data.database import Database
from ascend.data.repositories import CharacterRepository, ReportRepository

NO_DATA = "no_data"
NOT_DETECTED = "not_detected"
DETECTED = "detected"

MIN_PULLS_FOR_CONFIDENCE = 3


@dataclass
class CharacterConfidence:
    character_id: int
    display_name: str
    participations: int
    raid_nights: int
    status: str


@dataclass
class SmallSampleWarning:
    subject: str
    kind: str  # "report" or "encounter"
    pulls: int


def character_identity_confidence(db: Database) -> list[CharacterConfidence]:
    """One entry per enabled tracked character - flags characters that have
    never been detected in any synced report, which usually means the
    character_name/server on file doesn't exactly match what Warcraft Logs
    reports (see ascend/services/character_detection.py's name+server
    matching)."""
    characters = CharacterRepository(db).list_all(enabled_only=True)
    reports_repo = ReportRepository(db)
    any_reports = bool(reports_repo.list_all())

    results = []
    for character in characters:
        rows = db.query_all(
            """
            SELECT COUNT(*) AS participations, COUNT(DISTINCT f.report_id) AS raid_nights
            FROM fight_participants fp
            JOIN fights f ON f.id = fp.fight_id
            WHERE fp.character_id = ?
            """,
            (character.id,),
        )
        participations = rows[0]["participations"] if rows else 0
        raid_nights = rows[0]["raid_nights"] if rows else 0

        if not any_reports:
            status = NO_DATA
        elif participations == 0:
            status = NOT_DETECTED
        else:
            status = DETECTED

        results.append(
            CharacterConfidence(
                character_id=character.id,
                display_name=character.display_name,
                participations=participations,
                raid_nights=raid_nights,
                status=status,
            )
        )
    return results


def small_sample_warnings(db: Database, min_pulls: int = MIN_PULLS_FOR_CONFIDENCE) -> list[SmallSampleWarning]:
    """Reports and encounters with fewer than ``min_pulls`` pulls - not
    enough of a sample to draw a real conclusion from once scoring exists,
    surfaced now so the user isn't surprised later."""
    reports_repo = ReportRepository(db)
    warnings: list[SmallSampleWarning] = []

    for report in reports_repo.list_all():
        pulls = len(reports_repo.fights_for_report(report.id)) if report.id else 0
        if 0 < pulls < min_pulls:
            warnings.append(
                SmallSampleWarning(subject=report.title or report.report_code, kind="report", pulls=pulls)
            )

    encounter_pulls: dict[str, int] = {}
    for encounter_id, name in reports_repo.distinct_encounters():
        pulls = len(reports_repo.fights_for_encounter(encounter_id))
        if 0 < pulls < min_pulls:
            encounter_pulls[name] = pulls

    for name, pulls in encounter_pulls.items():
        warnings.append(SmallSampleWarning(subject=name, kind="encounter", pulls=pulls))

    return warnings
