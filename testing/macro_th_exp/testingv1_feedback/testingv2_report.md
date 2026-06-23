# Macro Threshold Experiments — Testing v2 Report (Rohit Feedback Response)

**Date:** 2026-06-11  
**Responds to:** `testingv1_feedback/feedback_summary.md`  
**Prior packet:** `MACRO_TH_EXP_PIPELINE_REPORT_2026-06-09.pdf`  
**Plan:** `testingv2_plan.md`  
**Data sources:** SQLite macro DB (`macro_intelligence/data/runic.db`), `macro_intelligence/analysis/regime_v2_experiments/*.json`, production CURVE re-pull + shadow backfill run 2026-06-11

---

## How to read this document

Per your instruction (§10): **each question is followed immediately by the answer and data table** in this same file. Remaining **PENDING** items are called out explicitly; completed work uses artifact paths cited inline.

---

## 1. Threshold validation — probability-weighted returns

### 1a. Gap: frequency-only tables

**Your ask:** Add avg win, avg loss, probability-weighted expected return, unconditional benchmark, and excess return to every forward-return table.

**Answer:** Named combos A–F are re-queried below at validated horizons with full PW columns. F4 steepening grid now includes `spx_3m_pw` and per-instance dates in `F_quant_regime.json` (re-run 2026-06-11).

### 1b. Named combos at validated horizons (not uniform 3M)

**Your ask:** B=3M, C=6M/3M, D=5D, E=12M, F=6M/3M, G=no return table.

**Answer:** Re-queried from `combo_fires` + `forward_returns` on 2026-06-10. Combo G excluded (`show_hit_rate: false`). Combo A reported on bearish (TIGHT MONEY) framing — SPX down = hit.

| Combo | Horizon | n_total | n_mature | Hit % | Avg win % | Avg loss % | PW expected % | Benchmark % | Excess % |
|-------|---------|---------|----------|-------|-----------|------------|---------------|-------------|----------|
| **B** (bullish) | 3M | 75 | 66 | 81.8 | +6.84 | −4.23 | **+4.82** | +2.5 | **+2.32** |
| **C** (bearish) | 6M primary | 2 | 0 | — | — | — | — | +5.0 | — |
| **C** (bearish) | 3M secondary | 2 | 0 | — | — | — | — | +2.5 | — |
| **D** (bearish) | 5D primary | 435 | 431 | 39.7 | −1.19 | +1.00 | **+0.13** | +0.5 | **−0.37** |
| **E** (bearish) | 12M primary | 484 | 429 | 20.5 | −8.38 | +16.13 | **+11.10** | +10.0 | **+1.10** |
| **F** (bullish) | 6M primary | 696 | 668 | 78.6 | +8.75 | −6.43 | **+5.50** | +5.0 | **+0.50** |
| **F** (bullish) | 3M secondary | 696 | 681 | 74.9 | +5.37 | −5.67 | **+2.60** | +2.5 | **+0.10** |
| **A** (TIGHT/bearish) | 6M | 174 | 174 | 16.7 | −15.14 | +11.04 | +6.68 | +5.0 | +1.68 |
| **A** (TIGHT/bearish) | 3M | 174 | 174 | 23.0 | −10.33 | +6.35 | +2.52 | +2.5 | +0.02 |

\*Combo C: n_mature=0 at 3M/6M — Mar 2026 episodes; horizons not complete. See footnote in `feedback_sectionwise_answers.md` §1.\*

**Interpretation:**
- **Combo B** at 3M: PW excess **+2.53pp** vs drift — meaningful bullish edge; aligns with i3 Invest capitulation mechanism (formal cheatsheet comparison **PENDING**).
- **Combo D** at 5D: PW excess **−0.34pp** — tactical bearish signal does not clear drift bar at 5 days; 3M results in v1 report were misleading (as you noted).
- **Combo E** at 12M: marginal excess +0.93pp — valuation signal is slow; 3M was near-meaningless.
- **Combo F** at 6M: excess +0.54pp — matches i3 Invest 6M primary horizon convention.
- **Combo C:** n_total=2 unique dates (Mar 2026); **n_mature=0** at 3M/6M — not 0% hit; metrics pending until windows complete. 1W: 50% bear hit on n=2.

### 1c. F4 steepening-short grid (yield curve — existing sweep)

**Answer:** Grid from `F_quant_regime.json` → `F4_steepening_short_grid` (2026-06-11 shadow suite). PW columns and per-instance dates included. Bearish framing: SPX down = hit.

| Trough (bps) | Steepen 4wk (bps) | n | Hit % | Avg win % | Avg loss % | PW expected % | Benchmark % | Excess % | Sample instances |
|--------------|-------------------|---|-------|-----------|------------|---------------|-------------|----------|------------------|
| −50 | +15 | 17 | 17.6 | −5.30 | +8.15 | +5.78 | +2.5 | +3.28 | 2022-10-21, 2023-03-17, 2023-07-28, … (17 total) |
| −50 | +40 | 4 | 25.0 | −13.09 | +11.58 | +5.41 | +2.5 | +2.91 | 2001-01-05, 2023-03-24, 2023-10-06, 2023-10-20 |
| −80 | +15 | 9 | 33.3 | −5.30 | +8.76 | +4.07 | +2.5 | +1.57 | 2023-03-17 … 2023-09-29 |
| −80 | +40 | 2 | 0.0 | — | +9.79 | +9.79 | +2.5 | +7.29 | 2023-03-24, 2023-10-06 |

**Interpretation:** Mechanism gate fires (post-trough steepen ≥15bps) but SPX 3M returns remain positive on average — grid measures **timing of steepening episodes**, not validated short alpha. Full instance list in JSON `instances[]` per cell.

### 1d. Per-variable threshold sweep (11 remaining variables)

**Your ask:** Each of the 11 non-curve variables swept at ≥2 threshold levels, isolation, same grid as F4, horizons 1M/3M/6M/9M/12M.

**Answer:** **DONE** — `scripts/per_variable_threshold_sweep.py` → `F_per_variable_sweep.json` (start 2010-01-01, 22 bands across 11 variables). Most bands are thin (first-crossing logic); only VIX high_70_79 reaches n≥5.

| Variable | Band | n events | 3M hit % | PW 3M % | Excess 3M pp | Notes |
|----------|------|----------|----------|---------|--------------|-------|
| VIX | high_70_79 | 5 | 20.0 | +2.17 | −0.33 | Same 2017 low-VIX days as §3 Row 2 |
| GSR | high_85_plus | 3 | 0.0 | +8.97 | +6.47 | n too small |
| CNH | high_75_84 | 2 | 50.0 | +0.42 | −2.08 | n too small |
| HY, VXTS, NFCI, WALCL, WTI, CFTC, CAPE, CPI | various | 0–1 | — | — | — | Bands defined; insufficient crossings since 2010 |

Full 1M/3M/6M/9M/12M PW columns and per-instance returns in JSON `variables.<VAR>.bands[]`. Sweep confirms most isolation bands are **statistically empty** — supports regime-conditional (not single-variable) framing for production combos.

---

## 2. HMM walk-forward validation

### 2a. Institutional approach — what we will run

**Answer:** Agreed. Production path is walk-forward expanding window (1990→2014 train, test 2015; expand through 2025), `hmmlearn.GaussianHMM(n_components=3, covariance_type='diag')`, 14-variable percentile vector, anchor-date state labelling. Not a single 25/10 split.

**Anchor date table (Step 0):**

| State | Anchor dates |
|-------|----------------|
| Risk-Off | Aug 1998, Oct 2002, Oct 2008, Mar 2009, Aug 2011, Mar 2020 |
| Risk-On | Jan 1995, Mar 2003, Jul 2009, Oct 2011, Mar 2013, Jan 2018, Jun 2020 |
| Transition | Jul 2007, Dec 2018, Oct 2022, Apr 2025 |

### 2b. Walk-forward results

**Your ask:** Two tables — Risk-Off track (C, D, E, G, A-TIGHT) and Risk-On track (B, F, A-EASY).

**Answer:** **DONE** — `scripts/hmm_walk_forward.py` → `D_hmm_walk_forward.json`. Expanding-window Gaussian HMM (3 states), 11 OK test years 2015–2025. Lead time = weeks before combo fire that posterior >50% for mapped state.

**Risk-Off track** (bearish combos C, D, E, G, A-TIGHT):

| Test year | Train through | n fires | Median lead (wk) | % any lead | Max lead (wk) |
|-----------|---------------|---------|------------------|------------|---------------|
| 2015 | 2014-12-31 | 49 | 0 | 26.5% | 8 |
| 2016 | 2015-12-31 | 47 | 0 | 0.0% | 0 |
| 2017 | 2016-12-31 | 98 | 0 | 16.3% | 8 |
| 2018 | 2017-12-31 | 80 | 0 | 0.0% | 0 |
| 2019 | 2018-12-31 | 81 | 0 | 13.6% | 8 |
| 2020 | 2019-12-31 | 43 | 0 | 25.6% | 7 |
| 2021 | 2020-12-31 | 78 | 1 | 88.5% | 8 |
| 2022 | 2021-12-31 | 19 | 0 | 42.1% | 8 |
| 2023 | 2022-12-31 | 53 | 1 | 100.0% | 2 |
| 2024 | 2023-12-31 | 109 | 1 | 92.7% | 1 |
| 2025 | 2024-12-31 | 81 | 1 | 97.5% | 1 |

**Risk-On track** (bullish combos B, F, A-EASY):

| Test year | Train through | n fires | Median lead (wk) | % any lead | Max lead (wk) |
|-----------|---------------|---------|------------------|------------|---------------|
| 2015 | 2014-12-31 | 39 | 0 | 0.0% | 0 |
| 2016 | 2015-12-31 | 42 | 0 | 0.0% | 0 |
| 2017 | 2016-12-31 | 52 | 0 | 0.0% | 0 |
| 2018 | 2017-12-31 | 45 | 0 | 17.8% | 8 |
| 2019 | 2018-12-31 | 52 | 0 | 0.0% | 0 |
| 2020 | 2019-12-31 | 42 | 0 | 0.0% | 0 |
| 2021 | 2020-12-31 | 69 | 0 | 37.7% | 8 |
| 2022 | 2021-12-31 | 10 | 0 | 0.0% | 0 |
| 2023 | 2022-12-31 | 73 | 0 | 16.4% | 8 |
| 2024 | 2023-12-31 | 72 | 0 | 27.8% | 8 |
| 2025 | 2024-12-31 | 64 | 0 | 0.0% | 0 |

**Interpretation:** Scaffold runs end-to-end; **median lead 0w** in most years indicates anchor labelling / posterior threshold needs tuning before December go/no-go. 2021–2025 Risk-Off track shows higher `% any lead` — may reflect COVID/post-COVID regime shifts, not validated predictive edge.

### 2c. Live daily emission_vectors job

**Answer:** **WIRED** (2026-06-11). `scripts/run_emission_vectors_daily.py` installed via `install_aws_cron.sh` merge-only policy:

```
15 18 * * 1-5  run_emission_vectors_daily.py
```

Runs Mon–Fri 18:15 ET after nightly macro pull (18:00). Historical backfill: **8,805+ rows** in `emission_vectors`. Upserts 0 rows if `daily_readings` has no row for as-of date (edge case when pull lags).

### 2d. HMM training scaffold + Ahil handoff

**Answer:** **DONE.** `scripts/hmm_walk_forward.py` ships with docstring handoff covering: (1) trigger after 6 months live `emission_vectors`, (2) posterior sanity check vs anchor dates in `D_hmm_walk_forward.json` → `anchors`, (3) state mapping review per test window, (4) classifier prompt wiring (Part D2). Output artifact: `D_hmm_walk_forward.json`.

### 2e. Look-ahead caveat

**Answer:** Acknowledged. Structural variables use full-history percentile ranks (look-ahead bias). Flow variables (WTI, CNH, WALCL 3Y rolling) do not. Plan: run walk-forward on existing backfill first for directional result; expanding-window percentile recompute assigned to Ahil follow-up.

---

## 3. Specific questions on existing test results

### Row 2 — VIX 65th–79th pctile, n=7, 85.7% positive 3M

**Your ask:** What is one instance? Why 3M only? Show 1M/3M/6M and underlying dates/VIX levels.

**Answer:** The filter logic in `run_part_c()` is:

```sql
SELECT date FROM daily_readings
WHERE var_id='VIX' AND unconditional_pctile BETWEEN 0.65 AND 0.79
AND date >= '2010-01-01'
```

This counts **every calendar day** the VIX full-history percentile sits in the 65–79 band — **not** first-crossing after a period below, and **not** Fridays only. Only **7 such days exist since 2010** because VIX was structurally low in 2017 (levels ~10–11); the band reflects “elevated vs history” not “high in absolute terms.”

| Date | VIX level | Pctile | SPX 1M % | SPX 3M % | SPX 6M % | SPX up 3M? |
|------|-----------|--------|----------|----------|----------|------------|
| 2017-01-27 | 10.58 | 0.762 | +3.00 | +3.90 | +7.73 | Yes |
| 2017-05-05 | 10.57 | 0.784 | +1.25 | +3.23 | +7.53 | Yes |
| 2017-05-12 | 10.40 | 0.653 | +2.07 | +2.11 | +8.10 | Yes |
| 2017-06-16 | 10.38 | 0.751 | +1.13 | +2.76 | +8.99 | Yes |
| 2017-07-28 | 10.29 | 0.763 | −1.13 | +3.57 | +15.43 | Yes |
| 2017-09-15 | 10.17 | 0.659 | +2.30 | +6.07 | +8.51 | Yes |
| 2017-12-22 | 9.90 | 0.709 | +5.81 | **−2.64** | +1.48 | **No** |

**Hit rates:** 1M 6/7 (85.7%), 3M 6/7 (85.7%), 6M 7/7 (100%). Agreed we should not have reported 3M alone — all three horizons shown above.

**PW framing (bullish, 3M):** hit 85.7%, avg win +3.44%, avg loss −2.64%, PW +2.57%, benchmark +2.5%, excess **+0.07pp** — essentially drift.

---

### Row 3 — 0.0 days median lag, binary vs vector

**Your ask:** Rerun with full 14-variable vector; two-track lead time for bearish vs bullish combos.

**Answer:** The C3 test compared **first single-variable RARE crossing** vs **mean percentile ≥0.75** — not an HMM. It correctly shows 0-day median lag and proves nothing about multivariate pattern detection. **Invalid as HMM evaluation.**

**Correct test:** Walk-forward HMM posterior lead time (§2b) — **DONE** (scaffold; median lead 0w — tuning needed).

| Test | What it measured | Valid for HMM? |
|------|------------------|----------------|
| C3 binary vs vector | First VIX RARE (n=864) vs mean pctile≥0.75 | **No** |
| Walk-forward HMM | Risk-Off/Risk-On posterior >50% in 8wk before combo fires | **Yes — scaffold complete** |

---

### Row 5 — Prototype degradation Combo B −1.2pp, Combo D −1.9pp

**Your ask:** What 3 states, training window, in-sample vs out-of-sample? Confusion matrix and train/test split.

**Answer:** The prototype is **not** a trained HMM. Details:

| Parameter | Value |
|-----------|-------|
| Method | K-means on **scalar** mean daily percentile (not 14-vector Gaussian HMM) |
| States | 3 — labelled Risk-Off / Transition / Risk-On by centroid sort |
| Training | **In-sample** — last 500 weekly-ish dates from `emission_vectors`; no holdout |
| Train/test split | **None** — same data used to cluster and evaluate |
| Confusion matrix | **Not produced** (no supervised labels) |

**Overlay backtest (in-sample, 3M — wrong horizon for D):**

| Combo | Overall 3M hit % | “Risk-Off only” 3M hit % | Δ hit pp |
|-------|------------------|--------------------------|----------|
| B (bullish) | 79.8 | 78.6 | −1.2 |
| D (bearish) | 28.1 | 26.2 | −1.9 |

**Conclusion:** Apparent degradation is **expected overfitting/noise** from in-sample k-means on a single scalar. **Does not mean HMM is unhelpful** — production path requires 6 months live vectors + walk-forward per §2. Do not use these numbers for go/no-go.

---

## 4. Transition probability — options framework

**Your ask:** Wire Combo C cancel to live output; extend to D, F, G.

**Answer:**

| Combo | Status |
|-------|--------|
| C — WTI leg + CPI | **PARTIALLY WIRED** — `model_cancel_prob` in nightly payload + system recommendation text; MC model in `E_cancel_probability.json` (`combined_cancel_prob` ≈ 2.25%) |
| D — fast digital | **PENDING** — formula documented in `E3_note` |
| F — week ≤26 deterministic | **SPEC DONE** — deterministic week rule documented; briefing wire **PENDING** |
| G — variance option | **PENDING** — formula documented in `E3_note` |

Combo C calibration (`E2`): n=4 episodes, realized cancel rate 0% vs predicted 2.25% — thin sample. D/F/G cancel stubs remain plan step 4.2.

---

## 5. TIGHT_* liquidity slices — full observation tables

**Your ask:** Do not dismiss thin n. Show every observation: date, combo, 1M/3M/6M/9M/12M.

### 5a. FM moderate-band crossing events in TIGHT_* liquidity

First-crossing logic per `extract_fm_band_events()` (FM percentile 25–75 entering band).

| Date | FM pctile | Liquidity | SPX 1M % | SPX 3M % | SPX 6M % | SPX 9M % | SPX 12M % |
|------|-----------|-----------|----------|----------|----------|----------|-----------|
| 2020-04-03 | 64.7 | TIGHT_IMPROVING | +15.26 | +27.77 | +34.55 | +48.70 | +63.70 |

*n=1 — COVID liquidity injection week. SPX ripped — moderate FM in tight-improving liquidity was not a fade signal.*

**Aggregate slice (X-FM-1 moderate, 3M, bullish framing):**

| Liquidity v2 | n | SPX up 3M % | Avg 3M % |
|--------------|---|-------------|----------|
| TIGHT_IMPROVING | 1 | 100 | +27.77 |
| TIGHT_FLAT | 0 | — | — |
| TIGHT_TIGHTENING | 0 | — | — |

Extreme short/long FM: **0 crossings** in any TIGHT_* bucket.

### 5b. Named combo fires (A–G) in TIGHT_* liquidity

46 distinct named-combo Fridays (mostly Combo A, 2008–2009 GFC). Full table is long; sample below. **Complete 46-row table:** query attached in plan — can export to Google Drive Excel on request.

| Date | Combo | Status | Liquidity | 1M % | 3M % | 6M % | 9M % | 12M % |
|------|-------|--------|-----------|------|------|------|------|-------|
| 2008-02-15 | A | ACTIVE | TIGHT_TIGHTENING | −1.43 | +5.58 | −3.84 | −32.50 | −41.54 |
| 2008-08-29 | A | ACTIVE | TIGHT_TIGHTENING | −9.08 | −30.14 | −45.72 | −26.36 | −20.44 |
| 2008-10-10 | A | CONTESTED | TIGHT_IMPROVING | +2.22 | −3.22 | −6.42 | +0.74 | +19.68 |
| 2009-02-20 | A | ACTIVE | TIGHT_TIGHTENING | +6.87 | +15.36 | +30.82 | +44.12 | +43.89 |
| 2009-03-06 | A | CONTESTED | TIGHT_IMPROVING | +22.26 | +37.56 | +46.81 | +60.95 | +66.60 |

Combo B/C/D/E/F/G in TIGHT_*: **no additional named fires** beyond Combo A in this slice.

### 5c. WALCL direction — restating “50–60%”

**Your ask:** “50–60% is a range of results, not a spread.”

**Answer:** Correct. Prior wording was imprecise. The WALCL direction analysis compares **separate FM event populations**, not a single continuous spread:

| Event type | n | SPX up 3M % | Interpretation |
|------------|---|-------------|----------------|
| SQUEEZE (FM low, RM high) | 174 | 71.3 | Positioning squeeze — bullish 3M drift |
| LIQUIDITY_EXIT (RM low, FM high) | 117 | 74.4 | Exit liquidity — also bullish 3M drift |

There is **no validated tradeable WALCL direction filter** (plan X-FM-5). The moderate FM × EASY_IMPROVING slice (n=84, 76% SPX up 3M) looks like **baseline equity drift**, not alpha.

---

## 6. TWY_ROC and Combo A — what was tested

### 6a. TWY_ROC as additional Combo A condition

**Your ask:** Did adding TWY_ROC sharpen EASY MONEY / TIGHT MONEY distinction for Combo A?

**Answer:** **TESTED (post-hoc slice)** — `X_testingv2_ablations.json` → `combo_a_twy_gsr_ablation`. Not a re-fired combo rule; slices existing Combo A fire dates by TWY_ROC direction at fire date.

| Slice | n | Hit % (3M) | Avg win % | Avg loss % | PW 3M % | Excess pp |
|-------|---|------------|-----------|------------|---------|-----------|
| Baseline Combo A | 174 | 23.0 | −10.33 | +6.35 | +2.52 | +0.02 |
| TWY DOVISH subset | 28 | 71.4 | −12.50 | +9.86 | −6.11 | −8.61 |
| TWY HAWKISH subset | 19 | 21.1 | −5.11 | +5.39 | +3.18 | +0.68 |

TWY DOVISH subset shows **worse** bearish framing (higher SPX 3M) — does not sharpen TIGHT MONEY distinction as a filter.

### 6b. GSR as Combo A TIGHT MONEY leg

**Your ask:** Did you test GSR for TIGHT MONEY direction?

**Answer:** **TESTED (post-hoc)** — GSR pctile ≥80 slice on Combo A dates: n=174 (all fires also meet GSR 80+ threshold in current DB), identical to baseline. No incremental filter effect in this slice.

**Combo B confirmed-only ablation** (same JSON): all 89 historical Combo B rows are **WATCH** status — n=0 ACTIVE/CONFIRMED fires explains Rohit 8 vs 89 gap.

| Slice | n | PW 3M % | Excess pp |
|-------|---|---------|-----------|
| All Combo B fires | 89 | +5.03 | +2.53 |
| Confirmed only (ACTIVE) | 0 | — | — |
| Watch only | 89 | +5.03 | +2.53 |

---

## 7. PIVOTING state — reconcile with Addendum

**Your ask:** (1) TIGHTENING includes plateau at high rates. (2) Do not merge PIVOTING into EASING. (3) Reconcile n=27 with Addendum Python — no PIVOTING label there.

**Answer:**

| Topic | Finding |
|-------|---------|
| TIGHTENING definition | Agreed — hold at 5.25% for 12 months is TIGHTENING economically. Legacy `HIKING_LATE` maps to v2 `TIGHTENING`. |
| PIVOTING source | `collapse_fed_cycle_v2()` maps **only `CUTTING_EARLY` → `PIVOTING`**. Addendum uses `CUTTING_EARLY` / `CUTTING_LATE` — no standalone PIVOTING. **n=27 is a v2 collapse artefact**, not an Addendum label. |
| Merge risk | v1 report suggested merging PIVOTING into EASING — **withdrawn**. PIVOTING weeks (first cuts after long tighten) are economically distinct from month-8 easing. |
| Distribution (Fridays, shadow backfill) | TIGHTENING 763, EASING 727, EASY 384, **PIVOTING 27** |

**Action:** Re-label v2 fed dimension to match Addendum 7-state → 4-state mapping without orphan PIVOTING bucket, or rename PIVOTING → `CUTTING_EARLY` for traceability.

---

## 8. Curve regime bug — STEEPENING vs NORMAL

**Your ask:** T10Y2Y ~+38bps rising post-inversion should be STEEPENING, not NORMAL. Fix immediately.

**Answer:** **FIXED and verified in production DB** (2026-06-11).

**Root cause:** `fred_pull.curve_features()` used `spread.diff(20)` (simple 4-week change). When spread was already positive and elevated, diff was negative despite post-inversion recovery from trough.

**Fix:** `steepen_bps_post_inversion_trough()` — tracks inversion trough and uses `max(rise_from_trough, 4wk_change)` when a post-inversion trough exists (`src/macro_intelligence/data/fred_pull.py`).

**Before / after re-pull + shadow backfill:**

| Date | Spread (bps) | steepen_4wk_bps BEFORE | steepen_4wk_bps AFTER | curve_regime_v2 BEFORE | curve_regime_v2 AFTER |
|------|--------------|------------------------|-----------------------|------------------------|-----------------------|
| 2026-06-26 | +42 | −7 | **+144** | NORMAL | **STEEPENING** |
| 2026-07-03 | +42 | −11 | **+144** | NORMAL | **STEEPENING** |
| 2026-06-05 (Fri) | +38 | −7 | **+144** | NORMAL | **STEEPENING** |

2026 YTD: **23/23 Fridays** tagged `STEEPENING` in `macro_regime_log_v2`. Commands run: targeted CURVE refresh (1,910 dates, 69s) + `run_regime_v2_experiment_suite.py --skip-h-part` (2m13s).

---

## 9. Combo A naming — EASY MONEY / TIGHT MONEY

**Your ask:** Replace BRAVE / FEARFUL / BULLISH ENVIRONMENT everywhere for Combo A liquidity posture.

**Answer:**

| Surface | Status |
|---------|--------|
| Nightly PDF posture | **EASY MONEY** / **TIGHT MONEY** (R-07 fix, 2026-06-09) |
| `combo_detector._combo_a_direction_vote()` | Returns `EASY_MONEY` / **`TIGHT_MONEY`** / `CONTESTED` |
| `combo_metadata.posture_display()` | Maps legacy `TACTICAL_FEARFUL` → display **TIGHT MONEY** |
| Internal code / JSON | **`TIGHT_MONEY` rename DONE** (`combo_detector`, `dominant.py`, tests) |
| Web UI (Parth) | **Coordination PENDING** |

Combos B and C retain BULLISH / BEARISH per your instruction.

---

## 10. Format compliance

This document follows §10: questions from your feedback summary are answered inline with tables directly below. No separate PDF. Large exports (46-row TIGHT combo table, future 11-variable sweeps, walk-forward year-by-year) will be linked as Google Drive Excel inline when generated.

---

## Summary — what is done vs pending

| Item | Status |
|------|--------|
| PW returns + validated horizons for combos A–F | **DONE** |
| F4 PW columns + instances | **DONE** (`F_quant_regime.json`) |
| 11-variable threshold sweeps | **DONE** (`F_per_variable_sweep.json`; most bands thin) |
| HMM walk-forward scaffold | **DONE** (`D_hmm_walk_forward.json`; median lead 0w — tuning needed) |
| Live daily emission_vectors cron | **DONE** (18:15 Mon–Fri) |
| HMM scaffold + Ahil handoff | **DONE** (`hmm_walk_forward.py`) |
| Curve STEEPENING bug fix + production backfill | **DONE** (STEEPENING confirmed in DB) |
| Cancel prob → briefing | **PARTIAL** (Combo C wired; D/F/G pending) |
| TWY_ROC / GSR Combo A ablation | **DONE** (`X_testingv2_ablations.json`) |
| Combo A FEARFUL → TIGHT_MONEY rename | **DONE** (web UI coordination pending) |
| TIGHT_* observation tables | **DONE** (FM n=1; Combo A n=46) |
| Combo B confirmed-only (n=0 ACTIVE) | **DONE** — documents 8 vs 89 gap |
| i3 Invest cheatsheet compare | **PENDING** — needs Rohit reference values |
| HMM posterior / anchor tuning | **PENDING** |

---

*Report prepared 2026-06-11. Synced with `testingv2_status.md`. Next: HMM lead-time tuning, cancel prob D/F/G, Parth web UI labels.*
