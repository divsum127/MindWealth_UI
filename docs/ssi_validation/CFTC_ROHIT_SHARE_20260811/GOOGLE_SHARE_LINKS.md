# Google share links — CFTC Rohit package

**Created:** 2026-08-11

## Send Rohit these links

### Google Sheet (all CSV data — 11 tabs + README)

**https://docs.google.com/spreadsheets/d/1VUT7POm6nNNEd6EnBNrlXlHm5tpmA_OTXX9cEiob0XQ/edit**

Spreadsheet ID: `1VUT7POm6nNNEd6EnBNrlXlHm5tpmA_OTXX9cEiob0XQ`

| Tab | Contents |
|-----|----------|
| README | Executive summary + tab index |
| squeeze_12w | SQUEEZE grid, 12w metrics (primary ranking) |
| squeeze_all_horizons | SQUEEZE all horizons |
| squeeze_abs_cuts | Absolute FM net cuts |
| liq_exit_4w | LIQUIDITY EXIT, 4w metrics |
| liq_exit_all | LIQUIDITY EXIT all horizons |
| episode_dates | Dated episodes for top cells |
| robustness | 12-offset subsample stability |
| fm_regression | FM pctile vs SPX regression |
| fm_distribution | Fixed FM net percentiles |
| par_row | Unconditional benchmark row |
| sample_diag | Sample start / 156w window diagnostics |

### PDF report

Drive upload **blocked** — Google Drive API not enabled on GCP project `mindwealth-gmail-mcp`.

**Option 1 (quick):** Attach this file to your email to Rohit:

`docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/pdf/CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_20260811.pdf`

**Option 2 (hosted link):** Enable Drive API, then re-run:

1. Open https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=mindwealth-gmail-mcp
2. Click **Enable**
3. Wait 2–3 minutes
4. Run: `.google-sheets-mcp/.venv/bin/python scripts/publish_cftc_rohit_to_google.py`
5. Script will upload PDF to a Drive folder and return a view link

---

## Before sending — share the Sheet with Rohit

The sheet is currently private to the OAuth account. In Google Sheets:

1. Open the sheet link above
2. Click **Share** (top right)
3. Add Rohit's email **or** set **Anyone with the link → Viewer**
4. Copy link and send with the PDF

---

## Suggested message to Rohit

> Rohit — CFTC SQUEEZE / LIQUIDITY EXIT re-run per your Aug 4 spec (episode collapse, extended FM axis, mean−median gap ranking, PAR/excess, robustness).  
> **Data (Google Sheet):** https://docs.google.com/spreadsheets/d/1VUT7POm6nNNEd6EnBNrlXlHm5tpmA_OTXX9cEiob0XQ/edit  
> **PDF sign-off report:** [attach PDF or Drive link after Option 2]  
> Top SQUEEZE cell: FM<10 / RM>55 (n_ep=21, gap 0.41%). PDF default FM<30/RM>50 negative gap. Sign-off still held on display wiring.
