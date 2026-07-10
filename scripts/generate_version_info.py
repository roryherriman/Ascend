"""Generate a Windows version-info resource file for PyInstaller.

Usage:
    python scripts/generate_version_info.py          # writes version_info.txt
    python scripts/generate_version_info.py --print  # print to stdout only

The generated file is consumed by Ascend.spec via the version= argument.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ascend.metadata import APP_NAME, APP_TAGLINE, APP_VERSION, BUILD_NUMBER, COPYRIGHT  # noqa: E402


def _version_tuple(version_str: str) -> tuple[int, int, int, int]:
    parts = version_str.split(".")
    padded = (parts + ["0", "0", "0", "0"])[:4]
    return tuple(int(x) for x in padded)  # type: ignore[return-value]


def generate(out_path: Path | None = None) -> str:
    major, minor, patch, build = _version_tuple(APP_VERSION)
    bn = int(BUILD_NUMBER)

    content = f"""\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {bn}),
    prodvers=({major}, {minor}, {patch}, {bn}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Rory Herriman'),
         StringStruct('FileDescription', '{APP_NAME} — {APP_TAGLINE}'),
         StringStruct('FileVersion', '{APP_VERSION}.{bn}'),
         StringStruct('InternalName', '{APP_NAME}'),
         StringStruct('LegalCopyright', '{COPYRIGHT}'),
         StringStruct('OriginalFilename', '{APP_NAME}.exe'),
         StringStruct('ProductName', '{APP_NAME}'),
         StringStruct('ProductVersion', '{APP_VERSION}'),
        ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""

    if out_path is not None:
        out_path.write_text(content, encoding="utf-8")
        print(f"Written: {out_path}")
    return content


if __name__ == "__main__":
    if "--print" in sys.argv:
        print(generate())
    else:
        generate(ROOT / "version_info.txt")
