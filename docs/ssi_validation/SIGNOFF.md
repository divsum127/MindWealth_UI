# SSI validation sign-off

**Status:** 21/22 tests complete (Test 15 env caveat); Test 11 full backtest waived.  
**Updated:** 2026-08-12  
**Status tracker:** [`testing/ssi_th_exp/SSI_OPEN_QUESTIONS_STATUS.md`](../../testing/ssi_th_exp/SSI_OPEN_QUESTIONS_STATUS.md)  
**Results:** [`testing/ssi_th_exp/SSI_EXPERIMENT_RESULTS.md`](../../testing/ssi_th_exp/SSI_EXPERIMENT_RESULTS.md)

## How to complete

1. Run `.venv/bin/python scripts/run_ssi_validation_suite.py`
2. Read **[SSI_THRESHOLD_JUSTIFICATION.md](SSI_THRESHOLD_JUSTIFICATION.md)** (why each threshold value)
3. Review **[SSI_EXPERIMENT_RESULTS.md](../../testing/ssi_th_exp/SSI_EXPERIMENT_RESULTS.md)** (compiled results + analysis)
4. Review detailed tables: `01_long_threshold_sweep.md` … `22_layer2_gate_grid.md`
5. Fill decisions below

## Test status summary

| Test | Name | Status | Conclusion |
|------|------|--------|------------|
| 1–2 | SSI long/short threshold sweep | **DONE** | Long pctile ≤20 (n=419, 3m +3.14%, 78% win). Short +0.6 rejected. ≥95 pctile for short context. |
| 3 | SQUEEZE grid | **DONE** (2026-08-07) | Best FM&lt;20/RM&gt;45 (12w Sharpe 1.18). Display flag only. |
| 4 | LIQUIDITY EXIT grid | **DONE** (2026-08-07) | RM&lt;30/FM&gt;60: ~35% 4w SPX-down. Stress flag only. |
| 5 | TP/SL optimization | **DONE** | Best: TP×5, SL×20 (Sharpe=4.06). Legacy 10×/15× suboptimal. |
| 6 | CNN Fear & Greed | **DONE** (2026-08-07) | Post wayback backfill: fear&lt;20 n=121, 3m +4.73%. Greed not a short trigger. |
| 7 | DBMF beta threshold | **DONE** | Contrarian long context; prod bands 0.5/1.2 defensible |
| 8 | HYG/LQD widening | **DONE** (2026-08-07) | −1.5% → 2d to VIX&gt;25. Granger lag-1 p=0.006. |
| 9 | Z-score vs percentile SSI | **DONE** (not deployed) | Percentile wins in 2020/2022 crises; awaiting sign-off |
| 10 | Layer 2 min_votes (legacy 4-input) | **DONE** | Superseded by Test 22 — not production 6-gate logic |
| 11 | VIX regime / Combo B bypass | **PARTIAL** (waiver) | Oct 2022 vix_bypass verified; full 20y curve waived |
| 12 | Bollinger + SSI | **DONE** (low-n) | Combo n=1 — overlay extremely rare |
| 13 | Stochastic + McClellan | **DONE** (2026-08-07) | Re-run: combo n=13. Research only. |
| 14 | Gross/net divergence | **DONE** | n=25; SPX rises ~76% of episodes |
| 15 | SBI short signal | **DONE** (env caveat) | BMS 2015→2026 complete; **n=0** — MW `cpp_functions` missing C++ backtest symbols. Re-run on C++-enabled host before product use. |
| 16 | Friday pull checklist | **DONE** | 12/12 PASS |
| 17 | TrendPulse 0.5/week | **DONE** | 11 episodes at p60; advisory |
| 18 | COT FM long gate | **DONE** (2026-08-07) | FM&lt;20: 3m +3.13% (n=203) vs FM&lt;30 +2.78% (n=274) |
| 19 | VIX≥35 FM distribution | **DONE** | FM&lt;15 only 18% of VIX≥35 episodes |
| 20 | Layer 2 z-score sweep | **DONE** | Inflection z≥1.25 (90.5% 3m hit, n=105) |
| 21 | Staleness decay | **DONE** (2026-08-12) | Caps 8/3/30; per-signal penalties live; margin debt in pull_all |
| 22 | Layer 2 gate 2-D grid | **DONE** (2026-08-12) | Prod z≥0.5/min=2: n=160 long+gate, **41.25%** 3m hit, −1.2% avg 3m. Joint grid shows parameter interaction; **pending Rohit** |

## Recommended thresholds (engineering draft)

| Parameter | CONFIG today | Empirical recommendation | Approve? |
|-----------|--------------|--------------------------|----------|
| `long_entry_pctile` | 20 | n=419, 3m +3.14%, 78% win | |
| `short_entry_pctile` | 85 | ≥95 for negative 3m avg (n=326). 85 = caution. | |
| `long_entry` (level) | -0.6 | Secondary only | |
| `short_entry` (level) | 0.85 | Reject +0.6 | |
| Percentile SSI (Test 9) | Not in prod | Strongly favored in crises | |
| TP/SL 10×/15× vol (Test 5) | PulseGauge legacy | TP×5/SL×20 (Sharpe 4.06) | |
| `cot_fast_money_max_pct` | 30 | Test 18: **20** — 3m +3.13% vs +2.78% | |
| `layer2.min_confirmed` | 2 of 6 | Test 22: prod n=160, 41% hit; min=3 → n=107, 37% hit (not clearly better) | |
| `layer2.gate_z_min` | 0.5 | Test 22: z=0.5/min=2 best among n≥30 cells; still −1.2% avg 3m on long+gate | |
| SQUEEZE display | FM&lt;20/RM&gt;45 | Test 3 Aug 2026 | |
| LIQUIDITY EXIT display | RM&lt;30/FM&gt;60 | Test 4 Aug 2026 | |

## Waivers

| Item | ID | Notes |
|------|-----|-------|
| NFCI in SSI Layer 2 | WAIVER-NFCI-SSI | Runic only |
| Full virtual-trading equity curve (Test 11) | WAIVER-VT-11 | Oct 2022 bypass verified |
| VIX removed from SSI Layer 2 | WAIVER-VIX-L2 | Product decision pending |

## Decisions needed from Rohit

1. **Short pctile gate**: 85 (caution) vs 90 vs 95 (only negative 3m avg)?
2. **Percentile SSI deployment** (Test 9): Switch from z-score to 3yr percentile?
3. **TP/SL change** (Test 5): TP×5 / SL×20?
4. **COT FM long gate** (Test 18): FM&lt;20 vs PDF &lt;30?
5. **SQUEEZE thresholds** (Test 3): FM&lt;20/RM&gt;45 vs PDF 30/50?
6. **Bollinger overlay** (Test 12): Product requirement? (combo n=1)

**Signed:** _______________ **Date:** _______________
