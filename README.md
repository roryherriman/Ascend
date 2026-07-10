# Ascend

**Understand how you actually perform during progression — not just what color your parse is.**

Ascend is a free Windows desktop app for World of Warcraft raiders. It connects to Warcraft Logs and analyzes your raid history across an entire tier, helping you understand:

- whether you are improving
- how often you die early
- whether you repeat the same mistakes
- how consistent your performance is
- how you compare with your own raid team
- whether missing data is affecting the result

Ascend is an independent community project and is not affiliated with Blizzard Entertainment or Warcraft Logs.

---

## Download

Download the latest portable build from the **Releases** page:

**[Ascend-Portable-0.2.0.zip](https://github.com/roryherriman/Ascende/releases/tag/v0.2.0)**

Unzip anywhere and run `Ascend.exe`. No installation required.

> **Windows SmartScreen** may warn that Ascend is from an unknown publisher. This is expected for an unsigned community tool. Click **More info → Run anyway** to proceed.

**Windows 10 and 11 (64-bit) are supported.**

---

## What Ascend does

Ascend pulls your raid data from Warcraft Logs and organizes it across an entire progression tier — every pull, every boss, every raid night.

From that data it builds:

- a **pull-by-pull timeline** showing when you got each kill and how your kill rate changed across progression
- a **death breakdown** flagging how often you die early and whether you repeat the same deaths
- a **performance score** across seven categories (survival, execution, damage, consistency, learning, utility, participation), each with a confidence level based on how much data Ascend actually has
- a **roster comparison** showing how your attendance and performance compare to your raidmates
- a **data quality view** that tells you when data is missing or too thin to score reliably

---

## First-time setup

1. Download and unzip `Ascend-Portable-0.2.0.zip`.
2. Run `Ascend.exe`.
3. The setup wizard walks you through:
   - Your display name and preferred region
   - Warcraft Logs client credentials (create a free client at [warcraftlogs.com/api/clients](https://www.warcraftlogs.com/api/clients/))
   - A connection test
   - Your characters (name, realm, class, role)
   - Your current raid tier and guild rank
4. Paste a Warcraft Logs report URL into the Dashboard and click **Analyze**.

---

## Your data stays on your computer

Ascend is local-first. Everything it stores — raid analysis, character history, settings — lives in a SQLite database on your machine at `%LOCALAPPDATA%\Ascend\`. Nothing is uploaded anywhere.

The only outbound connections Ascend makes are to the Warcraft Logs API when you explicitly fetch a report.

Your Warcraft Logs client secret is stored in Windows Credential Manager, not in a plain-text file.

**Backup:** File → Back Up Ascend Data saves a timestamped copy. File → Restore Ascend Data restores from a backup.

---

## Running from source

If you want to run from the Python source instead of the portable build:

1. Install **Python 3.11** (64-bit).
2. Run `setup.bat` to create the virtual environment and install dependencies.
3. Run `run_app.bat` to launch Ascend.

To build the portable ZIP yourself:

```
scripts\build_portable.bat
```

---

## Disclaimer

Ascend is an independent community project and is not affiliated with, endorsed by, or sponsored by Blizzard Entertainment or Warcraft Logs.

World of Warcraft and related trademarks are the property of Blizzard Entertainment. Class icons and imagery used in Ascend are sourced in accordance with Blizzard's fan content policies — see [docs/ASSET_LICENSES.md](docs/ASSET_LICENSES.md).
