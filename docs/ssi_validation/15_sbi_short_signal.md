# Test 15: SBI short signal validation

**Status: DONE (env caveat)** — batch complete 2026-08-12.

**Artifact:** `macro_intelligence/analysis/ssi_validation/15_sbi_short_20260812.json`

## Method

- MindWealth `calculate_trade_arrival_stats_for_breadth` (COMBINED_STRATEGY, S&P 500)
- Monthly BMS sampling: 2015-01-01 → 2026-08-03 (140 months)
- Short trigger: today's short percentile-from-top ≤ 10 (`BREADTH_INDICATOR_SBI_PERCENTILE_TRIGGER`)
- SPX forward returns at 1w / 4w / 8w (short side)

## Result

| Metric | Value |
|--------|-------|
| Short entry months | **0** |
| Sample dates | (none) |

## Caveat

MindWealth `cpp_functions` on this host lacks `backtest_bb` / `is_pivot` — COMBINED_STRATEGY returns **0 trades** for every stock/month. Short percentile-from-top stays at 100% (never ≤10). **Not a valid empirical test** until re-run on C++-enabled MindWealth host.

## Reproduce

```bash
# Full parallel batch (~2 hr)
bash scripts/run_test15_sbi_parallel.sh

# Or archive from existing output
.venv/bin/python -c "from src.sentiment_superindex.analysis.sbi_short_validation import run_and_report; run_and_report('2015-01-01')"
```
