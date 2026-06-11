# Macro Threshold Experiments — Testing v2 Plan

**Source feedback:** `testing/macro_th_exp/testingv1_feedback/feedback_summary.md` (Rohit, 2026-06)  
**Prior report:** `MACRO_TH_EXP_PIPELINE_REPORT_2026-06-09.pdf` / `.md`  
**Reference spec:** `understanding_and_research/Macro_Regime_System_v2_Understanding.md`  
**Deliverable:** `testingv2_report.md` — question → answer → inline data table (no separate PDF)  
**Status tracker:** `testingv2_status.md` (implementation detail)

---

## Report format guidelines (from Rohit)

1. **Single document** — Do not send answers in a separate PDF. Every question gets the answer and data table immediately below it in the same file.
2. **Inline tables** — Results appear directly under the relevant question. Large datasets may use a Google Drive Excel link inline in the paragraph (not scattered across repos).
3. **Probability-weighted returns** — Every forward-return table must include:
   - Hit rate (frequency)
   - Avg SPX return when signal correct (mean of wins)
   - Avg SPX return when signal wrong (mean of losses)
   - Probability-weighted expected return = `(hit_rate × avg_win) + ((1 − hit_rate) × avg_loss)`
   - Unconditional benchmark (drift): ~+0.5% (5D), +2.5% (3M), +5% (6M), +10% (12M)
   - Excess return = PW expected − benchmark
4. **Validated horizons per combo** — Never uniform 3M:
   - B: 3M | C: 6M primary, 3M secondary | D: 5D | E: 12M | F: 6M primary, 3M secondary | G: no return table
5. **Two-track HMM** — Risk-Off track (C, D, E, G, A-TIGHT) and Risk-On track (B, F, A-EASY) reported separately; never mix.
6. **Show thin-n data** — Do not dismiss TIGHT_* liquidity slices; show every observation with date, combo, and 1M/3M/6M/9M/12M returns.
7. **Naming** — Combo A: EASY MONEY / TIGHT MONEY (not BRAVE/FEARFUL/BULLISH ENVIRONMENT). Combos B/C keep BULLISH/BEARISH.

---

## Step-by-step execution plan

**Legend — Status:** ✅ done | 🔄 partial / follow-up | ⏳ not started | ⚠️ blocked  
**Legend — In v2 report?:** ✅ documented inline | 🔄 partial / PENDING called out | ⏳ not yet | — N/A (infra only)

### Phase 0 — Blockers (do first)

| Step | Action | Status | In v2 report? |
|------|--------|--------|---------------|
| 0.1 | **Fix curve STEEPENING bug** — T10Y2Y ~+38bps but `steepen_4wk_bps` stored as −11; verify `fred_pull.steepen_4wk` window and post-inversion trough logic in `curve_regime_f2` | ✅ DONE — `steepen_bps_post_inversion_trough()`; production re-pull + shadow backfill (2026-06-11); STEEPENING 23/23 Fri 2026 YTD | ✅ §8 (before/after DB table) |
| 0.2 | **Reconcile PIVOTING** — Map `collapse_fed_cycle_v2()` to Addendum Python (CUTTING_EARLY → PIVOTING; no standalone PIVOTING in spec) | 🔄 DOCUMENTED — Addendum alias optional | ✅ §7 |
| 0.3 | **Combo A naming sweep** — Replace remaining FEARFUL/BRAVE in code, JSON, briefing; coordinate with Parth on web UI | 🔄 CODE DONE (`TIGHT_MONEY` in detector, dominant, metadata); web UI coordination pending | ✅ §9 (code ✅; Parth ⏳) |

### Phase 1 — Return analytics (Rohit §1, §2)

| Step | Action | Status | In v2 report? |
|------|--------|--------|---------------|
| 1.1 | Add PW return columns to F4 steepening grid and all combo tables | ✅ DONE — `probability_weighted_summary`; F4 `spx_3m_pw` + `instances` in `F_quant_regime.json` | ✅ §1a, §1c |
| 1.2 | Re-run named combos A–F at validated horizons with PW columns | ✅ DONE — DB query 2026-06-10; tables in report | ✅ §1b |
| 1.3 | Remove Combo G return tables everywhere | ✅ CONFIRMED (`show_hit_rate=false`) | ✅ §1b (G omitted); summary |
| 1.4 | Per-variable threshold sweep (11 vars × 2 levels × 1M/3M/6M/9M/12M) — same grid as F4 | ✅ DONE — `scripts/per_variable_threshold_sweep.py` → `F_per_variable_sweep.json` | ✅ §1d |
| 1.5 | Compare combo results to i3 Invest Combo Cheatsheet hit rates | ⚠️ BLOCKED — needs cheatsheet reference values from Rohit | 🔄 §1b (PW table done; formal compare **PENDING**) |

### Phase 2 — HMM walk-forward (Rohit §2, §3 Row 3–5)

| Step | Action | Status | In v2 report? |
|------|--------|--------|---------------|
| 2.1 | Build anchor date table (Risk-Off / Risk-On / Transition) spanning 1990–2026 | ✅ DONE — in `hmm_walk_forward.py` / `D_hmm_walk_forward.json` → `anchors` | ✅ §2a, §2b |
| 2.2 | Implement `scripts/hmm_walk_forward.py` — hmmlearn GaussianHMM, diag covariance, expanding window 1990–2014 → test 2015, … → 2025 | ✅ DONE — 11 OK windows 2015–2025; `hmmlearn` in requirements.txt | ✅ §2b |
| 2.3 | Two-track lead-time tables (Risk-Off / Risk-On) with median/min/max weeks | 🔄 SCAFFOLD — runs end-to-end; median lead **0w** (anchor/posterior tuning needed) | ✅ §2b (tables + tuning caveat) |
| 2.4 | Document prototype limitations (k-means on mean pctile, 500 rows, in-sample) for Row 5 | ✅ DONE | ✅ §3 Row 5 |
| 2.5 | Confirm live daily `emission_vectors` job populating post-backfill | ✅ WIRED — `run_emission_vectors_daily.py`; cron **18:15 Mon–Fri** (merge-only install) | ✅ §2c |
| 2.6 | HMM training scaffold + Ahil handoff doc (trigger, evaluate, label, wire to classifier) | ✅ DONE — docstring in `hmm_walk_forward.py` | ✅ §2d |

### Phase 3 — Specific question answers (Rohit §3, §5–7)

| Step | Action | Status | In v2 report? |
|------|--------|--------|---------------|
| 3.1 | **Row 2** — Document VIX 65–79 filter logic; 7 instances with 1M/3M/6M table | ✅ DONE | ✅ §3 Row 2 |
| 3.2 | **Row 3** — Acknowledge binary VIX test invalid for HMM; defer to walk-forward | ✅ DONE — walk-forward scaffold complete | ✅ §3 Row 3 |
| 3.3 | **Row 5** — Prototype train window, states, confusion matrix, in-sample caveat | ✅ DONE | ✅ §3 Row 5 |
| 3.4 | **§5 TIGHT_*** — FM crossing events + named combo fires in TIGHT liquidity with full return table | ✅ DONE | ✅ §5a, §5b |
| 3.5 | **§5 WALCL** — Restate “50–60%” as separate regime cells, not a spread | ✅ DONE | ✅ §5c |
| 3.6 | **§6 TWY_ROC / GSR for Combo A** — Confirm tested or not | ✅ DONE — ablation `scripts/testingv2_ablations.py` → `X_testingv2_ablations.json` | ✅ §6a, §6b |
| 3.7 | **§7 PIVOTING** — Reconcile with Addendum; do not merge PIVOTING into EASING | ✅ DONE | ✅ §7 |

### Phase 4 — Transition probability & production wiring (Rohit §4)

| Step | Action | Status | In v2 report? |
|------|--------|--------|---------------|
| 4.1 | Wire Combo C cancel probability to nightly briefing / dashboard | 🔄 PARTIAL — `model_cancel_prob` in payload + briefing text; dashboard display pending | ✅ §4 (PARTIALLY WIRED) |
| 4.2 | Extend options-framework cancel to Combo D, F, G | ⏳ NOT STARTED — C only (options MC in `E_cancel_probability.json`) | ✅ §4 (D/F/G **PENDING** noted) |
| 4.3 | Combo F deterministic week≤26 rule documented | ✅ SPEC DONE | ✅ §4 |

### Phase 5 — Quality & handoff

| Step | Action | Status | In v2 report? |
|------|--------|--------|---------------|
| 5.1 | Publish `testingv2_report.md` in Rohit inline format | ✅ DONE — refreshed 2026-06-11 with artifact tables | ✅ §10 + full doc |
| 5.2 | Re-run shadow suite after curve fix + CONFIG B4 windows | ✅ DONE — CURVE refresh 1,910 dates + suite ~2m13s; STEEPENING in DB | ✅ §8; summary table |
| 5.3 | Combo B confirmed-only (3/3 ACTIVE) re-slice | 🔄 DONE — **n=0 ACTIVE** in DB (all 89 WATCH); explains Rohit 8 vs 89 gap | ✅ summary; §6 context |
| 5.4 | TWY_ROC / GSR Combo A ablation tests | ✅ DONE — `X_testingv2_ablations.json` | ✅ §6 |
| 5.5 | Read Rohit unsent email (Parts A–I) when attached; align regime score formula & 9-step discovery | ⚠️ PENDING attachment | ⏳ not in report |

---

## Priority order for next session

1. Tune HMM anchor labelling + 50% posterior lead-time logic (median 0w today)
2. Implement cancel prob stubs for Combos D, F, G (P1)
3. Coordinate Parth on web UI TIGHT MONEY labels (P1)
4. i3 Invest cheatsheet compare — needs Rohit reference values (P1)
5. CONFIG B4 window fix (HY/VIX/VXTS `rolling_3y`) — deferred
6. Production v2 regime swap to nightly PDF — deferred

---

*Plan created 2026-06-10. Status + report columns last synced 2026-06-11 with `testingv2_status.md` and `testingv2_report.md`.*
