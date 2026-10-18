# -*- mode: python ; coding: utf-8 -*-
# Ascend.spec — PyInstaller build specification
#
# Run:  pyinstaller Ascend.spec
# Or:   scripts\build_portable.bat  (recommended — runs tests + version-info first)
#
# Packaging tool decision:
#   PyInstaller was chosen over pyside6-deploy and Nuitka for the initial release:
#   - pyside6-deploy lacks mature support for keyring/pywin32 native extensions
#   - Nuitka produces faster binaries but has a much steeper debugging cycle for
#     Qt plugin issues; appropriate to evaluate after a stable baseline exists
#   - PyInstaller's PySide6 hook (via pyinstaller-hooks-contrib) handles Qt plugin
#     collection automatically and is battle-tested on Windows
#
# Folder-based build (not --onefile):
#   Faster startup, easier debugging, easier Qt plugin inspection, no temp-dir
#   extraction on every launch.

import subprocess
import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH)

# Generate version_info.txt before Analysis if it doesn't exist yet
version_info_path = ROOT / "version_info.txt"
if not version_info_path.exists():
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_version_info.py")],
        check=True
    )

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # SVG icon set (sidebar nav icons + logo)
        (str(ROOT / "ascend" / "resources" / "icons"), "ascend/resources/icons"),
        # WoW class icons (original glyphs)
        (str(ROOT / "ascend" / "resources" / "class_icons"), "ascend/resources/class_icons"),
        # Bundled demo report fixture (sanitized, no real credentials)
        (str(ROOT / "ascend" / "resources" / "demo_report.json"), "ascend/resources"),
        # Roadmap shown in the About / Roadmap widget
        (str(ROOT / "docs" / "ROADMAP.md"), "docs"),
        # License notices for bundled third-party components (LGPL/MPL/Apache require them)
        (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    ],
    hiddenimports=[
        # keyring Windows Credential Manager backend
        "keyring.backends.Windows",
        "keyring.backends.fail",
        # pywin32 — DPAPI fallback in secure_storage.py
        "win32crypt",
        "win32con",
        "pywintypes",
        # plotly (used by TrendChart widget)
        "plotly",
        "plotly.graph_objects",
        # python-dateutil
        "dateutil",
        "dateutil.parser",
        # yaml (PyYAML)
        "yaml",
        # PySide6 modules that may not be auto-detected
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtPrintSupport",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dev/test only — keep the bundle lean
        "pytest",
        "pytest_qt",
        "_pytest",
        "IPython",
        "notebook",
        "jupyter",
        "sphinx",
        "docutils",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Qt Virtual Keyboard is GPL-3.0/commercial only (not LGPL) and Ascend doesn't use it.
# The PySide6 hook collects it automatically, so drop the module and its input-context plugin.
_GPL_ONLY_QT = ("qt6virtualkeyboard", "qtvirtualkeyboard")


def _keep(entry):
    name = entry[0].replace("\\", "/").lower()
    if any(marker in name for marker in _GPL_ONLY_QT):
        return False
    # Blizzard class-icon images (scripts/fetch_assets.py) are local-only and must never ship:
    # Blizzard API data has a 30-day TTL. See CLASS_ICON_SOURCES.md.
    return not ("class_icons/" in name and name.endswith((".png", ".jpg", ".jpeg")))


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Ascend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX can break Qt binaries; leave off unless tested
    console=False,      # no console window in release build
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="ascend/resources/icons/logo_mark.ico",  # uncomment after converting SVG → ICO
    version=str(version_info_path) if version_info_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Ascend",
)
