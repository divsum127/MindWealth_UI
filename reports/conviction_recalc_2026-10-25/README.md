# Conviction dev recalculation — 2026-10-25

Full recalculation of all 198 dev `conviction_store` records after the CE-01..CE-05 / CE-07 /
CE-22 changes (`--mode full --include-existing-records`, `pe_history_cache/*_sec.json` set
aside first; 0 errors), plus a follow-up recalculation of the 29 equities with no P/E history
metadata after the neutral-P/E fix. Agent dimensions were not run.

| File | What it is |
|---|---|
| `SUMMARY.md` | Headline counts and every record whose conviction moved by 2+ points |
| `conviction_store_diff.csv` | One row per ticker, before/after for every scoring field (Rohit 1 Sep G3) |
| `g1_pe_adjusted_eps_universe.csv` | P/E and adjusted-EPS fields across the universe (G1) |
| `g2_empty_statement_fields.csv` | Records with empty statements or fetch errors at this recalc (G2); 62 of the 100 are non-equities |
| `ROHIT_REPLY_DRAFT.md` | Draft reply, not sent |

Regenerate with `scripts/conviction_store_diff.py` and `scripts/conviction_universe_export.py`.
The pre-recalc snapshot lived in the session scratchpad and is not committed.
