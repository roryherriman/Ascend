"""Tests for Issues #10 (Goals), #12 (Encounter Rules), #13 (Discord weekly summary)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ascend.data.database import Database


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path) -> Database:
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


# ---------------------------------------------------------------------------
# Issue #10 — Goals service
# ---------------------------------------------------------------------------

class TestGoalsRepository:
    def test_empty_on_fresh_db(self, tmp_path):
        from ascend.services.goals_service import GoalsRepository
        db = _make_db(tmp_path)
        repo = GoalsRepository(db)
        assert repo.list_all() == []

    def test_create_and_list(self, tmp_path):
        from ascend.services.goals_service import Goal, GoalsRepository
        db = _make_db(tmp_path)
        repo = GoalsRepository(db)
        g = repo.create(Goal(id=None, title="Kill Mythic Sark", description="", metric_key="manual", target_value=1.0))
        goals = repo.list_all()
        assert len(goals) == 1
        assert goals[0].title == "Kill Mythic Sark"
        assert goals[0].id is not None

    def test_mark_achieved(self, tmp_path):
        from ascend.services.goals_service import Goal, GoalsRepository
        db = _make_db(tmp_path)
        repo = GoalsRepository(db)
        g = repo.create(Goal(id=None, title="G1", description="", metric_key="manual", target_value=1.0))
        assert repo.list_all()[0].achieved_at is None
        repo.mark_achieved(g.id)
        assert repo.list_all()[0].achieved_at is not None

    def test_unmark_achieved(self, tmp_path):
        from ascend.services.goals_service import Goal, GoalsRepository
        db = _make_db(tmp_path)
        repo = GoalsRepository(db)
        g = repo.create(Goal(id=None, title="G2", description="", metric_key="manual", target_value=1.0))
        repo.mark_achieved(g.id)
        repo.unmark_achieved(g.id)
        assert repo.list_all()[0].achieved_at is None

    def test_delete(self, tmp_path):
        from ascend.services.goals_service import Goal, GoalsRepository
        db = _make_db(tmp_path)
        repo = GoalsRepository(db)
        g = repo.create(Goal(id=None, title="G3", description="", metric_key="manual", target_value=1.0))
        repo.delete(g.id)
        assert repo.list_all() == []

    def test_days_remaining_future(self, tmp_path):
        from datetime import date, timedelta
        from ascend.services.goals_service import Goal
        future = (date.today() + timedelta(days=5)).isoformat()
        g = Goal(id=1, title="T", description="", metric_key="manual", target_value=1.0, target_date=future)
        assert g.days_remaining() == 5

    def test_is_overdue_past_date(self, tmp_path):
        from datetime import date, timedelta
        from ascend.services.goals_service import Goal
        past = (date.today() - timedelta(days=3)).isoformat()
        g = Goal(id=1, title="T", description="", metric_key="manual", target_value=1.0, target_date=past)
        assert g.is_overdue()

    def test_is_overdue_no_date(self, tmp_path):
        from ascend.services.goals_service import Goal
        g = Goal(id=1, title="T", description="", metric_key="manual", target_value=1.0)
        assert not g.is_overdue()


# ---------------------------------------------------------------------------
# Issue #10 — Goals page UI
# ---------------------------------------------------------------------------

class TestGoalsPage:
    def test_page_loads(self, qtbot, tmp_path):
        from ascend.ui.goals_page import GoalsPage
        db = _make_db(tmp_path)
        page = GoalsPage(db)
        qtbot.addWidget(page)
        assert page is not None

    def test_empty_state_when_no_goals(self, qtbot, tmp_path):
        from ascend.ui.goals_page import GoalsPage
        db = _make_db(tmp_path)
        page = GoalsPage(db)
        qtbot.addWidget(page)
        assert page._rows_layout.count() == 0

    def test_rows_shown_when_goals_exist(self, qtbot, tmp_path):
        from ascend.services.goals_service import Goal, GoalsRepository
        from ascend.ui.goals_page import GoalsPage
        db = _make_db(tmp_path)
        repo = GoalsRepository(db)
        repo.create(Goal(id=None, title="G1", description="", metric_key="manual", target_value=1.0))
        repo.create(Goal(id=None, title="G2", description="", metric_key="manual", target_value=1.0))
        page = GoalsPage(db)
        qtbot.addWidget(page)
        assert page._rows_layout.count() == 2


# ---------------------------------------------------------------------------
# Issue #12 — Encounter Rules service
# ---------------------------------------------------------------------------

class TestEncounterRulesRepository:
    def test_empty_on_fresh_db(self, tmp_path):
        from ascend.services.encounter_rules_service import EncounterRulesRepository
        db = _make_db(tmp_path)
        repo = EncounterRulesRepository(db)
        assert repo.list_all() == []

    def test_create_and_list(self, tmp_path):
        from ascend.services.encounter_rules_service import EncounterRule, EncounterRulesRepository
        db = _make_db(tmp_path)
        repo = EncounterRulesRepository(db)
        r = repo.create(EncounterRule(id=None, encounter_name="Sarkareth", mechanic_label="Soak", note="Always soak"))
        rules = repo.list_all()
        assert len(rules) == 1
        assert rules[0].encounter_name == "Sarkareth"
        assert rules[0].mechanic_label == "Soak"

    def test_rules_for_encounter(self, tmp_path):
        from ascend.services.encounter_rules_service import EncounterRule, EncounterRulesRepository
        db = _make_db(tmp_path)
        repo = EncounterRulesRepository(db)
        repo.create(EncounterRule(id=None, encounter_name="Boss1", mechanic_label="Stack", note=""))
        repo.create(EncounterRule(id=None, encounter_name="Boss2", mechanic_label="Spread", note=""))
        assert len(repo.rules_for_encounter("Boss1")) == 1
        assert len(repo.rules_for_encounter("Boss2")) == 1
        assert repo.rules_for_encounter("Boss3") == []

    def test_update(self, tmp_path):
        from ascend.services.encounter_rules_service import EncounterRule, EncounterRulesRepository
        db = _make_db(tmp_path)
        repo = EncounterRulesRepository(db)
        r = repo.create(EncounterRule(id=None, encounter_name="Boss", mechanic_label="Old", note=""))
        r.mechanic_label = "New"
        repo.update(r)
        assert repo.list_all()[0].mechanic_label == "New"

    def test_delete(self, tmp_path):
        from ascend.services.encounter_rules_service import EncounterRule, EncounterRulesRepository
        db = _make_db(tmp_path)
        repo = EncounterRulesRepository(db)
        r = repo.create(EncounterRule(id=None, encounter_name="Boss", mechanic_label="X", note=""))
        repo.delete(r.id)
        assert repo.list_all() == []


# ---------------------------------------------------------------------------
# Issue #12 — Encounter Rules page UI
# ---------------------------------------------------------------------------

class TestEncounterRulesPage:
    def test_page_loads(self, qtbot, tmp_path):
        from ascend.ui.encounter_rules_page import EncounterRulesPage
        db = _make_db(tmp_path)
        page = EncounterRulesPage(db)
        qtbot.addWidget(page)
        assert page is not None

    def test_empty_state_when_no_rules(self, qtbot, tmp_path):
        from ascend.ui.encounter_rules_page import EncounterRulesPage
        db = _make_db(tmp_path)
        page = EncounterRulesPage(db)
        qtbot.addWidget(page)
        assert page._rows_layout.count() == 0

    def test_rows_shown_when_rules_exist(self, qtbot, tmp_path):
        from ascend.services.encounter_rules_service import EncounterRule, EncounterRulesRepository
        from ascend.ui.encounter_rules_page import EncounterRulesPage
        db = _make_db(tmp_path)
        repo = EncounterRulesRepository(db)
        repo.create(EncounterRule(id=None, encounter_name="Boss1", mechanic_label="A", note=""))
        repo.create(EncounterRule(id=None, encounter_name="Boss2", mechanic_label="B", note=""))
        page = EncounterRulesPage(db)
        qtbot.addWidget(page)
        # col_header + 2 rows = 3
        assert page._rows_layout.count() == 3


# ---------------------------------------------------------------------------
# Issue #13 — Discord weekly summary service
# ---------------------------------------------------------------------------

class TestDiscordService:
    def test_build_summary_no_data(self, tmp_path):
        from ascend.services.discord_service import build_weekly_summary
        db = _make_db(tmp_path)
        summary = build_weekly_summary(db, days=7)
        assert "No raid nights" in summary

    def test_post_returns_false_when_no_url(self, tmp_path):
        from ascend.services.discord_service import post_weekly_summary
        db = _make_db(tmp_path)
        ok, msg = post_weekly_summary(db, webhook_url="")
        assert not ok
        assert "No Discord webhook" in msg

    def test_post_calls_requests(self, tmp_path):
        from ascend.services.discord_service import post_weekly_summary
        db = _make_db(tmp_path)
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        with patch("ascend.services.discord_service.requests.post", return_value=mock_resp) as mock_post:
            ok, msg = post_weekly_summary(db, webhook_url="https://discord.com/api/webhooks/fake")
        assert ok
        assert mock_post.called

    def test_post_returns_false_on_http_error(self, tmp_path):
        from ascend.services.discord_service import post_weekly_summary
        db = _make_db(tmp_path)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("ascend.services.discord_service.requests.post", return_value=mock_resp):
            ok, msg = post_weekly_summary(db, webhook_url="https://discord.com/api/webhooks/fake")
        assert not ok
        assert "401" in msg

    def test_post_returns_false_on_network_error(self, tmp_path):
        import requests as req_lib
        from ascend.services.discord_service import post_weekly_summary
        db = _make_db(tmp_path)
        with patch("ascend.services.discord_service.requests.post", side_effect=req_lib.exceptions.ConnectionError("timeout")):
            ok, msg = post_weekly_summary(db, webhook_url="https://discord.com/api/webhooks/fake")
        assert not ok
        assert "timeout" in msg

    def test_rejects_non_discord_url_without_posting(self, tmp_path):
        from ascend.services.discord_service import post_weekly_summary
        db = _make_db(tmp_path)
        with patch("ascend.services.discord_service.requests.post") as mock_post:
            for url in ("http://discord.com/api/webhooks/1/abc",          # not https
                        "https://evil.example/api/webhooks/1/abc",         # wrong host
                        "https://discord.com.evil.example/api/webhooks/1", # lookalike host
                        "https://discord.com/channels/1/2"):               # not a webhook
                ok, msg = post_weekly_summary(db, webhook_url=url)
                assert not ok
                assert "Discord webhook URL" in msg
        assert not mock_post.called

    def test_network_error_does_not_leak_webhook_token(self, tmp_path):
        import requests as req_lib
        from ascend.services.discord_service import post_weekly_summary
        db = _make_db(tmp_path)
        url = "https://discord.com/api/webhooks/123456/SECRET-TOKEN-VALUE"
        err = req_lib.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='discord.com', port=443): Max retries exceeded with url: "
            "/api/webhooks/123456/SECRET-TOKEN-VALUE?wait=true (Caused by timeout)"
        )
        with patch("ascend.services.discord_service.requests.post", side_effect=err):
            ok, msg = post_weekly_summary(db, webhook_url=url)
        assert not ok
        assert "SECRET-TOKEN-VALUE" not in msg
        assert "timeout" in msg

    def test_is_discord_webhook_url_accepts_official_hosts(self):
        from ascend.services.discord_service import is_discord_webhook_url
        assert is_discord_webhook_url("https://discord.com/api/webhooks/1/abc")
        assert is_discord_webhook_url("https://discordapp.com/api/webhooks/1/abc")
        assert is_discord_webhook_url(" https://ptb.discord.com/api/webhooks/1/abc ")
        assert not is_discord_webhook_url("")
