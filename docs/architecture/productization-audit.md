# Ascend Productization Audit

**Date:** 2026-07-10  
**Baseline:** 193 tests passing  
**Branch:** feature/productization-pr-a  
**Purpose:** Repository-wide audit before public distribution. Every developer-specific or personal assumption discovered before and during PR A is documented here.

---

## Executive Summary

Ascend was originally built as a single-developer personal tool, with the developer's own characters, guild, server, and progression goals woven directly into production code. This audit identifies all assumptions that would create a broken or misleading experience for any public user and documents what was fixed (in this PR) versus what is deferred to later PRs.

---

## Personal Assumptions Discovered

### 1. Developer characters seeded into every new installation

**File:** `ascend/ui/characters_page.py`, lines 30–53  
**Severity:** BLOCKS PUBLIC RELEASE

`INITIAL_CHARACTERS` contains two real characters with real Warcraft Logs character IDs:
- **Kysarra** — Mage, US/Stormrage, WCL ID 108832382
- **Kyssandra** — Warlock, US/Stormrage, WCL ID 110023835

`seed_initial_characters()` is called on every application start (`MainWindow.__init__`). Every new user's database would be pre-populated with the developer's own characters.

**Fixed in this PR:** `INITIAL_CHARACTERS` removed. `seed_initial_characters()` is now a no-op for real users. Demo mode uses fictional characters via `seed_demo_characters()`.

---

### 2. "Your Mage and Warlock" hardcoded in first-run wizard

**File:** `ascend/ui/first_run_wizard.py`, line 154  
**Severity:** BLOCKS PUBLIC RELEASE

```python
"Ascend comes with your Mage and Warlock pre-configured."
```

This text appears during the first-run setup wizard for every new user, referencing class and count assumptions that are only true for the original developer.

**Fixed in this PR:** Replaced with neutral language: "Add the characters you play to get started."

---

### 3. Demo mode shows developer characters and guild name

**File:** `ascend/ui/dashboard_states.py`, lines 912–917  
**Severity:** BLOCKS PUBLIC RELEASE

Demo mode dashboard table shows:
- Character names: Kysarra, Kyssandra
- Guild: Ascend Raiders
- Encounters: Dimensius, Rasha'nan (real encounter names — acceptable, but personal progression context is not)

**Fixed in this PR:** Replaced with fictional characters from the Ascend demo roster:
- **Aeloria** — Mage
- **Thornveil** — Warlock
- **Kaelric** — Protection Warrior
- **Seraphyne** — Holy Priest
- Guild: **Stellar Ascent**

---

### 4. "Ranged roster median" assumed in demo insight

**File:** `ascend/ui/dashboard_states.py`, line 903  
**Severity:** BLOCKS PUBLIC RELEASE

```python
"Your active time was 6.2% below the ranged roster median."
```

Explicitly assumes the user is a ranged DPS player.

**Fixed in this PR:** Changed to role-neutral language: "Your active time was 6.2% below your role cohort median."

---

### 5. "Guild US Rank" field hardcoded as US-specific

**Files:**  
- `ascend/ui/first_run_wizard.py`, line 188  
- `ascend/ui/settings_page.py`, line 174  
- `ascend/ui/top_context_bar.py`, line 163  
- Settings key: `guild_us_rank`  
**Severity:** BLOCKS PUBLIC RELEASE

The word "US" appears in:
- The form label ("Guild US Rank:")
- The TopContextBar display text (`f"US Rank {guild_rank}"`)
- The persistent settings key `guild_us_rank`

A European, Korean, Taiwanese, or Chinese player's guild rank is labeled "US Rank" regardless of their actual region.

**Fixed in this PR:**
- Form label changed to "Guild Rank:"
- TopContextBar display changed to `f"Rank {guild_rank}"`
- Settings key remains `guild_us_rank` for backwards compatibility (migration to `guild_rank` is deferred to PR C with the full guild model redesign)

---

### 6. "Ascend Raiders" as placeholder text

**File:** `ascend/ui/settings_page.py`, line 165  
**Severity:** COSMETIC

```python
self.guild_name_edit.setPlaceholderText("e.g. Ascend Raiders")
```

**Fixed in this PR:** Changed to `"e.g. Example Guild Name"`.

---

### 7. "Stormrage" in demo report fixture

**File:** `ascend/resources/demo_report.json`, line 16  
**Severity:** COSMETIC

```json
"guild": { "name": "Test Guild", "server": { "name": "Stormrage" } }
```

Other fields are already sanitized (guild name, report owner, report code). Only the server remained as the developer's personal realm.

**Fixed in this PR:** Changed to `"Proudmoore"`.

---

### 8. "PHASE 1" rendered in sidebar footer for all users

**File:** `ascend/navigation.py`, line 170  
**Severity:** COSMETIC

A `QLabel("PHASE 1")` is displayed in the sidebar footer, visible to all users. Development phase numbers are internal engineering terminology and should not appear in a shipped product.

**Fixed in this PR:** Removed. The version label remains.

---

### 9. `phase=N` numbers passed to placeholder pages

**File:** `ascend/main_window.py`, `PLACEHOLDER_META`  
**Severity:** LOW (renders to users as "PHASE 3", "PHASE 4")

Placeholder pages for unfinished features show "PHASE N" badges. For end users, "Phase 4" is meaningless. The pages should explain *what will come* without internal phase labels.

**Fixed in this PR:** `phase=` removed from `PLACEHOLDER_META`. Placeholder widgets that render phase badges are updated to use "Coming Soon" or omit the badge entirely. The `PlaceholderPage` widget still accepts `phase=` for backwards compatibility but renders it as "Coming Soon" instead of "PHASE N".

---

### 10. GitHub repository URL typo

**File:** `ascend/metadata.py`, line 14  
**Severity:** LOW but BLOCKS RELEASE

```python
GITHUB_REPO = "roryherriman/Ascende"   # was "Ascende" — missing trailing d
```

All "Check for Updates" links and About dialog URLs would point to a non-existent repository.

**Fixed in this PR:** Corrected to `"roryherriman/Ascend"`.

---

### 11. Personal names in test fixtures (test-only, repository-public)

**Files:** 15+ test files contain "Kysarra", "Kyssandra", "Mookson", "Stormrage", "Ascend Raiders"  
**Severity:** LOW (does not affect production behavior, but personal names are publicly visible in the repository)

**Fixed in this PR:** All test fixtures updated to use fictional demo characters:
- Kysarra → Aeloria (Mage)
- Kyssandra → Thornveil (Warlock)
- Mookson → Kaelric (Warrior/Tank)
- Stormrage → Proudmoore
- Ascend Raiders → Stellar Ascent

---

## What Is Clean (No Changes Needed)

| Area | Status |
|---|---|
| Database migrations | No personal data in schema defaults |
| Analysis/scoring engine | No class/role/realm assumptions |
| Roster comparison logic | Attendance-only; no role assumptions |
| WCL API client | No hardcoded credentials or personal data |
| Region list in CharacterDialog | All WCL regions: US, EU, KR, TW, CN |
| WCL class list | Complete and generic |
| Discord webhook | Stored only via SecureStorage, never hardcoded |
| Absolute file paths | No developer username paths in production code |
| Credential storage | Windows Credential Manager, DPAPI fallback — no hardcoded secrets |

---

## Public Release Blockers (Status After This PR)

| # | Blocker | Status |
|---|---|---|
| 1 | Developer characters seeded on install | **FIXED** |
| 2 | "Your Mage and Warlock" in wizard | **FIXED** |
| 3 | Personal names in demo mode | **FIXED** |
| 4 | "Ranged roster median" in demo | **FIXED** |
| 5 | "Guild US Rank" US-specific label | **FIXED** (label; full model in PR C) |
| 6 | "Stormrage" in demo fixture | **FIXED** |
| 7 | "PHASE 1" in sidebar | **FIXED** |
| 8 | GitHub URL typo | **FIXED** |
| 9 | Personal names in tests | **FIXED** |
| 10 | First-run wizard redesign (arbitrary user) | **DEFERRED → PR B** |
| 11 | API-backed raid tier selection | **DEFERRED → PR C** |
| 12 | Guild verification via WCL API | **DEFERRED → PR C** |
| 13 | Role generalization in scoring | **DEFERRED → PR D** |
| 14 | Privacy/data management page | **DEFERRED → PR E** |
| 15 | Build type separation (dev/demo/release) | **DEFERRED → PR E** |
| 16 | Addon architecture documentation | **DEFERRED → PR F** |
| 17 | Combat log watcher service boundary | **DEFERRED → PR F** |

---

## Deferred Work

The following is documented here but not implemented in this PR per the productization spec:

- **First-run wizard redesign** — The current wizard is functional but developer-oriented. PR B will redesign it as a polished public onboarding flow with proper progress indication, character verification via an official API, and neutral default values.

- **API-backed raid tier selection** — The current free-text "Current Raid Tier" field cannot be validated. PR C will replace it with a WCL zone API-backed searchable dropdown with caching, expiry, and stable zone ID storage.

- **Guild verification** — The current free-text "Guild Name" field is unverified. PR C will implement WCL guild verification, multiple-match resolution, and stable guild ID storage.

- **Full guild model redesign** — The settings key `guild_us_rank` remains in the database for backwards compatibility. The full migration to a structured Guild model with regional rank support is deferred to PR C.

- **Role generalization in scoring** — The scoring architecture is designed for evidence-based evaluation without class/role assumptions, but the per-category implementations need auditing to confirm tank and healer metrics are properly marked UNAVAILABLE (not guessed) until event data is available. Deferred to PR D.

- **"Phase N" placeholder text in user UI** — Completely removed in this PR, but placeholder pages still display vague "Coming later" text. PR B/C will replace these with feature-specific descriptions.

- **Privacy page** — Full privacy and data management UI (what is stored, where, how to delete) is deferred to PR E.

- **Addon architecture** — The full addon scope, data contract, and combat log watcher service boundary documentation are deferred to PR F.

---

## Recommended Future Changes (Not Blocking This PR)

1. Add a `guild_rank_region` field to the settings alongside the existing `guild_us_rank` key so region-specific rank labels can be displayed correctly without a full model migration.
2. Consider removing the sidebar `PlaceholderPage` phase badge rendering entirely — replace with a simple "Coming later" label with no phase number.
3. The `guild_icon_service.py` imports PySide6 Qt rendering APIs (an architectural concern) — should be extracted to a separate rendering helper so the service is independently testable without a QApplication.

---

## Implementation Plan Summary (All PRs)

| PR | Scope | Status |
|---|---|---|
| **PR A** | Audit + neutral language + demo data | This PR |
| **PR B** | Public first-run onboarding + local profile + multi-character model | Next |
| **PR C** | API-backed raid tier + realm selection + guild verification | After PR B |
| **PR D** | Role generalization + historical guild/tier context | After PR C |
| **PR E** | Privacy/about/data management + build types + README | After PR D |
| **PR F** | Addon architecture + combat log watcher interfaces + raid session model + addon contract | After PR E |
