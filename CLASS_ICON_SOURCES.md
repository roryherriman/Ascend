# Class Icon Sources

Ascend uses two sources for World of Warcraft class icons, in preference order:

## 1. Blizzard Game Data API (preferred, build-time fetch)

Class icon images (`ascend/resources/class_icons/*.png`) are fetched at build time
from the Blizzard Game Data API using the `/data/wow/media/playable-class/{classId}`
endpoint.

These files are **not committed to the repository** (gitignored). They are downloaded
by `scripts/fetch_assets.py` before building a release, then bundled into the
distributable ZIP.

**Usage rights:** Images are property of Blizzard Entertainment, Inc. and are used in
accordance with the [Blizzard Game APIs Terms of Use](https://www.blizzard.com/en-us/legal/a2989b50-54b6-4a16-bff7-5d4dea46e87f/blizzard-developer-api-terms-of-use).
Ascend is a free, non-commercial application.

## 2. Original SVG glyphs (fallback)

If PNG files have not been fetched (e.g. running from source without credentials),
the app falls back to original SVG glyphs in `ascend/resources/class_icons/*.svg`.

These are original artwork created for Ascend and are committed to the repository.
See `ascend/resources/class_icons/LICENSE.txt` for the license.

---

*To regenerate the fetched icons, set `BNET_CLIENT_ID` and `BNET_CLIENT_SECRET`
environment variables and run `python scripts/fetch_assets.py`.*
