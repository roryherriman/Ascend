from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository
from ascend.ui.raid_night_page import PullDetailDialog, RaidNightSummaryPage


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
                display_name="Aeloria", character_name="Aeloria",
                region="US", server="Proudmoore", character_role="primary",
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
        assert names == {"Aeloria", "Otherraider"}
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


def test_notes_load_for_selected_report_and_save_persists(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))
        reports_repo.update_notes(report.id, "Existing note")

        page = RaidNightSummaryPage(db)
        qtbot.addWidget(page)

        assert page.notes_edit.toPlainText() == "Existing note"

        page.notes_edit.setPlainText("Updated note")
        page._on_save_notes()

        reloaded = ReportRepository(db).get_by_code("ABC123")
        assert reloaded.notes == "Updated note"
    finally:
        db.close()


def test_resyncing_a_report_does_not_erase_its_notes(tmp_path):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night"))
        reports_repo.update_notes(report.id, "Do not lose me")

        # Simulate a re-sync: upsert_report is called again for the same code.
        reports_repo.upsert_report(Report(report_code="ABC123", title="Test Night (updated title)"))

        reloaded = reports_repo.get_by_code("ABC123")
        assert reloaded.notes == "Do not lose me"
        assert reloaded.title == "Test Night (updated title)"
    finally:
        db.close()


def test_pull_detail_dialog_shows_fight_and_participants(tmp_path, qtbot):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", zone_id=44))
        fight = reports_repo.upsert_fight(
            Fight(
                report_id=report.id, fight_id=7, name="Test Boss",
                difficulty=5, kill=False, start_time=0, end_time=30000,
            )
        )
        reports_repo.upsert_fight_participant(
            FightParticipant(
                fight_id=fight.id, actor_id=1, name="Aeloria", server="Proudmoore", class_name="Priest",
            )
        )

        dialog = PullDetailDialog(db, report, fight, pull_number=3)
        qtbot.addWidget(dialog)

        assert "Test Boss" in dialog.windowTitle()
        assert dialog.participants_table.rowCount() == 1
        assert dialog.participants_table.item(0, 0).text() == "Aeloria"
        assert dialog.evidence_button.text() == "Open This Pull on Warcraft Logs"
    finally:
        db.close()


def test_double_clicking_a_pull_opens_its_detail_dialog(tmp_path, qtbot, monkeypatch):
    db = _make_db(tmp_path)
    try:
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="ABC123", zone_id=44))
        reports_repo.upsert_fight(
            Fight(report_id=report.id, fight_id=1, name="Test Boss", kill=True, start_time=0, end_time=1000)
        )

        page = RaidNightSummaryPage(db)
        qtbot.addWidget(page)

        opened = {}

        class FakeDialog:
            def __init__(self, db_, report_, fight_, pull_number, parent=None):
                opened["fight_name"] = fight_.name
                opened["pull_number"] = pull_number

            def exec(self):
                opened["executed"] = True

        monkeypatch.setattr("ascend.ui.raid_night_page.PullDetailDialog", FakeDialog)
        page._on_pull_double_clicked(0, 0)

        assert opened == {"fight_name": "Test Boss", "pull_number": 1, "executed": True}
    finally:
        db.close()
