#!/usr/bin/env python3
"""Publish CFTC Rohit share package to Google Sheets + Drive PDF."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "docs" / "ssi_validation" / "CFTC_ROHIT_SHARE_20260811"
PDF_PATH = PACKAGE / "pdf" / "CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_20260811.pdf"
TOKEN_PATH = Path.home() / ".google-sheets-mcp" / "token.json"
LINKS_OUT = PACKAGE / "GOOGLE_SHARE_LINKS.md"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CSV_TABS: list[tuple[str, Path]] = [
    ("squeeze_12w", PACKAGE / "csv" / "squeeze_grid_12w.csv"),
    ("squeeze_all_horizons", PACKAGE / "csv" / "squeeze_grid_all_horizons.csv"),
    ("squeeze_abs_cuts", PACKAGE / "csv" / "squeeze_absolute_cuts.csv"),
    ("liq_exit_4w", PACKAGE / "csv" / "liquidity_exit_grid_4w.csv"),
    ("liq_exit_all", PACKAGE / "csv" / "liquidity_exit_grid_all_horizons.csv"),
    ("episode_dates", PACKAGE / "csv" / "episode_dates_top_cells.csv"),
    ("robustness", PACKAGE / "csv" / "robustness_subsample.csv"),
    ("fm_regression", PACKAGE / "csv" / "fm_pctile_regression.csv"),
    ("fm_distribution", PACKAGE / "csv" / "fm_net_distribution.csv"),
    ("par_row", PACKAGE / "csv" / "par_row.csv"),
    ("sample_diag", PACKAGE / "csv" / "sample_diagnostics.csv"),
]


def load_creds() -> Credentials:
    if not TOKEN_PATH.is_file():
        raise FileNotFoundError(f"OAuth token missing: {TOKEN_PATH}")
    return Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def col_letter(n: int) -> str:
    """1-based column index to A1 letter."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def share_anyone(drive, file_id: str) -> None:
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()


def main() -> int:
    if not PACKAGE.is_dir():
        print(f"Missing package: {PACKAGE}", file=sys.stderr)
        return 1

    creds = load_creds()
    sheets = build("sheets", "v4", credentials=creds)

    title = "CFTC Pattern Thresholds — Rohit (Aug 2026)"
    pdf_url = ""
    folder_url = ""
    pdf_id = ""
    folder_id = ""

    # Optional Drive (folder + PDF) — requires Drive API enabled on GCP project
    drive = None
    try:
        drive = build("drive", "v3", credentials=creds)
        folder = (
            drive.files()
            .create(
                body={
                    "name": title,
                    "mimeType": "application/vnd.google-apps.folder",
                },
                fields="id, webViewLink",
            )
            .execute()
        )
        folder_id = folder["id"]
        folder_url = folder.get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")

        if PDF_PATH.is_file():
            pdf_meta = {
                "name": "CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_20260811.pdf",
                "parents": [folder_id],
            }
            media = MediaFileUpload(str(PDF_PATH), mimetype="application/pdf", resumable=True)
            pdf_file = (
                drive.files()
                .create(body=pdf_meta, media_body=media, fields="id, webViewLink")
                .execute()
            )
            pdf_id = pdf_file["id"]
            pdf_url = f"https://drive.google.com/file/d/{pdf_id}/view"
    except Exception as exc:
        print(f"Drive upload skipped ({exc})", file=sys.stderr)
        pdf_url = "(Drive API not enabled — attach local PDF or enable Drive API on GCP project mindwealth-gmail-mcp)"

    # Spreadsheet with README + data tabs
    sheet_titles = ["README"] + [t[0] for t in CSV_TABS]
    ss_body = {
        "properties": {"title": f"{title} — Data"},
        "sheets": [{"properties": {"title": t}} for t in sheet_titles],
    }
    ss = sheets.spreadsheets().create(body=ss_body, fields="spreadsheetId,spreadsheetUrl,sheets.properties").execute()
    spreadsheet_id = ss["spreadsheetId"]
    spreadsheet_url = ss["spreadsheetUrl"]

    if drive and folder_id:
        drive.files().update(
            fileId=spreadsheet_id,
            addParents=folder_id,
            fields="id",
        ).execute()

    # README tab content
    readme = [
        ["CFTC SQUEEZE / LIQUIDITY EXIT — Rohit Share Package"],
        ["COT through 2026-08-04 | Aug 4 2026 spec"],
        [""],
        ["PDF sign-off report", pdf_url or str(PDF_PATH)],
        ["This spreadsheet", spreadsheet_url],
        ["Drive folder", folder_url or "(not created — Drive API disabled)"],
        [""],
        ["Executive summary"],
        ["Top SQUEEZE (12w gap)", "FM_roll_pct<10 AND RM_roll_pct>55 | n_ep=21 | gap≈0.41% | excess_hit 65%"],
        ["PDF default FM<30/RM>50", "Negative gap (−0.57%) — market beta, not tail"],
        ["Extreme FM<5", "n_ep=6 only — high mean but tiny sample"],
        ["LIQ EXIT RM<30/FM>60", "n_ep=40 — stress context flag, not clean short"],
        ["Sample start", "Raw TFF 2006-06-13; full 156w window from 2009-06-02"],
        ["GFC 2008", "Excluded from rolling-percentile grids (window not full until mid-2009)"],
        [""],
        ["Tabs in this workbook"],
    ]
    for tab, path in CSV_TABS:
        readme.append([tab, path.name])

    data_requests: list[dict] = []
    data_requests.append(
        {
            "range": "README!A1",
            "values": readme,
        }
    )

    # Map sheet title -> sheetId for batchUpdate values
    sheet_id_map = {s["properties"]["title"]: s["properties"]["sheetId"] for s in ss["sheets"]}

    value_batches = [{"range": "README!A1", "values": readme}]
    for tab, csv_path in CSV_TABS:
        rows = read_csv_rows(csv_path)
        if not rows:
            continue
        ncols = max(len(r) for r in rows)
        end_col = col_letter(ncols)
        end_row = len(rows)
        value_batches.append(
            {
                "range": f"{tab}!A1:{end_col}{end_row}",
                "values": rows,
            }
        )

    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": value_batches},
    ).execute()

    # Freeze header row on data tabs
    freeze_requests = []
    for tab, _ in CSV_TABS:
        sid = sheet_id_map[tab]
        freeze_requests.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": freeze_requests},
    ).execute()

    # Share spreadsheet (anyone with link) if Drive permissions API available
    if drive:
        try:
            if folder_id:
                share_anyone(drive, folder_id)
            share_anyone(drive, spreadsheet_id)
            if pdf_id:
                share_anyone(drive, pdf_id)
        except Exception as exc:
            print(f"Share permissions skipped ({exc})", file=sys.stderr)

    folder_url = folder_url or ""
    pdf_view_url = pdf_url
    links_md = f"""# Google share links — CFTC Rohit package

**Created:** publish script run

## Send Rohit these links

| Item | Link |
|------|------|
| **Drive folder** (PDF + Sheet) | {folder_url} |
| **Google Sheet** (all CSV tabs) | {spreadsheet_url} |
| **PDF report** | {pdf_view_url} |

## Sheet tabs

"""
    for tab, path in CSV_TABS:
        links_md += f"- `{tab}` — from `{path.name}`\n"

    LINKS_OUT.write_text(links_md, encoding="utf-8")

    result = {
        "folder_id": folder_id,
        "folder_url": folder_url,
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": spreadsheet_url,
        "pdf_id": pdf_id,
        "pdf_url": pdf_view_url,
    }
    print(json.dumps(result, indent=2))
    print(f"\nLinks written: {LINKS_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
