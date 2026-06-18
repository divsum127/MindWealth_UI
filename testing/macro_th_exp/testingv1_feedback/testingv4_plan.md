# Testing v4 Plan — Rohit Feedback Response

**Date:** 2026-06-16  
**Feedback sources:**  
- `feedback_sectionwise_details.md` — inline comment-by-comment TODOs  
- `feedback_summary.md` — consolidated 10-point instruction list  
- `Additional_email.md` — unsent email (architecture spec, Addendum Sections A–F)

**Deliverable:** Edit `Macro_Regime_Threshold_Experiments_Report_2026-06-09.md` in-place, inserting answers and data tables directly below each question, inline.  
**Status tracker:** `testingv4_status.md`

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Done — result in report |
| 🔄 | Partial — result inserted, caveat noted |
| ⏳ | Pending code execution |
| ⚠️ | Blocked / needs Rohit decision |
| 🆕 | New test not in v2/v3 |

---

## Phase 0 — History window fix (prerequisite for all re-runs)

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 0.1 | Fix VIX, HY, VXTS from `rolling_3y` → FULL EXPANDING history from inception | ⏳ 🆕 | B2 feedback + Additional_email §1 |
| 0.2 | WALCL, WTI, CNH, CPI stay `rolling_3y` — confirm no regression | ⏳ | Additional_email §1 |
| 0.3 | Re-run `backfill_macro_history.py` + `run_regime_v2_experiment_suite.py` after window fix | ⏳ | B2 |
| 0.4 | Verify dual pctile (unconditional + regime_pctile) <50 fallback is logged | 🔄 | B2, Additional_email §1 |

---

## Phase 1 — Return analytics corrections (Rohit §1 + §2)

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 1.1 | All return tables: add avg_win, avg_loss, PW_expected, benchmark, excess_return columns | ✅ (testingv2 §1b, §1c) | feedback_summary §1 |
| 1.2 | Named combos at validated horizons: B=3M, C=6M primary, D=5D, E=12M, F=6M | ✅ (testingv2 §1b) | feedback_summary §2 |
| 1.3 | Per-variable threshold sweep — 11 remaining vars × 2 threshold levels × 1m/3m/6m/9m/12m | ✅ (F_per_variable_sweep.json) | feedback_summary §1 |
| 1.4 | Compare results to i3 Invest Combo Cheatsheet hit rates | ⚠️ Needs Rohit reference | feedback_summary §2 |

---

## Phase 2 — Part A: Five regime dimensions

### A1 — Fed cycle / PIVOTING

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 2.1 | PIVOTING: reconcile with Addendum Python function — 9-state labels (PAUSING_DOVISH, PAUSING_HAWKISH, etc.) vs v2 PIVOTING | ⏳ 🆕 | feedback_sectionwise §3, feedback_summary §7 |
| 2.2 | TIGHTENING includes "holding tight" — document in A1 text | ⏳ | feedback_sectionwise §3 |
| 2.3 | Do NOT merge PIVOTING into EASING — show distinct forward-return profile | ⏳ 🆕 | feedback_summary §7 |
| 2.4 | Store 9 states honestly; collapse to 4 for analytics (NEUTRAL_FLAT: EASY if NFCI<0, TIGHT if NFCI>0; FLAT: dominant 4wk WALCL trend) | ⏳ | feedback_sectionwise §3 |

### A3 — CAPE / Valuation

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 2.5 | Confirm triple CAPE storage: full-history pctile, 3yr rolling pctile, 8wk velocity | ✅ (partial — velocity exists) | feedback_sectionwise §4 |
| 2.6 | 10-year and 5-year distribution CAPE buckets — compute and share table | ⏳ 🆕 | feedback_sectionwise §4 |
| 2.7 | Define moderate vs extreme CAPE threshold (not "n=0") — propose and justify | ⏳ 🆕 | feedback_sectionwise §4 |
| 2.8 | Combo E at 6m, 12m, 18m — show all three horizons | ⏳ 🆕 | feedback_sectionwise B3 |

### A4 — Geo overlay

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 2.9 | Move to 2-state geo (NEUTRAL / ELEVATED) — research Bridgewater/Druckenmiller/Soros best practices | ⏳ 🆕 | feedback_sectionwise §5a |
| 2.10 | Show ALL geo slice observations per combo — even thin n — with date + combo + SPX 1m/3m/6m | ⏳ 🆕 | feedback_sectionwise §5b |

### A5/A6 — Liquidity (WALCL direction)

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 2.11 | Explain v2 liquidity label in plain text (what is liquidity_v2?) | ⏳ | feedback_sectionwise §6 A6.1 |
| 2.12 | SPX tables at 1m, 3m, 6m, 9m, 12m for each of 9 liquidity bands | ⏳ 🆕 | feedback_sectionwise §6 A6.2 |
| 2.13 | Show ALL TIGHT_* observations with date, combo, SPX 1m/3m/6m/9m/12m | ⏳ 🆕 | feedback_summary §5 |
| 2.14 | Define "positive WALCL trend" for EASY_FLAT collapse rule | ⏳ | feedback_sectionwise §6e |
| 2.15 | Restate "spread not large" → use correct language (range of results, not spread) | ⏳ | feedback_sectionwise §6 d/c |
| 2.16 | Insert output rows for ALL 9 states with observation counts and SPX outcomes | ⏳ 🆕 | feedback_sectionwise §6g |
| 2.17 | Confirm all 7 combos A–G tested against liquidity states; where results differ from i3 Invest table | ⏳ | feedback_sectionwise §6f |

---

## Phase 3 — Part B: 14th variable and history windows

### B1 — TWY_ROC

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 3.1 | ±0.30pp band sweep with historical outcome table (not just anchor pass) | ⏳ 🆕 | feedback_sectionwise B1 Q2 |
| 3.2 | Explain 13,089 generic fires to Rohit (sub-threshold variable pair fires, not all named) | ⏳ | feedback_sectionwise B1 Q3 |
| 3.3 | Confirm: was TWY_ROC tested as Combo A additional condition? Show results | ⏳ 🆕 | feedback_summary §6, feedback_sectionwise B1 Q3 |
| 3.4 | Confirm: was GSR tested as Combo A TIGHT MONEY leg? Show results | ⏳ 🆕 | feedback_summary §6 |

### B2 — History windows (see Phase 0)

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 3.5 | VIX/HY/VXTS → FULL EXPANDING (not rolling_3y) — confirm fix in code | ⏳ (Phase 0) | feedback_sectionwise B2 |
| 3.6 | "Not clear" → add clear table showing before/after pctile comparison for affected vars | ⏳ 🆕 | feedback_sectionwise B2 |

### B3 — CAPE storage

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 3.7 | Share CAPE storage comparison test results (level vs velocity vs rolling) | ⏳ 🆕 | feedback_sectionwise B3 |
| 3.8 | Combo E at 6m, 12m, 18m with PW columns (each leg has different dynamics) | ⏳ 🆕 | feedback_sectionwise B3 |

---

## Phase 4 — Part C: HMM

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 4.1 | Address Rohit's HMM clarification — HMM is regime detector not hit-rate improver; response in report | ✅ (partial — testingv2 §2b) | feedback_sectionwise C |
| 4.2 | HMM walk-forward: two-track tables (Risk-Off: C/D/E/G/A-TIGHT; Risk-On: B/F/A-EASY) | ✅ scaffold (D_hmm_walk_forward.json; median 0w — tuning needed) | feedback_summary §2 |
| 4.3 | Show confusion matrix + train/test split for prototype | ⏳ 🆕 | feedback_sectionwise C (Row 5) |
| 4.4 | Row 2: 7 VIX instances — show filter logic + dates + VIX + SPX 1m/3m/6m each | ✅ (testingv2 §3 Row 2) | feedback_summary §3 |

---

## Phase 5 — Part F: Formal regime definitions

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 5.1 | F2 INVERTED: show ALL historical inversion episodes with dates + duration (not just Oct 2022) | ⏳ 🆕 | feedback_sectionwise F Q1 |
| 5.2 | Explain "shadow" in plain language (shadow = test suite run against historical data but not wired to production briefing) | ⏳ | feedback_sectionwise F last TODO |
| 5.3 | F4 grid: already has PW columns; verify inline in report | ✅ (testingv2 §1c) | — |

---

## Phase 6 — Format compliance (Rohit §10)

| Step | Action | Status | Rohit source |
|------|--------|--------|--------------|
| 6.1 | All answers inserted inline in `Macro_Regime_Threshold_Experiments_Report_2026-06-09.md` | ⏳ | feedback_summary §10 |
| 6.2 | No separate PDF; data tables directly below each question | ⏳ | feedback_summary §10 |
| 6.3 | Large data → Google Drive link inline in relevant para | ⚠️ (no Drive access; use inline tables where possible) | feedback_summary §10 |

---

## New tests to execute (🆕 items requiring code runs)

| # | Test | Script / method | Expected output |
|---|------|-----------------|-----------------|
| T1 | VIX/HY/VXTS window fix → backfill re-run | Modify config; re-run suite | Updated pctiles + regime log |
| T2 | WALCL 9-state SPX tables: 1m/3m/6m/9m/12m per state | DB query + forward_returns | 9×5 outcome matrix |
| T3 | TIGHT_* all observations table | DB query combo_fires + daily_readings | Date + combo + SPX returns |
| T4 | CAPE 10yr/5yr buckets + Combo E 6m/12m/18m | regime_experiments/run_all.py or direct DB | Multi-horizon E table |
| T5 | Geo overlay all observations per combo | DB query with geo tag | Date + combo + SPX returns |
| T6 | TWY_ROC ±0.30pp band sweep | DB + DGS2 series | Band sweep table |
| T7 | TWY_ROC as Combo A condition — test | `testingv2_ablations.py` extension | PW hit rate delta |
| T8 | GSR as Combo A TIGHT MONEY leg | Same | PW hit rate delta |
| T9 | HMM confusion matrix + train/test detail | `hmm_walk_forward.py` verbose run | Matrix per window |
| T10 | ALL inversion episodes from T10Y2Y data | DB/FRED query | List of episodes + duration |

---

## Priority order

1. **P0** — Phase 0 (history window fix) — prerequisite for data accuracy
2. **P0** — T2, T3 (WALCL 9-state tables + TIGHT_* observations) — Rohit asked explicitly, inline
3. **P0** — T4 (CAPE multi-horizon Combo E)
4. **P1** — T5, T6, T7, T8 (geo, TWY band, ablations)
5. **P1** — Phase 6 (inline report edits with all answers)
6. **P2** — T9, T10 (HMM detail, inversion list)

---

*Plan created 2026-06-16. Execution tracked in `testingv4_status.md`.*
