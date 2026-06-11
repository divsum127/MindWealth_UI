# Testing v2 — Implementation Status

**Started:** 2026-06-11  
**Plan:** `testingv2_plan.md`  
**Report:** `testingv2_report.md` (refreshed 2026-06-11 with artifact tables + post-backfill curve verification)  
**Crontab policy:** Merge-only — existing jobs preserved ✅

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Done and verified |
| 🔄 | Partial / needs follow-up |
| ⏳ | Not started |
| ⚠️ | Blocked / needs input |

---

## Phase 0 — Blockers

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 0.1 | Fix curve `steepen_4wk_bps` | ✅ | `fred_pull.steepen_bps_post_inversion_trough`; live T10Y2Y → **STEEPENING** (spread 42bps, steepen 144bps) |
| 0.2 | PIVOTING reconcile | 🔄 | `CUTTING_EARLY`→`PIVOTING` documented; Addendum alias optional |
| 0.3 | FEARFUL→TIGHT_MONEY rename | ✅ | `combo_detector`, `dominant.py`, `combo_metadata.posture_display`; test added |

## Phase 1 — Return analytics

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 1.1 | PW columns on F4 grid | ✅ | `run_part_f` + `probability_weighted_summary`; JSON updated |
| 1.2 | Combos at validated horizons | ✅ | v2 report (2026-06-10) |
| 1.3 | Combo G no return table | ✅ | |
| 1.4 | Per-variable threshold sweep | ✅ | `scripts/per_variable_threshold_sweep.py` → `F_per_variable_sweep.json` (11 vars) |
| 1.5 | i3 Invest cheatsheet compare | ⚠️ | Needs Rohit reference values |

## Phase 2 — HMM

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 2.1 | Anchor date table | ✅ | In `hmm_walk_forward.py` |
| 2.2 | `hmm_walk_forward.py` | ✅ | 11 OK windows 2015–2025; `hmmlearn` in requirements.txt |
| 2.3 | Two-track lead-time tables | 🔄 | Scaffold runs; median lead **0w** (posterior/labelling needs tuning) |
| 2.4 | Prototype limitations doc | ✅ | v2 report |
| 2.5 | Daily `emission_vectors` cron | ✅ | `run_emission_vectors_daily.py`; cron **18:15 Mon–Fri** (merged) |
| 2.6 | HMM handoff in script | ✅ | Docstring at top of `hmm_walk_forward.py` |

## Phase 3 — Q&A (report)

| Step | Task | Status |
|------|------|--------|
| 3.1–3.7 | Rohit specific questions | ✅ initial report; refresh with new artifacts 🔄 |

## Phase 4 — Cancel probability

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 4.1 | Combo C cancel on briefing | ✅ | `model_cancel_prob` in payload + system recommendation text |
| 4.2 | Cancel for D, F, G | ⏳ | C only (options MC) |
| 4.3 | Combo F week≤26 rule | ✅ | Spec only |

## Phase 5 — Quality

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 5.1 | v2 report refresh | ✅ | §1c/1d/2b/4/6/8/9 + summary synced |
| 5.2 | Re-run shadow suite | ✅ | CURVE refresh 1910 dates + suite 2m13s; STEEPENING in DB |
| 5.3 | Combo B confirmed-only | 🔄 | **n=0 ACTIVE** in DB (all 89 are WATCH) — see ablations JSON |
| 5.4 | TWY/GSR Combo A ablation | ✅ | `X_testingv2_ablations.json` |
| 5.5 | Rohit unsent email | ⚠️ | Not attached |

---

## Crontab (verified 2026-06-11)

All prior entries kept; added emission daily:

```
0 22 * * *  MindWealth emailscript.sh
0 8 * * 1-5  run_ssi_daily.py
30 17 * * 5  run_macro_friday_pull.py
0 18 * * 1-5  run_macro_nightly.py
15 18 * * 1-5  run_emission_vectors_daily.py   ← NEW
```

---

## New / changed files

| File | Purpose |
|------|---------|
| `src/macro_intelligence/data/fred_pull.py` | Post-trough steepen metric |
| `src/macro_intelligence/analysis/regime_experiments/metrics.py` | `probability_weighted_summary` |
| `scripts/per_variable_threshold_sweep.py` | 11-var isolation sweep |
| `scripts/hmm_walk_forward.py` | Walk-forward HMM scaffold |
| `scripts/run_emission_vectors_daily.py` | Live emission vector sync |
| `scripts/testingv2_ablations.py` | Combo B + TWY/GSR ablations |
| `tests/test_curve_steepen.py` | Curve fix tests |
| `macro_intelligence/analysis/regime_v2_experiments/F_per_variable_sweep.json` | Sweep output |
| `macro_intelligence/analysis/regime_v2_experiments/D_hmm_walk_forward.json` | HMM output |
| `macro_intelligence/analysis/regime_v2_experiments/X_testingv2_ablations.json` | Ablation output |

---

## Test results (2026-06-11)

```
pytest tests/test_curve_steepen.py tests/test_combo_a_vote.py
     tests/test_combo_metadata.py tests/test_regime_v2_experiments.py
→ 12 passed
```

---

## Key findings this session

1. **Curve bug fixed** — simple 4wk diff was −4bps; post-trough steepen **+144bps** → `STEEPENING`.
2. **Combo B confirmed-only** — 0 fires with ACTIVE/CONFIRMED status; all 89 historical rows are WATCH (explains Rohit 8 vs 89 gap).
3. **TWY_ROC ablation** — DOVISH TWY subset on Combo A dates (n=28) shows different PW excess vs baseline; GSR rare slice in JSON.
4. **HMM walk-forward** — runs end-to-end; lead times 0 median → needs anchor labelling / posterior threshold review before December decision.

---

## Next steps

1. Tune HMM state mapping + 50% posterior lead-time logic.
2. Implement cancel prob stubs for D/F/G.
3. Coordinate Parth on web UI TIGHT MONEY labels.
4. i3 Invest cheatsheet compare (needs Rohit reference values).

---

*Last updated: 2026-06-11*
