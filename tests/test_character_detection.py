import json
from pathlib import Path

from ascend.data.database import Database
from ascend.data.models import Character
from ascend.data.repositories import CharacterRepository, ReportRepository
from ascend.services.background_worker import CancellationToken
from ascend.services.character_detection import match_character
from ascend.services.sync_service import sync_report_by_code

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_sample_report() -> dict:
    return json.loads((FIXTURES_DIR / "sample_report.json").read_text(encoding="utf-8"))


class FakeWCLClient:
    def __init__(self, report: dict | None):
        self._report = report

    def fetch_report_by_code(self, report_code: str):
        return self._report


def _noop_progress(_percent, _message):
    pass


def _make_character(name="Aeloria", server="Proudmoore", region="US", enabled=True) -> Character:
    return Character(
        display_name=name,
        character_name=name,
        region=region,
        server=server,
        character_role="primary",
        enabled=enabled,
    )


# -- match_character (unit) -------------------------------------------------

def test_match_character_matches_name_and_server_case_insensitively():
    characters = [_make_character("Aeloria", "Proudmoore")]
    match = match_character("Aeloria", "Proudmoore", characters)
    assert match is not None
    assert match.character_name == "Aeloria"


def test_match_character_returns_none_when_server_differs():
    characters = [_make_character("Aeloria", "Proudmoore")]
    assert match_character("Aeloria", "Illidan", characters) is None


def test_match_character_returns_none_when_name_differs():
    characters = [_make_character("Aeloria", "Proudmoore")]
    assert match_character("Someoneelse", "Proudmoore", characters) is None


def test_match_character_ignores_disabled_characters():
    characters = [_make_character("Aeloria", "Proudmoore", enabled=False)]
    assert match_character("Aeloria", "Proudmoore", characters) is None


def test_match_character_returns_none_for_missing_name():
    assert match_character(None, "Proudmoore", [_make_character()]) is None


# -- sync_service integration -------------------------------------------------

def test_sync_links_fight_participants_to_tracked_character(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        character = CharacterRepository(db).create(_make_character("Aeloria", "Proudmoore"))

        client = FakeWCLClient(load_sample_report())
        token = CancellationToken()
        report = sync_report_by_code(_noop_progress, token, db, client, "AbCdEfGh123456")

        reports_repo = ReportRepository(db)
        fights = reports_repo.fights_for_report(report.id)
        assert len(fights) == 2

        for fight in fights:
            participants = reports_repo.participants_for_fight(fight.id)
            assert len(participants) == 3
            Aeloria = next(p for p in participants if p.name == "Aeloria")
            assert Aeloria.character_id == character.id
            others = [p for p in participants if p.name != "Aeloria"]
            assert all(p.character_id is None for p in others)

        tracked = reports_repo.tracked_characters_for_report(report.id)
        assert len(tracked) == 1
        assert tracked[0].id == character.id
    finally:
        db.close()


def test_sync_leaves_participants_unmatched_when_no_characters_tracked(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        client = FakeWCLClient(load_sample_report())
        token = CancellationToken()
        report = sync_report_by_code(_noop_progress, token, db, client, "AbCdEfGh123456")

        reports_repo = ReportRepository(db)
        fights = reports_repo.fights_for_report(report.id)
        participants = reports_repo.participants_for_fight(fights[0].id)
        assert len(participants) == 3
        assert all(p.character_id is None for p in participants)
        assert reports_repo.tracked_characters_for_report(report.id) == []
    finally:
        db.close()


def test_sync_is_idempotent_for_participants(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        CharacterRepository(db).create(_make_character("Aeloria", "Proudmoore"))
        client = FakeWCLClient(load_sample_report())
        token = CancellationToken()

        report = sync_report_by_code(_noop_progress, token, db, client, "AbCdEfGh123456")
        sync_report_by_code(_noop_progress, token, db, client, "AbCdEfGh123456")

        reports_repo = ReportRepository(db)
        fights = reports_repo.fights_for_report(report.id)
        participants = reports_repo.participants_for_fight(fights[0].id)
        assert len(participants) == 3  # no duplicates on re-sync
    finally:
        db.close()
