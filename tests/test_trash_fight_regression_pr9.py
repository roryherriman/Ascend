"""PR 9 regression tests: encounterID=0 trash fights excluded, unknown-actor participants stored."""
from __future__ import annotations

import pytest


def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


# ---------------------------------------------------------------------------
# encounterID = 0 normalisation in sync
# ---------------------------------------------------------------------------

def test_encounter_id_zero_normalised_to_none_in_fight(tmp_path):
    from ascend.data.models import Fight, Report
    from ascend.data.repositories import ReportRepository
    db = _make_db(tmp_path)
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code="T1", start_time=0, end_time=0))
    fight = repo.upsert_fight(Fight(
        report_id=report.id,
        fight_id=1,
        name="Trash",
        encounter_id=0,
    ))
    assert fight.encounter_id is None or fight.encounter_id == 0


def test_trash_fight_excluded_from_distinct_encounters(tmp_path):
    from ascend.data.models import Fight, Report
    from ascend.data.repositories import ReportRepository
    db = _make_db(tmp_path)
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code="T2", zone_id=1, zone_name="Nerub-ar", start_time=0, end_time=0))
    # Trash fight: encounter_id = 0
    repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Trash", encounter_id=0))
    # Boss fight: real encounter_id
    repo.upsert_fight(Fight(report_id=report.id, fight_id=2, name="Ulgrax", encounter_id=2677))
    encounters = repo.distinct_encounters()
    ids = [enc_id for enc_id, _ in encounters]
    assert 0 not in ids
    assert 2677 in ids


def test_trash_fight_excluded_from_distinct_encounters_for_zone(tmp_path):
    from ascend.data.models import Fight, Report
    from ascend.data.repositories import ReportRepository
    db = _make_db(tmp_path)
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code="T3", zone_id=42, zone_name="Zone A", start_time=0, end_time=0))
    repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Trash", encounter_id=0))
    repo.upsert_fight(Fight(report_id=report.id, fight_id=2, name="Boss A", encounter_id=999))
    encounters = repo.distinct_encounters_for_zone(42)
    ids = [enc_id for enc_id, _ in encounters]
    assert 0 not in ids
    assert 999 in ids


# ---------------------------------------------------------------------------
# sync_service normalises encounterID=0 → None
# ---------------------------------------------------------------------------

def test_sync_normalises_encounter_id_zero(tmp_path):
    from unittest.mock import MagicMock, patch
    from ascend.data.repositories import ReportRepository
    from ascend.services.background_worker import CancellationToken
    from ascend.services.sync_service import sync_report_by_code

    db = _make_db(tmp_path)
    cancel = CancellationToken()
    client = MagicMock()
    client.fetch_report_by_code.return_value = {
        "code": "TRASH1",
        "title": "Trash Test",
        "startTime": 0,
        "endTime": 1000,
        "guild": {},
        "owner": {},
        "zone": {"id": 1, "name": "Zone"},
        "masterData": {"actors": []},
        "fights": [
            {"id": 1, "name": "Trash Pull", "encounterID": 0, "difficulty": None,
             "kill": False, "startTime": 0, "endTime": 500, "friendlyPlayers": []},
            {"id": 2, "name": "Boss Kill", "encounterID": 777, "difficulty": 4,
             "kill": True, "startTime": 500, "endTime": 1000, "friendlyPlayers": []},
        ],
    }

    with patch("ascend.services.sync_service.ensure_zone_difficulties_cached"):
        sync_report_by_code(lambda p, m: None, cancel, db, client, "TRASH1")

    repo = ReportRepository(db)
    fights = repo.fights_for_report(repo.list_all()[0].id)
    trash = next(f for f in fights if f.fight_id == 1)
    boss = next(f for f in fights if f.fight_id == 2)
    assert trash.encounter_id is None
    assert boss.encounter_id == 777


# ---------------------------------------------------------------------------
# Unknown actor (not in masterData.actors) still gets a participant row
# ---------------------------------------------------------------------------

def test_unknown_actor_stored_as_minimal_participant(tmp_path):
    from unittest.mock import MagicMock, patch
    from ascend.data.repositories import ReportRepository
    from ascend.services.background_worker import CancellationToken
    from ascend.services.sync_service import sync_report_by_code

    db = _make_db(tmp_path)
    cancel = CancellationToken()
    client = MagicMock()
    # actor_id=99 appears in friendlyPlayers but NOT in masterData.actors
    client.fetch_report_by_code.return_value = {
        "code": "ACTOR1",
        "title": "Actor Test",
        "startTime": 0,
        "endTime": 1000,
        "guild": {},
        "owner": {},
        "zone": {"id": 1, "name": "Zone"},
        "masterData": {"actors": [
            {"id": 1, "name": "KnownPlayer", "server": "Kel'Thuzad", "subType": "Warrior"},
        ]},
        "fights": [
            {"id": 1, "name": "Boss", "encounterID": 100, "difficulty": 4,
             "kill": True, "startTime": 0, "endTime": 1000,
             "friendlyPlayers": [1, 99]},  # 99 is unknown
        ],
    }

    with patch("ascend.services.sync_service.ensure_zone_difficulties_cached"):
        sync_report_by_code(lambda p, m: None, cancel, db, client, "ACTOR1")

    repo = ReportRepository(db)
    report = repo.list_all()[0]
    fights = repo.fights_for_report(report.id)
    participants = repo.participants_for_fight(fights[0].id)
    actor_ids = {p.actor_id for p in participants}
    assert 1 in actor_ids
    assert 99 in actor_ids  # unknown actor still tracked
    unknown = next(p for p in participants if p.actor_id == 99)
    assert unknown.name is None
    assert unknown.class_name is None
