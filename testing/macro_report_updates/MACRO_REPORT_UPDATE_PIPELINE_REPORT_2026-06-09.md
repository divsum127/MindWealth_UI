# Macro Report Pipeline Update: What I Changed, What I Found, What Got Stuck

Divyanshu sent an 11-point review of the nightly briefing PDF (`Report update todo details.md`). I used that as the spec for a full pass on the engine and report pipeline. Below I match my implementation plan against the current status file, answer the questions he raised, and flag what still needs a decision from him.

---

## The short version

| Area | My plan (`MACRO_REPORT_UPDATE_PLAN.md`) | Where things stand (2026-06-09) |
|------|----------------------------------------|----------------------------------|
| Phase 1: CONFIG + metadata | Done | Done |
| Phase 2: Engine logic (R-01 to R-11) | Done | 10/11 done; R-10 partial |
| Phase 3: Briefing/PDF pipeline | Done | Done (I also fixed PDF table overlap) |
| Phase 4: Tests | 15+ passing | 15 combo tests + 5 briefing tests |
| Phase 5: Docs | Done | Requirements, plan, analysis, status files |
| MRU follow-ups | MRU-01..03 | Done; MRU-04..06 still open |

My nightly PDFs now show per-combo horizons, bearish E at 12M, CANCELLED Combo C, EASY MONEY posture, and a CFTC source note. I have **not** been able to validate the G→B early-warning story in automated backtest yet.

---

## Divyanshu's 11 points vs what I shipped

| # | His ask | Req | Plan phase | Status | What I changed |
|---|---------|-----|------------|--------|----------------|
| 1 | Combo E hit rate inverted (~19.9%) | R-01 | 2a, 3 | Done | Bearish + 12M in `combo_hit_rates`; `raw_hit_rate` counts SPX down |
| 2 | Combo C should be CANCELLED, not INACTIVE | R-02 | 2b, 3 | Done | `cancel_date` column; brown row; smoke test PASS (MRU-03) |
| 3 | Combo F week 10: show episode start | R-03 | 2f, 3 | Done | `Week N of 26 (MEDIUM) · started YYYY-MM-DD` |
| 4 | No commanding/dismal; use 3m not three | R-04 | 3b | Done | Claude prompt + Python `dominant_reason` templates |
| 5 | E confirmed but CFTC 5th pctile: which legs? | R-05 | 2e, 3 | Done | `confirmed_legs: [CAPE, NFCI]` on CONFIRMED rows |
| 6 | WALCL 0.03% MoM at 85th pctile wrong | R-06 | Phase 1 | Done | WALCL `pctile_window: full` from 2008; flat MoM ~51st now |
| 7 | BRAVE → EASY MONEY | R-07 | 2d, 3 | Done | `EASY_MONEY` in detector; `TACTICAL EASY MONEY` in briefing |
| 8 | Clarify CFTC source | R-08 | 3a | Done | TFF · S&P 500 Consolidated · Lev Money net |
| 9 | Per-combo horizons, not uniform 3M | R-09 | 2a, 3 | Done | See table below; G = N/A |
| 10 | G→B test; HY audit; G from 2007 only | R-10 | 2c + MRU | Partial | I ran scripts; 0 G fires; keep_400bps; appendix not in PDF yet |
| 11 | C HOT fire; governing CPI cancel; no PPI | R-11 | 2b | Done | Fire: CPI ≥ +0.2pp hot; cancel: latest CPI ≤ consensus |

### Horizons I configured (his point 9)

| Combo | Primary | Secondary | Hit rate? | Direction |
|-------|---------|-----------|-----------|-----------|
| A | 6M | 3M | Yes | Bullish |
| B | 3M | n/a | Yes | Bullish |
| C | 6M | 3M | Yes | Bearish |
| D | 5D | n/a | Yes | Bearish |
| E | 12M | n/a | Yes | Bearish |
| F | 6M | 3M | Yes | Bullish |
| G | n/a | n/a | N/A | Timing warning only |

That lines up with what he asked for: E at 12M, D at ~5 days, G with no return hit rate. Worth noting here is that I seperated primary and secondary horizons in CONFIG so the PDF row labels update automatically.

---

## My plan phases: planned vs delivered

Rollout order in the plan was Config → Engine → Nightly → Briefing → Tests → Docs.

| Phase | I planned | I delivered | Evidence |
|-------|-----------|-------------|----------|
| 1 | `combo_metadata.py`, horizons, WALCL full pctile | Yes | `CONFIG.yaml`, new module |
| 2 | C fire/cancel, B HY dual, A vote, E legs, F start | Yes | `combo_detector.py`, `combo_c_cancel.py`, etc. |
| 3 | Briefing table, Claude prompt, CANCELLED, CFTC | Yes | `briefing_renderer.py`, `nightly_briefing.py` |
| 4 | Six test files | Yes | 15 passed first pass; +PDF test after layout fix |
| 5 | Analysis + master doc | Yes | `MACRO_REPORT_UPDATE_*.md` |
| Post-plan | MRU-01..03 | Yes | `analyze_combo_g_b_cascade.py`, smoke on 2026-07-03 |

---

## Answers to his explicit questions (point 10 and related)

### How many post-2007 B fires had G within 6 weeks?

He suggested that if all 5 had G within 6 weeks, G would be a perfect early warning.

| Metric | His reference instances | My backtest (2007–2026) |
|--------|----------------------|-------------------------|
| G→B within 6 weeks | ~3–4 week leads cited | **0/3 B episodes (0%)** |
| G fires in full scan | Aug 2015, Dec 2018, COVID, Apr 2025 | **0 G fires in 1,018 Fridays** |
| B ACTIVE episodes | 8 confirmed since 1990 (manual) | 3 in my automated rescan |

**My answer:** I cannot confirm G as early warning from the detector + DB today. I need to build the manual episode table (MRU-06) for his canonical dates.

### HY at every B fire: 400bps floor + dual 80th pctile?

| Check | My result |
|-------|-----------|
| Any fire in 375–400 bps? | No |
| Keep 400bps floor? | **Yes** |
| Dual gate implemented? | Yes (400bps + 80th pctile full history) |

| Label | Date | HY bps | Pctile | Dual OK? |
|-------|------|--------|--------|----------|
| Pre-Aug 2015 | 2015-08-21 | 618.0 | 82.5 | Yes |
| Pre-Dec 2018 | 2018-12-21 | 455.9 | 42.1 | No |
| Pre-COVID | 2020-03-20 | 850.0 | 97.2 | Yes |
| Oct 2022 | 2022-10-07 | 427.1 | 35.4 | No |

**My answer:** 400bps is fine. The dual gate blocks Oct 2022 and Dec 2018. I need his sign-off on that tension (MRU-04).

### G testable from 2007 only?

**Yes.** I added that to the Claude prompt. VXTS data starts 2007.

### Is the narrative tone Claude or Python?

**Both.** I control `dominant_reason` in Python (neutral, numeric horizons). Claude writes the body under SYSTEM guardrails I added in point 4.

### How is WALCL percentile computed?

MoM% on weekly resampled WALCL, not the absolute level. The bug was `rolling_3y` during QT making +0.03% look like the 85th pctile. I switched to `full` from 2008-01-01.

---

## Files I touched

| Layer | Files |
|-------|-------|
| Config | `macro_intelligence/CONFIG.yaml` |
| Engine | `combo_metadata.py`, `combo_detector.py`, `combo_c_cancel.py`, `dominant.py` |
| Nightly | `nightly_run.py` |
| Output | `briefing_renderer.py`, `json_writer.py`, `nightly_briefing.py` |
| Schema | `schema.sql`, `migrate.py` |
| Tests | `test_combo_*.py`, `test_walcl_percentile.py`, `test_briefing_renderer.py` |
| Analysis | `scripts/analyze_combo_g_b_cascade.py` |
| Outputs | `runic_briefing_2026-06-09.pdf`, `runic_briefing_2026-07-03.pdf` |

---

## What gave me trouble

| Issue | What happened | What I did |
|-------|---------------|------------|
| HY % vs bps | FRED HY in %; spec in bps | `_hy_oas_bps()` helper |
| WALCL false 85th | Rolling 3Y in QT regime | Full history from 2008 |
| Combo C cancel in May | CPI governing prints HOT | Found 4 clean Fridays Jun 12–Jul 3 for smoke test |
| Zero G fires | No Friday met all 3 G legs | Logged it; MRU-05/06 for manual dates |
| Oct 2022 vs dual HY | 427 bps passes abs, fails 35th pctile | Flagged for Divyanshu (MRU-04) |
| DB vs rescan | 89 B WATCH, 0 ACTIVE in `combo_fires` | Used rescan for MRU; no reconcile yet |
| FRED 504 | Live nightly pull timed out | Fell back to DB cache some runs |
| PDF table overlap | Duration bled into Direction column | Paragraph wrap in ReportLab |
| FRED HY for audit | API only ~3 years | Used `daily_readings` back to 1997 |
| Combo E duration blank | CONFIRMED has no week counter | Shows `legs CAPE, NFCI` only (by design) |

On the flip side, the experiment rescan only took ~13 minutes once I pointed it at the DB instead of FRED. That part was manageable.

---

## Still open (`MACRO_REPORT_UPDATE_STATUS.md`)

| ID | Item | Blocker |
|----|------|---------|
| MRU-04 | HY dual 80th vs Oct 2022 | Divyanshu sign-off |
| MRU-05 | G detection (0 fires) | Data / detector audit |
| MRU-06 | Manual G/B/SPX bottom table | His confirmed dates |
| Unticketed | G/B appendix in PDF | Not wired yet |
| Unticketed | CFTC full-history pctile for B/E | CONFIG still 156-week |

---

## What I'd do next

1. Get Divyanshu's call on the HY dual gate before the next backfill (Oct 2022 is the stress-test date).
2. Build MRU-06 manual episode table and add it to the briefing appendix.
3. Reconcile `combo_fires` with the current detector so B WATCH vs ACTIVE counts make sense.
4. Show "legs met" on B WATCH (e.g. 1/3) so partial watch rows do not read like near-capitulation.

---

## My doubts and questions

- Divyanshu cites 8 confirmed B instances since 1990; my rescan finds 3. Is that mostly WATCH vs ACTIVE definition, or did my pre-2023 backfill use old rules?
- Zero G fires feels wrong given Aug 2015 and Dec 2018 anecdotes. Is VXTS or HY 4wk data too sparse early on, or are my thresholds too tight?
- Combo E at 18.9% (12M bearish) is directionally right now, but n=507 mixes regimes and the data shows some pretty flat slices across fed cycles. Should I show regime-conditional hit rates in the PDF?
- The dual HY rule makes sense on paper but contradicts Oct 2022 as a B date. Which wins: the rule or his canonical list?
- I fixed the Claude tone guardrails in the prompt, but I have not done a careful read of every live narrative since. Did "commanding" and "dismal" actually disappear in production output?

---

*Sources: `Report update todo details.md`, `MACRO_REPORT_UPDATE_STATUS.md`, `MACRO_REPORT_UPDATE_PLAN.md`, `MACRO_REPORT_UPDATE_ANALYSIS.md` Parts 1–2, `mru01_mru02_results.json`.*
