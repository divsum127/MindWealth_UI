# SSI Experiment Results — Compiled Analysis

> **Corrected 2026-08-17.** This file previously cited `*_20260807` artifacts while quoting `*_20260804` numbers. Seven headline figures were wrong and are fixed inline below (marked **[corrected 08-17]**). Read [`SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md`](SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md) first — it carries the corrections table, the PAR-relative scoring rule and the freshness ledger. Per-value CSVs: `macro_intelligence/analysis/ssi_validation/csv/`.

**Spec:** [`SSI_OpenQuestions_DivyanshuTestList (1).pdf`](SSI_OpenQuestions_DivyanshuTestList%20(1).pdf)  
**Status tracker:** [`SSI_OPEN_QUESTIONS_STATUS.md`](SSI_OPEN_QUESTIONS_STATUS.md)  
**Benchmark:** SPX (`^GSPC`) forward returns unless noted  
**Artifact directory:** [`macro_intelligence/analysis/ssi_validation/`](../../macro_intelligence/analysis/ssi_validation/)

---

## Cross-cutting analysis

### 1. Asymmetric long vs short gates

Longs work at the **bottom quintile** of 5-year SSI (pctile ≤20: n=419, 3m +3.14%, 78% win). Symmetric level gates fail: **+0.6 short fires 884 times with only 36% 3m SPX-down**. Actionable short context requires **≥95th percentile** (n=326, 3m −0.78%, 51% short win). Production CONFIG correctly uses pctile 20 long / 85 short caution.

### 2. CFTC patterns are context flags, not sizing gates — and most fail to beat PAR **[corrected 08-17]**

Judge every cell against the **PAR row** (all weeks, no filter): 12w mean **+2.30%**, hit **71.6%**, excess-hit **59.55%**, n=1,033 weeks.

**SQUEEZE** best cell on the current ranking metric (mean−median gap) is **FM&lt;10/RM&gt;55** — n_ep **21**, 12w **+3.44%**, gap **+0.411%**, excess-hit **65.0%**. Clears PAR. The previously-quoted `FM<20/RM>45` ("12w +3.32%, Sharpe 1.18, n=125") is actually n_ep **37**, 12w **+1.34%**, Sharpe **0.42**, gap **−1.96%** — **below PAR**; the old n counted overlapping weeks, and Sharpe rewarded market beta. **LIQUIDITY EXIT** `RM<30/FM>60` is n_ep **40**, 4w SPX-down **32.5%**, 12w **+2.48%**, excess-hit **45.0%** — also below PAR. Wire to Layer 3 display / Runic warnings only, and see §5.2 of the analysis doc: **no cell is statistically distinguishable from null**.

### 3. Layer 2 confirmation **[corrected 08-17]**

**`min_confirmed: 2` is not established.** Test 22 (window **2015-01-01→2026**, 3,872 trading days — not 2010) gives production defaults (z≥0.5, min=2) **160** long-gate+confirmed days at **41.25%** 3m hit and **−1.20%** 3m mean, firing on 50.2% of days. Test 10 shows vote count is a live parameter, not a no-op: n = 419/413/**314**/**231**/**78** for min_votes 0→4, with 3m win rising 78.0% → 89.8% → 93.5% → **96.2%**. Z-score overlay at **≥1.25** gives 3m hit 90.5% (n=105) vs 79.3% at z=0.

### 4. Composite scoring method

**3-year percentile composite** registers crisis windows the z-score path under-samples **[corrected 08-17]**: COVID 2020 — percentile **71 days** vs **46** for z-score, 6m **+23.96%** at 100% win. Strong case for deployment pending Rohit sign-off; not yet in `ssi_score.py`.

### 5. Data quality

83-day SSI history bug fixed (now 5,023 rows from 2010). CNN F&G backfilled Aug 2026 (wayback + real API). McClellan extended to 2014 Aug 2026. Residual gaps: CNN 2011-01→2012-05-24 (~16 months, no free source).

### 6. Production gaps awaiting sign-off

TP/SL (5×/20×), percentile SSI composite, COT FM&lt;20 for long-entry condition 3, SQUEEZE display thresholds.

---

## Test results (1–22)

### Test 1–2 — SSI long/short threshold sweep

- **Question:** Do PDF default gates (−0.6 long, +0.6 short) work? What inflection points exist?
- **Method:** Level sweep −0.3→−0.9 and +0.4→+0.9; percentile sweep; 2010→2026-06-06.
- **Artifact:** `01_02_threshold_sweep_20260606.json`
- **Headline numbers:**
  - Long pctile ≤20: **n=419**, 3m **+3.14%**, win **78.0%**
  - Long level ≤−0.6: n=303, 3m +6.31%, Sharpe 2.84
  - Short ≥+0.6: n=884, 3m +2.78%, short win **35.6%** — reject
  - Short ≥95 pctile: n=326, 3m **−0.78%**, short win 51.2%
- **Analysis:** Percentile long gate is primary; level −0.6 is valid secondary. Short asymmetry confirmed — +0.6 is not a short trigger. ≥95 pctile is only level with negative avg 3m SPX.

---

### Test 3 — CFTC SQUEEZE grid

- **Question:** Are FM&lt;30/RM&gt;50 round numbers optimal?
- **Method:** Grid FM 15–40 × RM 40–65; 4w/8w/12w SPX returns; 2006→2026-07-28 COT.
- **Artifact:** `03_squeeze_grid_v2_20260811.json` **[corrected 08-17 — was citing `_20260807` and quoting `_20260804` numbers]**
- **Headline numbers:** ranking is **mean−median gap**, not Sharpe. Best cell **FM&lt;10/RM&gt;55** — n_ep **21**, 12w mean **+3.44%**, gap **+0.411%**, excess-hit **65.0%**. PDF default FM&lt;30/RM&gt;50: n_ep **43**, 12w **+2.76%**, gap **−0.57%**, excess-hit 62.8%. Old pick FM&lt;20/RM&gt;45: n_ep **37**, 12w **+1.34%**, Sharpe **0.42**, gap **−1.96%**, excess-hit 58.3%.
- **Analysis:** the previous recommendation does not survive. Against PAR (12w +2.30%, excess-hit 59.55%), `FM<20/RM>45` is **worse than doing nothing** — its old "n=125, Sharpe 1.18" came from counting overlapping weeks and ranking on Sharpe, which rewards market beta. `FM<10/RM>55` clears PAR but rests on 21 episodes, **14 of them 2023 or later and none before 2010**. Sign-off on this pattern is **HELD** (2026-08-07), and the display flags are already wired on dev at the held values.

---

### Test 4 — CFTC LIQUIDITY EXIT grid

- **Question:** Does RM low + FM high predict SPX drawdowns?
- **Method:** Grid RM 15–40 × FM 45–75; includes median drawdown.
- **Artifact:** `04_liquidity_exit_grid_v2_20260811.json` **[corrected 08-17]**
- **Headline numbers:** PDF default RM&lt;30/FM&gt;60: n_ep **40** (n_wk 162), 4w SPX-down **32.5%**, 4w gap −0.67%, 12w avg **+2.48%**, 12w excess-hit **45.0%**.
- **Analysis:** Modest stress flag — SPX still rises in ~67% of 4w episodes, and 12w excess-hit of 45.0% is **well below PAR's 59.55%**. Use for macro warnings, not automated shorts. Sign-off **HELD**.

---

### Test 5 — TP/SL optimization

- **Question:** Is legacy TP×10/SL×15 optimal for PulseGauge?
- **Method:** Grid TP 5–20×, SL 8–25× daily vol; SPY long entries.
- **Artifact:** `05_tp_sl_20260606.json`
- **Headline numbers:** Best **TP×5/SL×20**: n=430, Sharpe **4.06**, win **97.7%**, avg +4.80%. Legacy TP×10/SL×15: Sharpe 0.91.
- **Analysis:** Take profit sooner, stop wider. Large Sharpe improvement — recommend CONFIG change after Rohit approval.

---

### Test 6 — CNN Fear & Greed

- **Question:** Do fear&lt;20 and greed&gt;80 thresholds work for this system?
- **Method:** SPX returns after threshold crossings; CNN history with wayback backfill.
- **Artifact:** `06_cnn_fear_greed_20260812.json` — **but this run is byte-identical to `_20260807` across all four rules, so it never ingested the wayback backfill.** Test 21 independently sees `cnn_fg` with `n_obs_total=670` against 4,327 for AAII. Treat as **STALE — must re-run**.
- **Headline numbers:**
  - Fear&lt;20: n=**121**, 3m +4.73%, win 71.7%
  - Fear&lt;10: n=58, 3m +8.15%, win 87.9%
  - Greed&gt;80: n=65, 3m +0.99%, win 69.2% (momentum, not fade)
  - Greed&gt;90: n=25, 3m −2.46%
- **Analysis:** Extreme fear supports long context. Greed thresholds do not work as short triggers — momentum continuation dominates. Production Layer 2 uses 25/75 (conservative). Residual 2011–2012 CNN gap disclosed.

---

### Test 7 — DBMF beta threshold

- **Question:** Does β&lt;−0.10 predict SPX weakness?
- **Method:** 21-day rolling beta vs SPY; OLS regression; Granger causality.
- **Artifact:** `07_dbmf_beta_20260606.json`
- **Headline numbers:** β&lt;−0.10: n=29, 4w SPX **+1.33%**, win 65.5%. OLS 4w R²=0.004, p=0.007. Granger: not predictive (p&gt;0.55).
- **Analysis:** Negative beta coincides with positive SPX drift — contrarian long context. Production Layer 2 uses 0.5/1.2 bands (different scale).

---

### Test 8 — HYG/LQD widening

- **Question:** Do −1.5%/−3.0% 4-week cuts predict stress? Does ratio change lead SPX?
- **Method:** Threshold crossings; lead time to VIX&gt;25; Granger lags 1–8 weeks.
- **Artifact:** `08_hyg_lqd_20260807.json`
- **Headline numbers:**
  - −1.5%: n=116, median **2 days** to VIX&gt;25
  - −3.0%: n=53, median **0 days**
  - Granger (4wk chg → SPX ret): lag-1 **p=0.006**, lag-4 p=0.075
- **Analysis:** PDF stress bands validated for VIX lead time. Granger shows weak short-horizon predictive signal at lag-1. Layer 2 uses ratio percentiles, not 4wk % cuts.

---

### Test 9 — Z-score vs percentile SSI

- **Question:** Should composite switch from z-score to 3yr percentile?
- **Method:** Parallel scoring paths; crisis window comparison (2020, 2022).
- **Artifact:** `09_zscore_vs_percentile_20260606.json` **[corrected 08-17]**
- **Headline numbers:** COVID Feb–Apr 2020: z-path **46** events; percentile **71 days**, 6m **+23.96%**, **100%** win. Oct 2022: z-path **122**; percentile **47 days**, 6m **+8.70%**, 97.9% win.
- **Analysis:** Percentile clearly superior in crises. Production still uses z-score — deployment is sign-off decision, not more experimentation.

---

### Test 10 — Layer 2 vote sweep

- **Question:** Does raising min_votes improve long quality?
- **Method:** Sweep min_confirmed 0–4 on long-gate days.
- **Artifact:** `10_layer2_sweep_20260606.json` **[corrected 08-17 — the previous claim was contradicted by this same artifact]**
- **Headline numbers:** n by min_votes: 0→**419**, 1→**413**, 2→**314**, 3→**231**, 4→**78**. 3m win: **78.0% → 78.5% → 89.8% → 93.5% → 96.2%**. (Previously recorded as "0–3 identical, min_votes=4 → 0 days" — neither is true.)
- **Analysis:** vote count **monotonically improves hit rate** all the way to 4. That does not make 4 correct — n collapses to 78 — but it means `min_confirmed` is a genuine tuning parameter, the same one Test 22 finds unproven at its production value. Raised as decision **D-7**.

---

### Test 11 — VIX regime multiplier

- **Question:** Does VIX&gt;35 size cut hurt crisis bottoms (Oct 2022)?
- **Method:** Oct 2022 spot check; full 2006–2026 equity curve.
- **Artifact:** `11_vix_regime_ab_20260606.json`
- **Headline numbers:** Oct 13 2022: `combo_b=true`, `vix_bypass=true`, multiplier **1.2**.
- **Analysis:** Bypass wiring correct. Full 20yr backtest waived (WAIVER-VT-11). Economic magnitude unquantified.

---

### Test 12 — Bollinger + SSI combo

- **Question:** Does BB lower touch + SSI pctile≤20 improve long entries?
- **Method:** BB(20,2) lower touch intersect SSI long gate.
- **Artifact:** `12_bollinger_ssi_20260606.json`
- **Headline numbers:** BB-only n=115, 3m +5.05%, win 80.4%. Combo n=**1**.
- **Analysis:** Overlay is extremely rare — insufficient sample to validate or reject. Advisory only unless Rohit requires product feature.

---

### Test 13 — Stochastic + McClellan

- **Question:** Does stoch&lt;20 turning up + McClellan positive beat either alone?
- **Method:** SPX stochastic cross + McClellan z&gt;0; horizons 1w/2w/4w.
- **Artifact:** `13_stoch_mcclellan_20260807.json`
- **Headline numbers:** Stoch-only n=179; McClellan-only n=291; combo n=**13**. Combo 2w: +0.45%, win 61.5%.
- **Analysis:** Re-run with McClellan backfill to 2014 improved n from 3→13. Still research-only; not a production gate.

---

### Test 14 — Gross/net divergence

- **Question:** Is the 3-condition gross/net rule reliably bearish?
- **Method:** Gross&gt;75th pctile 3yr for 3+ weeks + net falling + HYG/LQD 4wk&lt;−1%.
- **Artifact:** `14_gross_net_20260606.json`
- **Headline numbers:** n=25; 4w SPX-down **24%**; 12w avg +2.44%.
- **Analysis:** Flags stress clusters but SPX rises in ~76% of episodes. Warning text only, not short gate.

---

### Test 15 — SBI short signal

- **Question:** Is SBI short &gt;90th pctile useful confirmation?
- **Method:** MindWealth `calculate_trade_arrival_stats_for_breadth` (COMBINED_STRATEGY) monthly BMS 2015-01-01 → 2026-08-03 (140 months, 4 parallel shards).
- **Artifact:** `15_sbi_short_20260812.json`
- **Headline numbers:** **n=0** short-entry months at trigger ≤10th percentile-from-top.
- **Analysis:** **[corrected 08-17]** Batch infrastructure complete (adapter fixes, kaleido suppression, checkpointing). The previously-recorded cause — "MindWealth `cpp_functions` lacks `backtest_bb`/`is_pivot`" — is **wrong**: `/home/ubuntu/MindWealth/cpp_functions.cpython-310-*.so` exists and exports both. The real cause is an **interpreter mismatch** — `scripts/run_test15_sbi_parallel.sh` runs `${MW}/.venv/bin/python` (**3.12**), which skips the 3.10-ABI `.so` and silently imports the empty `cpp_functions/` directory as a namespace package. No ImportError, so COMBINED_STRATEGY returns 0 trades every symbol-month and short percentile-from-top never leaves 100%. **Not a valid empirical conclusion**, but **no C++ rebuild is needed** — re-run under `/home/ubuntu/MindWealth/venv/bin/python` (3.10.19). Fix first: `scripts/mindwealth_adapters/sbi_breadth.py` never calls `data.initialize_data()`, so `load_stake()` raises `NameError: name 'df_stake' is not defined` and the **DELTADRIFT** leg returns L0/S0 for all 500 symbols.

---

### Test 16 — Friday pull checklist

- **Question:** Can all ~18 macro variables be pulled automatically?
- **Method:** Operational health check of Friday jobs.
- **Artifact:** `16_friday_pull_20260817.json` **[corrected 08-17]**
- **Headline numbers:** **11 PASS, 1 WARN** of 12 checks — not 12/12. The warning is **CPI surprise** (`cpi_pull`, Trading Economics primary). PASS: NFCI, HY OAS, VIX/VIX3M, WTI/CNH/GSR, CFTC FM/RM, Curve/WALCL/CAPE, HYG/LQD, DBMF beta, CNN F&G, AAII, NAAIM.
- **Analysis:** Friday automation effectively complete, with one fragile source. Ongoing monitoring via daily job runs.

---

### Test 17 — TrendPulse deterioration

- **Question:** Which weekly |ΔSSI| threshold predicts negative returns?
- **Method:** Sweep p60/p70/p80 of weekly |ΔSSI|; 2+ week episodes.
- **Artifact:** `17_trendpulse_20260606.json`
- **Headline numbers:** p60: n=11 episodes, 3m +7.87%, win 90.9%, Sharpe 1.82.
- **Analysis:** Small sample (11 episodes). Episodes coincide with recoveries, not tops — TrendPulse needs product scoping before threshold finalization.

---

### Test 18 — COT FM long gate sweep

- **Question:** Is FM&lt;30 optimal for long-entry condition 3?
- **Method:** Sweep FM percentile max 15–45; SPX forward returns.
- **Artifact:** `18_cot_fm_long_gate_20260807.json`
- **Headline numbers:** FM&lt;20: n=203, 3m **+3.13%**, win **73.7%**, 6m +8.35%. FM&lt;30 (PDF): n=274, 3m +2.78%.
- **Analysis:** Tighter FM&lt;20–25 improves per-event returns with fewer fires. Recommend over PDF &lt;30 pending Rohit sign-off.

---

### Test 19 — VIX≥35 + FM distribution

- **Question:** How common is FM&lt;15 washout when VIX≥35?
- **Method:** Distribution of FM percentile on all VIX≥35 days.
- **Artifact:** `19_vix_fm_washout_20260607.json`
- **Headline numbers:** n=93 VIX≥35 episodes; FM median **54.5**; only **18.3%** below 15th pctile. FM 0–15 bin: n=17, 3m +8.25%, 94% SPX up.
- **Analysis:** FM washout is minority state at VIX≥35. FM&lt;15 episodes are contrarian longs, not shorts. Consider relaxing override to FM&lt;20.

---

### Test 20 — Layer 2 z-score sweep

- **Question:** What z threshold improves hit rate vs false positives?
- **Method:** Sweep z 0→2.0 in 0.25 steps on long-gate + confirmed days.
- **Artifact:** `20_layer2_zscore_sweep_20260607.json`
- **Headline numbers:** z≥1.25: n=105, 3m hit **90.5%**. z=0: n=396, hit 79.3%.
- **Analysis:** Clear inflection at z≥1.25–1.5. Optional overlay on vote-count architecture; not required for launch.

---

### Test 21 — Staleness decay (beyond PDF)

- **Question:** Should forward-filled signals be penalized by post-print age?
- **Method:** R² and hit rate by signal age 1–5 days post-print.
- **Artifact:** `21_staleness_decay_20260812.json`
- **Headline numbers:** AAII/NAAIM: no penalty warranted. COT: supports per-signal decay. Caps 8/3/30 applied in CONFIG.
- **Analysis:** Validated staleness policy in production CONFIG. Weekly series tolerate 6–10 day gaps.

---

### Test 22 — Layer 2 gate 2-D grid

- **Question:** How do `gate_z_min` and `min_confirmed` interact on 6-gate Layer 2?
- **Method:** Joint sweep z∈{0,0.25,…,1.0} × min_confirmed∈{1,2,3,4}; **2015-01-01→2026**, 3,872 trading days, long_entry_pctile 20.
- **Artifact:** `22_layer2_gate_grid_20260811.json` **[corrected 08-17]**
- **Headline numbers:** Production (z≥0.5, min=2): n=**160** long+gate, 3m hit **41.25%**, 3m mean **−1.20%**, Sharpe −0.34, fires on **50.2%** of days. Comparisons: z=0/min=3 → n=183, hit 36.6%; z=0.25/min=3 → n=145, hit 38.6%; z=1.0/min=2 → n=109, hit 38.5%. Worst corner z=0/min=1 → n=11, 3m −3.68%, 6m win 0%.
- **Analysis:** **Neither production default is empirically supported.** `min_confirmed: 2` was design intent and had never been backtested on the 6-gate logic; at the production cell the 3m mean is *negative*. Window is five years shorter than previously recorded — 2010–2014 is absent entirely. Decision **D-7**: keep 2, tighten to 3, or demote Layer 2 to sizing-only.

---

## PDF sub-experiments A–F

| ID | Sub-experiment | Status | Result |
|----|---------------|--------|--------|
| A | COT FM long gate 15–45 | **DONE** (Test 18) | FM&lt;20 optimal |
| B | VIX≥35 FM distribution | **DONE** (Test 19) | FM washout rare (18%) |
| C | Layer 2 z-score 0→2.0 | **DONE** (Test 20) | Inflection z≥1.25 |
| D | HYG/LQD Granger | **DONE** (Test 8, Aug 2026) | Lag-1 p=0.006 |
| E | VIX excluded from Layer 2 | **PRODUCT** | Not implemented |
| F | NFCI in SSI | **WAIVED** | WAIVER-NFCI-SSI |

---

*Compiled 2026-08-12; seven figures corrected 2026-08-17 (Tests 3, 4, 9, 10, 15, 16, 22) — see [`SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md`](SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md) §4 for the full corrections table. Per-value CSVs: `.venv/bin/python scripts/export_ssi_validation_csvs.py`.*
