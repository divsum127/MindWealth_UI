# B4 Window Fix Pipeline — Original Spec

**Date:** 2026-07-17

## Authoritative rule

This pipeline uses the **original B4 rule** from the consolidated plan / experiment suite — **not** Rohit's 2026-06-11 override.

| Class | Variables | `pctile_window` |
|-------|-----------|-----------------|
| Structural / level | CAPE, NFCI, **WALCL**, CURVE, DXY | `full` |
| Flow / ROC / pctile | **HY, VIX, VXTS**, CFTC, WTI, CNH, CPI, GSR | `rolling_3y` |

Rohit's June 11 note (HY/VIX/VXTS = full, WALCL MoM = rolling) was **explicitly rejected** for this run per task instruction.

## Step 1 — CONFIG applied

- HY → `rolling_3y`
- VIX → `rolling_3y`
- VXTS → `rolling_3y`
- WALCL → `full` (unchanged since 2026-06-09 fix)

## Step 2 — Percentile recompute

- Dates touched: **7802**
- Rows updated: **13476**
- Rows with pctile or tier change: **3428**

## Step 3 — B4 audit

- **pass:** `True`
- **mismatches:** 0

All 12 variables PASS.

## Step 4 — Combo B / D / G sweeps (post-fix panel)

- Sweep output dir: `/home/ubuntu/uiv2/git/MindWealth_UI/macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2_b4_fix`

### Combo B (bullish, 3M primary)

| Gate | n @ VIX≥25 | hit 3M |
|------|------------|--------|
| CONFIG (VIX≥25, HY≥400bps, CFTC≤15pct) | **7** | **100%** |
| VIX≥20 (same HY/CFTC) | 9 | 88.9% |

Artifact: `threshold_sweep_v2_b4_fix/COMBO_B_gate_sweep.json`

### Combo D (bearish)

| Gate set | n | bear hit 1W |
|----------|---|-------------|
| Legacy sweep 2-of-3 @ VXTS≥1.10/CFTC≥85/VIX≤18 | 89 | 33.7% |
| **Production score** VXTS≥1.18/CFTC≥95/VIX≤13, 2-of-3 | **46** | **56.5%** |

Artifacts: `COMBO_D_gate_sweep.json` + production gate replay (post-B4 fix, in `B4_window_fix_pipeline_2026-07-17.json` → `combo_d_production_gates`)

### Combo G (bearish, CONFIG baseline VXTS<1.0 / VIX≤20 / HY 4wk widen≥30bps)

| Metric | Value |
|--------|-------|
| CONFIG baseline n_events | **0** (first-crossing model; all three legs rarely align) |
| Nearest univariate (VXTS<1.05) | n=3, hit_mean 33.3% |

Artifact: `COMBO_G_gate_sweep.json` — CONFIG G gates may need recalibration or extended sweep after rolling_3y pctile shift.

## Step 5 — Part B JSON refreshed

- `B_twy_and_percentiles.json` B4 pass: **True**
- Dual percentile rows (both): **25083**

## Step 6 — D6 analytics re-slice

- Artifacts: `D6_regime_analytics_2026-07-17.*`

## Feedback backlog triage

### cheatsheet_compare
- **Status:** BLOCKED
- i3 Invest Combo Cheatsheet reference numbers not in repo; need Rohit to share values for diff column.

### liquidity_spx_tables
- **Status:** PARTIAL
- D6 reslice produces FM band + 9-state/4-state liquidity combo-fire tables at 1M–12M (FM) and 3M (combo fires). Full A5 band grid (every liquidity slice × 1m/3m/6m/9m/12m) in separate export if needed.
- Artifacts: D6_fm_regime_slices_analytics_2026-07-17.csv, D6_liquidity_9state_combo_fires_2026-07-17.csv, D6_liquidity_4state_analytics_combo_fires_2026-07-17.csv

### geo_2state_prod
- **Status:** PENDING
- D6 decision: 2-state NEUTRAL/ELEVATED approved in principle; production classifier still 3-state. Prompt + code switch deferred.

### regime_score_validation
- **Status:** PENDING
- Section D addendum tests (Spearman ρ, AND vs time-only, hit-rate weights, time-decay) not implemented as automated suite yet.
