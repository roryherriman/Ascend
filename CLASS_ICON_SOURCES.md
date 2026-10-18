# Class Icon Sources

Ascend uses two sources for World of Warcraft class icons, in preference order:

## Status of released builds

**Every published release (v0.1.0 to v1.0.0) ships only the original SVG glyphs described in section 2.** No Blizzard class-icon images are included in any released ZIP. This was verified on 2026-10-18 by inspecting all five release archives.

## 1. Blizzard Game Data API (optional, local only, do not redistribute)

`scripts/fetch_assets.py` can download class icon images (`ascend/resources/class_icons/*.png`) from the Blizzard Game Data API `/data/wow/media/playable-class/{classId}` endpoint. These files are gitignored and must **not** be bundled into public releases:

- They are Blizzard Entertainment property, obtained under the [Blizzard Developer API Terms of Use](https://www.blizzard.com/en-gb/legal/a2989b50-5f16-43b1-abec-2ae17cc09dd6/blizzard-developer-api-terms-of-use).
- Those terms require a maximum 30-day retention (TTL) for data obtained through the APIs (§2, item 18). A static image baked into a downloadable ZIP can't meet that.
- Before any release, confirm that `ascend/resources/class_icons/` contains no `.png`/`.jpg` files.

## 2. Original SVG glyphs (fallback)

If PNG files have not been fetched (e.g. running from source without credentials),
the app falls back to original SVG glyphs in `ascend/resources/class_icons/*.svg`.

These are original artwork created for Ascend and are committed to the repository.
See `ascend/resources/class_icons/LICENSE.txt` for the license.

---

*To fetch the Blizzard icons for local use only, set `BNET_CLIENT_ID` and `BNET_CLIENT_SECRET`
environment variables and run `python scripts/fetch_assets.py`.*
