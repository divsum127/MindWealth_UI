# SSI Open Questions — Status (Updated)

> **Corrected 2026-08-17.** This file previously cited `*_20260807` artifacts while quoting `*_20260804` numbers. Seven headline figures were wrong and are fixed below. Full reasoning, PAR-relative scoring and the freshness ledger live in [`SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md`](SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md) §4 — read that first.

**Spec:** [`SSI_OpenQuestions_DivyanshuTestList (1).pdf`](SSI_OpenQuestions_DivyanshuTestList%20(1).pdf) (May 25, 2026)  
**Last validation refresh:** 2026-08-12 (CFTC + Layer 2 re-runs 08-11; CNN/staleness 08-12; Friday pull 08-17)  
**Artifacts:** [`macro_intelligence/analysis/ssi_validation/`](../../macro_intelligence/analysis/ssi_validation/)  
**Results summary:** [`SSI_EXPERIMENT_RESULTS.md`](SSI_EXPERIMENT_RESULTS.md)  
**Archive (detailed history):** [`SSI_OPEN_QUESTIONS_SUMMARY.md`](SSI_OPEN_QUESTIONS_SUMMARY.md)  
**Sign-off:** [`docs/ssi_validation/SIGNOFF.md`](../../docs/ssi_validation/SIGNOFF.md)

---

## Executive summary

| Category | Count |
|----------|-------|
| Tests with a **usable result** | **19 / 22** |
| Tests **VOID** (ran, no usable sample) | **1** (Test 15 — interpreter bug, runnable) |
| Tests **WAIVED** in part | **1** (Test 11 full 20yr equity curve) |
| Tests **SIGN-OFF HELD** | **2** (Tests 3–4; held 2026-08-07, never released) |
| Test families on **pre-backfill inputs** | **11** (1–2, 5, 7, 9, 10, 11, 12, 14, 17, 19, 20) |
| PDF sub-experiments **open** | **2** (Part 8: VIX in Layer 2, NFCI in SSI — product decisions) |

Central empirical finding unchanged: **long gates work at bottom quintile of 5y SSI; short gates are asymmetric** — reject +0.6 level; use ≥85–95 percentile for caution/short context.

Two findings added 2026-08-17: **(a)** with the PAR row in place (12w +2.30%, hit 71.6%, excess-hit 59.55%), several previously-recommended CFTC cells score **below doing nothing**; **(b)** no CFTC cell is statistically distinguishable from null — `stable_across_offsets` is a sign-count heuristic, and the FM-percentile regression gives p = 0.295/0.216/0.533/0.777, R² ≤ 0.0015.

---

## Completion matrix — Tests 1–22

| # | Test | Status | Latest artifact | Notes |
|---|------|--------|-----------------|-------|
| 1–2 | SSI long/short threshold sweep | **DONE** | `01_02_threshold_sweep_20260606.json` | Long pctile ≤20 (n=419, 3m +3.14%, 78% win). Short +0.6 rejected; ≥95 pctile only negative 3m avg. |
| 3 | CFTC SQUEEZE grid | **SIGN-OFF HELD** | `03_squeeze_grid_v2_20260811.json` | Ranking is now mean−median **gap**, not Sharpe. Best cell FM&lt;10/RM&gt;55: n_ep 21, 12w +3.44%, gap +0.411%, excess-hit 65.0%. Old pick FM&lt;20/RM&gt;45 is n_ep 37, +1.34%, gap −1.96% — **below PAR**. |
| 4 | CFTC LIQUIDITY EXIT grid | **SIGN-OFF HELD** | `04_liquidity_exit_grid_v2_20260811.json` | RM&lt;30/FM&gt;60: n_ep 40, 4w SPX-down 32.5%, 12w +2.48%, excess-hit 45.0% (below PAR). Stress flag, not short trigger. |
| 5 | TP/SL optimization | **DONE** | `05_tp_sl_20260606.json` | Best TP×5/SL×20 (Sharpe 4.06). Legacy 10×/15× suboptimal. CONFIG unchanged. |
| 6 | CNN Fear & Greed | **STALE — must re-run** | `06_cnn_fear_greed_20260812.json` | Fear&lt;20 n=121; greed&gt;80 n=65. **The 08-12 run is byte-identical to 08-07 across all four rules** — it did not ingest the wayback backfill. Test 21 sees `cnn_fg` n_obs=670 vs 4,327 for AAII. |
| 7 | DBMF beta | **DONE** | `07_dbmf_beta_20260606.json` | β&lt;−0.10 contrarian long context; DBMF Granger done. |
| 8 | HYG/LQD widening | **DONE** | `08_hyg_lqd_20260807.json` | −1.5% → median 2 days to VIX&gt;25. **Granger added Aug 2026** (lag-1 p=0.006). |
| 9 | Z-score vs percentile SSI | **DONE (stale inputs)** | `09_zscore_vs_percentile_20260606.json` | Percentile flags 71 COVID days vs 46 for z-score (6m +23.96%, 100% win); Oct 2022 47 days, 6m +8.70%. **Not deployed** — awaiting Rohit. |
| 10 | Layer 2 vote sweep | **DONE (stale inputs)** | `10_layer2_sweep_20260606.json` | **Correction:** votes are not neutral. n by min_votes = 419/413/**314**/**231**/**78**; 3m win 78.0%→78.5%→**89.8%**→**93.5%**→**96.2%**. min_votes=4 gives 78 days, not 0. `min_confirmed` is a live tuning parameter — see Test 22. |
| 11 | VIX regime multiplier | **PARTIAL** | `11_vix_regime_ab_20260606.json` | Oct 2022 bypass verified. Full 20yr curve **WAIVED** (WAIVER-VT-11). |
| 12 | Bollinger + SSI | **DONE** (low-n) | `12_bollinger_ssi_20260606.json` | BB-only n=115; combo (pctile≤20) **n=1** — overlay extremely rare. Advisory only. |
| 13 | Stochastic + McClellan | **DONE** | `13_stoch_mcclellan_20260807.json` | **Re-run Aug 2026** after McClellan backfill to 2014. Combo n=13 (was 3). Research only. |
| 14 | Gross/net divergence | **DONE** | `14_gross_net_20260606.json` | n=25; SPX rises ~76% of episodes. |
| 15 | SBI short signal | **VOID — runnable, not blocked** | `15_sbi_short_20260812.json` | BMS batch 2015→2026 complete (140 months, 4 shards). **n=0 short entries.** **Recorded cause was wrong:** the `.so` exports both symbols. Real cause is an interpreter mismatch — `run_test15_sbi_parallel.sh` uses the 3.12 `.venv` against a `cpython-310` `.so`, silently importing an empty namespace package. Re-run under `/home/ubuntu/MindWealth/venv/bin/python` (3.10.19) after fixing the missing `data.initialize_data()` call in `scripts/mindwealth_adapters/sbi_breadth.py`. |
| 16 | Friday pull checklist | **DONE** | `16_friday_pull_20260817.json` | **11 PASS, 1 WARN** (CPI surprise, Trading Economics primary) — not 12/12. |
| 17 | TrendPulse deterioration | **DONE** | `17_trendpulse_20260606.json` | 11 episodes at p60 threshold. Small n, advisory. |
| 18 | COT FM long gate | **DONE** | `18_cot_fm_long_gate_20260807.json` | FM&lt;20 beats PDF &lt;30: 3m +3.13% (n=203) vs +2.78% (n=274). |
| 19 | VIX≥35 + FM distribution | **DONE** | `19_vix_fm_washout_20260607.json` | 93 episodes; FM&lt;15 only 18%. |
| 20 | Layer 2 z-score sweep | **DONE** | `20_layer2_zscore_sweep_20260607.json` | Inflection z≥1.25 (90.5% 3m hit, n=105). Research overlay. |
| 21 | Staleness decay | **DONE** | `21_staleness_decay_20260812.json` | Beyond original PDF. Caps weekly 8 / daily 3 / monthly 30. AAII/NAAIM no penalty; COT decays hard (`cftc_fm_net` R² ratio 0.36, `cftc_rm_net` 0.44 at 4w). |
| 22 | Layer 2 gate 2-D grid | **DONE — neither default proven** | `22_layer2_gate_grid_20260811.json` | Window is **2015-01-01→2026** (3,872 days), not 2010. Prod (z≥0.5, min=2): n=**160** long+gate, 3m hit **41.25%**, 3m mean **−1.20%**, fires 50.2% of days. |

---

## PDF Parts 1–10 status

| Part | Topic | Status |
|------|-------|--------|
| 1 | Critical validation gaps (thresholds) | **DONE** — Tests 1–2, 5–10, 18–20 |
| 2 | Signal definition gaps (HYG/LQD, DBMF, CNN) | **DONE** — Test 8 Granger closed Aug 2026 |
| 3 | Date corrections (2025 vs 2026) | **DONE** — documented in summary §3 |
| 4 | Gross/net divergence | **DONE** — Test 14 |
| 5 | VIX regime multiplier | **PARTIAL** — bypass verified; full backtest waived |
| 6 | SBI correction | **DONE** (env caveat) — Test 15 batch complete; n=0 due to MW cpp_functions gap |
| 7 | TrendPulse deterioration | **DONE** — Test 17 |
| 8 | Runic vs SSI overlap | **PRODUCT** — VIX still in Layer 2; NFCI waived (WAIVER-NFCI-SSI) |
| 9 | Numbered test deliverables | **21/22 done**, 1 waived; Test 15 done with env caveat |
| 10 | Friday pull list | **DONE** — Test 16 |

---

## Done since June 2026 audit

1. **CFTC grids re-run** (Aug 4–7, superseded by a clean full run Aug 11): Tests 3–4 with COT through 2026-08-04; latest Rohit report `docs/ssi_validation/CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_20260811.md`. Note the Aug-7 report was compiled from an **aborted** grid run that reused the existing v2 JSON; only the Aug-11 artifacts are a clean full run.
2. **CNN F&G backfill** (Aug 2): Wayback reconstruction 2012–2020 + real CNN API 2020+. **Test 6 has not actually consumed it** — see the Test 6 row.
3. **Test 18 re-run** with fresh COT (`18_cot_fm_long_gate_20260807.json`).
4. **Test 21 staleness decay** — new test beyond PDF, recalibrated Aug 12 (`21_staleness_decay_20260812.json`).
5. **Layer 3 CFTC pattern flags** wired to Sentiment UI (display only) — **at the held FM&lt;20/RM&gt;45 and RM&lt;30/FM&gt;60 values**, which is a merge-blocker while sign-off is held.
6. **Breadth/McClellan backfill** (Aug 7): `mcclellan_oscillator.csv` extended 2014-01-02 → 2026-08-06 (3,167 rows).
7. **Test 13 re-run** — combo n=13 (was 3).
8. **Test 22 re-run** — window is **2015→2026** (3,872 trading days), not 2010.
9. **Test 8 Granger** — HYG/LQD 4wk % change → SPX return (lag-1 p=0.0062).
10. **Test 15 SBI batch** (Aug 11–12): 4-shard parallel BMS scan 2015→2026 (`15_sbi_short_20260812.json`). Adapter fixes: inline SPX metrics, kaleido/plot suppression, checkpointing, offline sp500 cache. **Result n=0 — void, and the recorded cause was wrong** (see the Test 15 row: interpreter mismatch, not a missing C++ build).
11. **CFTC method overhaul** (Aug 7–11): ranking switched Sharpe → mean−median gap; overlapping weeks collapsed into episodes; **PAR row + excess-over-market added**; 12-offset subsample stability + block bootstrap; dated tail-episode lists; absolute FM net cuts.
12. **Analysis doc + CSV value exports** (Aug 17): [`SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md`](SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md) and `scripts/export_ssi_validation_csvs.py` → 50 CSVs + `INDEX.csv` under `macro_intelligence/analysis/ssi_validation/csv/`.

---

## Remaining work

| Priority | Item | Action |
|----------|------|--------|
| **P0** | Agree the stale-backtest list | [`STALE_BACKTESTS_AFTER_CNN_HY_FIXES.md`](../../docs/ssi_validation/STALE_BACKTESTS_AFTER_CNN_HY_FIXES.md) gates all re-runs. **Amend it first** — the "Layer 2 via `hyg_lqd`" bucket conflates SSI's Yahoo ETF ratio (`src/sentiment_superindex/data/yahoo_inputs.py:15`) with ICE BofA HY OAS, which lives only under `src/macro_intelligence/`. No shared code path. |
| **P0** | Test 15 re-run | **No C++ rebuild needed.** Run under `/home/ubuntu/MindWealth/venv/bin/python` (3.10.19), not the 3.12 `.venv`. Fix the missing `data.initialize_data()` in `scripts/mindwealth_adapters/sbi_breadth.py` first, or the DELTADRIFT leg returns L0/S0 for all 500 symbols. |
| **P1** | Rohit sign-off | Fill [`SIGNOFF.md`](../../docs/ssi_validation/SIGNOFF.md) — D-1…D-6 below, **plus D-7 `min_confirmed`**. Note SIGNOFF still marks Tests 3–4 DONE; they are HELD. |
| **P2** | Product decisions | Part 8: remove VIX from Layer 2? NFCI in SSI? (NFCI waived) |

### Optional (do not block sign-off)

- Test 11 full 20yr VIX multiplier equity curve (waived)
- Test 12 Bollinger rerun (n=1 may be true signal frequency)

---

## Data health checklist (2026-08-07)

| Series | Start | End | Rows | Status |
|--------|-------|-----|------|--------|
| SSI history (`build_ssi_history_frame`) | 2010-06-15 | 2026-08-07 | 5,023 | OK |
| `mcclellan_oscillator.csv` | 2014-01-02 | 2026-08-06 | 3,167 | OK (backfilled Aug 7) |
| `pct_above_200dma.csv` | 2014-10-16 | 2026-08-06 | 2,968 | OK |
| `nh_nl_ratio.csv` | 2014-12-31 | 2026-08-06 | 2,906 | OK |
| `cnn_fear_greed.csv` | 2012-05-25 | 2026-07-31 | ~3,500+ | OK (provenance tags: real_cnn_api / wayback / crypto_proxy) |
| CFTC FM/RM | 2010-06-15 | 2026-07-28 | 833 weeks | OK |

---

## Rohit decisions (blocking CONFIG changes)

| # | Topic | Options | Evidence |
|---|-------|---------|----------|
| D-1 | Short pctile gate | 85 vs 90 vs 95 | ≥85: +1.38% 3m; ≥95: −0.78% 3m (n=326) |
| D-2 | Percentile SSI composite | Deploy vs keep z-score | Test 9 — percentile registers crisis days z-score misses |
| D-3 | TP/SL | TP×5/SL×20 vs legacy 10×/15× | Sharpe 4.06 vs 0.91 |
| D-4 | COT FM long gate | FM&lt;20 vs PDF &lt;30 | Test 18 — +3.13% vs +2.78% at 3m |
| D-5 | Bollinger overlay | Product requirement? | Test 12 — combo n=1 |
| D-6 | SQUEEZE thresholds | **FM&lt;10/RM&gt;55** vs PDF 30/50 | Gap +0.411% (n_ep 21) vs −0.57% (n_ep 43). The old FM&lt;20/RM&gt;45 pick is below PAR. But 14 of the 21 episodes are 2023+, and no cell is significant vs null. |
| **D-7** | **`min_confirmed` (new)** | Keep 2 / tighten to 3 / demote Layer 2 to sizing-only | Test 22: prod cell n=160, 3m hit 41.25%, mean −1.20% — never backtested on 6-gate logic. Test 10: 3m win rises 78.0%→89.8%→93.5%→96.2% as votes go 0→4. |

---

*Updated 2026-08-17 (seven figures corrected — see [`SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md`](SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md) §4). Reproduce values: `.venv/bin/python scripts/export_ssi_validation_csvs.py`. Re-run experiments: `.venv/bin/python scripts/run_ssi_validation_suite.py` or `scripts/run_test15_sbi_parallel.sh`.*
