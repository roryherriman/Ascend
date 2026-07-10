from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository
from ascend.ui.raid_night_page import RaidNightSummaryPage


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_shows_empty_state_when_no_reports(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        page = RaidNightSummaryPage(db)
        qtbot.addWidget(page)
        assert page.empty_state is not None
        assert not page.empty_state.isHidden()
        assert page.detail_container.isHidden()
    finally:
        db.close()


def test_shows_detail_with_pulls_and_roster_for_seeded_report(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        character = CharacterRepository(db).create(
            Character(
                display_name="Kysarra", character_name="Kysarra",
                region="US", server="Stormrage", character_role="primary",
            )
        )
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(
            Report(report_code="ABC123", title="Test Night", guild_name="Test Guild", zone_id=44)
        )
        fight = reports_repo.upsert_fight(
            Fight(
                report_id=report.id, fight_id=1, name="Test Boss",
                difficulty=5, kill=True, start_time=0, end_time=60000,
            )
        )
        reports_repo.upsert_fight_participant(
            FightParticipant(
                fight_id=fight.id, actor_id=1, name="Kysarra", server="Stormrage",
                class_name="Priest", character_id=character.id,
            )
        )
        reports_repo.upsert_fight_participant(
            FightParticipant(
                fight_id=fight.id, actor_id=2, name="Otherraider", server="Stormrage",
                class_name="Mage", character_id=None,
            )
        )

        page = RaidNightSummaryPage(db)
        qtbot.addWidget(page)

        assert page.empty_state is None or page.empty_state.isHidden()
        assert not page.detail_container.isHidden()
        assert page._overview_labels["guild"].text() == "Test Guild"
        assert page._overview_labels["pulls"].text() == "1"
        assert page._overview_labels["kills"].text() == "1 / 0"

        assert page.pull_table.rowCount() == 1
        assert page.pull_table.item(0, 1).text() == "Test Boss"
        assert page.pull_table.item(0, 3).text() == "Kill"

        assert page.roster_table.rowCount() == 2
        names = {page.roster_table.item(r, 0).text() for r in range(2)}
        assert names == {"Kysarra", "Otherraider"}
    finally:
        db.close()


def test_select_report_navigates_to_matching_entry(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        first = reports_repo.upsert_report(Report(report_code="FIRST", title="First Night", start_time=1000))
        second = reports_repo.upsert_report(Report(report_code="SECOND", title="Second Night", start_time=2000))

        page = RaidNightSummaryPage(db)
        qtbot.addWidget(page)

        page.select_report(first.id)
        assert page.report_combo.currentData() == first.id
        assert page._overview_labels["guild"].text() == "--"

        page.select_report(second.id)
        assert page.report_combo.currentData() == second.id
    finally:
        db.close()
