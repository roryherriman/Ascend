# Asset Licenses and Attribution

## Disclaimer

> World of Warcraft and related assets are trademarks or copyrighted
> materials of Blizzard Entertainment. Ascend is an independent community
> project and is not affiliated with or endorsed by Blizzard Entertainment
> or Warcraft Logs.

This disclaimer is shown in the README and applies to every class/guild
visual described below.

## Class icons (`ascend/resources/class_icons/`)

Ascend does not have access to Blizzard's actual class icon artwork, and
deliberately does not scrape it from any website. Before building this
feature, the Warcraft Logs API v2 schema (`GameClass`, `GameSpec`,
`GameFaction`) was checked for an icon/image field - it does not expose
one (see `docs/WCL_API.md`). Retrieving real Blizzard class icons would
require a separate Battle.net Game Data API integration (its own OAuth
client, distinct from the Warcraft Logs credentials), which is out of
scope until a future phase, if ever pursued.

Instead, each class has an **original, hand-authored abstract glyph**
(see `ascend/resources/class_icons/LICENSE.txt`) paired with the
conventional World of Warcraft class color - a widely-published reference
hex value, not itself a copyrighted asset. These glyphs do not reproduce
Blizzard's class icon artwork.

An "Unknown" neutral glyph is shown for any character whose class isn't
recognized.

## Nav/UI icons (`ascend/resources/icons/`)

Also original, hand-authored SVGs - see that folder's own `LICENSE.txt`.
Not WoW-specific; used for sidebar navigation and general UI chrome.

## Guild icons

Verified before implementation: the Warcraft Logs `Guild` type exposes
`id`, `name`, `server`, `faction`, `description`, `competitionMode`,
`stealthMode`, `tags`, `members`, `currentUserRank`, `zoneRanking`, `type`,
`parentGuild`, `teams` - **no emblem, crest, icon, or image-URL field**.
Ascend does not have Battle.net Game Data API credentials configured
either. Per the preferred source order (WCL API -> Battle.net API ->
local fallback), Ascend always falls through to:

1. **A locally generated badge** (`ascend/services/guild_icon_service.py`):
   the guild's initials on an Ascend-branded ring, rendered with `QPainter`
   - no downloaded or scraped image involved.
2. **A user-chosen local image**, set via Settings -> "Choose Custom
   Image...". This file is copied into the local guild-icon cache folder
   and is **never uploaded, transmitted, or committed automatically**.

If real Warcraft Logs or Battle.net guild-image support is added in a
later phase, it slots into the same `source_type` column
(`guild_icons.source_type = 'official_api'`) without a schema change.

## Guild icon cache

Stored under `%LOCALAPPDATA%\Ascend\guild_icons\` - outside the git
repository entirely, so it's never at risk of being committed regardless
of `.gitignore`. Tracked per guild (region + realm + guild name + guild ID)
in the `guild_icons` SQLite table: source URL (if any), source type,
last-retrieved time, cache file path, and retrieval status - so Ascend
never regenerates or redownloads on every launch, and the user can
refresh, clear, replace, or reset it from Settings.
