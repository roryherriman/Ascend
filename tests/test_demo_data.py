from ascend.data.database import Database
from ascend.data.repositories import ReportRepository
from ascend.services.demo_data import ensure_demo_report_seeded


def test_demo_report_is_seeded(tmp_path):
    db = Database(tmp_path / "demo.db")
    db.initialize()
    try:
        ensure_demo_report_seeded(db)
        reports = ReportRepository(db).list_all()
        assert len(reports) == 1
        assert reports[0].fight_count == 2
    finally:
        db.close()


def test_demo_report_seeding_is_idempotent(tmp_path):
    db = Database(tmp_path / "demo.db")
    db.initialize()
    try:
        ensure_demo_report_seeded(db)
        ensure_demo_report_seeded(db)
        reports = ReportRepository(db).list_all()
        assert len(reports) == 1
    finally:
        db.close()
