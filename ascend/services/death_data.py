"""Caches the raw Death table (Report.table(dataType: Deaths)) per report.

WCL does not publish a GraphQL type for table/event payloads (see
graphql_queries.py's DEATH_TABLE_QUERY docstring) - the shape is whatever
the site returns, undocumented and "not considered frozen." Ascend caches
it via the same raw-preservation pattern used for reports (ApiCacheRepository)
and treats it as opaque data to display, not a verified structure to parse
confidently - see ascend/ui/death_review_page.py for how it's rendered.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from ascend.api.client import WCLClient
from ascend.data.database import Database
from ascend.data.repositories import ApiCacheRepository
from ascend.services.background_worker import CancellationToken


def _cache_key(report_code: str) -> str:
    return f"death_table:{report_code}"


def get_cached_death_table(db: Database, report_code: str) -> Any | None:
    """Returns the cached payload, or None if it hasn't been fetched yet -
    no network call."""
    row = ApiCacheRepository(db).get(_cache_key(report_code))
    if row is None:
        return None
    return json.loads(row["response_json"])


def fetch_and_cache_death_table(
    db: Database, client: WCLClient, report_code: str, fight_ids: list[int] | None = None
) -> Any:
    """Always re-fetches (unlike zone_data's cache-forever, death data isn't
    static - a re-analyzed/updated report could change it). Meant to be
    called from a background task, not the GUI thread."""
    payload = client.fetch_death_table(report_code, fight_ids)
    ApiCacheRepository(db).set(_cache_key(report_code), json.dumps(payload))
    return payload


def fetch_death_table_task(
    progress_callback: Callable[[int, str], None],
    _cancel_token: CancellationToken,
    db: Database,
    client: WCLClient,
    report_code: str,
    fight_ids: list[int] | None = None,
) -> Any:
    """BackgroundTaskManager-shaped wrapper around fetch_and_cache_death_table
    (every task function must accept progress_callback/cancel_token first -
    see BackgroundTask.run) - this is what the UI submits directly."""
    progress_callback(50, f"Fetching death data for {report_code}...")
    return fetch_and_cache_death_table(db, client, report_code, fight_ids)
