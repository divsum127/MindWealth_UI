# Runic Agent — Maintenance Guide

## Add a new variable

1. Add entry under `variables` in `macro_intelligence/CONFIG.yaml`.
2. Run `init_db()` or migrate SQLite `variables` / `thresholds` tables.
3. Implement pull logic in `src/macro_intelligence/data/pull_all.py`.
4. Add percentile rules in `src/macro_intelligence/engine/percentiles.py`.
5. Update combo detector if the variable participates in named combos.

## SSI daily

```bash
python scripts/run_ssi_daily.py
python scripts/run_ssi_threshold_sweep.py
```

## Rotate API keys

- `ANTHROPIC_API_KEY` — Claude geo + narrative
- `FRED_API_KEY` — macro series (NFCI, HY, WALCL, curve, CPI fallback)
- `BLS_API_KEY` — CPI primary on release day
- `TAVILY_API_KEY` — geo_overlay news context
- `SSI_POSITIONING_JSON` — path to positioning.json for C++
- `MACRO_INTEL_JSON_PATH` — Ahil C++ consumption path on AWS
- Set `MACRO_CLAUDE_MODEL` to override model string

## Threshold recalibration

```bash
python scripts/recalibrate_thresholds.py --json
```

## Update CPI scraper

Edit `src/macro_intelligence/data/cpi_pull.py` or append rows to `macro_intelligence/data/cpi_surprises.csv`.

## Update CAPE source

Cache file: `macro_intelligence/data/cape_history.csv`. Scraper: `src/macro_intelligence/data/cape_scrape.py`.

## Combo discovery pipeline (monthly, Part H)

Runs all 298 generic combos through fixed CONFIG gates (no per-combo threshold fitting):

```bash
.venv/bin/python scripts/run_combo_discovery_pipeline.py --backfill-returns --write-report
.venv/bin/python scripts/run_combo_discovery_pipeline.py --use-claude --write-report  # Step 7 narratives
```

Monthly cron (first of month):

`python -c "from src.macro_intelligence.jobs.monthly_threshold_review import run_monthly_review; print(run_monthly_review())"`

Outputs: `macro_intelligence/analysis/combo_discovery/combo_discovery_YYYYMMDD.json` and `docs/ssi_validation/COMBO_DISCOVERY_PIPELINE_REPORT.md`. Logged to `threshold_review_log` with status `COMPLETE`.

## Variable dashboard — Signal column behaviour

The **Signal** column in the Live Variable Dashboard is sourced from `direction` in the `variables_dashboard` payload.

**How direction is set:**

| Tier | Source | Logic |
|------|--------|-------|
| `EXTREME` | Engine (`evaluate_variable_tier()` in `percentiles.py`) | Variable-specific: e.g. CAPE ≥ 32 → `UP`, HY ≥ 500bps → `UP`, CFTC at 5th pctile → `DOWN` |
| `RARE` | Engine | Same variable-specific thresholds at a lower severity |
| `NORMAL` | Renderer fallback (`_derive_direction()` in `briefing_renderer.py`) | Derived from 3yr percentile: ≥ 50% → `UP`, < 50% → `DOWN` |

**Design intent:** The engine treats `direction` as an alert-level flag — it only fires when the variable enters a notable state (RARE/EXTREME). For NORMAL tier variables, `direction=None` is returned by the engine. The renderer adds a percentile-based fallback so all 12 rows are populated in the report.

**To change the fallback logic:** edit `_derive_direction()` in `src/macro_intelligence/output/briefing_renderer.py`.

---

## Nightly PDF briefing (Mon–Fri)

After `run_macro_nightly.py`, outputs land in `macro_intelligence/output/`:

| File | Description |
|------|-------------|
| `runic_briefing_{date}.pdf` | Spec-format 2-page PDF (dominant signal, combos A–G, regime, narrative, variable dashboard, recommendation) |
| `runic_briefing_{date}.html` | Same content as HTML |
| `runic_output.json` | Machine-readable payload for C++ / Ahil |

Manual run:

```bash
.venv/bin/python scripts/run_macro_nightly.py
# or a specific date:
.venv/bin/python scripts/run_macro_nightly.py --date 2026-06-05 --no-claude
```

Requires `reportlab` (in `requirements.txt`). PDF path is printed under `briefing_paths` and logged to `macro_intelligence/logs/nightly.log` when cron runs.

## Scheduled jobs (AWS 51.20.53.218)

```bash
# From repo root after .env is configured:
bash scripts/install_aws_cron.sh
```

Manual cron (America/New_York):

```cron
0 8 * * 1-5  cd /path/to/MindWealth_UI && .venv/bin/python scripts/run_ssi_daily.py
30 17 * * 5  cd /path/to/MindWealth_UI && .venv/bin/python scripts/run_macro_friday_pull.py
0 18 * * 1-5 cd /path/to/MindWealth_UI && .venv/bin/python scripts/run_macro_nightly.py
```

## Data validation checklist

```bash
python scripts/export_data_validation.py
# -> macro_intelligence/output/data_validation_checklist.csv
```

## Historical backfill + geo batch

```bash
python scripts/backfill_macro_history.py --start 2010-01-01 --weekly-only --limit 100
python scripts/backfill_geo_overlay.py
```
