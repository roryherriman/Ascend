# Addon Architecture

## Overview

Ascend currently pulls data from Warcraft Logs via the public API. The addon
layer extends this with **live local data** captured directly from the WoW
client, without requiring an upload to any external service.

The design keeps a strict boundary between the WoW addon (Lua, runs in-game)
and the Ascend desktop app (Python, runs on Windows). They communicate through
a file that WoW already writes on logout and `/reload`: the addon's
**SavedVariables** file.

---

## Components

### 1. In-Game WoW Addon (Lua)

Lives in a separate repository. Ascend does not ship Lua code — the addon
is an optional companion.

**Responsibilities:**
- Hook `COMBAT_LOG_EVENT_UNFILTERED` to capture deaths, mechanic events,
  interrupts, dispels, casts, and damage events in real time
- Maintain a `RaidSession` table in memory during a raid
- Write the table to SavedVariables (`AscendData.lua`) on logout and `/reload`
- Expose a `/ascend` slash command for manual export and status display
- Respect contract version so Ascend can detect incompatible addon versions

**What the addon does NOT do:**
- Upload data anywhere
- Read or write Ascend's SQLite database
- Display analysis results (that is Ascend's job)
- Override any API restrictions (WoW forbids reading arbitrary file paths)

### 2. Combat Log Watcher (Python, `ascend/addon/combat_log_watcher.py`)

Runs as a background thread inside the Ascend process.

**Responsibilities:**
- Watch the WoW SavedVariables directory for changes to `AscendData.lua`
- Parse the Lua table using the contract parser (`addon_contract.py`)
- Emit `RaidSession` objects to registered callbacks
- Fall back to `NullCombatLogWatcher` when the addon is not installed or the
  path is not configured, so Ascend works normally without it

**Implementation status:** Interface defined. Concrete `WindowsCombatLogWatcher`
using `ReadDirectoryChangesW` (or a polling fallback for compatibility) is
deferred until the addon ships.

### 3. Addon Contract (`ascend/addon/addon_contract.py`)

Defines the SavedVariables schema as Python constants and provides
`parse_saved_variables()`. Both sides of the boundary must agree on
`CONTRACT_VERSION`. Ascend rejects data from unknown versions rather than
silently misinterpreting it.

### 4. Session Model (`ascend/addon/session_model.py`)

Plain Python dataclasses:
- `RaidSession` — one zone-entry-to-exit session
- `RaidEncounter` — one boss attempt
- `RaidEvent` — one timestamped combat event

These are the canonical internal type for the live-log pipeline. They are
serialisable to SQLite and intentionally have no PySide6 or WCL API
dependencies.

---

## Data Flow

```
WoW Client
  ↓  COMBAT_LOG_EVENT_UNFILTERED
Ascend Addon (Lua)
  ↓  SavedVariables write (logout / /reload)
AscendData.lua  ←  CombatLogWatcher polls / watches
  ↓  parse_saved_variables()
RaidSession dataclasses
  ↓  callback
Ascend UI (live-log panel, in-progress encounter display)
  ↓  persist
SQLite (ascend.db)
```

---

## WoW Platform Constraints

WoW addons run in a heavily sandboxed Lua environment:

- **No arbitrary file I/O** — addons can only write to SavedVariables
- **No network access** — addons cannot make HTTP requests
- **No external process communication** — no named pipes, sockets, or shared memory
- **Combat log access is provided** — `COMBAT_LOG_EVENT_UNFILTERED` is the standard mechanism all major analysis tools use

The SavedVariables file is written by WoW on logout and `/reload`, not in real
time during combat. This means Ascend receives data at session boundaries, not
pull by pull. Real-time display (showing the current pull live) would require a
different approach (e.g. reading `WoWCombatLog.txt` directly — which is possible
from outside the game, but is out of scope for this architecture).

---

## Configuration

The watcher needs to know the path to the WoW SavedVariables directory.
Default path: `C:\Program Files (x86)\World of Warcraft\_retail_\WTF\Account\<ACCOUNT>\SavedVariables\AscendData.lua`

Ascend will auto-detect standard WoW installation paths and allow manual
override in Settings. This configuration is deferred to the implementation PR.

---

## What Is NOT In Scope

- Real-time pull-by-pull live display (requires reading `WoWCombatLog.txt` externally)
- Transmitting data from the addon to any server
- Modifying WoW game files
- Classic WoW / Cataclysm Classic support (different SavedVariables path, different API)
