import pytest

from ascend.api.url_parser import InvalidReportReferenceError, build_report_url, parse_report_reference


def test_bare_report_code():
    result = parse_report_reference("AbCdEfGh123456")
    assert result.report_code == "AbCdEfGh123456"
    assert result.fight is None
    assert result.fight_is_last is False


def test_full_report_url():
    result = parse_report_reference("https://www.warcraftlogs.com/reports/ABC123xyz")
    assert result.report_code == "ABC123xyz"
    assert result.fight is None


def test_url_with_fight_number():
    result = parse_report_reference("https://www.warcraftlogs.com/reports/ABC123xyz#fight=12")
    assert result.report_code == "ABC123xyz"
    assert result.fight == 12
    assert result.fight_is_last is False


def test_url_with_fight_last():
    result = parse_report_reference("https://www.warcraftlogs.com/reports/ABC123xyz#fight=last")
    assert result.report_code == "ABC123xyz"
    assert result.fight is None
    assert result.fight_is_last is True


def test_url_with_boss_param():
    result = parse_report_reference("https://www.warcraftlogs.com/reports/ABC123xyz#boss=-2")
    assert result.report_code == "ABC123xyz"
    assert result.boss == -2


def test_url_with_type_param():
    result = parse_report_reference("https://www.warcraftlogs.com/reports/ABC123xyz#type=damage-done")
    assert result.report_code == "ABC123xyz"
    assert result.view_type == "damage-done"


def test_url_with_combined_fragment_params():
    result = parse_report_reference(
        "https://www.warcraftlogs.com/reports/ABC123xyz#fight=12&type=damage-done"
    )
    assert result.report_code == "ABC123xyz"
    assert result.fight == 12
    assert result.view_type == "damage-done"


def test_url_ignores_unrelated_fragment_params():
    result = parse_report_reference(
        "https://www.warcraftlogs.com/reports/ABC123xyz#fight=12&translate=true&something=else"
    )
    assert result.report_code == "ABC123xyz"
    assert result.fight == 12


def test_classic_subdomain_is_supported():
    result = parse_report_reference("https://classic.warcraftlogs.com/reports/ABC123xyz")
    assert result.report_code == "ABC123xyz"


def test_empty_input_is_rejected():
    with pytest.raises(InvalidReportReferenceError):
        parse_report_reference("")


def test_whitespace_only_input_is_rejected():
    with pytest.raises(InvalidReportReferenceError):
        parse_report_reference("   ")


def test_non_warcraftlogs_domain_is_rejected():
    with pytest.raises(InvalidReportReferenceError):
        parse_report_reference("https://example.com/reports/ABC123xyz")


def test_malformed_url_is_rejected():
    with pytest.raises(InvalidReportReferenceError):
        parse_report_reference("https://www.warcraftlogs.com/not-a-report-path")


def test_invalid_fight_value_is_rejected():
    with pytest.raises(InvalidReportReferenceError):
        parse_report_reference("https://www.warcraftlogs.com/reports/ABC123xyz#fight=notanumber")


def test_build_report_url_without_fight():
    assert build_report_url("ABC123xyz") == "https://www.warcraftlogs.com/reports/ABC123xyz"


def test_build_report_url_with_fight():
    assert build_report_url("ABC123xyz", fight=5) == "https://www.warcraftlogs.com/reports/ABC123xyz#fight=5"
