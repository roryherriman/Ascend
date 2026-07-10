"""Parses Warcraft Logs report URLs (or raw report codes) into a report code
plus optional fight/boss/type/source hints.

The URL is only ever used to extract these identifiers locally; all report
data itself is retrieved through the official Warcraft Logs GraphQL API, and
the raw input string is never sent anywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_ALLOWED_HOSTS = {
    "www.warcraftlogs.com",
    "warcraftlogs.com",
    "classic.warcraftlogs.com",
    "vanilla.warcraftlogs.com",
    "fresh.warcraftlogs.com",
    "sod.warcraftlogs.com",
}

_REPORT_CODE_RE = re.compile(r"^[A-Za-z0-9]{6,20}$")
_REPORT_PATH_RE = re.compile(r"/reports/([A-Za-z0-9]{6,20})")


class InvalidReportReferenceError(ValueError):
    """Raised when the input isn't a recognizable Warcraft Logs report URL or code."""


@dataclass
class ParsedReportReference:
    report_code: str
    fight: int | None = None
    fight_is_last: bool = False
    boss: int | None = None
    view_type: str | None = None
    source: int | None = None
    raw_input: str = ""


def parse_report_reference(raw_input: str) -> ParsedReportReference:
    text = (raw_input or "").strip()
    if not text:
        raise InvalidReportReferenceError("Enter a Warcraft Logs report URL or report code.")

    if _REPORT_CODE_RE.fullmatch(text):
        return ParsedReportReference(report_code=text, raw_input=raw_input)

    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        raise InvalidReportReferenceError(
            f"'{raw_input}' doesn't look like a Warcraft Logs report URL or report code."
        )

    if parsed.netloc.lower() not in _ALLOWED_HOSTS:
        raise InvalidReportReferenceError(
            "Only warcraftlogs.com report links (or a bare report code) are supported."
        )

    match = _REPORT_PATH_RE.search(parsed.path)
    if not match:
        raise InvalidReportReferenceError("Could not find a report code in that URL.")
    report_code = match.group(1)

    params = parse_qs(parsed.fragment) if parsed.fragment else {}

    fight: int | None = None
    fight_is_last = False
    if "fight" in params:
        fight_value = params["fight"][0]
        if fight_value == "last":
            fight_is_last = True
        else:
            try:
                fight = int(fight_value)
            except ValueError as exc:
                raise InvalidReportReferenceError(
                    f"Invalid fight value in URL: '{fight_value}'."
                ) from exc

    boss: int | None = None
    if "boss" in params:
        try:
            boss = int(params["boss"][0])
        except ValueError:
            boss = None  # unrecognized boss param is ignored, not a hard failure

    source: int | None = None
    if "source" in params:
        try:
            source = int(params["source"][0])
        except ValueError:
            source = None

    view_type = params.get("type", [None])[0]

    return ParsedReportReference(
        report_code=report_code,
        fight=fight,
        fight_is_last=fight_is_last,
        boss=boss,
        view_type=view_type,
        source=source,
        raw_input=raw_input,
    )


def build_report_url(report_code: str, fight: int | None = None) -> str:
    """Construct a warcraftlogs.com URL from a report code (and optional fight)."""
    url = f"https://www.warcraftlogs.com/reports/{report_code}"
    if fight is not None:
        url += f"#fight={fight}"
    return url
