from ascend.data.database import Database
from ascend.services.zone_data import ensure_zone_difficulties_cached, get_cached_zone_difficulties


class FakeClient:
    def __init__(self, difficulties):
        self._difficulties = difficulties
        self.calls = 0

    def fetch_zone_difficulties(self, zone_id):
        self.calls += 1
        return self._difficulties


def test_get_cached_zone_difficulties_returns_empty_when_not_cached(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        assert get_cached_zone_difficulties(db, 44) == {}
    finally:
        db.close()


def test_ensure_zone_difficulties_cached_fetches_once_and_caches(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        client = FakeClient([{"id": 3, "name": "Normal"}, {"id": 4, "name": "Heroic"}, {"id": 5, "name": "Mythic"}])

        result = ensure_zone_difficulties_cached(db, client, 44)
        assert result == {3: "Normal", 4: "Heroic", 5: "Mythic"}
        assert client.calls == 1

        # Second call should be served from cache, not hit the client again.
        result2 = ensure_zone_difficulties_cached(db, client, 44)
        assert result2 == {3: "Normal", 4: "Heroic", 5: "Mythic"}
        assert client.calls == 1

        assert get_cached_zone_difficulties(db, 44) == {3: "Normal", 4: "Heroic", 5: "Mythic"}
    finally:
        db.close()


def test_ensure_zone_difficulties_cached_is_per_zone(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    try:
        client = FakeClient([{"id": 3, "name": "Normal"}])
        ensure_zone_difficulties_cached(db, client, 44)
        assert get_cached_zone_difficulties(db, 99) == {}
    finally:
        db.close()
