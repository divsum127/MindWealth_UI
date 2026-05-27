# Runic Agent — Maintenance Guide

## Add a new variable

1. Add entry under `variables` in `macro_intelligence/CONFIG.yaml`.
2. Run `init_db()` or migrate SQLite `variables` / `thresholds` tables.
3. Implement pull logic in `src/macro_intelligence/data/pull_all.py`.
4. Add percentile rules in `src/macro_intelligence/engine/percentiles.py`.
5. Update combo detector if the variable participates in named combos.

## Rotate API keys

- `ANTHROPIC_API_KEY` — Claude regime + narrative
- `FRED_API_KEY` — optional; public CSV fallback exists
- Set `MACRO_CLAUDE_MODEL` to override model string

## Update CPI scraper

Edit `src/macro_intelligence/data/cpi_pull.py` or append rows to `macro_intelligence/data/cpi_surprises.csv`.

## Update CAPE source

Cache file: `macro_intelligence/data/cape_history.csv`. Scraper: `src/macro_intelligence/data/cape_scrape.py`.

## Threshold review (monthly)

`python -c "from src.macro_intelligence.jobs.monthly_threshold_review import run_monthly_review; print(run_monthly_review())"`

Suggestions land in `threshold_review_log` with status `PENDING`.

## Scheduled jobs (cron examples)

```cron
0 18 * * 5  cd /path/to/MindWealth_UI && .venv/bin/python scripts/run_macro_friday_pull.py
0 21 * * 1-5 cd /path/to/MindWealth_UI && .venv/bin/python scripts/run_macro_nightly.py
0 10 1 * *   cd /path/to/MindWealth_UI && .venv/bin/python -c "from src.macro_intelligence.jobs.monthly_threshold_review import run_monthly_review; run_monthly_review()"
```
