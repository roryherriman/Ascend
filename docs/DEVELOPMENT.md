# Development

## Setup

```
setup.bat
```

Creates `.venv`, installs `requirements.txt`, and runs the test suite.
Requires Python 3.11+ on PATH.

## Running

```
run_app.bat
```

Activates `.venv` and runs `python app.py` with a visible console for
development logging (`ASCEND_DEV=1`). The packaged `Ascend.exe` (Phase 4)
runs windowed with no console.

## Testing

```
pytest -q
```

All tests use sanitized mock API responses (`tests/fixtures/`) - no live
Warcraft Logs API calls. GUI tests run headless via `QT_QPA_PLATFORM=offscreen`
(set automatically in `tests/conftest.py`) and `pytest-qt`.

Watch out for two easy mistakes when adding GUI tests:
- Any code path that calls `QMessageBox.exec()` (via `ui/dialogs.py`'s
  `show_info`/`show_error`/`confirm`) will hang forever in a headless test
  since nothing dismisses it - monkeypatch those functions out in the test.
- Background tasks run on a real `QThreadPool` thread; use
  `qtbot.waitSignal(...)` rather than sleeping.

## Branching and commits

Current phase branch: `feature/ascend-phase-1`. Do not force-push, don't
rewrite published history, don't auto-merge PRs - leave them open for
review. Use conventional-ish prefixes: `feat:`, `fix:`, `test:`, `docs:`,
`chore:`.

## Building the Windows executable

```
build_windows.bat
```

Runs tests, then a folder-based PyInstaller build (`--windowed --name
Ascend`), output in `dist/Ascend/`. Folder-based (not one-file) builds are
used initially since they're easier to debug and start faster. Icon bundling
and portable packaging refinement happen in Phase 4.

## Optional developer convenience: `.env`

Copy `.env.example` to `.env` to pre-fill Warcraft Logs/Discord credentials
in Settings on first run (never overwrites an existing stored value).
`.env` is gitignored and must never be committed.
