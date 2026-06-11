# Macro Report Update — Current Status

**Last updated:** 2026-06-07  
**Source:** `Report update todo details.md` (11 points) + follow-ups MRU-01..06  
**Detail docs:** `MACRO_REPORT_UPDATE_ANALYSIS.md` (Part 1 + Part 2), `MACRO_REPORT_UPDATE_REQUIREMENTS.md`, `MACRO_REPORT_UPDATE_PLAN.md`

---

## DONE

### Phase 1 — Engine & briefing fixes (Divyanshu 11-point review)

| ID | Item | Status | Summary |
|----|------|--------|---------|
| R-01 | Combo E bearish hit rate | ✅ | Bearish direction + 12m primary horizon; no longer inverted at 3m |
| R-02 | Combo C CANCELLED status | ✅ | `cancel_date` column, brown CANCELLED row distinct from INACTIVE |
| R-03 | Combo F/C episode start date | ✅ | Duration shows `· started YYYY-MM-DD` |
| R-04 | Narrative tone | ✅ | Claude prompt + Python reason: no "commanding/dismal"; numeric horizons |
| R-05 | Combo E CFTC leg clarity | ✅ | `confirmed_legs` surfaced (e.g. CAPE, NFCI only) |
| R-06 | WALCL percentile | ✅ | `pctile_window: full` from 2008 on MoM% |
| R-07 | BRAVE → EASY MONEY | ✅ | `EASY_MONEY` posture; display layer updated |
| R-08 | CFTC source note | ✅ | TFF · S&P 500 Consolidated · Lev Money net |
| R-09 | Per-combo validated horizons | ✅ | `combo_hit_rates` in CONFIG; G = N/A |
| R-11 | Combo C fire + cancel logic | ✅ | HOT surprise fire (≥+0.2pp); governing CPI cancel; PPI removed from cancel |

**Tests:** 15 passed (`test_combo_metadata`, `test_combo_c_fire`, `test_combo_c_cancel`, `test_combo_b_hy_dual`, `test_combo_a_vote`, `test_walcl_percentile`, etc.)

**Docs synced:** `docs/MACRO_INTELLIGENCE_MASTER.md`

---

### Phase 2 — Follow-up execution (MRU-01..03)

| ID | Task | Status | Outcome |
|----|------|--------|---------|
| MRU-01 | G→B cascade timing analysis | ✅ | Rescan 2007–2026: 3 B episodes, **0 G fires**, 0/3 with prior G within 6 weeks |
| MRU-02 | HY threshold audit at B fires | ✅ | **keep_400bps**; Oct 2022 = 427 bps but 35th pctile → fails dual 80th gate |
| MRU-03 | Production nightly smoke test | ✅ | `as_of=2026-07-03`: Combo C `CANCELLED`, `cancel_date=2026-07-03`, briefing HTML/PDF confirmed |

**Artifacts:**

| File | Purpose |
|------|---------|
| `scripts/analyze_combo_g_b_cascade.py` | MRU-01 + MRU-02 analysis script |
| `mru01_mru02_results.json` / `.md` | Machine + human-readable results |
| `macro_intelligence/output/runic_briefing_2026-07-03.html` / `.pdf` | MRU-03 smoke test output |
| `MACRO_REPORT_UPDATE_ANALYSIS.md` Part 2 | Full execution write-up |

**R-10 status:** Engine/briefing pieces done (G = N/A hit rate, "testable from 2007" note). Empirical G→B + HY audit **executed** via MRU-01/02 — results documented; spec's ~3–4 week G→B leads **not validated** (zero G fires in rescan).

---

## TODO

### Blocked on Divyanshu / product sign-off

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| MRU-04 | HY dual 80th pctile vs Oct 2022 canonical B | High | 427 bps passes abs floor but fails full-history pctile (35.4th). Dec 2018 (456 bps, 42nd) also fails. Need decision: keep dual, use rolling window, or exception for canonical dates |

### Investigation / backfill

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| MRU-05 | Combo G historical detection audit | Medium | 0 G fires in 2007–2026 rescan and 0 G rows in `combo_fires`. Investigate VXTS/HY 4wk widening data gaps; consider backfill |
| MRU-06 | Manual G→B episode table | Medium | Tag confirmed Divyanshu dates (Aug 2015, Dec 2018, COVID Feb 2020, Apr 2025 G-only) with G fire, B fire, SPX bottom columns for briefing appendix |

### Not yet ticketed (from analysis Part 2)

| Item | Priority | Notes |
|------|----------|-------|
| CFTC full-history percentile for Combo B/E | Low | Currently 156-week rolling per CONFIG; structural combos may need full history like HY |
| Persisted `combo_fires` vs detector rescan gap | Medium | DB has 89 B WATCH, 0 B ACTIVE, 0 G — backfill used pre-fix rules; no automatic reconciliation |
| Briefing appendix: G/B historical instance columns | Medium | Divyanshu asked for G fire, B fire, SPX bottom dates in report (R-10 narrative piece) |
| `test_combo_b_oct_2022.py` vs dual HY gate | Low | Oct 2022 test may not include full-history 80th pctile — align test with MRU-02 finding |
| Claude narrative re-run spot-check | Low | R-04 fix in prompt; not re-verified on a live Claude nightly after engine changes |

---

## Quick reference — key findings needing action

1. **G→B early warning unproven in data** — 0% cascade rate in automated rescan; cannot confirm "G is perfect early warning for B" without MRU-05/06.
2. **400bps HY floor is fine** — no historical fires in 375–400 bps band.
3. **HY dual percentile may be too strict** — blocks Oct 2022 and Dec 2018 under full-history benchmark (MRU-04).
4. **Combo C CANCELLED works in production** — verified on 2026-07-03; `runic.db` now has `combo_c_cancel.cancel_date=2026-07-03` until next real episode.

---

## Related files in this directory

| File | Role |
|------|------|
| `Report update todo details.md` | Original Divyanshu review (11 points) |
| `MACRO_REPORT_UPDATE_REQUIREMENTS.md` | Formatted requirements |
| `MACRO_REPORT_UPDATE_PLAN.md` | Implementation plan |
| `MACRO_REPORT_UPDATE_ANALYSIS.md` | Root cause + fix (Part 1) + execution results (Part 2) |
| `MACRO_REPORT_UPDATE_TODO.md` | MRU ticket tracker (superseded by this status file for at-a-glance view) |
| `MACRO_REPORT_UPDATE_PIPELINE_REPORT_2026-06-09.md` / `.pdf` | Pipeline updates report (report-creation skill): plan vs status, Q&A, challenges |
| `understanding_and_research/Macro_Report_Update_Understanding.md` | Plain-English guide: 11 points, glossary, Q&A, doubts for Rohit Sir |
| `MACRO_REPORT_UPDATE_STATUS.md` | **This file** — current TODO / DONE snapshot |
