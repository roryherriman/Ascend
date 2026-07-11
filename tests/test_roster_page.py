from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository
from ascend.ui.roster_page import RosterComparisonPage


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_shows_empty_state_when_no_roster_data(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        page = RosterComparisonPage(db)
        qtbot.addWidget(page)
        assert page.empty_state is not None
        assert not page.empty_state.isHidden()
        assert page._card.isHidden()
    finally:
        db.close()


def test_roster_shows_rows_for_members(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        character = CharacterRepository(db).create(
            Character(display_name="Aeloria", character_name="Aeloria", region="US", server="Proudmoore")
        )
        reports_repo = ReportRepository(db)
        report1 = reports_repo.upsert_report(Report(report_code="NIGHT1"))
        report2 = reports_repo.upsert_report(Report(report_code="NIGHT2"))

        fight1 = reports_repo.upsert_fight(Fight(report_id=report1.id, fight_id=1, name="Boss"))
        fight2 = reports_repo.upsert_fight(Fight(report_id=report2.id, fight_id=1, name="Boss"))

        for fight in (fight1, fight2):
            reports_repo.upsert_fight_participant(
                FightParticipant(
                    fight_id=fight.id, actor_id=1, name="Aeloria", server="Proudmoore",
                    class_name="Priest", character_id=character.id,
                )
            )
            reports_repo.upsert_fight_participant(
                FightParticipant(
                    fight_id=fight.id, actor_id=2, name="Otherraider", server="Proudmoore",
                    class_name="Mage", character_id=None,
                )
            )

        page = RosterComparisonPage(db)
        qtbot.addWidget(page)

        assert not page._card.isHidden()
        assert page._rows_layout.count() == 2
    finally:
        db.close()


def test_roster_page_has_no_table_widget(tmp_path, qtbot):
    from PySide6.QtWidgets import QTableWidget
    db = _make_db(tmp_path)
    try:
        page = RosterComparisonPage(db)
        qtbot.addWidget(page)
        assert not page.findChildren(QTableWidget)
    finally:
        db.close()
