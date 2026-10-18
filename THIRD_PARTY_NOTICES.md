# Third-party notices

The Ascend portable build bundles the third-party software below. Each component remains under its own license. Versions are those used for the most recent build. Re-check this list whenever dependencies change.

| Component | Version | License | Source |
|---|---|---|---|
| Qt for Python (PySide6, Shiboken6) and the Qt 6 libraries it ships | 6.11.1 | LGPL-3.0-only | https://code.qt.io/cgit/pyside/pyside-setup.git/ · https://download.qt.io/official_releases/qt/ |
| Python runtime | 3.11 | PSF-2.0 | https://www.python.org/ |
| OpenSSL (via Python's `ssl` module) | see build | Apache-2.0 (3.x) / OpenSSL & SSLeay (1.1.x) | https://www.openssl.org/source/ |
| SQLite (via Python's `sqlite3` module) | see build | Public domain | https://sqlite.org/ |
| requests | 2.34.2 | Apache-2.0 | https://github.com/psf/requests |
| urllib3 | 2.7.0 | MIT | https://github.com/urllib3/urllib3 |
| certifi | 2026.6.17 | MPL-2.0 | https://github.com/certifi/python-certifi |
| charset-normalizer | 3.4.9 | MIT | https://github.com/jawah/charset_normalizer |
| idna | 3.18 | BSD-3-Clause | https://github.com/kjd/idna |
| PyYAML | 6.0.3 | MIT | https://github.com/yaml/pyyaml |
| plotly | 6.9.0 | MIT | https://github.com/plotly/plotly.py |
| narwhals | 2.23.0 | MIT | https://github.com/narwhals-dev/narwhals |
| keyring | 25.7.0 | MIT | https://github.com/jaraco/keyring |
| jaraco.classes / jaraco.context / jaraco.functools | 3.4.0 / 6.1.2 / 4.5.0 | MIT | https://github.com/jaraco |
| more-itertools | 11.1.0 | MIT | https://github.com/more-itertools/more-itertools |
| pywin32 | 312 | PSF-2.0 | https://github.com/mhammond/pywin32 |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | https://github.com/enthought/pywin32-ctypes |
| python-dateutil | 2.9.0.post0 | Apache-2.0 / BSD-3-Clause (dual) | https://github.com/dateutil/dateutil |
| six | 1.17.0 | MIT | https://github.com/benjaminp/six |
| python-dotenv | 1.2.2 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| importlib_metadata / zipp | 9.0.0 / 4.1.0 | Apache-2.0 / MIT | https://github.com/python/importlib_metadata |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| PyInstaller bootloader | 6.21.0 | GPL-2.0-or-later **with the PyInstaller bootloader exception**, which allows distributing the bundled application under any license | https://github.com/pyinstaller/pyinstaller |

## Qt / PySide6 (LGPL-3.0)

Ascend uses Qt for Python and Qt under the GNU Lesser General Public License v3.0. The Qt and PySide6 libraries are shipped as separate, unmodified DLL and `.pyd` files in the `_internal` folder of the portable build, so you can replace them with compatible versions. The full license texts are available at https://www.gnu.org/licenses/lgpl-3.0.html and https://www.gnu.org/licenses/gpl-3.0.html, and the corresponding source code is available from the Qt project at the links above.

Qt modules that are licensed only under the GPL (for example Qt Virtual Keyboard) are deliberately excluded from the build.

## Data sources

- Report and combat data comes from the [Warcraft Logs](https://www.warcraftlogs.com/) API, under the RPGLogs API Terms of Service.
- Optional guild crests come from the Blizzard Battle.net API. The crest data and images belong to Blizzard Entertainment.

Ascend isn't affiliated with or endorsed by Blizzard Entertainment, Warcraft Logs, RPGLogs or The Qt Company.
