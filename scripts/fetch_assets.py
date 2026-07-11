"""Build-time script: fetch Blizzard class icons and save to resources/class_icons/.

Usage (from repo root):
    BNET_CLIENT_ID=xxx BNET_CLIENT_SECRET=yyy python scripts/fetch_assets.py

Requires:
    pip install requests

The downloaded image files (.png extension, JPEG content — QPixmap handles both)
are gitignored. Only CLASS_ICON_SOURCES.md (attribution) is committed.

Class IDs are stable Blizzard numeric identifiers that do not change between patches.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

BLIZZARD_CLASS_IDS: dict[str, int] = {
    "warrior": 1,
    "paladin": 2,
    "hunter": 3,
    "rogue": 4,
    "priest": 5,
    "death_knight": 6,
    "shaman": 7,
    "mage": 8,
    "warlock": 9,
    "monk": 10,
    "druid": 11,
    "demon_hunter": 12,
    "evoker": 13,
}

OAUTH_URL = "https://us.battle.net/oauth/token"
API_BASE = "https://us.api.blizzard.com"
NAMESPACE = "static-us"
LOCALE = "en_US"

OUT_DIR = Path(__file__).parent.parent / "ascend" / "resources" / "class_icons"


def _get_access_token(client_id: str, client_secret: str) -> str:
    resp = requests.post(
        OAUTH_URL,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _fetch_class_icon_url(token: str, class_id: int) -> str | None:
    url = f"{API_BASE}/data/wow/media/playable-class/{class_id}"
    resp = requests.get(
        url,
        params={"namespace": NAMESPACE, "locale": LOCALE},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    assets = resp.json().get("assets", [])
    for asset in assets:
        if asset.get("key") == "icon":
            return asset["value"]
    return None


def _download_icon(icon_url: str, dest_path: Path) -> None:
    resp = requests.get(icon_url, timeout=20)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)


def main() -> None:
    client_id = os.environ.get("BNET_CLIENT_ID", "").strip()
    client_secret = os.environ.get("BNET_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print(
            "ERROR: BNET_CLIENT_ID and BNET_CLIENT_SECRET environment variables must be set.\n"
            "Register an application at https://develop.battle.net/ to obtain credentials.",
            file=sys.stderr,
        )
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Authenticating with Battle.net OAuth...")
    try:
        token = _get_access_token(client_id, client_secret)
    except requests.HTTPError as exc:
        print(f"ERROR: OAuth token request failed: {exc}", file=sys.stderr)
        sys.exit(1)

    ok = 0
    failed: list[str] = []

    for slug, class_id in BLIZZARD_CLASS_IDS.items():
        dest = OUT_DIR / f"{slug}.png"
        print(f"  [{class_id:>2}] {slug} ... ", end="", flush=True)
        try:
            icon_url = _fetch_class_icon_url(token, class_id)
            if not icon_url:
                print("SKIP (no icon asset returned)")
                failed.append(slug)
                continue
            _download_icon(icon_url, dest)
            print(f"OK ({dest.name})")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED: {exc}")
            failed.append(slug)

    print(f"\n{ok}/{len(BLIZZARD_CLASS_IDS)} icons downloaded to {OUT_DIR}")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
