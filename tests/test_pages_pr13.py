"""PR 13: QTableWidget removed from InsightsPage and DataQualityPage."""
from __future__ import annotations


def _make_db(tmp_path):
    from ascend.data.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_insights_page_has_no_table_widget(tmp_path, qtbot):
    from PySide6.QtWidgets import QTableWidget
    from ascend.ui.insights_page import InsightsPage
    db = _make_db(tmp_path)
    page = InsightsPage(db)
    qtbot.addWidget(page)
    assert not page.findChildren(QTableWidget)
    db.close()


def test_insights_page_loads_with_no_characters(tmp_path, qtbot):
    from ascend.ui.insights_page import InsightsPage
    db = _make_db(tmp_path)
    page = InsightsPage(db)
    qtbot.addWidget(page)
    assert page._empty_state is not None
    assert page._body.count() == 0
    db.close()


def test_data_quality_page_has_no_table_widget(tmp_path, qtbot):
    from PySide6.QtWidgets import QTableWidget
    from ascend.ui.data_quality_page import DataQualityPage
    db = _make_db(tmp_path)
    page = DataQualityPage(db)
    qtbot.addWidget(page)
    assert not page.findChildren(QTableWidget)
    db.close()


def test_data_quality_confidence_shows_empty_state(tmp_path, qtbot):
    from ascend.ui.data_quality_page import DataQualityPage
    db = _make_db(tmp_path)
    page = DataQualityPage(db)
    qtbot.addWidget(page)
    # No characters -> one "no data" label widget
    assert page._confidence_rows_layout.count() == 1
    db.close()


def test_data_quality_sync_shows_empty_state(tmp_path, qtbot):
    from ascend.ui.data_quality_page import DataQualityPage
    db = _make_db(tmp_path)
    page = DataQualityPage(db)
    qtbot.addWidget(page)
    # No sync history -> one "no history" label widget
    assert page._sync_rows_layout.count() == 1
    db.close()
