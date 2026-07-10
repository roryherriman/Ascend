from ascend.analysis.categories import (
    compute_consistency_category,
    compute_damage_category,
    compute_execution_category,
    compute_learning_category,
    compute_participation_category,
    compute_survival_category,
    compute_utility_category,
)
from ascend.analysis.scoring_models import CategoryStatus
from ascend.data.database import Database
from ascend.data.models import Character, Fight, FightParticipant, Report
from ascend.data.repositories import CharacterRepository, ReportRepository


def _make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def _make_character(db, name="Kysarra", server="Stormrage"):
    return CharacterRepository(db).create(
        Character(display_name=name, character_name=name, region="US", server=server)
    )


# -- Participation ------------------------------------------------------------

def test_participation_unavailable_with_no_reports(tmp_path):
    db = _make_db(tmp_path)
    try:
        character = _make_character(db)
        category = compute_participation_category(db, character.id)
        assert category.status == CategoryStatus.UNAVAILABLE
        assert category.score is None
    finally:
        db.close()


def test_participation_available_and_scored_correctly(tmp_path):
    db = _make_db(tmp_path)
    try:
        character = _make_character(db)
        reports_repo = ReportRepository(db)
        report1 = reports_repo.upsert_report(Report(report_code="N1"))
        report2 = reports_repo.upsert_report(Report(report_code="N2"))
        fight1 = reports_repo.upsert_fight(Fight(report_id=report1.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight(Fight(report_id=report2.id, fight_id=1, name="Boss"))
        reports_repo.upsert_fight_participant(
            FightParticipant(fight_id=fight1.id, actor_id=1, name="Kysarra", server="Stormrage", character_id=character.id)
        )

        category = compute_participation_category(db, character.id)
        assert category.status == CategoryStatus.AVAILABLE
        # Participated in 1 of 2 eligible pulls = 50% raw, but at only 2
        # pulls confidence/sample-size modifiers are near zero, so the
        # discounted score is far below the raw 50.
        assert category.metrics[0].raw_value == "1/2"
        assert category.metrics[0].normalized_value == 50.0
        assert category.score < 5  # heavily discounted at n=2
    finally:
        db.close()


def test_participation_score_rises_with_more_data_at_same_rate(tmp_path):
    """Same 100% participation rate, but more pulls -> higher confidence ->
    higher discounted score, since sample-size/confidence modifiers scale
    with pull count."""
    db = _make_db(tmp_path)
    try:
        character = _make_character(db)
        reports_repo = ReportRepository(db)
        for i in range(60):
            report = reports_repo.upsert_report(Report(report_code=f"N{i}"))
            fight = reports_repo.upsert_fight(Fight(report_id=report.id, fight_id=1, name="Boss"))
            reports_repo.upsert_fight_participant(
                FightParticipant(fight_id=fight.id, actor_id=1, name="Kysarra", server="Stormrage", character_id=character.id)
            )

        category = compute_participation_category(db, character.id)
        assert category.metrics[0].normalized_value == 100.0
        assert category.score == 100.0  # full confidence + sample size at 60 pulls
    finally:
        db.close()


# -- Learning -----------------------------------------------------------------

def test_learning_unavailable_with_no_participation(tmp_path):
    db = _make_db(tmp_path)
    try:
        character = _make_character(db)
        category = compute_learning_category(db, character.id)
        assert category.status == CategoryStatus.UNAVAILABLE
    finally:
        db.close()


def test_learning_unavailable_with_too_few_pull_range_buckets(tmp_path):
    db = _make_db(tmp_path)
    try:
        character = _make_character(db)
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="N1"))
        fight = reports_repo.upsert_fight(
            Fight(report_id=report.id, fight_id=1, name="Boss", encounter_id=1, kill=False)
        )
        reports_repo.upsert_fight_participant(
            FightParticipant(fight_id=fight.id, actor_id=1, name="Kysarra", server="Stormrage", character_id=character.id)
        )

        category = compute_learning_category(db, character.id)
        assert category.status == CategoryStatus.UNAVAILABLE
    finally:
        db.close()


def test_learning_partial_with_improving_wipe_rate(tmp_path):
    db = _make_db(tmp_path)
    try:
        character = _make_character(db)
        reports_repo = ReportRepository(db)
        report = reports_repo.upsert_report(Report(report_code="N1"))
        # 10 pulls, all wipes (bucket 1); 5 more pulls, all kills (bucket 2 = pulls 11-25).
        for i in range(10):
            fight = reports_repo.upsert_fight(
                Fight(report_id=report.id, fight_id=i + 1, name="Boss", encounter_id=1, kill=False)
            )
            reports_repo.upsert_fight_participant(
                FightParticipant(fight_id=fight.id, actor_id=1, name="Kysarra", server="Stormrage", character_id=character.id)
            )
        for i in range(10, 15):
            fight = reports_repo.upsert_fight(
                Fight(report_id=report.id, fight_id=i + 1, name="Boss", encounter_id=1, kill=True)
            )
            reports_repo.upsert_fight_participant(
                FightParticipant(fight_id=fight.id, actor_id=1, name="Kysarra", server="Stormrage", character_id=character.id)
            )

        category = compute_learning_category(db, character.id)
        assert category.status == CategoryStatus.PARTIAL
        assert len(category.metrics) == 1
        metric = category.metrics[0]
        # First bucket 0% kills, last bucket 100% kills -> normalized should be 100 (max improvement).
        assert metric.normalized_value == 100.0
    finally:
        db.close()


# -- Unavailable categories are explicit, not silently zero -----------------

def test_unavailable_categories_expose_candidate_metrics_with_reasons(tmp_path):
    db = _make_db(tmp_path)
    try:
        character = _make_character(db)
        for compute_fn, expected_metric_count in [
            (compute_survival_category, 4),
            (compute_execution_category, 4),
            (compute_damage_category, 4),
            (compute_consistency_category, 4),
            (compute_utility_category, 6),
        ]:
            category = compute_fn(db, character.id)
            assert category.status == CategoryStatus.UNAVAILABLE
            assert category.score is None
            assert len(category.metrics) == expected_metric_count
            assert all(m.normalized_value is None for m in category.metrics)
            assert all(m.note for m in category.metrics)
            assert category.note
    finally:
        db.close()
