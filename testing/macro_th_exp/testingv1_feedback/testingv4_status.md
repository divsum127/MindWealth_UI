# Testing v4 — Implementation Status

**Started:** 2026-06-16  
**Triggered by:** Rohit's inline feedback on `Macro_Regime_Threshold_Experiments_Report_2026-06-09.md`  
**Scope:** Run T2/T3/T4/T5/T6/T10 DB queries; insert data tables inline in report; apply text clarifications  
**Report edited:** `testing/macro_th_exp/testingv1_feedback/Macro_Regime_Threshold_Experiments_Report_2026-06-09.md`  
**DB:** `macro_intelligence/data/runic.db`  
**Python:** `.venv/bin/python3`

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Done and verified |
| 🔄 | Partial / needs follow-up |
| ⏳ | Not started |
| ⚠️ | Blocked / needs input |

---

## Phase 0 — DB Schema Verification

| Step | Task | Status | Notes |
|------|------|--------|-------|
| 0.1 | Confirmed `macro_regime_log_v2` schema | ✅ | `date`, `regime_json` (liquidity_v2, twy_roc, geo_overlay_v2, cape_level) |
| 0.2 | Confirmed `forward_returns` join key | ✅ | Joins `combo_fires` via `combo_id`; returns already in % form |
| 0.3 | Confirmed `daily_readings` CURVE var | ✅ | raw_value = T10Y2Y in bps; meta_json.steepen_4wk_bps present |
| 0.4 | Confirmed no `TWY_ROC` var_id in daily_readings | ✅ | TWY_ROC lives in `macro_regime_log_v2` regime_json only |

---

## Phase 1 — Tests Run

| Test | Description | Status | Inserted Location | n (rows) | Notes |
|------|------------|--------|------------------|----------|-------|
| T2 | WALCL 9-state SPX forward returns (1m/3m/6m/9m/12m) | ✅ | A5 after distribution table | 14,878 total combo fires with regime join | All 9 states present |
| T3 | TIGHT_* all combo fires — full observation table | ✅ | A5 after T2 table | 1,639 total (46 named, 1,593 unnamed) | All named fires are Combo A only |
| T4 | Combo E multi-horizon (6m/12m/18m) | ✅ | B3 section | n=507 Combo E fires | Superseded by T11 (full 6–18M sweep) |
| T5 | Geo overlay non-neutral observations | ✅ | A4 after geo question | 70 named-combo rows on 46 non-neutral dates | CRISIS=21 dates, ELEVATED_RISK=25 dates |
| T6 | TWY_ROC band sweep (all thresholds) | ✅ | B1 after ±0.30pp question | 1,098 combo fire dates with TWY_ROC data | Two tables: calendar-date + combo-fire-date |
| T10 | All historical inversion episodes (T10Y2Y) | ✅ | F2 after INVERTED question | 5 episodes, 36-year backfill | 2022–24 deepest (−106 bps, 112 weeks) |
| T11 | Combo E horizon sweep 6M–18M (3M steps) | ✅ | B3 section (replaced T4 tables) | n=508 fires; 413–507 mature per horizon | `scripts/combo_e_horizon_sweep.py`; JSON artifact |

---

## Phase 2 — Text Edits Applied

| Section | Edit | Status | Notes |
|---------|------|--------|-------|
| A1 | Rohit's clarification on PIVOTING/TIGHTENING/9-states | ✅ | After "Doubt for Rohit sir" |
| A3 | Triple storage confirmed; CAPE threshold distribution | ✅ | After CAPE velocity doubt |
| A4 | 2-state geo recommendation; Bridgewater/Druckenmiller ref | ✅ | After geo question table |
| A5 (A6) | "Range of hit rates" spread clarification | ✅ | Replaced "The spread is not large enough yet" sentence |
| B1 | 13,089 generic fires explanation; TWY_ROC/Combo A ablation ref | ✅ | After TWY_ROC excluded row |
| C (Part C) | HMM clarification — regime detector not hit-rate improver | ✅ | After HMM doubt |
| F2 | "Shadow" defined explicitly | ✅ | After T10 inversion table |

---

## Phase 3 — Key Test Findings

### T2: 9-State Liquidity SPX Returns
- **TIGHT_FLAT** is the most bearish state (34.6% up at 3m, avg −8.52%)
- **NEUTRAL_IMPROVING** is the most bullish near-term (88.9% up 1m, 91.3% at 3m)
- **EASY_TIGHTENING** shows the strongest long-term trend (94.9% up 12m, avg +17.18%) — QT periods
- TIGHT_* states at 9m/12m show identical % to 6m = NULL forward windows for recent fires

### T3: TIGHT_* Fires
- All 46 named combo fires in TIGHT_* are **Combo A** (NFCI/WALCL bear signal)
- 2008–2009 GFC cluster dominates: TIGHT_IMPROVING during 2008 crisis → TIGHT_TIGHTENING Jan 2009 → recovery
- TIGHT_IMPROVING 3m avg (−4.89%) is misleading due to deep 2008 draws; 12m avg flips to +13.80%
- No Combo B/D/E/F fires in TIGHT_* states (all those combos require EASY/NEUTRAL conditions)

### T4 / T11: Combo E Multi-Horizon (6M–18M)
- **T11 (2026-06-18):** Full sweep at 6M, 9M, 12M, 15M, 18M via Yahoo ^GSPC (`COMBO_E_horizon_sweep_6_18m.json`)
- Bear hit (validated direction): 19.7% / 18.7% / **18.9%** / 15.5% / 14.5% — low at all horizons (structural risk, not SPX short timer)
- **Recommendation: keep 12M primary** — stable bear hit, n_mature=507; 6M marginally higher bear hit but too short for valuation story; 15M/18M add bull drift
- SPX Up% diagnostic: 79–86% up across horizons
- EXTREME CAPE (>35) weakest at 6m/12m (from T4 CAPE buckets)
- MODERATE CAPE (25–30) fires all pre-2018

### T5: Geo Overlay
- 46 non-neutral dates: CRISIS=21 (COVID Feb–Jun 2020), ELEVATED_RISK=25 (Ukraine 2022, Tariff shock 2025)
- Geo does NOT uniformly suppress returns: CRISIS Combo A (Apr 2020) fired at COVID bottom +27.77%; ELEVATED_RISK Combo B (Apr 2025 tariff shock) was at a local low
- Confirms "no geo signal" finding at n<10 per cell
- **Recommendation: collapse to 2-state (NEUTRAL/ELEVATED)**

### T6: TWY_ROC Band Sweep
- Calendar-date sweep (all Fridays): NEUTRAL band best (81.3% up 3m); STRONG_HAWKISH worst (58.5%)
- DB combo-fire sweep: same pattern but lower n; NEUTRAL 84.3%, STRONG_HAWKISH 53.8%
- April 2025: TWY_ROC = −0.61 on Apr 4, −0.38 on Apr 18 — firmly DOVISH, confirming the anchor
- **±0.30 bands partially validated**: extreme dovish is a stress signal, not a bullish signal at 3m

### T10: Inversion Episodes
- 5 episodes in 36-year backfill (1990–2026)
- 2022–2024 episode: −106 bps peak, 112 weeks — longest and deepest in dataset
- All 5 episodes followed by steepening >+15 bps/4wk within 1–8 months
- Oct 2022 reference in report = mid-episode 5 (14 inverted weeks through that date)

---

## Phase 4 — Blockers / Open Items

| Item | Description | Status |
|------|------------|--------|
| 18m horizon | SPX 18m computed in T11 sweep; not yet persisted in `forward_returns` schema | 🔄 Optional DB migration |
| TIGHT_* named combos | Only Combo A fires in TIGHT_* — Combos B/D/E/F need tighter liquidity threshold investigation | 🔄 Low priority |
| Geo 2-state implementation | Production geo classifier still uses 3-state (NEUTRAL/ELEVATED_RISK/CRISIS) | ⏳ Prompt update deferred |
| TWY_ROC standalone filter | Not validated as standalone combo filter; regime classifier use only | 🔄 As expected |
| PIVOTING → PAUSING_DOVISH | Reconciliation documented; production prompt not updated | ⏳ Pending Rohit sign-off |

---

## Files Changed

| File | Action |
|------|--------|
| `testing/macro_th_exp/testingv1_feedback/Macro_Regime_Threshold_Experiments_Report_2026-06-09.md` | All 6 test tables inserted inline; all 7 text edits applied; B3 updated T11 |
| `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md` | B3 maturities answered (6M–18M) |
| `testing/macro_th_exp/testingv1_feedback/combo_e_horizon_plan.md` | Experiment plan |
| `scripts/combo_e_horizon_sweep.py` | T11 runner |
| `macro_intelligence/analysis/regime_v2_experiments/COMBO_E_horizon_sweep_6_18m.json` | T11 results |
| `testing/macro_th_exp/testingv1_feedback/testingv4_status.md` | Created (this file) |

---

## Crontab (unchanged)
No changes to crontab. All work is read-only query + report editing.

---

*Last updated: 2026-06-18*
