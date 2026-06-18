# Threshold Validation v2 — Execution Status

**Plan:** `threshold_validation_plan.md`  
**Started:** 2026-06-16  
**Completed:** 2026-06-16  
**Report:** `threshold_validation_report.md` + `threshold_validation_report.pdf`

## Legend
| Symbol | Meaning |
|--------|---------|
| ✅ | Done and verified |
| 🔄 | Partial / in progress |
| ⏳ | Not started |
| ⚠️ | Blocked / needs decision |

---

## Phase 1 — Data foundation

| Step | Task | Status | Notes |
|------|------|--------|-------|
| P1.0 | Normalize mixed 0–1 / 0–100 pctiles in `daily_readings` | ✅ | 220 rows normalized to 0–100; 0 legacy rows remain |
| P1.1 | Fix 0–1 scale bug in `per_variable_threshold_sweep.py` | ✅ | Bands 70–100 scale; added CURVE; inline `_norm_pctile()` |
| P1.2 | Re-run corrected sweep → `F_per_variable_sweep_v2.json` | ✅ | 12 vars; VIX high_80_plus n=30 vs broken v1 (13/22 bands n=0) |
| P1.3 | Verify full-expanding window vars in CONFIG | ✅ | VIX, HY, VXTS, NFCI, CURVE, CAPE = `full`; ROC vars = `rolling_3y` |

**P1 run timestamp:** 2026-06-16 ~23s (migration + F sweep)

## Phase 2 — Build threshold_sweep_v2.py

| Step | Task | Status | Notes |
|------|------|--------|-------|
| P2.1 | Build `scripts/threshold_sweep_v2.py` | ✅ | First-crossing + 5d cooldown + PW + hostile slice + raw CONFIG bands |
| P2.2 | Run all 12 variables → 12 sweep JSONs | ✅ | All 12 `*_sweep.json` in `threshold_sweep_v2/` |
| P2.3 | Build `SUMMARY.json` | ✅ | Current vs best per variable; WTI change_justified=true |

**P2 run timestamp:** 2026-06-16 ~227s

## Phase 3 — Named combo gate sweeps (B, F, E, D)

| Step | Task | Status | Notes |
|------|------|--------|-------|
| P3.1 | Combo B gate sweep (VIX/HY/CFTC) at 3M | ✅ | Leg replay; 3-of-3 n=0 all variants; 2-of-3 n=12 PW excess +5.06% |
| P3.2 | Combo F SPX threshold sweep (1/2/3/5% above WMA) at 6M | ✅ | Current 3% best hit (85.7%); 5% highest excess (+3.50%) |
| P3.3 | Combo E gate sweep (CAPE/NFCI/CFTC) at 12M | ✅ | Current CAPE≥28 confirmed; CE_CAPE_28 n=22 |
| P3.4 | Combo D gate sweep (VXTS/CFTC/VIX) at 5D | ✅ | No gate clears hit≥60%; current gates as good as alternatives |

**P3 run timestamp:** 2026-06-16 ~20s

## Phase 4 — Report

| Step | Task | Status | Notes |
|------|------|--------|-------|
| P4.1 | Create `threshold_validation_report.md` with inline tables | ✅ | Expanded 2026-06-16: method/instruments/duration + appendix (all bands × 5 horizons); 1,679 lines |
| P4.2 | Flag threshold changes clearing all 4 success criteria | ✅ | WTI only (WTI_down_15pct vs WTI_up_6pct at 6M) |
| P4.3 | Export PDF | ✅ | `threshold_validation_report.pdf` (251 KB) |

---

## Output artifacts (all paths)

| Artifact | Path | Status |
|----------|------|--------|
| Pctile migration script | `scripts/normalize_pctile_scale.py` | ✅ |
| Corrected pctile sweep | `macro_intelligence/analysis/regime_v2_experiments/F_per_variable_sweep_v2.json` | ✅ |
| Main sweep script | `scripts/threshold_sweep_v2.py` | ✅ |
| Combo sweep script | `scripts/combo_gate_sweep_v2.py` | ✅ |
| Extended combo module | `src/macro_intelligence/analysis/combo_threshold_sweep.py` | ✅ |
| VIX sweep | `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/VIX_sweep.json` | ✅ |
| HY sweep | `.../HY_sweep.json` | ✅ |
| CFTC sweep | `.../CFTC_sweep.json` | ✅ |
| NFCI sweep | `.../NFCI_sweep.json` | ✅ |
| WALCL sweep | `.../WALCL_sweep.json` | ✅ |
| WTI sweep | `.../WTI_sweep.json` | ✅ |
| CNH sweep | `.../CNH_sweep.json` | ✅ |
| GSR sweep | `.../GSR_sweep.json` | ✅ |
| VXTS sweep | `.../VXTS_sweep.json` | ✅ |
| CAPE sweep | `.../CAPE_sweep.json` | ✅ |
| CPI sweep | `.../CPI_sweep.json` | ✅ |
| CURVE sweep | `.../CURVE_sweep.json` | ✅ |
| Summary | `.../SUMMARY.json` | ✅ |
| Combo B | `.../COMBO_B_gate_sweep.json` | ✅ |
| Combo F | `.../COMBO_F_spx_sweep.json` | ✅ |
| Combo E | `.../COMBO_E_cape_sweep.json` | ✅ |
| Combo D | `.../COMBO_D_gate_sweep.json` | ✅ |
| Report MD | `testing/macro_th_exp/testingv2/threshold_validation_report.md` | ✅ |
| Report PDF | `testing/macro_th_exp/testingv2/threshold_validation_report.pdf` | ✅ |
| Section 4a raw returns CSV | `testing/macro_th_exp/testingv2/section_4a_rare_threshold_raw_returns.csv` | ✅ |
| Section 4b raw returns CSV | `testing/macro_th_exp/testingv2/section_4b_extreme_threshold_raw_returns.csv` | ✅ |

---

## Key findings snapshot

| Finding | Detail |
|---------|--------|
| Scale bug fixed | 220 legacy pctile rows normalized; per-variable sweep now populates all bands |
| WTI threshold change justified | WTI_down_15pct: n=30, hit=73.3%, PW excess +0.16% at 6M vs current −1.99% |
| Combo B 3-of-3 never fires | n=0 for all strict gate variants; 2-of-3 WATCH has n=12, +5.06% PW excess |
| Most CONFIG thresholds confirmed | VIX, HY, CFTC, NFCI, GSR, CURVE, VXTS, Combo E/F gates hold |

---

## Known gaps / follow-ups

| Gap | Impact | Suggested next step |
|-----|--------|---------------------|
| Combo B combo_detector uses AND for HY level+pctile | May explain n=0 vs CONFIG OR spec | Align detector with CONFIG or document intentional strictness |
| CPI n=1 at 0.20pp RARE | Cannot validate CPI threshold | Backfill more CPI surprise history |
| Combo D hit rate <60% at all gates | Weak 5D bearish signal | Revisit horizon or combo definition with Rohit |

---

*Last updated: 2026-06-16 (P1–P4 complete)*
