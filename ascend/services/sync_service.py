"""Sync operations: report-code entry, report/fight retrieval, and
character detection.

Bulk report discovery and full pull/event ingestion are added in Phase 3.
For now this supports fetching one report by its code and storing its
top-level metadata, its list of fights (pulls), and the player actors
present in each fight (matched against tracked Characters where possible),
without ever creating duplicate report/fight/participant rows on repeated
syncs.
"""
from __future__ import annotations

import json
from typing import Callable

from ascend.api.client import WCLClient
from ascend.data.database import Database
from ascend.data.models import Fight, FightParticipant, Report
from ascend.data.repositories import (
    ApiCacheRepository,
    CharacterRepository,
    ReportRepository,
    SyncHistoryRepository,
)
from ascend.services.background_worker import CancellationToken
from ascend.services.character_detection import match_character
from ascend.services.zone_data import ensure_zone_difficulties_cached


class ReportCodeNotFoundError(Exception):
    pass


def sync_report_by_code(
    progress_callback: Callable[[int, str], None],
    cancel_token: CancellationToken,
    db: Database,
    client: WCLClient,
    report_code: str,
) -> Report | None:
    """Fetch a single report by code and upsert it (and its fights) into SQLite.

    Returns the stored Report, or None if the operation was cancelled.
    """
    history = SyncHistoryRepository(db)
    reports_repo = ReportRepository(db)
    history_id = history.start(f"report_code:{report_code}")

    try:
        progress_callback(10, f"Requesting report {report_code} from Warcraft Logs...")
        raw = client.fetch_report_by_code(report_code)

        if cancel_token.is_cancelled:
            history.finish(history_id, "cancelled")
            return None

        if raw is None:
            history.finish(history_id, "error", error_message="Report not found")
            raise ReportCodeNotFoundError(
                f"No report found for code '{report_code}'. Check the code and try again."
            )

        # Preserve the raw API response so analysis can be recalculated later
        # (e.g. after a scoring/engine update) without redownloading it.
        ApiCacheRepository(db).set(f"report:{report_code}", json.dumps(raw))

        progress_callback(50, "Storing report metadata...")
        guild = raw.get("guild") or {}
        owner = raw.get("owner") or {}
        zone = raw.get("zone") or {}

        report = Report(
            report_code=raw["code"],
            title=raw.get("title"),
            owner_name=owner.get("name"),
            guild_name=guild.get("name"),
            zone_id=zone.get("id"),
            zone_name=zone.get("name"),
            start_time=raw.get("startTime"),
            end_time=raw.get("endTime"),
        )
        report = reports_repo.upsert_report(report)

        if report.zone_id is not None:
            # Best-effort: difficulty labels are a display nicety, not worth
            # failing the whole sync over if this secondary lookup errors.
            try:
                ensure_zone_difficulties_cached(db, client, report.zone_id)
            except Exception:  # noqa: BLE001 - see comment above
                pass

        master_data = raw.get("masterData") or {}
        actors_by_id = {
            actor["id"]: actor for actor in (master_data.get("actors") or []) if actor.get("id") is not None
        }
        tracked_characters = CharacterRepository(db).list_all(enabled_only=True)

        fights_raw = raw.get("fights") or []
        for i, fight_raw in enumerate(fights_raw):
            if cancel_token.is_cancelled:
                history.finish(
                    history_id, "cancelled", reports_processed=1, pulls_processed=i
                )
                return None
            fight = Fight(
                report_id=report.id,
                fight_id=fight_raw["id"],
                name=fight_raw.get("name"),
                encounter_id=fight_raw.get("encounterID"),
                difficulty=fight_raw.get("difficulty"),
                kill=fight_raw.get("kill"),
                start_time=fight_raw.get("startTime"),
                end_time=fight_raw.get("endTime"),
            )
            fight = reports_repo.upsert_fight(fight)

            for actor_id in fight_raw.get("friendlyPlayers") or []:
                actor = actors_by_id.get(actor_id)
                if actor is None:
                    continue
                matched = match_character(actor.get("name"), actor.get("server"), tracked_characters)
                reports_repo.upsert_fight_participant(
                    FightParticipant(
                        fight_id=fight.id,
                        actor_id=actor_id,
                        name=actor.get("name"),
                        server=actor.get("server"),
                        class_name=actor.get("subType"),
                        character_id=matched.id if matched else None,
                    )
                )

            pct = 50 + int(40 * (i + 1) / max(len(fights_raw), 1))
            progress_callback(pct, f"Stored pull {i + 1}/{len(fights_raw)}...")

        history.finish(
            history_id, "success", reports_processed=1, pulls_processed=len(fights_raw)
        )
        progress_callback(100, "Done.")
        return report
    except ReportCodeNotFoundError:
        raise
    except Exception as exc:
        history.finish(history_id, "error", error_message=str(exc))
        raise
