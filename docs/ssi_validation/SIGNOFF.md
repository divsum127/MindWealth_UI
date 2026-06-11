# SSI validation sign-off

**Status:** Partially complete — see table below. Tests 1–4, 7–11, 13 are archived. Remaining items tracked in Phase 1 / Phase 2 columns.

## How to complete

1. Run `.venv/bin/python scripts/run_ssi_validation_suite.py`
2. Read **[SSI_THRESHOLD_JUSTIFICATION.md](SSI_THRESHOLD_JUSTIFICATION.md)** (why each threshold value)
3. Optional: [SSI_OPEN_QUESTIONS_SUMMARY.md](SSI_OPEN_QUESTIONS_SUMMARY.md) (experiment overview)
4. Review detailed tables: `01_long_threshold_sweep.md` … `17_trendpulse_deterioration.md`
5. Fill decisions below

## Test status summary

| Test | Name | Status | Conclusion |
|------|------|--------|------------|
| 1–2 | SSI long/short threshold sweep | **DONE** | Long pctile ≤20 (n=16, +4.08% 3m, 81.25% win). Short +0.6 rejected. Short pctile ≥85 supported. |
| 3 | SQUEEZE grid | **DONE** | Macro flag only — not an SSI gate |
| 4 | LIQUIDITY EXIT grid | **DONE** | Macro flag only — not an SSI gate |
| 5 | TP/SL optimization | **DONE** (artifact saved 2026-06-06) | Best: TP×5, SL×20 (Sharpe=4.06, win=97.67%). Legacy 10×/15× is suboptimal. |
| 6 | CNN Fear & Greed | **PENDING** (CNN cache only 2025–2026; greed n=0) | Re-run after historical backfill |
| 7 | DBMF beta threshold | **DONE** | Layer 2 context; prod bands 0.5/1.2 defensible |
| 8 | HYG/LQD widening | **DONE** | −1.5% threshold → 3 median days to VIX>25 |
| 9 | Z-score vs percentile SSI | **DONE** (not deployed) | Percentile wins in 2020/2022 crises; awaiting sign-off |
| 10 | Layer 2 min_votes | **DONE** | `min_confirmed: 2` correct |
| 11 | VIX regime / Combo B bypass | **DONE** (full 20y curve waived) | Oct 2022 vix_bypass wiring verified |
| 12 | Bollinger + SSI | **DONE** | Uses pctile ≤20 gate; see report |
| 13 | Stochastic + McClellan | **DONE** | Research only — not a production gate |
| 14 | Gross/net divergence | **DONE** | 21 instances found; forward returns populated |
| 15 | SBI short signal | **PARTIAL** (MindWealth accessible; batch run needed) | `sbi_breadth.py --start 2015-01-01` from MindWealth venv; each day loads 500 stocks |
| 16 | Friday pull checklist | **DONE** | All items PASS after CPI + AAII automation fixes |
| 17 | TrendPulse 0.5/week | **DONE** | See 17_trendpulse_deterioration.md |

## Recommended thresholds (engineering draft)

| Parameter | CONFIG today | Empirical recommendation | Approve? |
|-----------|--------------|--------------------------|----------|
| `long_entry_pctile` | 20 | Test 1–2: n=16, 3m +4.08%, 81.25% win | |
| `short_entry_pctile` | 85 | Test 2: n=7, 57% 1w short win. Consider 90 (n=5, 60%) | |
| `long_entry` (level) | -0.6 | Secondary only — never fires in-sample | |
| `short_entry` (level) | 0.85 | Test 2: n=30 vs 57 at +0.6 | |
| Percentile SSI (Test 9) | Not in prod | Strongly favored in crises — waive / v3.1 | |
| TP/SL 10×/15× vol (Test 5) | MindWealth PulseGauge | Best is TP×5, SL×20 (Sharpe 4.06 vs 2.36 legacy) — approve change? | |

## Waivers

| Item | ID | Notes |
|------|-----|-------|
| NFCI in SSI Layer 2 | WAIVER-NFCI-SSI | Product decision — Runic only today |
| Full virtual-trading equity curve (Test 11) | WAIVER-VT-11 | Oct 2022 vix_bypass verified in unit tests |

## Decisions needed from Rohit

1. **Short pctile gate**: 85 vs 90? (n=7 vs n=5; 57% vs 60% 1w short win — both defensible; 90 is more selective)
2. **Percentile SSI deployment** (Test 9): Approve switch from z-score to 3yr percentile? (Strongly favored in 2020/2022 crises — z-score path had 0 events; percentile had 62–84 days with +19% / +8% 6m avg returns)
3. **TP/SL change** (Test 5): Switch from 10×/15× to optimal TP×5 / SL×20? (Sharpe improves from ~2.36 to 4.06)
4. **Test 15 batch run**: Approve overnight `sbi_breadth.py --start 2015-01-01` run in MindWealth venv?
5. **Bollinger overlay** (Test 12): Is the Bollinger + SSI gate a product requirement? (0 combo events — can only be evaluated with full SSI history)

**Signed:** _______________ **Date:** _______________
