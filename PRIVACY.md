# Ascend privacy notice

*Last updated: 2026-10-18*

Ascend is a free desktop app that runs on your own Windows PC. There's no Ascend server, no account, and no analytics or telemetry. Nothing is sent to the author.

## What Ascend stores on your PC

Everything is stored under `%LOCALAPPDATA%\Ascend\`:

| What | Where |
|---|---|
| **Your characters:** display name, character name, region, realm, class, role, Warcraft Logs character ID, and any notes you add | `ascend.db` (SQLite) |
| **App settings**, including your guild, raid tier, and your Warcraft Logs and Battle.net client IDs | `ascend.db` |
| **Warcraft Logs reports you fetch:** report code, title, the uploader's Warcraft Logs name, guild name, zone, dates, fights, and the **character names, realms and classes of the players in those reports**, plus copies of the API responses | `ascend.db` |
| **Your own notes, goals and encounter rules** | `ascend.db` |
| **Sync history** (when a sync ran, how many reports it processed, and any error message) | `ascend.db` |
| **Guild badges:** a generated badge from your guild name, or, if you add Battle.net credentials, your guild's crest from Blizzard | `guild_icons\` |
| **Folder locations** for data and exports | `config.json` |
| **Logs:** app version, start-up information, errors, HTTP status codes and Warcraft Logs error messages. Logs never contain credentials. Files rotate at 2 MB, and 5 are kept | `logs\` |
| **Backups** created with **File → Back Up Ascend Data** (a copy of `ascend.db`) | `backups\` |

To show you where your combat log is, Ascend checks whether `WoWCombatLog.txt` exists in common World of Warcraft install folders and reads its size and date. **It never opens or uploads the file's contents.**

### Credentials

Your Warcraft Logs client secret, Battle.net client secret (optional) and Discord webhook URL (optional) are stored in **Windows Credential Manager**, under entries named `Ascend`. If Credential Manager isn't available, they're stored in a file encrypted with Windows DPAPI, tied to your Windows login. If neither is available, they're stored in a file that is only obfuscated, **not encrypted**, and Settings shows a red warning when that happens.

Credentials are never written to the database, logs or exports. Ascend uses API client credentials only and never asks for your Blizzard or Warcraft Logs account password.

## What Ascend sends, and to whom

Ascend connects to these services only when you take an action that needs them:

- **Warcraft Logs API** (RPGLogs, LLC): your API client ID and secret, and the report codes, guilds and zones you look up. Ascend only accesses **public** reports. See the [RPGLogs API Terms of Service](https://www.archon.gg/classic-mop/articles/help/rpg-logs-api-terms-of-service).
- **Blizzard Battle.net API** (optional, only if you add Battle.net credentials): your Battle.net client ID and secret, and your guild's region, realm and name, to fetch its crest. Blizzard is the source of that data. See the [Blizzard Developer API Terms of Use](https://www.blizzard.com/en-gb/legal/a2989b50-5f16-43b1-abec-2ae17cc09dd6/blizzard-developer-api-terms-of-use).
- **Discord** (optional): when you click to post a summary or send a test, Ascend sends a message to the webhook **you** configured. The weekly summary contains the number of raid nights, pulls and kills, the kill rate and boss names. **It doesn't include player names.** Anyone who can read that Discord channel can see it. Ascend only sends to `https://` webhook URLs on Discord's own domains.

**Help → Check for Updates** and the report links open pages in your web browser. Ascend itself doesn't contact GitHub or Warcraft Logs' website.

## Exports

The **Export** page saves JSON, CSV or HTML files wherever you choose. Exports can include encounter summaries and **roster attendance with player names, realms and classes**. Check an export before sharing it.

## Other players' data

Reports contain other players' character names, realms and classes from public Warcraft Logs reports. Ascend keeps them only on your PC, for your own analysis. Please don't publish exports containing other players' details without their agreement.

## Keeping and deleting your data

Data stays until you delete it.

- **Delete individual reports** from the Reports page.
- **Settings → Reset** deletes `ascend.db`, guild badges and `config.json`, and can also remove your saved Warcraft Logs secret and Discord webhook. Reset does **not** remove the Battle.net secret, backups, logs or exports.
- **To remove everything:** delete the `%LOCALAPPDATA%\Ascend\` folder, delete any exports you saved elsewhere, and remove the `Ascend` entries from Windows Credential Manager.
- **To remove a single credential:** clear it in Settings and save.

## Children

Ascend isn't directed at children and doesn't collect any information about who uses it.

## Changes and contact

Changes to this notice are recorded in this file's history on GitHub. For questions, open an issue at https://github.com/roryherriman/Ascende/issues.
