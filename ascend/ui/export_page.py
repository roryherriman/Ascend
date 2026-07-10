"""Export - save raid analysis data to CSV or HTML.

Exports data that is already ingested and verified:
  - Encounter Summary: boss, total pulls, kills, wipes, first kill pull, progression pulls, farm pulls
  - Roster Attendance: player, server, class, raid nights, pulls
  - Combined HTML report (both tables plus basic metadata)

Performance stats (DPS, mechanic pass rates) aren't exported here because
they don't exist yet in the ingested data. The export is honest about what's
included.
"""
from __future__ import annotations

import csv
import io
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ascend.data.database import Database
from ascend.data.repositories import ReportRepository
from ascend.services.encounter_classification import classify_pulls
from ascend.services.roster import roster_summary


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# -- Data assembly -----------------------------------------------------------

def _encounter_summary_rows(db: Database) -> list[dict]:
    repo = ReportRepository(db)
    encounters = repo.distinct_encounters()
    rows = []
    for encounter_id, name in encounters:
        pairs = repo.fights_for_encounter(encounter_id)
        fights = [f for _, f in pairs]
        if not fights:
            continue
        classification = classify_pulls(fights)
        progression = [f for f in fights if classification[f.id] != "farm"]
        farm = [f for f in fights if classification[f.id] == "farm"]
        kills = sum(1 for f in fights if f.kill)
        wipes = sum(1 for f in fights if f.kill is False)
        first_kill_pull: int | None = None
        for i, f in enumerate(progression):
            if f.kill:
                first_kill_pull = i + 1
                break
        rows.append({
            "Encounter": name,
            "Total Pulls": len(fights),
            "Kills": kills,
            "Wipes": wipes,
            "Kill Rate": f"{round(100 * kills / len(fights))}%" if fights else "--",
            "Progression Pulls": len(progression),
            "Farm Pulls": len(farm),
            "First Kill Pull": str(first_kill_pull) if first_kill_pull else "Not killed",
        })
    return rows


def _roster_attendance_rows(db: Database) -> list[dict]:
    members = roster_summary(db)
    return [
        {
            "Name": m.name,
            "Server": m.server or "--",
            "Class": m.class_name or "--",
            "Raid Nights": str(m.raid_nights),
            "Pulls": str(m.pulls),
            "Tracked": "Yes" if m.character_id else "No",
        }
        for m in members
    ]


# -- CSV serialization -------------------------------------------------------

def _to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# -- HTML serialization -------------------------------------------------------

def _table_html(title: str, rows: list[dict]) -> str:
    if not rows:
        return f"<h2>{title}</h2><p><em>No data.</em></p>"
    headers = list(rows[0].keys())
    th = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = ""
    for row in rows:
        td = "".join(f"<td>{row[h]}</td>" for h in headers)
        body_rows += f"<tr>{td}</tr>\n"
    return textwrap.dedent(f"""
        <h2>{title}</h2>
        <table>
          <thead><tr>{th}</tr></thead>
          <tbody>{body_rows}</tbody>
        </table>
    """)


_HTML_STYLE = textwrap.dedent("""
    body { font-family: system-ui, sans-serif; max-width: 960px; margin: 40px auto; color: #dde2f0; background: #1a1f2e; }
    h1 { color: #5b8dd9; }
    h2 { color: #a0b4d6; margin-top: 32px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 24px; }
    th { background: #252b3b; color: #8eb4e8; text-align: left; padding: 8px 12px; }
    td { padding: 7px 12px; border-bottom: 1px solid #2a2f3a; }
    tr:nth-child(even) td { background: #1e2436; }
    p.meta { color: #6b7280; font-size: 0.85em; }
""")


def export_html(db: Database) -> str:
    enc_rows = _encounter_summary_rows(db)
    roster_rows = _roster_attendance_rows(db)
    enc_table = _table_html("Encounter Summary", enc_rows)
    roster_table = _table_html("Roster Attendance", roster_rows)
    return textwrap.dedent(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="utf-8"><title>Ascend Export</title>
        <style>{_HTML_STYLE}</style></head>
        <body>
        <h1>Ascend — Raid Analysis Export</h1>
        <p class="meta">Generated: {_now_utc()}<br>
        Includes encounter progression stats and roster attendance. Performance stats
        (DPS, mechanic pass rates) are not yet available — they require event-level
        data ingestion.</p>
        {enc_table}
        {roster_table}
        </body></html>
    """).strip()


# -- Page widget -------------------------------------------------------------

class ExportPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Export")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Export encounter progression and roster attendance data. "
            "Performance stats (DPS, mechanic pass rates) aren't available yet — "
            "they require event-level data that isn't ingested yet."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size: 11px;")

        # Encounter Summary CSV
        enc_group = QGroupBox("Encounter Summary")
        enc_layout = QVBoxLayout(enc_group)
        enc_desc = QLabel(
            "Boss name, total pulls, kills, wipes, kill rate, first kill pull, "
            "progression vs. farm pull counts."
        )
        enc_desc.setWordWrap(True)
        enc_desc.setProperty("class", "muted")
        enc_layout.addWidget(enc_desc)
        enc_btn = QPushButton("Save as CSV…")
        enc_btn.clicked.connect(self._export_encounter_csv)
        enc_layout.addWidget(enc_btn)
        layout.addWidget(enc_group)

        # Roster Attendance CSV
        roster_group = QGroupBox("Roster Attendance")
        roster_layout = QVBoxLayout(roster_group)
        roster_desc = QLabel("All detected players — name, server, class, raid nights, pulls, tracked status.")
        roster_desc.setWordWrap(True)
        roster_desc.setProperty("class", "muted")
        roster_layout.addWidget(roster_desc)
        roster_btn = QPushButton("Save as CSV…")
        roster_btn.clicked.connect(self._export_roster_csv)
        roster_layout.addWidget(roster_btn)
        layout.addWidget(roster_group)

        # Combined HTML
        html_group = QGroupBox("Combined HTML Report")
        html_layout = QVBoxLayout(html_group)
        html_desc = QLabel(
            "Both tables in a styled HTML file. Open in any browser — "
            "no external dependencies, all data is inline."
        )
        html_desc.setWordWrap(True)
        html_desc.setProperty("class", "muted")
        html_layout.addWidget(html_desc)
        html_btn = QPushButton("Save as HTML…")
        html_btn.clicked.connect(self._export_html)
        html_layout.addWidget(html_btn)
        layout.addWidget(html_group)

        layout.addWidget(self._status)
        layout.addStretch()

    def _set_status(self, msg: str, ok: bool = True) -> None:
        color = "#2d8a4e" if ok else "#c0392b"
        self._status.setStyleSheet(f"font-size: 11px; color: {color};")
        self._status.setText(msg)

    def _save_file(self, caption: str, filter_: str, default: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(self, caption, default, filter_)
        return path or None

    def _export_encounter_csv(self) -> None:
        rows = _encounter_summary_rows(self.db)
        if not rows:
            self._set_status("No encounter data to export yet.", ok=False)
            return
        path = self._save_file("Save Encounter Summary", "CSV files (*.csv)", "encounter_summary.csv")
        if not path:
            return
        try:
            Path(path).write_text(_to_csv(rows), encoding="utf-8")
            self._set_status(f"Saved {len(rows)} encounters → {path}")
        except OSError as exc:
            self._set_status(f"Save failed: {exc}", ok=False)

    def _export_roster_csv(self) -> None:
        rows = _roster_attendance_rows(self.db)
        if not rows:
            self._set_status("No roster data to export yet.", ok=False)
            return
        path = self._save_file("Save Roster Attendance", "CSV files (*.csv)", "roster_attendance.csv")
        if not path:
            return
        try:
            Path(path).write_text(_to_csv(rows), encoding="utf-8")
            self._set_status(f"Saved {len(rows)} roster members → {path}")
        except OSError as exc:
            self._set_status(f"Save failed: {exc}", ok=False)

    def _export_html(self) -> None:
        path = self._save_file("Save HTML Report", "HTML files (*.html)", "ascend_report.html")
        if not path:
            return
        try:
            html = export_html(self.db)
            Path(path).write_text(html, encoding="utf-8")
            self._set_status(f"Saved HTML report → {path}")
        except OSError as exc:
            self._set_status(f"Save failed: {exc}", ok=False)
