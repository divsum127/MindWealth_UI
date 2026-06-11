# Macro Intelligence Threshold & Regime Experiments — Forward Plan

**Date:** 2026-06-07  
**Companion:** [`MACRO_TH_EXP_STATUS_ANALYSIS.md`](MACRO_TH_EXP_STATUS_ANALYSIS.md)  
**Source:** [`Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`](../../macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf)

---

## 1. Current phase

```
[ DONE: Shadow experiments A–H + FM track (2026-06-06) ]
        ↓
[ NOW: Rohit review + gap fixes + production wiring decisions ]
        ↓
[ NEXT: Shadow → production swap (signed items only) ]
        ↓
[ LATER: 6mo live vectors → HMM production (est. ~Dec 2026+) ]
```

Experiments are **complete in analysis mode**. The plan below covers sign-off, fixes, wiring, and the deferred HMM track.

---

## 2. Immediate actions (before next Rohit sync)

### P0 — Prepare review packet for Rohit

| # | Action | Output | Effort |
|---|--------|--------|--------|
| 1 | Send FM/regime validation summary | §3 of `MACRO_TH_EXP_STATUS_ANALYSIS.md` | Done |
| 2 | Fix experiment report terminology | Clarify SPX down vs FM wrong in `MACRO_REGIME_V2_EXPERIMENT_REPORT.md` §2 | ~1 hr |
| 3 | Produce Combo B "confirmed only" slice | Re-run X-FM-2 filtering `status=ACTIVE` (3/3 legs), not WATCH rows | ~2 hr |
| 4 | Regime combo matrix one-pager | Table: each combo A–G × 5 v2 dimensions, min n≥5 cells only | ~3 hr |

**Questions for Rohit at sync:**

1. Approve shadow v2 fed_cycle 4-state collapse (PIVOTING n=27 — merge into EASING or drop)?
2. Confirm F4 steepening-short stays **mechanism+analog only** given grid win rates <35%?
3. Per-combo beta bar: default **55% or 60%** hostile-regime hit rate?
4. Approve TWY_ROC ±0.30pp bands for classifier prompt?
5. OK to start daily `emission_vectors` job (starts 6-month HMM clock)?

---

### P1 — CONFIG and data fixes (pre-production)

| # | Item | File(s) | Rationale |
|---|------|---------|-----------|
| 1 | B4 window audit | `macro_intelligence/CONFIG.yaml` | Align HY, VIX, VXTS → `rolling_3y`; WALCL → `full` per plan Part B |
| 2 | Fed PAUSING state | `fed_cycle.py`, shadow v2 | Job tracker T-01: legacy CUTTING_LATE wrong during pause/hike-risk |
| 3 | Re-run experiment suite after CONFIG fix | `run_regime_v2_experiment_suite.py` | Refresh B4 pass flag and percentile ranks |
| 4 | Part H re-tag with v2 regimes | `combo_discovery_pipeline.py` | Beta filter currently uses legacy regime JSON |

---

### P2 — Production wiring (post Rohit GO)

Sequencing matches plan §5 (B+C first, D last):

| Priority | Work item | Depends on |
|----------|-----------|------------|
| 1 | Add TWY_ROC to data pull (FRED DGS2, 56-day ROC) | Rohit GO on B |
| 2 | Dual percentile columns in `daily_readings` + fallback logging | CONFIG fix |
| 3 | Daily `emission_vectors` write in nightly job | Schema migrated |
| 4 | Swap production regime labels to v2 shadow rules | Rohit GO on A |
| 5 | Update classifier prompt Section 5.2 | A + TWY_ROC |
| 6 | Wire `combo_cancel_probability()` to briefing PDF/HTML | Rohit GO on E |
| 7 | Persistence framing: 7WK grind amplifier, VIX suppressed watch | Rohit GO on G |
| 8 | Monthly Part H combo discovery cron | `--use-claude` for story step at review |

**Do not wire until signed:** HMM posterior in prompt, production regime_rules.py replacement, new named combos from Part H.

---

## 3. Regime isolation — follow-up experiments

These extend Rohit's ask in `additional_details.md` beyond the 2026-06-06 run.

### Experiment R-1: Combo-conditional FM bands

**Hypothesis:** FM contrary signal appears only when Combo B/D leg sets align, not on raw percentile crossings.

| Step | Method |
|------|--------|
| 1 | Define "confirmed B" = all 3 legs at RARE+ on same Friday |
| 2 | Compare SPX 3m up rate: confirmed B vs FM<15 alone vs FM<15 + VIX≥25 |
| 3 | Slice each by fed_cycle_v2, curve_regime_v2, liquidity_v2 |
| 4 | Tag evidence: STATISTICAL if n≥5 per cell |

**Expected outcome:** Confirmed B recovers ~80%+ hit rate; raw FM band stays ~60%.

### Experiment R-2: Regime interaction matrix for D and F

**Hypothesis:** Combo D short edge exists only in CUTTING_LATE / STEEPENING; Combo F long edge boosted in QE + EASY liquidity.

| Step | Method |
|------|--------|
| 1 | Build 5×5 heatmap (fed_cycle × curve) for combos D and F |
| 2 | Require n≥10 per cell; report hit rate vs unconditional base rate |
| 3 | Feed results into briefing as regime-conditional hit rate footnotes |

### Experiment R-3: FM × RM divergence (X-FM-5 extension)

Already in manifest (`SQUEEZE_fm_low_rm_high` n=174, 71% SPX up 3m; `LIQUIDITY_EXIT_rm_low_fm_high` n=117, 74% up). **Extend** with full 5-dimension slices (currently fed_cycle buckets empty in JSON).

### Experiment R-4: Fiscal offset filter on F4

Re-run F4 grid excluding weeks where fiscal deficit >5% GDP **or** active QE. Tests plan hypothesis that 2022–23 steepening-short failed due to fiscal/AI capex offset.

---

## 4. SSI threshold track (parallel, not in regime PDF)

For completeness — tracked in `testing/ssi_th_exp/`:

| Status | Item |
|--------|------|
| Done | Tests 1–5, 7–13, 17 re-run with corrected data (2026-06-06/07) |
| Pending | Test 6 (wrong data), Test 12 (was zero events — breadth now extended to 2015), Test 15 (not run) |
| Pending | 4 PDF sub-experiments never run |
| Done | Short gate confirmed weak (26% SPX down at SSI≥0.85) |
| Done | CFTC squeeze validated as long signal (68% 4w win) |

**Next SSI actions:** Re-run Tests 12–13 with 2015+ breadth; run Test 15; close Test 6 data source issue.

No dependency on regime v2 production swap.

---

## 5. HMM deferred track

| Milestone | Target date | Trigger |
|-----------|-------------|---------|
| Start daily emission_vectors in production | After Rohit sign-off on C | Manual |
| 6 months clean live vectors | ~6mo after C wired | Automatic gate |
| Train production 3-state HMM | After vector gate | Part D |
| HSMM dwell-time (phase 2) | TBD | After HMM validated |

Prototype code: `src/macro_intelligence/analysis/regime_experiments/hmm_prototype.py`  
Backtest: `regime_backtest.py` — research only, no Sharpe improvement shown yet.

---

## 6. Success criteria for "experiments complete → production ready"

| Criterion | Measure |
|-----------|---------|
| Rohit written sign-off | Email/doc on A, B, C, E, F2, G |
| CONFIG B4 audit pass | `B4_window_audit.pass = true` in manifest |
| FM/regime questions answered | R-1 through R-3 run; added to this folder |
| Classifier prompt updated | Section 5.2 reflects 4-state fed, 3-state geo, TWY_ROC |
| Daily jobs wired | TWY_ROC pull, emission_vectors, cancel prob in briefing |
| Part H monthly cron | Scheduled; first `--use-claude` review with Rohit |
| Ahil F4 alignment | Written note on steepening-of-inversion vs F4 grid |
| No production regression | Nightly A–G audit passes after any swap |

---

## 7. Suggested timeline

| Week | Focus |
|------|-------|
| **W1 (now)** | Rohit review packet; CONFIG B4 fix; Combo B confirmed-only re-slice |
| **W2** | R-1, R-2 regime matrices; fix report terminology; Ahil F4 note |
| **W3** | Production wiring P2 items 1–3 if Rohit GO (TWY_ROC, dual pctile, emission job) |
| **W4** | Regime label swap + classifier prompt if A approved; cancel prob on dashboard |
| **Monthly** | Part H combo discovery re-run; promotion review with Rohit |
| **+6 months** | HMM production evaluation |

---

## 8. Commands reference

```bash
# Full experiment suite (~2 min)
.venv/bin/python scripts/run_regime_v2_experiment_suite.py

# Skip Part H combo discovery (faster)
.venv/bin/python scripts/run_regime_v2_experiment_suite.py --skip-h-part

# Combo discovery only
.venv/bin/python -m src.macro_intelligence.analysis.combo_discovery_pipeline

# Unit tests
.venv/bin/python -m pytest tests/test_regime_v2_experiments.py -q
```

---

## 9. Ownership

| Area | Primary | Reviewer |
|------|---------|----------|
| Regime v2 experiments & wiring | Divyanshu | Rohit |
| F4 steepening / curve defs | Divyanshu | Ahil |
| SSI threshold experiments | Divyanshu | Rohit |
| Production nightly / briefing | Divyanshu | Rohit |
| C++ JSON consumer | Ahil | Rohit |

---

*Plan v1 — 2026-06-07. Update after Rohit sync and CONFIG re-run.*
