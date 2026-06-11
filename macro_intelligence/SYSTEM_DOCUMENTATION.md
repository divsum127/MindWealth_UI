# Runic Agent — System Documentation

> **Full architecture:** see [`docs/macro_intelligence_architecture.md`](../docs/macro_intelligence_architecture.md) for complete flow, CONFIG reference, CFTC pipeline, schema, SSI integration, backfill, tests, and known gaps.

## Components

| Component | Entry point | Schedule (AWS `install_aws_cron.sh`, ET) |
|-----------|-------------|---------------------------------------------|
| SSI daily | `scripts/run_ssi_daily.py` | Mon–Fri `0 8 * * 1-5` |
| Friday data pull | `scripts/run_macro_friday_pull.py` | Fri `30 17 * * 5` |
| Nightly JSON + briefing | `scripts/run_macro_nightly.py` | Mon–Fri `0 18 * * 1-5` |
| CFTC zip cache | `scripts/download_cftc_tff_zip.py` | Manual / before backfill |
| Historical backfill | `scripts/backfill_macro_history.py` | Manual |
| CPI ingest | `scripts/ingest_cpi_release.py` | On release day |
| CFTC column validate | `scripts/validate_cftc_tff_columns.py` | Manual |
| Monthly threshold review | `src/macro_intelligence/jobs/monthly_threshold_review.py` | Not in cron installer |

**Note:** `CONFIG.yaml` lists `nightly_cron: "0 21 * * 1-5"` but production cron uses **18:00 ET**. See architecture doc §4.2.

## Outputs

- SQLite: `macro_intelligence/data/runic.db` (`MACRO_INTEL_DB`)
- C++ JSON: `macro_intelligence/output/runic_output.json` (`MACRO_INTEL_JSON_PATH`)
- SSI JSON: `macro_intelligence/output/positioning.json` (`SSI_POSITIONING_JSON`)
- SSI DB: `macro_intelligence/data/ssi/ssi.db`
- Briefings: `macro_intelligence/output/runic_briefing_{date}.html` (+ PDF if reportlab)
- CFTC cache: `macro_intelligence/data_cache/cftc/*.zip` (gitignored)

## v3 verification (full sign-off)

```bash
set -a && source .env && set +a
.venv/bin/python scripts/run_full_v3_verification.py --allow-warn
.venv/bin/python scripts/export_data_validation.py
```

Outputs: `macro_intelligence/output/v3_traceability_matrix.csv`, `v3_go_no_go.md`, `production_validation.json`  
Rohit checklist: `docs/plans/macro_intelligence_rohit_signoff.md`

## Restart procedure

1. Copy `.env.example` to `.env` — set `FRED_API_KEY` (recommended), `BLS_API_KEY`, `ANTHROPIC_API_KEY`, `TAVILY_API_KEY` as needed.
2. `cd /path/to/MindWealth_UI && source .venv/bin/activate`
3. Optional: `python scripts/download_cftc_tff_zip.py --year $(date +%Y)`
4. Morning: `python scripts/run_ssi_daily.py`
5. Friday: `python scripts/run_macro_friday_pull.py`
6. Nightly: `python scripts/run_macro_nightly.py`
7. Verify:
   ```bash
   jq '{ssi: .ssi_multiplier, bypass: .vix_bypass, layer2: .ssi_layer2_status, cftc: .cftc_status}' \
     macro_intelligence/output/runic_output.json
   ```

## Scraper / cache pipelines

| Variable | Module | Live source | Manual fallback |
|----------|--------|-------------|-----------------|
| CAPE | `cape_scrape.py` | multpl.com | `cape_history.csv` |
| CNN F&G | `cnn_fear_greed.py` | CNN graphdata API | `data/ssi/cnn_fear_greed.csv` |
| AAII | `aaii_pull.py` | aaii.com XLS (often 403) | `scripts/ingest_aaii_sentiment.py` |
| NAAIM | `naaim_pull.py` | naaim.org table | `data/ssi/naaim_exposure.csv` |
| NH/NL | `nh_nl_pull.py` | CNN strength/breadth proxy | cache CSV |
| McClellan | `mcclellan_pull.py` | CNN proxy oscillator | cache CSV |
| % >200DMA | `pct_200dma_pull.py` | Full S&P 500 via `sp500_breadth.py` | cache CSV |
| NH/NL | `nh_nl_pull.py` | S&P 500 52w high/low counts | cache CSV |
| McClellan | `mcclellan_pull.py` | Classic EMA(19−39) on SP500 net advances | cache CSV |
| AAII | `aaii_pull.py` | `sent_results` HTML table + XLS/CSV | `ingest_aaii_sentiment.py` |
| CPI consensus | `investing_cpi_consensus.py` | Investing.com calendar | `cpi_consensus.csv`, `sync_cpi_consensus.py` |

Tests: `python -m unittest tests.test_scraper_pipelines -q`

## CFTC (self-service — no external sample zip)

Official TFF zips from CFTC; download locally:

```bash
python scripts/download_cftc_tff_zip.py --year 2026 --extract-sample
python scripts/validate_cftc_tff_columns.py --zip macro_intelligence/data_cache/cftc/fut_fin_txt_2026.zip
```

Column manifest: `macro_intelligence/CFTC_TFF_COLUMNS.yaml`. Market: **S&P 500 Consolidated** only (FM combos).

## C++ integration

C++ reads `runic_output.json` at market open. When `vix_bypass` is true, ignore SSI size multiplier (Combo B active, or Combo F with SSI Layer2 CONFIRMED).

## Streamlit UI

Navigation → **Runic Macro Intelligence** (`src/pages/runic_page.py`) — reads `runic_output.json` and `positioning.json`.

## AWS deploy

```bash
bash scripts/install_aws_cron.sh   # from repo root on 51.20.53.218
```

Logs: `macro_intelligence/logs/`.
