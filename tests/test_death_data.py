from ascend.data.database import Database
from ascend.services.death_data import fetch_and_cache_death_table, get_cached_death_table


class FakeClient:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def fetch_death_table(self, report_code, fight_ids=None):
        self.calls.append((report_code, fight_ids))
        return self._payload


def test_get_cached_death_table_returns_none_when_not_fetched(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        assert get_cached_death_table(db, "ABC123") is None
    finally:
        db.close()


def test_fetch_and_cache_stores_and_returns_payload(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        payload = {"entries": [{"name": "Aeloria", "deathTime": 12345}]}
        client = FakeClient(payload)

        result = fetch_and_cache_death_table(db, client, "ABC123", fight_ids=[1, 2])
        assert result == payload
        assert client.calls == [("ABC123", [1, 2])]

        cached = get_cached_death_table(db, "ABC123")
        assert cached == payload
    finally:
        db.close()


def test_fetch_and_cache_always_refetches_unlike_zone_difficulties(tmp_path):
    """Death data isn't static like zone difficulties - a second fetch must
    hit the client again, not silently serve a stale cache."""
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        client = FakeClient({"entries": []})
        fetch_and_cache_death_table(db, client, "ABC123")
        fetch_and_cache_death_table(db, client, "ABC123")
        assert len(client.calls) == 2
    finally:
        db.close()


def test_cache_is_per_report_code(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        client = FakeClient({"entries": ["night1"]})
        fetch_and_cache_death_table(db, client, "NIGHT1")
        assert get_cached_death_table(db, "NIGHT2") is None
    finally:
        db.close()


def test_handles_list_shaped_payload_not_just_dict(tmp_path):
    """The payload's shape isn't schema-guaranteed - could be a list, dict,
    or None (e.g. a fight with no deaths)."""
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        client = FakeClient([{"name": "Someone"}])
        result = fetch_and_cache_death_table(db, client, "ABC123")
        assert result == [{"name": "Someone"}]
        assert get_cached_death_table(db, "ABC123") == [{"name": "Someone"}]
    finally:
        db.close()
