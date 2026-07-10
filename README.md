# Ascend

**Know exactly how you're performing in raid — with the evidence to back it up.**

Ascend is a free Windows desktop app for competitive World of Warcraft raiders. It pulls your raid data from Warcraft Logs and gives you a clear, honest breakdown of how you're performing across your whole progression tier — not just a parse color, but real answers to questions like *am I actually improving?*, *do I keep dying to the same mechanic?*, and *is my attendance and effort showing up in the data?*

> Ascend is an independent community tool. It is not affiliated with, endorsed by,
> or sponsored by Blizzard Entertainment or Warcraft Logs.

---

## What Ascend does

### Tracks your full progression arc

Every pull you've logged on a boss — from your first wipe to your kill and every farm reclear after — is organized into a clear timeline. You can see exactly which pull you got the kill, how your kill rate improved across pull ranges (pulls 1–10, 11–25, 26–50, 51+), and how your team's performance changed night to night.

### Shows you how you're actually improving

The Trends page charts your kill rate across pull ranges so you can see whether you're genuinely learning a boss or spinning your wheels. It compares early pulls against late progression pulls and tells you whether your raid is trending in the right direction.

### Breaks down your performance score with full evidence

The Insights page gives you a confidence-weighted score across seven categories:

| Category | What it measures |
|---|---|
| **Survival** | How often you're alive, how early you die, and where you fall in the death order |
| **Execution** | How consistently you handle assigned mechanics and avoid confirmed failures |
| **Damage** | Boss damage and priority target damage relative to your raidmates, adjusted for time alive |
| **Consistency** | How stable your performance is pull to pull — not just your best parse |
| **Learning** | How quickly your wipe rate drops and mistakes get corrected over progression |
| **Utility** | Defensive cooldown usage, interrupts, dispels, and configured assignments |
| **Participation** | How often you're present across all logged raid nights |

Every score shows you exactly how it was computed: the raw value, the comparison baseline, how confident Ascend is in the number, and how many pulls it's based on. Nothing is hidden.

### Keeps data quality honest

If Ascend doesn't have enough data to score a category reliably — too few pulls, missing event data, unrecognized character — it tells you. Missing data lowers confidence, not the score itself. You won't get a misleadingly low score just because a category couldn't be measured.

### Exports your data

Save your encounter progression summary and roster attendance as CSV or a styled HTML report you can open in any browser. No formatting, no spreadsheet gymnastics — just the data.

---

## What makes it different from just looking at Warcraft Logs

Warcraft Logs shows you where you rank on a given parse. Ascend looks across your entire tier and asks different questions:

- Are you improving pull over pull, or are you stuck?
- Do you die to the same mechanic repeatedly, or are your deaths random?
- Is your participation and preparation actually reflected in the data?
- What does your performance look like on progression pulls specifically, not just your best farm kill?

Parse color tells you how you compare to everyone who's ever done the fight. Ascend tells you how *you're* doing relative to your own history and your own raidmates.

---

## Getting started

1. Install **Python 3.11+** (check "Add python.exe to PATH" during install).
2. Double-click **`setup.bat`** — sets up the environment and installs everything automatically.
3. Double-click **`run_app.bat`** to launch Ascend.
4. On first launch, enter your Warcraft Logs API credentials and add your character. You can get free API credentials at [warcraftlogs.com](https://www.warcraftlogs.com/api/clients/).
5. Paste any Warcraft Logs report URL into Ascend and click **Analyze** to import it.

No command line needed after setup.

### Getting Warcraft Logs API credentials

Ascend uses the official Warcraft Logs API — the same one third-party tools like raid planners and log viewers use. To get credentials:

1. Go to [warcraftlogs.com/api/clients](https://www.warcraftlogs.com/api/clients/)
2. Click **Create Client** and give it any name (e.g. "Ascend")
3. Copy the **Client ID** and **Client Secret** into Ascend's Settings page

Your credentials stay on your computer — they are never sent anywhere except directly to Warcraft Logs to authenticate.

---

## Your data stays on your computer

Ascend is local-first. Your raid analysis, character history, encounter data, and settings are stored in a SQLite database on your own machine. Nothing is uploaded to any server. The only outbound connections Ascend makes are to the Warcraft Logs API when you explicitly fetch a report.

Your Warcraft Logs client secret is stored in the Windows Credential Manager — the same system your browser uses for saved passwords. It is never written to a plain text file or database.

---

## What's available now

- **Dashboard** — overview of your raid activity and quick insights
- **Reports** — import and manage your Warcraft Logs reports
- **Raid Night Summary** — pull counts, kills, and encounter breakdown per night
- **Encounter Analysis** — per-boss pull history with progression vs. farm classification
- **Encounter Progression** — visual progression arc from first pull to kill, pull-range bucket stats
- **Learning & Trends** — kill rate trends across pull ranges and raid nights
- **Death Review** — raw death evidence from your logs (structured parsing coming with verified event data)
- **Roster Comparison** — attendance across everyone you raid with
- **Data Quality** — flags characters not yet matched, reports with gaps, and small sample sizes
- **Insights** — full score breakdown with category-by-category evidence
- **Export** — save encounter and roster data as CSV or HTML

---

## Disclaimer

Ascend is an independent community project and is not affiliated with, endorsed by, or sponsored by Blizzard Entertainment or Warcraft Logs.

World of Warcraft and related trademarks are the property of Blizzard Entertainment. Class icons and imagery used in Ascend are sourced and used in accordance with Blizzard's fan content policies — see [docs/ASSET_LICENSES.md](docs/ASSET_LICENSES.md).
