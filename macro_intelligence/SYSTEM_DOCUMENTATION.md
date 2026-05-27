# Runic Agent — System Documentation

## Components

| Component | Entry point | Schedule |
|-----------|-------------|----------|
| Friday data pull | `scripts/run_macro_friday_pull.py` | Friday after CFTC (~3:30pm ET) |
| Nightly JSON | `scripts/run_macro_nightly.py` | Mon–Fri 21:00 ET (`0 21 * * 1-5`) |
| Historical backfill | `scripts/backfill_macro_history.py` | Manual |
| Monthly threshold review | `src/macro_intelligence/jobs/monthly_threshold_review.py` | 1st of month |

## Outputs

- SQLite DB: `macro_intelligence/data/runic.db` (override: `MACRO_INTEL_DB`)
- C++ JSON: `macro_intelligence/output/runic_output.json` (override: `MACRO_INTEL_JSON_PATH`)
- SSI JSON (separate system): `positioning.json` at 08:00 ET

## Restart procedure

1. Ensure `.env` has `ANTHROPIC_API_KEY`, optional `FRED_API_KEY`.
2. `cd /path/to/MindWealth_UI && source .venv/bin/activate`
3. Friday: `python scripts/run_macro_friday_pull.py`
4. Nightly: `python scripts/run_macro_nightly.py`
5. Verify: `cat macro_intelligence/output/runic_output.json | jq .date,.dominant_signal,.vix_bypass`

## C++ integration

C++ reads `runic_output.json` at market open. When `vix_bypass` is true, ignore SSI size multiplier (Combo B active).

## Streamlit UI

Navigation → **Runic Macro Intelligence** (reads `runic_output.json` only).
