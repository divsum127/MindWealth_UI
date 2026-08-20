# SSI Threshold Experiments — Analysis (Open Questions Parts 1–10, Tests 1–22)

**Date:** 2026-08-17
**Spec:** [`SSI_OpenQuestions_DivyanshuTestList (1).pdf`](SSI_OpenQuestions_DivyanshuTestList%20(1).pdf) (May 2026)
**Values:** every number below was read from the newest JSON artifact in [`macro_intelligence/analysis/ssi_validation/`](../../macro_intelligence/analysis/ssi_validation/), flattened to CSV by [`scripts/export_ssi_validation_csvs.py`](../../scripts/export_ssi_validation_csvs.py) → [`csv/INDEX.csv`](../../macro_intelligence/analysis/ssi_validation/csv/INDEX.csv)

> **Read §4 before quoting any older doc.** `SSI_EXPERIMENT_RESULTS.md` and `SSI_OPEN_QUESTIONS_STATUS.md` (both 2026-08-12) cite `*_20260807` artifacts while quoting `*_20260804` numbers, and seven of their headline figures are contradicted by the artifacts they point at.

---

## 1. How to read this

### 1.1 Freshness legend

| Tag | Meaning |
|---|---|
| **CURRENT** | Newest artifact post-dates the 2026-08-02 CNN/HY fixes *and* its inputs actually changed |
| **STALE** | Scores the SSI composite, which carries `cnn_fg` at weight 0.25; newest artifact predates the CNN backfill |
| **UNAFFECTED** | Inputs are CFTC / VIX / breadth / DBMF only — the two data fixes cannot move them |
| **VOID** | Ran to completion but produced no usable sample for an environment reason |

Source of truth for the tagging is [`STALE_BACKTESTS_AFTER_CNN_HY_FIXES.md`](../../docs/ssi_validation/STALE_BACKTESTS_AFTER_CNN_HY_FIXES.md) (2026-08-17). Two places where the artifacts disagree with that list are flagged in §5.4.

### 1.2 Scoring rule — judge against PAR, not against zero

The August CFTC re-runs added a **PAR row**: the same metrics computed on *every* week with no filter. A pattern is only interesting if it beats PAR.

| PAR (12-week, unconditional) | Value |
|---|---|
| n weeks | 1,033 (1,021 with a full 12w forward window) |
| mean | **+2.3027%** |
| median | +3.5011% |
| hit rate | **71.6%** |
| excess-hit rate | **59.55%** |

Any cell below +2.30% mean or below 59.55% excess-hit is **worse than doing nothing**. Several previously-recommended cells are.

---

## 2. Three method changes that move conclusions

| # | Change | Effect |
|---|---|---|
| 2.1 | Ranking metric **Sharpe → mean−median gap** | A high Sharpe cell can be pure market beta. The gap isolates tail behaviour. This alone demoted the SQUEEZE recommendation. |
| 2.2 | Counting **overlapping weeks → collapsed episodes** | `FM<20/RM>45` was "n=125 weeks"; as independent episodes it is **n=37**. Every earlier n is inflated. |
| 2.3 | **PAR + excess-over-market** added | Converts "this cell returns +3%" into "this cell returns +1.1% *more than the market did over the same windows*". |

---

## 3. Answers by PDF Part

> **Mapping note.** Part→Test assignment follows the sub-question granularity in `understanding_and_research/SSI_OpenQuestions_Understanding.md` (1.3→T3, 1.4→T4, 2.1→T8, 2.2→T7). It differs from `SSI_OPEN_QUESTIONS_STATUS.md`, which lists Part 1 as "Tests 1–2, 5–10, 18–20" — that omits Tests 3 and 4 entirely and files 7 and 8 under Part 1 rather than Part 2. Tests 21 and 22 have no PDF Part; 21 is beyond the spec, 22 is retro-fitted to §1.8.

### Part 1 — Critical validation gaps (thresholds) · Tests 1–2, 3, 4, 5, 6, 9, 10, 18, 19, 20

**Asked:** where did the ±0.6 gates, the SQUEEZE/LIQUIDITY-EXIT cutoffs, TP/SL multipliers and the CNN 20/80 levels come from, and do they survive testing?
**Ran:** level + percentile sweeps on 5y SSI; 6×6 CFTC grids; TP/SL grid; CNN crossings; Layer 2 vote and z sweeps.
**Found:**
- **Long/short is asymmetric.** Long pctile ≤20: n=419, 3m **+3.14%**, win **78.0%**. Short ≥+0.6 fires 884× with only ~36% down — rejected. Only pctile **≥95** has a negative 3m mean (n=326, **−0.78%**).
- **SQUEEZE:** best cell on gap is **FM<10 / RM>55** — n_ep **21**, 12w mean **+3.44%**, gap **+0.411%**, excess-hit **65.0%**. Clears PAR. The previously-recommended `FM<20/RM>45` is n_ep 37, mean **+1.34%**, gap **−1.96%**, excess-hit 58.3% — **below PAR**.
- **TP/SL:** best is **TP×5 / SL×20** (n=430, Sharpe **4.06**, win 97.7%) vs legacy 10×/15× Sharpe 0.91.
- **CNN:** fear<20 n=121, 3m **+4.73%**, win 71.7%; fear<10 n=58, 3m **+8.15%**. Greed>80 is momentum (3m +0.99%, win 69.2%), **not** a short trigger.
- **COT FM long gate (Test 18):** FM<20 n=203, 3m **+3.13%**, win 73.7% beats PDF's FM<30 (n=274, +2.78%).
- **VIX≥35 washout (Test 19):** 93 episodes, FM median 54.5, only **18.3%** below the 15th pctile. The FM<15 slice (n=17) returns 3m **+8.25%**, 94% up — a contrarian long, not a short.
- **Layer 2 z sweep (Test 20):** inflection at z≥1.25 — n=105, 3m hit **90.5%** vs 79.3% at z=0.

**Verdict:** long gate settled; short gate settled as *caution context only*; SQUEEZE and TP/SL **await sign-off**; CNN greed rejected as a short.
**Values:** `csv/01_02_threshold_sweep__{long,short}_pctile_sweep.csv`, `csv/03_squeeze_grid_v2__rows.csv`, `csv/05_tp_sl__rows.csv`, `csv/06_cnn_fear_greed__rules.csv`, `csv/18_cot_fm_long_gate__rows.csv`, `csv/19_vix_fm_washout__fm_threshold_sweep.csv`, `csv/20_layer2_zscore_sweep__rows.csv`

---

### Part 2 — Signal definition gaps · Tests 6, 7, 8

**Asked:** what exactly is HYG/LQD "widening", is the DBMF beta threshold on/off, are the CNN levels validated?
**Ran:** threshold crossings + lead-time to VIX>25 + Granger; 21-day rolling DBMF beta vs SPY.
**Found:** HYG/LQD −1.5% over 4 weeks → median **2 days** to VIX>25 (n=116); −3.0% → **0 days** (n=53). Granger on the 4-week change → SPX return is significant at **lag-1 p=0.0062**. DBMF β<−0.10: n=29, 4w **+1.33%**, win 65.5% — negative beta coincides with *positive* drift, so it is contrarian long context; DBMF Granger is not predictive (p>0.55).
**Verdict:** all three definitions closed. Production Layer 2 uses ratio percentiles rather than the 4-week % cuts — a deliberate difference, not a gap.
**Values:** `csv/08_hyg_lqd__rows.csv`, `csv/08_hyg_lqd__meta.csv`, `csv/07_dbmf_beta__rows.csv`

---

### Part 3 — Date corrections (2025 vs 2026) · no test artifact

**Asked:** correct the year references in the spec.
**Verdict:** documentation-only, closed in `SSI_OPEN_QUESTIONS_SUMMARY.md` §3. No experiment, no values file.

---

### Part 4 — Gross/net divergence · Test 14

**Asked:** is the 3-condition rule (gross >75th pctile 3y for 3+ weeks, net falling, HYG/LQD 4w < −1%) reliably bearish?
**Found:** n=25 episodes. SPX **falls in only 24%** of 4-week windows; 4w median **+1.93%**, 12w mean +2.44%.
**Verdict:** **not bearish.** Stress-cluster warning text only — never a short gate. `STALE` (composite path).
**Values:** `csv/14_gross_net__meta.csv` (the 20 sampled episode dates are carried in the `instances` key)

---

### Part 5 — VIX regime multiplier (the Dalio problem) · Test 11

**Asked:** does the VIX>35 size cut wrongly shrink positions at crisis bottoms like Oct 2022?
**Found:** 2022-10-13 shows `combo_b=true`, `vix_bypass=true` — the bypass fires correctly. Average multiplier with Layer 2 **1.199** vs 1.000 without.
**Verdict:** wiring verified; **economic magnitude never quantified**. Full 20-year equity curve waived (`WAIVER-VT-11`) because it needs MindWealth virtual_trading.
**Values:** `csv/11_vix_regime_ab__meta.csv`

---

### Part 6 — SBI correction · Test 15

**Asked:** is an SBI short reading above the 90th percentile useful confirmation?
**Ran:** monthly BMS scan 2015-01 → 2026-08 (140 months, 4 parallel shards).
**Found:** **n=0 short entries.**
**Verdict:** **VOID, not a result — and the recorded reason is wrong.** The artifact and `SIGNOFF.md` blame a MindWealth `cpp_functions` build "lacking `backtest_bb`/`is_pivot`". It does not: `/home/ubuntu/MindWealth/cpp_functions.cpython-310-*.so` exists and exports both. The real cause is an **interpreter mismatch** — `scripts/run_test15_sbi_parallel.sh` invokes `${MW}/.venv/bin/python` (**3.12**), which skips the 3.10-ABI `.so` and silently imports the empty `cpp_functions/` directory as a namespace package. No ImportError is raised, so COMBINED_STRATEGY returns 0 trades for every symbol-month and the short percentile-from-top never drops to ≤10. Under `/home/ubuntu/MindWealth/venv/bin/python` (3.10.19, the interpreter `mindwealth-app.service` itself uses) a smoke run returns real trades on both sides.
**So Test 15 is runnable, not blocked** — no C++ rebuild needed, just the right interpreter. One adapter defect must be fixed first: `scripts/mindwealth_adapters/sbi_breadth.py` never calls `data.initialize_data()`, so `load_stake()` raises `NameError: name 'df_stake' is not defined` on the `load_ipo_date` path and the **DELTADRIFT** leg returns L0/S0 for all 500 symbols — one of three COMBINED_STRATEGY legs would be silently under-counted.
**Values:** `csv/15_sbi_short__meta.csv`

---

### Part 7 — TrendPulse deterioration · Test 17

**Asked:** which weekly |ΔSSI| threshold predicts negative forward returns?
**Found:** at the p60 threshold, **11 episodes**, 3m **+7.87%**, win **90.9%**.
**Verdict:** the threshold flags **recoveries, not tops** — the opposite of the intent. n=11 is too small to conclude either way. TrendPulse needs product scoping before any threshold is fixed.
**Values:** `csv/17_trendpulse__results.csv`

---

### Part 8 — Runic Agent vs SSI overlap · product decision + Test 22

**Asked:** VIX and NFCI appear in both engines — is that double-counting?
**Verdict:** **open product decision.** VIX is still in SSI Layer 2 (`WAIVER-VIX-L2`, "pending"); NFCI stays Runic-only (`WAIVER-NFCI-SSI`). Ownership convention is recorded in [`00_methodology.md`](../../docs/ssi_validation/00_methodology.md): HY OAS → Runic; HYG/LQD → SSI; VIX term structure → Runic combos; CNN F&G → SSI Layer 1/2.

---

### Part 9 — Numbered test deliverables · Tests 1–22 roll-up

**Asked:** deliver the numbered test list.
**Verdict:** 22 tests exist against a spec that listed 15. Delivered: **19 with a usable result**, 1 void (15), 1 waived in part (11), 1 contradicting its own summary (10). Tests 18–22 were added beyond the PDF; 21 has no PDF Part at all.

Two Part-9 tests are worth calling out because their samples are too small to support any claim:
- **Test 12 (Bollinger + SSI):** BB-only n=115 (3m +5.05%, win 80.4%), but the **combo fires exactly once** (n=1). Cannot validate or reject.
- **Test 13 (Stochastic + McClellan):** stoch-only n=179, McClellan-only n=291, **combo n=13** (2w +0.45%, win 61.5%). Research only.

**Values:** `csv/12_bollinger_ssi__meta.csv`, `csv/13_stoch_mcclellan__meta.csv`

---

### Part 10 — Friday pull list · Test 16

**Asked:** can all ~18 macro variables be pulled automatically each Friday?
**Found:** **11 PASS, 1 WARN** of 12 checks. The warning is **CPI surprise** (`cpi_pull`, Trading Economics primary).
**Verdict:** automation effectively complete, with one fragile source. Note this is *not* the "12/12 PASS" quoted in the compiled docs — see §4.
**Values:** `csv/16_friday_pull__items.csv`

---

### Beyond the PDF — Tests 21, 22 and the CFTC robustness pass

- **Test 21 (staleness decay).** Calibrated caps now live in `SSI_CONFIG.yaml`: **weekly 8 / daily 3 / monthly 30**. AAII and NAAIM need **no penalty** (day-5 R² ≥ 90% of day-1). COT decays hard — `cftc_fm_net` R² ratio **0.36**, `cftc_rm_net` **0.44** at 4w, both well below the global 0.8 penalty, so per-signal penalties are justified. `margin_debt` has insufficient data.
- **Test 22 (Layer 2 gate 2-D grid).** Production cell (z≥0.5, min_confirmed=2): **n=160** long-gate-confirmed days, 3m hit **41.25%**, 3m mean **−1.20%**, firing on **50.2%** of days. Neither production default is empirically supported — `min_confirmed=2` was design intent and had never been backtested on the 6-gate logic.
- **CFTC robustness.** Across 12 non-overlapping subsamples: `FM<7.5/RM>45` and `FM<7.5/RM>40` are positive in **10/12** offsets, `FM<5/RM>45` in **12/12** (but n_ep=11). `FM<7.5 AND FM_net<0` fails at 7/12. See §5.2 for what this does *not* prove.

**Values:** `csv/21_staleness_decay__signals.csv`, `csv/21_staleness_decay__signals__age_buckets.csv`, `csv/22_layer2_gate_grid__rows.csv`, `csv/cftc_robustness_subsample__cells.csv`, `csv/cftc_fm_pctile_regression__rows.csv`

---

## 4. Corrections — superseded numbers in the 2026-08-12 compiled docs

Five real number changes and two stale citations. Every "actual" was read from the artifact named in the last column.

| # | Test | Compiled docs claim | Actual | Artifact |
|---|---|---|---|---|
| C-1 | 3 SQUEEZE best cell | `FM<20/RM>45` — n=125, 12w **+3.32%**, Sharpe **1.18**, win 77.5% | n_ep **37**, 12w **+1.34%**, Sharpe **0.42**, gap **−1.96%**, excess **−0.96%** → **below PAR**. New best on gap: `FM<10/RM>55`, n_ep 21, +3.44%, gap +0.411% | `03_squeeze_grid_v2_20260811.json` |
| C-2 | 3 PDF default | `FM<30/RM>50` — n=170, 12w +2.66%, Sharpe 0.88 | n_ep **43**, 12w +2.76%, gap −0.57%, excess-hit **62.8%** (this one *does* clear PAR) | same |
| C-3 | 4 LIQUIDITY EXIT | `RM<30/FM>60` — n=116, 4w down **35.3%**, 12w +2.84% | n_ep **40**, 4w down **32.5%**, 12w **+2.48%**, 12w excess-hit **45.0%** → below PAR | `04_liquidity_exit_grid_v2_20260811.json` |
| C-4 | 22 production cell | n=**180**, 3m hit **45.0%**, window **2010**→2026, freq 41.6% | n=**160**, 3m hit **41.25%**, 3m mean **−1.20%**, window **2015-01-01**→2026, freq **50.2%** | `22_layer2_gate_grid_20260811.json` |
| C-5 | 10 Layer 2 vote sweep | "min_votes 0–3 **identical metrics** on n=419; min_votes=**4: 0 days**" | Neither holds. n by min_votes: 0→419, 1→413, 2→**314**, 3→**231**, 4→**78**. 3m win rises 78.0% → 78.5% → **89.8%** → **93.5%** → **96.2%** | `10_layer2_sweep_20260606.json` |
| C-6 | 9 percentile vs z-score | COVID percentile **62 days**, 6m **+19.3%**, win 93.6%; Oct 2022 **84 days**, 6m +8.0% | COVID percentile **71 days**, 6m **+23.96%**, win **100%**; Oct 2022 **47 days**, 6m +8.70%, win 97.9% | `09_zscore_vs_percentile_20260606.json` |
| C-7 | 16 Friday pull | "**12/12 PASS**" | **11 PASS, 1 WARN** — CPI surprise | `16_friday_pull_20260817.json` |
| — | 6 and 21 | Values quoted are **correct** (fear<20 n=121; caps 8/3/30) but cited to `*_20260807` | Newest is `*_20260812`; headline values unchanged. Citation-only fix. | `06_cnn_fear_greed_20260812.json`, `21_staleness_decay_20260812.json` |

**C-5 changes a recommendation.** The compiled reading — "votes make no difference, so 2 is as good as anything" — is backwards. Vote count monotonically improves hit rate right up to 4. That does not make 4 correct (n falls to 78), but it means `min_confirmed` is a real tuning parameter, and it is the same parameter Test 22 found unproven.

Also: `SIGNOFF.md` still marks Tests 3–4 **DONE**. Sign-off on both patterns was **HELD** on 2026-08-07 and never released.

---

## 5. Caveats that survive the corrections

### 5.1 The SQUEEZE recommendation rests on 21 episodes, and they are not spread out
`FM<10/RM>55` has **zero episodes before 2010-06-15**, and **14 of its 21 episodes are 2023 or later**. It is close to a recent-regime artefact. The sample itself is fine — raw COT starts 2006-06-13, analysis covers **1,033 weeks** to 2026-08-04, and the GFC *is* in-sample (136 weeks run on a partial <156-week percentile base before the first full window at 2009-06-02) — the problem is this cell's own coverage, not the window.

### 5.2 No CFTC cell is statistically distinguishable from null
`stable_across_offsets` is a **sign-count heuristic** (`n_with_data≥8 and n_positive≥max(8, 0.67·n_with_data)`, `cftc_episode_metrics.py:336`) — not a significance test. The block bootstrap reports `pctile_of_observed` of **40–55**, i.e. the observed value sits in the middle of its *own* resample; that is a confidence interval, not a null test. Three of four cells have 90% intervals straddling zero. The FM-percentile regression gives p = **0.295 / 0.216 / 0.533 / 0.777** with R² ≤ 0.0015. **Stability ≠ alpha.**

### 5.3 Test 22's window is 2015→2026, not 2010→2026
3,872 trading days from 2015-01-01. Roughly five years shorter than the compiled docs imply, and it excludes 2010–2014 entirely.

### 5.4 Eleven test families still run on pre-backfill inputs — and the published list has two edge cases
No August artifact exists for Tests **1–2, 5, 7, 9, 10, 11, 12, 14, 17, 19, 20**. Two notes where the artifacts and the 2026-08-17 list need reconciling before re-runs start:

- **Test 6 and Test 8 are listed "must re-run", and the artifacts agree** despite carrying August dates. `06_cnn_fear_greed_20260812.json` is **byte-identical** to the 08-07 run across all four rules — a re-run that ingests a 2012–2020 backfill cannot produce identical output, so it did not see the new data. `08_hyg_lqd_20260807.json` differs from June only at the −1.0% threshold (167→168 crossings); the other three thresholds are unchanged. Corroborating evidence: Test 21 reports `cnn_fg` `n_obs_total = 670` against 4,327 for AAII — the short CNN series, not the backfilled one.
- **The HY OAS fix does not reach SSI's `hyg_lqd`.** SSI's input is the **HYG/LQD ETF price ratio** from `src/sentiment_superindex/data/yahoo_inputs.py:15`; ICE BofA HY OAS is consumed only under `src/macro_intelligence/`. The two do not share a code path. Tests 8, 10, 20 and 22 are therefore stale via `cnn_fg` in the composite gate, **not** via HY OAS — worth confirming before anyone re-runs them on that basis.

---

## 6. Value-file index

Generated by `scripts/export_ssi_validation_csvs.py`; full listing with row counts in [`csv/INDEX.csv`](../../macro_intelligence/analysis/ssi_validation/csv/INDEX.csv). All paths relative to repo root.

| Test | Part | Newest artifact | Exported CSVs (`macro_intelligence/analysis/ssi_validation/csv/`) | Fresh |
|---|---|---|---|---|
| 1–2 | 1 | `01_02_threshold_sweep_20260606.json` | `01_02_threshold_sweep__{long,short}_{level,pctile}_sweep.csv`, `__meta.csv` | STALE |
| 3 | 1 | `03_squeeze_grid_v2_20260811.json` | `03_squeeze_grid_v2__rows.csv`, `__rows__episodes.csv`, `__rows__all_episodes.csv`, `__meta.csv` | CURRENT |
| 4 | 1 | `04_liquidity_exit_grid_v2_20260811.json` | `04_liquidity_exit_grid_v2__rows.csv`, `__rows__episodes.csv`, `__rows__all_episodes.csv`, `__meta.csv` | CURRENT |
| 5 | 1 | `05_tp_sl_20260606.json` | `05_tp_sl__rows.csv`, `__meta.csv` | STALE |
| 6 | 1,2 | `06_cnn_fear_greed_20260812.json` | `06_cnn_fear_greed__rules.csv`, `__meta.csv` | STALE |
| 7 | 2 | `07_dbmf_beta_20260606.json` | `07_dbmf_beta__rows.csv`, `__meta.csv` | UNAFFECTED |
| 8 | 2 | `08_hyg_lqd_20260807.json` | `08_hyg_lqd__rows.csv`, `__meta.csv` | STALE |
| 9 | 1 | `09_zscore_vs_percentile_20260606.json` | `09_zscore_vs_percentile__meta.csv` | STALE |
| 10 | 1 | `10_layer2_sweep_20260606.json` | `10_layer2_sweep__rows.csv`, `__meta.csv` | STALE |
| 11 | 5 | `11_vix_regime_ab_20260606.json` | `11_vix_regime_ab__meta.csv` | UNAFFECTED |
| 12 | 9 | `12_bollinger_ssi_20260606.json` | `12_bollinger_ssi__meta.csv` | STALE |
| 13 | 9 | `13_stoch_mcclellan_20260807.json` | `13_stoch_mcclellan__meta.csv` | UNAFFECTED |
| 14 | 4 | `14_gross_net_20260606.json` | `14_gross_net__meta.csv` | STALE |
| 15 | 6 | `15_sbi_short_20260812.json` | `15_sbi_short__meta.csv` | VOID |
| 16 | 10 | `16_friday_pull_20260817.json` | `16_friday_pull__items.csv`, `__meta.csv` | CURRENT |
| 17 | 7 | `17_trendpulse_20260606.json` | `17_trendpulse__results.csv`, `__meta.csv` | UNAFFECTED |
| 18 | 1 | `18_cot_fm_long_gate_20260807.json` | `18_cot_fm_long_gate__rows.csv`, `__meta.csv` | CURRENT |
| 19 | 1 | `19_vix_fm_washout_20260607.json` | `19_vix_fm_washout__{episodes,bins,fm_threshold_sweep}.csv`, `__meta.csv` | UNAFFECTED |
| 20 | 1 | `20_layer2_zscore_sweep_20260607.json` | `20_layer2_zscore_sweep__rows.csv`, `__meta.csv` | STALE |
| 21 | — | `21_staleness_decay_20260812.json` | `21_staleness_decay__signals.csv`, `__signals__age_buckets.csv`, `__meta.csv` | CURRENT |
| 22 | 1 | `22_layer2_gate_grid_20260811.json` | `22_layer2_gate_grid__rows.csv`, `__meta.csv` | CURRENT |
| 3–4 sup | 1 | `cftc_robustness_subsample_20260811.json` | `cftc_robustness_subsample__cells.csv`, `__meta.csv` | CURRENT |
| 18 sup | 1 | `cftc_fm_pctile_regression_20260811.json` | `cftc_fm_pctile_regression__rows.csv`, `__meta.csv` | CURRENT |

**Pre-existing share bundles** (not regenerated — richer, hand-built for Rohit):
`docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/` — 11 CSVs for Tests 3/4/18 including `par_row.csv`, `episode_dates_top_cells.csv`, `robustness_subsample.csv`, `sample_diagnostics.csv`.
`docs/ssi_validation/LAYER2_GATE_GRID_ROHIT_SHARE_20260812/csv/` — 2 CSVs for Test 22 (**untracked in git; no script produces them**).

**Input series** (raw, not experiment output): `macro_intelligence/data/ssi/*.csv` — `cnn_fear_greed.csv` (4,526 rows, 2012-05-25→), `put_call_{ratio_raw,ema}.csv`, `mcclellan_oscillator.csv` (3,173), `nh_nl_ratio.csv` (2,912), `pct_above_200dma.csv` (1,630), `naaim_exposure.csv` (1,047), `margin_debt.csv` (86); plus `macro_intelligence/data/aaii_sentiment.csv` (2,036) and the daily store `macro_intelligence/data/ssi/ssi.db` (table `ssi_daily`, 3,183 rows, 2015-01-01→2026-08-17).

---

## 7. Open decisions for Rohit

Labels **D-1…D-6** come from `SSI_OPEN_QUESTIONS_STATUS.md`; [`SIGNOFF.md`](../../docs/ssi_validation/SIGNOFF.md) lists the same six unlabelled and is **unsigned**, with all 12 `Approve?` cells blank.

| # | Decision | Options | Evidence |
|---|---|---|---|
| D-1 | Short percentile gate | 85 (caution) / 90 / 95 | Only ≥95 has a negative 3m mean (−0.78%, n=326); ≥90 gives +0.50% |
| D-2 | Percentile SSI composite | Deploy / keep z-score | Percentile catches 71 COVID days vs 46 for z-score; 6m +23.96% at 100% win |
| D-3 | TP/SL | TP×5/SL×20 / legacy 10×/15× | Sharpe 4.06 vs 0.91 |
| D-4 | COT FM long gate | FM<20 / PDF FM<30 | +3.13% vs +2.78% at 3m |
| D-5 | Bollinger overlay | Product requirement? | Combo n=1 — cannot be validated |
| D-6 | SQUEEZE thresholds | `FM<10/RM>55` / PDF `FM<30/RM>50` | Gap +0.411% vs −0.57%; but see §5.1 and §5.2 |

**Plus two not on that list, raised by this analysis:**
- **D-7 — `min_confirmed`.** Test 22 shows the production value was never backtested on 6-gate logic; Test 10 (C-5) shows vote count materially improves hit rate. Keep 2, tighten to 3, or demote Layer 2 to sizing-only?
- **D-8 — agree the re-run list.** Nothing in `STALE_BACKTESTS_AFTER_CNN_HY_FIXES.md` steps 2–4 starts until the list is agreed. §5.4 proposes two amendments to it first.

---

*Compiled 2026-08-17. Regenerate values: `.venv/bin/python scripts/export_ssi_validation_csvs.py`. Re-run experiments: `.venv/bin/python scripts/run_ssi_validation_suite.py` (30–90 min, needs `set -a && source .env`), `scripts/run_test15_sbi_parallel.sh` (needs C++-enabled MindWealth).*
