"""Tests for ascend/services/fixture_sanitizer.py.

Verifies that the sanitizer replaces the right fields, preserves structural
keys, and that the load/export round-trip works correctly.
"""
import json
from pathlib import Path

from ascend.services.fixture_sanitizer import (
    FIXTURE_SCHEMA_VERSION,
    export_fixture_json,
    load_fixture,
    sanitize_fixture,
)

_SAMPLE_PAYLOAD = {
    "reportData": {
        "report": {
            "code": "AbCdEfGhIj",
            "title": "My Guild's Raid Night",
            "guildName": "Test Guild",
            "startTime": 1700000000000,
            "endTime": 1700007200000,
            "masterData": {
                "actors": [
                    {"id": 1, "name": "Kysarra", "displayName": "Kysarra", "server": "Stormrage"},
                    {"id": 2, "name": "Mookson", "displayName": "Mookson", "server": "Stormrage"},
                ],
            },
            "events": {
                "data": [
                    {"timestamp": 1700001000000, "type": "death", "sourceID": 1, "targetID": 2, "abilityGameID": 12345},
                    {"timestamp": 1700002000000, "type": "damage", "sourceID": 2, "targetID": -1, "amount": 50000},
                ],
            },
        }
    },
    "accessToken": "super-secret-token-abc123",
}


def test_envelope_structure():
    result = sanitize_fixture(_SAMPLE_PAYLOAD)
    assert result["ascend_fixture"] is True
    assert result["sanitized"] is True
    assert "warning" in result
    assert result["schema_version"] == FIXTURE_SCHEMA_VERSION
    assert "payload" in result
    assert "exported_at" in result
    assert "timestamp_shift_ms" in result


def test_access_token_is_redacted():
    result = sanitize_fixture(_SAMPLE_PAYLOAD)
    assert result["payload"]["accessToken"] == "<redacted>"


def test_report_code_is_replaced_not_removed():
    result = sanitize_fixture(_SAMPLE_PAYLOAD)
    sanitized_code = result["payload"]["reportData"]["report"]["code"]
    assert sanitized_code != "AbCdEfGhIj"
    assert sanitized_code.startswith("FIXTURE")


def test_same_code_maps_to_same_hash_within_one_export():
    payload = {"code": "XxYy1234", "nested": {"code": "XxYy1234"}}
    result = sanitize_fixture(payload)
    assert result["payload"]["code"] == result["payload"]["nested"]["code"]


def test_player_names_replaced_with_placeholders():
    result = sanitize_fixture(_SAMPLE_PAYLOAD)
    actors = result["payload"]["reportData"]["report"]["masterData"]["actors"]
    for actor in actors:
        assert actor["name"].startswith("Player")
        assert actor["displayName"].startswith("Player")


def test_consistent_name_replacement_within_one_export():
    """The same name must map to the same placeholder throughout the fixture."""
    payload = {
        "actors": [{"name": "Kysarra"}, {"name": "Kysarra"}],
    }
    result = sanitize_fixture(payload)
    assert result["payload"]["actors"][0]["name"] == result["payload"]["actors"][1]["name"]


def test_different_names_get_different_placeholders():
    payload = {
        "actors": [{"name": "Kysarra"}, {"name": "Mookson"}],
    }
    result = sanitize_fixture(payload)
    names = [a["name"] for a in result["payload"]["actors"]]
    assert names[0] != names[1]


def test_timestamps_are_shifted():
    result = sanitize_fixture(_SAMPLE_PAYLOAD)
    shift = result["timestamp_shift_ms"]
    report = result["payload"]["reportData"]["report"]
    assert report["startTime"] == 1700000000000 + shift
    assert report["endTime"] == 1700007200000 + shift


def test_non_timestamp_numerics_unchanged():
    result = sanitize_fixture(_SAMPLE_PAYLOAD)
    events = result["payload"]["reportData"]["report"]["events"]["data"]
    # abilityGameID and amount are not shifted
    assert events[0]["abilityGameID"] == 12345
    assert events[1]["amount"] == 50000


def test_structural_field_names_preserved():
    result = sanitize_fixture(_SAMPLE_PAYLOAD)
    report = result["payload"]["reportData"]["report"]
    assert "masterData" in report
    assert "events" in report
    assert "actors" in report["masterData"]
    assert "data" in report["events"]


def test_event_types_and_ids_preserved():
    result = sanitize_fixture(_SAMPLE_PAYLOAD)
    events = result["payload"]["reportData"]["report"]["events"]["data"]
    assert events[0]["type"] == "death"
    assert events[0]["sourceID"] == 1
    assert events[0]["targetID"] == 2
    assert events[1]["type"] == "damage"


def test_source_endpoint_label_preserved():
    result = sanitize_fixture({}, source_endpoint="reportData.report.events")
    assert result["source_endpoint"] == "reportData.report.events"


def test_export_fixture_json_is_valid_json():
    text = export_fixture_json(_SAMPLE_PAYLOAD, source_endpoint="test")
    parsed = json.loads(text)
    assert parsed["ascend_fixture"] is True


def test_load_fixture_round_trip(tmp_path):
    path = tmp_path / "fixture.json"
    text = export_fixture_json(_SAMPLE_PAYLOAD, source_endpoint="test")
    path.write_text(text, encoding="utf-8")
    payload = load_fixture(str(path))
    # payload is the sanitized API tree
    assert "reportData" in payload
    assert payload["accessToken"] == "<redacted>"


def test_load_fixture_rejects_non_fixture(tmp_path):
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    try:
        load_fixture(str(path))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_load_fixture_rejects_wrong_schema_version(tmp_path):
    path = tmp_path / "old.json"
    bad = {
        "ascend_fixture": True,
        "sanitized": True,
        "schema_version": 999,
        "payload": {},
    }
    path.write_text(json.dumps(bad), encoding="utf-8")
    try:
        load_fixture(str(path))
        assert False, "expected ValueError"
    except ValueError:
        pass
