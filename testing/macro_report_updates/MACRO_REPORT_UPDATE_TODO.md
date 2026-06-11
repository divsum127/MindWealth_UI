# Macro Report Update — Open Follow-Ups

**Created:** 2026-06-07  
**Parent work:** DONE #15 in `docs/mindwealth_ui_job_status.md`  
**Results:** `MACRO_REPORT_UPDATE_ANALYSIS.md` **Part 2**

---

## Status Summary

| ID | Task | Priority | Status |
|----|------|----------|--------|
| MRU-01 | G→B cascade timing analysis | High | **DONE** — 2026-06-07 |
| MRU-02 | HY threshold audit at historical B fires | High | **DONE** — 2026-06-07 |
| MRU-03 | Production nightly smoke test (Combo C CANCELLED) | High | **DONE** — 2026-06-07 |

---

## DONE — MRU-01 (G→B cascade)

**Outcome:** 3 B ACTIVE episodes in 2007–2026 rescan; **0 G fires** ever detected; **0/3** B episodes had prior G within 6 weeks.

**Artifacts:** `mru01_mru02_results.json`, `scripts/analyze_combo_g_b_cascade.py`

**Caveat:** G never persisted in DB; cannot confirm spec's ~3–4 week G→B leads without manual episode tagging or G detection tuning.

---

## DONE — MRU-02 (HY threshold audit)

**Outcome:** **keep_400bps** — no fires in 375–400 bps band. Oct 2022 HY = 427 bps but **35th pctile** on full history → fails new dual gate.

**Artifacts:** `mru01_mru02_results.md` § MRU-02

**Follow-up for Divyanshu:** Sign-off on HY 80th pctile dual vs Oct 2022 canonical B date.

---

## DONE — MRU-03 (Combo C CANCELLED smoke test)

**Outcome:** PASS on `as_of=2026-07-03` after 4-Friday cancel (Jun 12–Jul 3). Briefing shows `CANCELLED · cancelled 2026-07-03`.

**Artifacts:** `macro_intelligence/output/runic_briefing_2026-07-03.html`, `.pdf`

---

## NEW — Open items from Part 2

| ID | Task | Priority | Status |
|----|------|----------|--------|
| MRU-04 | Divyanshu sign-off: HY dual 80th pctile vs Oct 2022 B | High | **TODO** |
| MRU-05 | Historical Combo G backfill / detection audit (0 fires in DB) | Medium | **TODO** |
| MRU-06 | Manual G→B episode table from confirmed Divyanshu dates | Medium | **TODO** |
