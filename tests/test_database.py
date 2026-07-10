import sqlite3

import pytest

from ascend.data.database import Database, default_app_data_root, load_bootstrap_config
from ascend.data.migrations import MIGRATIONS, apply_migrations, current_version
from ascend.data.models import Character, Fight, Report
from ascend.data.repositories import (
    AnalysisRunRepository,
    ApiCacheRepository,
    CharacterRepository,
    ReportRepository,
    SessionOperationRepository,
    SettingsRepository,
)


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    yield database
    database.close()


def test_migrations_apply_and_record_version(db):
    assert current_version(db.connection) == MIGRATIONS[-1].version


def test_migrations_are_idempotent(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "idempotent.db"))
    first = apply_migrations(conn)
    second = apply_migrations(conn)
    assert first == second == MIGRATIONS[-1].version


def test_expected_tables_exist(db):
    tables = {
        row["name"]
        for row in db.query_all("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for expected in {
        "characters", "reports", "fights", "settings", "sync_history", "api_cache",
        "session_operations", "analysis_runs",
    }:
        assert expected in tables


def test_character_crud_roundtrip(db):
    repo = CharacterRepository(db)
    character = Character(
        display_name="Kysarra",
        character_name="Kysarra",
        region="US",
        server="Stormrage",
        wcl_character_id=108832382,
        character_class="Mage",
    )
    created = repo.create(character)
    assert created.id is not None

    fetched = repo.get(created.id)
    assert fetched.display_name == "Kysarra"
    assert fetched.enabled is True

    fetched.display_name = "Kysarra (Renamed)"
    repo.update(fetched)
    assert repo.get(created.id).display_name == "Kysarra (Renamed)"

    repo.set_enabled(created.id, False)
    assert repo.get(created.id).enabled is False

    repo.delete(created.id)
    assert repo.get(created.id) is None


def test_report_and_fight_upsert_prevents_duplicates(db):
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code="CODE123", title="First Sync"))
    report_id = report.id

    fight = Fight(report_id=report_id, fight_id=1, name="Boss A", kill=False)
    repo.upsert_fight(fight)
    repo.upsert_fight(fight)  # duplicate ingestion attempt

    fights = repo.fights_for_report(report_id)
    assert len(fights) == 1
    assert fights[0].name == "Boss A"

    # Re-syncing the same report code must update, not duplicate, the report row.
    repo.upsert_report(Report(report_code="CODE123", title="Second Sync"))
    all_reports = [r for r in repo.list_all() if r.report_code == "CODE123"]
    assert len(all_reports) == 1
    assert all_reports[0].title == "Second Sync"


def test_settings_repository_json_roundtrip(db):
    repo = SettingsRepository(db)
    repo.set("scoring_weights", {"attendance": 15, "consistency": 10})
    assert repo.get("scoring_weights") == {"attendance": 15, "consistency": 10}
    assert repo.get("does_not_exist", "default") == "default"


def test_session_operation_marks_unclean_shutdown_as_interrupted(db):
    repo = SessionOperationRepository(db)
    first_run_id = repo.start("app_session")
    # Simulate a crash: never call complete() for first_run_id before the "next launch".

    interrupted_count = repo.mark_unclosed_as_interrupted("app_session")
    assert interrupted_count == 1

    recent = repo.recent()
    assert recent[0]["status"] == "interrupted"

    second_run_id = repo.start("app_session")
    repo.complete(second_run_id)
    assert repo.mark_unclosed_as_interrupted("app_session") == 0
    assert first_run_id != second_run_id


def test_analysis_run_repository_records_versions(db):
    repo = ReportRepository(db)
    report = repo.upsert_report(Report(report_code="VERCODE1"))

    analysis_repo = AnalysisRunRepository(db)
    analysis_repo.record(
        report_id=report.id,
        character_id=None,
        app_version="0.1.0",
        analysis_engine_version="0.1.0",
        scoring_model_version="0.1.0",
    )
    latest = analysis_repo.latest_for_report(report.id)
    assert latest["app_version"] == "0.1.0"


def test_api_cache_repository_preserves_raw_response(db):
    cache = ApiCacheRepository(db)
    cache.set("report:ABC123", '{"code": "ABC123", "title": "Raw Preserved"}')

    row = cache.get("report:ABC123")
    assert row is not None
    assert "Raw Preserved" in row["response_json"]

    cache.delete("report:ABC123")
    assert cache.get("report:ABC123") is None


def test_demo_mode_uses_a_separate_database_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    app_root = default_app_data_root()
    config = load_bootstrap_config(app_root)
    config["demo_mode"] = False
    from ascend.data.database import save_bootstrap_config

    save_bootstrap_config(app_root, config)
    real_db = Database.default_path_instance()
    assert real_db.db_path.name == "ascend.db"

    config["demo_mode"] = True
    save_bootstrap_config(app_root, config)
    demo_db = Database.default_path_instance()
    assert demo_db.db_path.name == "ascend_demo.db"
    assert demo_db.db_path != real_db.db_path
