# Macro Report Pipeline Update — Plain-English Understanding Guide

**For:** Divyanshu, Rohit Sir, implementation team  
**Source spec:** `testing/macro_report_updates/Report update todo details.md` (11 points, Divyanshu review)  
**Status files:** `MACRO_REPORT_UPDATE_STATUS.md`, `MACRO_REPORT_UPDATE_ANALYSIS.md`, `MACRO_REPORT_UPDATE_TODO.md` (implementation through 2026-06-09)  
**Purpose:** Explain what Divyanshu's review asks us to fix in the nightly briefing pipeline, what each technical term means, what we already built and tested, and what doubts to raise with Rohit Sir.

---

## 1. What is this document?

Divyanshu reviewed a nightly briefing PDF and sent **11 numbered fix suggestions** plus follow-up questions on Combo G→B timing and Combo B HY thresholds. Your job is to make the **Runic nightly report** (PDF/HTML/JSON) match that spec: correct hit rates, correct combo statuses, honest horizons, and empirically tested G/B rules where possible.

Success looks like: production `run_nightly()` output where Combo E shows bearish 12M hit rate, Combo C can end as **CANCELLED** (not INACTIVE), Combo G shows **N/A** hit rate, and the open empirical questions (G→B cascade, HY dual gate vs Oct 2022) have clear answers or documented doubts.

**How to read the experiment tables:** Every Q&A table has a **Doubts to ask Rohit Sir** column. These are open questions raised by the backtest or status file, not formal approval requests.

---

## 2. Core concepts (read this first)

| Term | Simple meaning |
|------|----------------|
| **Named combo (A–G)** | One of seven pre-defined macro signals (Liquidity, Capitulation, Stagflation, FOMO Top, Valuation Extreme, Recovery, Hidden Stress). |
| **Hit rate (HR)** | % of historical combo fires where SPX moved the way the combo predicts at a chosen time horizon. |
| **Bullish combo** | Success = SPX **up** at horizon (e.g. B Recovery, F). |
| **Bearish combo** | Success = SPX **down** at horizon (e.g. C, D, E). |
| **Horizon** | How far forward we measure SPX (5D, 3M, 6M, 12M). Each combo has its own validated horizon. |
| **ACTIVE / WATCH / INACTIVE** | Combo state: fully firing, partial legs only, or not firing. |
| **CANCELLED** | Combo C ended via the 4-Friday cancel rule (distinct from INACTIVE). |
| **Episode start date** | First Friday a combo episode began (e.g. when F Recovery turned ACTIVE). |
| **CPI surprise** | Actual CPI minus consensus forecast, in percentage points (pp). |
| **HOT surprise** | CPI actual **above** consensus by ≥0.2pp (fires Combo C). |
| **Governing CPI print** | Most recent confirmed CPI release on or before the Friday we evaluate. |
| **WTI 4wk change** | Oil price % change over ~4 weeks; used in Combo C cancel. |
| **HY OAS (bps)** | High-yield bond spread over Treasuries, in **basis points** (100 bps = 1%). |
| **Dual HY gate** | Combo B needs HY ≥400bps **and** HY at ≥80th percentile on full history. |
| **WALCL MoM%** | Week-over-week % change in Fed balance sheet (not the absolute level). |
| **Percentile (pctile)** | Where today's reading sits vs history (50th = median). |
| **CFTC Lev Money net** | CFTC Commitments of Traders: leveraged money long minus short on S&P 500 futures. |
| **VXTS** | VIX 3-month / VIX spot ratio (term structure of volatility). |
| **MRU-01..06** | Follow-up tickets after the main 11-point fix (G→B test, HY audit, smoke tests). |

---

## 3. Point 1 — Combo E bearish hit rate (R-01)

**What the spec asks:** Combo E is **bearish**. Hit rate must count fires where SPX was **negative** at the target horizon, not positive. Label combos bullish/bearish explicitly. The PDF showed ~19.9% at 3M, which looked like a logic inversion.

### Point 1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Added `combo_hit_rates` in CONFIG; new `combo_metadata.py`; bearish SQL uses `spx_12m < 0` for E. |
| **Results** | E now shows **18.9% (12M)** bearish hit rate in live briefing (`runic_output_2026-06-09.json`); 15 unit tests passed. |
| **Production** | **Live** in nightly pipeline. |

### Point 1 — Old vs new

| Aspect | Old / production | New / spec | Status |
|--------|------------------|------------|--------|
| E direction | Treated as bullish in SQL (`spx_3m > 0`) | Bearish: SPX down = hit | Fixed |
| E horizon | Uniform 3M column | Primary **12M** | Fixed |
| Display | ~19.9% (3M) looked "broken" | 18.9% (12M) bearish | Fixed |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is E hit rate computed as bearish (SPX down)? | **Yes** | `raw_hit_rate()` uses `spx_12m < 0` when `bullish=False`. Live row: **18.9% (12M)**, n=507 fires in DB stats. | **Doubt:** 18.9% at 12M is still low for a "structural top" signal. Is that acceptable, or should we show regime-conditional hit rates? |
| Should E use 3M or 12M? | **Yes** | Spec says 12M; CONFIG `primary_horizon: spx_12m`. | None closed. |
| Was the old 19.9% a bug? | **Yes** | Root cause: bullish-only SQL + wrong 3M horizon (`MACRO_REPORT_UPDATE_ANALYSIS.md` R-01). | None. |

---

## 4. Point 2 — Combo C CANCELLED status (R-02)

**What the spec asks:** When the 4-Friday cancel clock finishes (WTI 4wk below +5% for 4 Fridays in a row), Combo C must show **CANCELLED** with the **cancel date**, not INACTIVE. INACTIVE means it never fired recently.

### Point 2 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Added `combo_c_cancel.cancel_date`; brown CANCELLED row in PDF; cancel check wired into `nightly_run.py`. |
| **Results** | MRU-03 smoke test on **2026-07-03**: status=CANCELLED, duration=`cancelled 2026-07-03`, brown row in HTML/PDF. |
| **Production** | **Live**; `runic.db` has `cancel_date=2026-07-03` from smoke test. |

### Point 2 — Old vs new

| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| Terminal state after cancel | INACTIVE (grey) | CANCELLED (brown) + date | Fixed |
| `cancel_date` stored | No | Yes | Fixed |
| Nightly cancel check | Friday pull only | Every nightly run | Fixed |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does briefing show CANCELLED after 4-Friday cancel? | **Yes** | MRU-03: 4 Fridays (**2026-06-12** through **2026-07-03**), both legs pass; `cancel_date=2026-07-03`. | **Doubt:** DB still holds that cancel state until the next real C episode. Is that OK for production readers? |
| Is CANCELLED visually distinct from INACTIVE? | **Yes** | Brown `#4A3728` vs grey INACTIVE (`briefing_renderer.py`). | None. |

---

## 5. Point 3 — Combo F episode start date (R-03)

**What the spec asks:** When the header says "Combo F active (week 10, MEDIUM)", also show **when week 1 started** so readers know if week 10 is complete or just beginning.

### Point 3 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `_combo_f_episode_start()`; duration string includes `· started YYYY-MM-DD`. |
| **Results** | Live briefing **2026-06-09**: `Week 10 of 26 (MEDIUM) · started 2026-04-03`. |
| **Production** | **Live**. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is F episode start shown in PDF? | **Yes** | Dominant band + combo table show `started 2026-04-03` on 2026-06-09 run. | None. |
| Same for Combo C when ACTIVE? | **Yes** | `_combo_c_episode_start()` pattern applied. | None. |

---

## 6. Point 4 — Narrative tone (R-04)

**What the spec asks:** No words like "commanding" or "dismal". Use numeric horizons (`75% 3m` not "three-month"). Clarify whether tone comes from Claude API or Python.

### Point 4 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Claude SYSTEM prompt guardrails; Python `dominant_reason` uses neutral templates with horizon labels. |
| **Results** | Dominant reason example: `79% 6M hit rate` (no adjectives). |
| **Production** | **Live** in prompt + `dominant.py`. |

### Point 4 — Old vs new

| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| Subjective adjectives | "commanding", "dismal" | Banned in Claude prompt | Fixed in spec |
| Horizon spelling | "three-month" | `3m`, `6m`, `12m` | Fixed |
| Who writes dominant band text | Mixed | Python `dominant_reason` + Claude body | Documented |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is tone controlled in Python or only Claude? | **Yes** | **Both**: `dominant_reason` is Python; 5-paragraph body is Claude under SYSTEM rules (`nightly_briefing.py`). | **Doubt:** R-04 prompt fix not fully spot-checked on every live Claude narrative since deploy. Worth a one-pass read of latest PDF? |
| Are spelled-out horizons removed? | **Partially** | Python layer uses `6M` etc.; Claude body may still slip occasionally. | Same doubt as above. |

---

## 7. Point 5 — Combo E CFTC leg clarity (R-05)

**What the spec asks:** E can confirm on **2 of 3** legs (CAPE, NFCI, CFTC). If CFTC is at 5th percentile, the briefing must **not** imply CFTC is active. Show which legs actually fired.

### Point 5 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `confirmed_legs` list on E fire; shown in duration row and Claude payload. |
| **Results** | Live **2026-06-09**: E CONFIRMED, `legs CAPE, NFCI` while CFTC at 1st–5th pctile. |
| **Production** | **Live**. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Can reader see which E legs fired? | **Yes** | Duration: `· legs CAPE, NFCI`. CFTC not listed when below 80th pctile threshold. | None. |

---

## 8. Point 6 — WALCL percentile (R-06)

**What the spec asks:** WALCL at +0.03% MoM should be near **50th percentile**, not 85th. Confirm we use **MoM%** not absolute Fed balance sheet level. Active QE historically ~+0.5–0.8% MoM at 85th pctile.

### Point 6 — Experiment status

| | Detail |
|---|--------|
| **What we did** | CONFIG: `pctile_window: full`, `pctile_start: 2008-01-01` for WALCL. |
| **Results** | Live **2026-06-09**: WALCL 0.03% MoM at **51%** pctile. `test_walcl_percentile.py` passed. |
| **Production** | **Live**. |

### Point 6 — Old vs new

| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| WALCL pctile window | `rolling_3y` (QT regime inflated rank) | `full` from 2008 | Fixed |
| Series used | MoM% (was already MoM%) | MoM% | Confirmed correct |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Was percentile computed on level vs MoM%? | **Yes** | Already MoM%; bug was **window**, not series (`MACRO_REPORT_UPDATE_ANALYSIS.md` R-06). | None. |
| Is +0.03% MoM near 50th now? | **Yes** | **51%** on 2026-06-09 dashboard. | None. |

---

## 9. Point 7 — BRAVE → EASY MONEY (R-07)

**What the spec asks:** Replace **BRAVE** with **EASY MONEY / BULLISH**. "Brave" means facing challenge; easy-money euphoria should not use that label.

### Point 7 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Detector returns `EASY_MONEY`; briefing shows `TACTICAL EASY MONEY`. |
| **Results** | Live **2026-06-09** posture: `TACTICAL EASY MONEY`. |
| **Production** | **Live** (JSON field `brave_fearful` kept for C++ compat; display layer translates). |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is BRAVE removed from user-facing PDF? | **Yes** | Shows EASY MONEY in dominant band and recommendation. | **Doubt:** Internal JSON still uses `brave_fearful` key for C++. OK to leave until C++ consumer updates? |

---

## 10. Point 8 — CFTC source note (R-08)

**What the spec asks:** Clarify where the CFTC number comes from in the variable dashboard.

### Point 8 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `source_note` on CFTC variable row. |
| **Results** | Text: `CFTC.gov TFF · S&P 500 Consolidated · Lev Money net (Fri report = Tue positions)`. |
| **Production** | **Live** in JSON payload; extendable in HTML/PDF. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is CFTC source documented in output? | **Yes** | `variables_dashboard` in `runic_output.json` includes `source_note`. | None. |

---

## 11. Point 9 — Per-combo validated horizons (R-09)

**What the spec asks:** Stop showing uniform **3M Hit Rate** for every combo. Each combo has its own horizon from i3 Invest / spec reasoning. Combo G has **no** return hit rate.

### Point 9 — Horizon table (spec vs implemented)

| Combo | Spec primary | Implemented | Hit rate shown? |
|-------|--------------|-------------|-----------------|
| A | 6M (3M secondary) | 6M / 3M | Yes |
| B | 3M | 3M | Yes |
| C | 6M (3M secondary) | 6M / 3M | Yes |
| D | 5 days | 5D (`spx_1w`) | Yes |
| E | 12M (6–18M range in spec) | 12M | Yes |
| F | 6M (3M secondary) | 6M / 3M | Yes |
| G | None (timing warning) | N/A | **No** |

### Point 9 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `combo_hit_rates` block in CONFIG; `combo_metadata.py`; table cells show e.g. `78.8% (6M)`. |
| **Results** | All 7 rows show correct horizon suffix in 2026-06-09 PDF. G = `N/A`. |
| **Production** | **Live**. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does each combo show its own horizon? | **Yes** | See table above; verified in `runic_briefing_2026-06-09.pdf`. | None. |
| Does G show N/A? | **Yes** | `show_hit_rate: false` in CONFIG. | None. |

---

## 12. Point 10 — G→B testing, HY audit, briefing notes (R-10)

**What the spec asks:**

1. Note in briefing: **Combo G testable from 2007 only** (no VXTS pre-2007).
2. Add historical columns: G fire date, B fire date, SPX bottom date.
3. Measure weeks between G and B fires; of post-2007 B fires, how many had G within **6 weeks**?
4. At every confirmed B fire: HY OAS in bps; if any in **375–400 bps**, lower the 400 threshold.
5. Implement **dual HY**: ≥400bps **and** ≥80th percentile on **full history** from 1996 (not 3-year rolling).

### Point 10a — G testable from 2007 / N/A hit rate

| | Detail |
|---|--------|
| **What we did** | G `show_hit_rate: false`; Claude prompt note. |
| **Results** | G row shows N/A in PDF. |
| **Production** | **Live** for N/A; footnote in Claude prompt only (not PDF appendix yet). |

### Point 10b — G→B cascade (MRU-01)

| | Detail |
|---|--------|
| **What we did** | `scripts/analyze_combo_g_b_cascade.py`; rescan **1,018 Fridays** (2007-01-01 to 2026-07-03). |
| **Results** | **3** B ACTIVE episodes; **0** G fires; **0/3** with prior G within 6 weeks. |
| **Production** | Analysis only; **not** in briefing appendix. |

**Divyanshu reference instances vs rescan:**

| Instance | His G→B lead | In automated rescan? |
|----------|--------------|----------------------|
| Pre-Aug 2015 | ~3 weeks | G not detected |
| Pre-Dec 2018 | ~4 weeks | G not detected |
| Pre-COVID Feb 2020 | ~3 weeks | G not detected |
| Apr 2025 | G only, no B | Not in rescan window |

### Point 10c — HY audit (MRU-02)

| Label | Date | HY bps | Full-history pctile | Dual OK? |
|-------|------|--------|---------------------|----------|
| Pre-Aug 2015 | 2015-08-21 | 618.0 | 82.5 | Yes |
| Pre-Dec 2018 | 2018-12-21 | 455.9 | 42.1 | No |
| Pre-COVID | 2020-03-20 | 850.0 | 97.2 | Yes |
| Oct 2022 bottom | 2022-10-07 | 427.1 | 35.4 | No |

| Check | Result |
|-------|--------|
| Any B fire in 375–400 bps? | **No** |
| Keep 400bps floor? | **Yes** (`keep_400bps`) |
| Dual gate in code? | **Yes** (`combo_detector.py`) |

### Point 10 — Old vs new

| Aspect | Old | New / spec | Status |
|--------|-----|------------|--------|
| G hit rate in table | 3M like others | N/A | Fixed |
| G→B empirical test | None | MRU-01 run | **Partial** (0% cascade) |
| HY at B fires | Not audited | MRU-02 run | Done |
| HY dual gate | Abs only (wrong units) | Abs + 80th pctile full history | Fixed in code |
| G/B date appendix in PDF | None | Requested | **Not built** (MRU-06) |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Of post-2007 B fires, how many had G within 6 weeks? | **Yes** | **0/3 (0%)** in rescan. **0** G fires in entire 2007–2026 scan (`mru01_mru02_results.json`). | **Doubt:** Divyanshu cites ~3–4 week G→B leads on canonical dates, but detector finds **zero G fires**. Should we relax G legs, backfill manually (MRU-06), or treat G as mechanism-only? |
| Any B fire with HY 375–400 bps? | **Yes** | **None** in audit. Recommendation: **keep_400bps**. | None. |
| Is dual HY (400 + 80th pctile full history) implemented? | **Yes** | Code in `combo_detector.py`; audit uses `daily_readings` (7,364 rows, 1997–2026). | **Doubt:** Oct 2022 canonical B (**427 bps**, **35.4th** pctile) **fails** dual gate. Dec 2018 (**456 bps**, **42.1st**) also fails. Keep rule or use rolling 3Y pctile (MRU-04)? |
| Is "G testable from 2007" in briefing? | **Partially** | In Claude prompt; **not** a visible PDF footnote yet. | **Doubt:** Should the PDF combo table include a static note under G? |
| Historical G/B/SPX bottom columns in PDF? | **No** | MRU-06 **TODO**. | **Doubt:** Divyanshu asked for date columns in briefing. Priority vs other open MRU work? |

---

## 13. Point 11 — Combo C fire and cancel logic (R-11)

**What the spec asks:**

**Fire:** CPI actual **>** consensus by **≥+0.2pp** (HOT surprise only). Cold CPI must **not** fire C.

**Cancel CPI leg:** On each Friday, use the **most recent confirmed CPI print**. If actual ≤ consensus → leg **PASSES**. If actual > consensus → leg **BLOCKED**. No pending state. WTI 4-Friday counter runs independently; resets if either leg fails that Friday.

**No PPI** in cancel logic (PPI narrative-only).

### Point 11 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Fire: `cpi_surprise >= 0.2`; cancel: `_governing_cpi_print()`; PPI removed from cancel path; `_combo_c_episode_start()` for week anchor. |
| **Results** | `test_combo_c_fire.py`, `test_combo_c_cancel.py` passed. May 2026 Fridays failed CPI HOT leg during MRU-03; Jun 12–Jul 3 passed. |
| **Production** | **Live**. |

### Point 11 — Old vs new

| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| C fire CPI | `abs(surprise) >= 0.2` (cold could fire) | HOT only: `>= +0.2pp` | Fixed |
| Cancel CPI | Week-paired / PPI fallback | Governing latest print; PASSES or BLOCKED only | Fixed |
| C week counter | Reset to Week 1 each Friday | Episode anchor after last WTI <10% | Fixed |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does C fire only on HOT CPI surprise? | **Yes** | `test_combo_c_fire.py`; cold surprise does not fire. | None. |
| Does cancel use governing CPI (not PPI)? | **Yes** | PPI removed from cancel; governing print logic in `combo_c_cancel.py`. | None. |
| Does cancel clock reset when CPI leg blocks? | **Yes** | May 22–Jun 5 failed HOT CPI; counter reset; Jun 12–Jul 3 completed (`MACRO_REPORT_UPDATE_ANALYSIS.md` Part 2). | None. |

---

## 14. Additional fix — Combo B HY units + dual gate

**What the spec asks (point 10):** HY ≥400bps and ≥80th pctile; VIX ≥25 and ≥80th pctile for full B ACTIVE.

### Combo B — Experiment status

| | Detail |
|---|--------|
| **What we did** | `_hy_oas_bps()` converts FRED % to bps; dual percentile legs added. |
| **Results** | `test_combo_b_hy_dual.py` passed. DB has **89 B WATCH**, **0 B ACTIVE** (pre-fix backfill). |
| **Production** | **Live** in detector. |

### Combo B — Old vs new

| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| HY threshold | Compared raw 2.74 to 400 (wrong) | `hy_bps = raw * 100` | Fixed |
| HY pctile gate | None | ≥80th full history | Fixed |
| VIX pctile gate | Abs only | Abs + ≥80th | Fixed |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Why zero B ACTIVE in DB? | **Partially** | Backfill used old rules; rescan finds 3 episodes but none match Divyanshu's 8 "confirmed" list cleanly. | **Doubt:** Should we re-backfill `combo_fires` with current detector before the next briefing audit? |
| Does Oct 2022 pass B under new rules? | **Yes** | **No**: 427 bps passes abs, **35.4th** pctile fails dual (`MRU-02`). | Same as MRU-04 doubt. |

---

## 15. Deliverables checklist (spec vs status)

| ID | Divyanshu point | Engine / test | Production nightly | MRU follow-up |
|----|-----------------|---------------|-------------------|---------------|
| R-01 | 1 E bearish HR | **Done** (15 tests) | **Live** | — |
| R-02 | 2 C CANCELLED | **Done** | **Live** | MRU-03 PASS |
| R-03 | 3 F start date | **Done** | **Live** | — |
| R-04 | 4 Narrative tone | **Done** | **Live** | Spot-check open |
| R-05 | 5 E legs | **Done** | **Live** | — |
| R-06 | 6 WALCL pctile | **Done** | **Live** | — |
| R-07 | 7 EASY MONEY | **Done** | **Live** | — |
| R-08 | 8 CFTC source | **Done** | **Live** | — |
| R-09 | 9 Horizons | **Done** | **Live** | — |
| R-10 | 10 G/B tests | **Partial** | G N/A live | MRU-01/02 done; MRU-05/06 open |
| R-11 | 11 C fire/cancel | **Done** | **Live** | — |
| — | B HY dual | **Done** | **Live** | MRU-04 open |

### MRU ticket status (`MACRO_REPORT_UPDATE_TODO.md`)

| ID | Task | Status |
|----|------|--------|
| MRU-01 | G→B cascade | **DONE** — 0/3 within 6w |
| MRU-02 | HY audit | **DONE** — keep_400bps |
| MRU-03 | C CANCELLED smoke test | **DONE** — 2026-07-03 |
| MRU-04 | HY dual vs Oct 2022 | **TODO** |
| MRU-05 | G detection audit | **TODO** |
| MRU-06 | Manual G/B/SPX table | **TODO** |

---

## 16. Recommended build order (from plan)

Already executed in this order (`MACRO_REPORT_UPDATE_PLAN.md`):

1. CONFIG + `combo_metadata.py`
2. Engine fixes (C, B, A, E, F)
3. Nightly integration (`nightly_run.py`)
4. Briefing/PDF (`briefing_renderer.py`)
5. Tests (15 passed)
6. Docs + MRU scripts

**Still to do:** MRU-04..06, briefing G/B appendix, optional `combo_fires` backfill reconcile.

---

## 17. Doubts to ask Rohit Sir (consolidated master list)

| # | Doubt to ask Rohit Sir | Evidence from status |
|---|------------------------|----------------------|
| 1 | Oct 2022 is a canonical Combo B date but **427 bps HY** only ranks **35.4th** pctile on full history, so the new dual gate blocks it. Keep full-history 80th rule, switch to rolling 3Y, or add canonical-date exceptions? | `MACRO_REPORT_UPDATE_ANALYSIS.md` MRU-02; MRU-04 TODO |
| 2 | Automated rescan found **0 G fires** in 1,018 Fridays (2007–2026) but Divyanshu cites G before B in Aug 2015, Dec 2018, COVID. Are G detection thresholds too strict, or is data missing for HY 4wk widening / VXTS? | MRU-01: 0 G; MRU-05 TODO |
| 3 | G→B cascade rate is **0/3 (0%)** in rescan vs Divyanshu's hypothesis that all 5 post-2007 B fires might have G within 6 weeks. Should we build manual episode table (MRU-06) before changing G spec? | `mru01_mru02_results.json` |
| 4 | `combo_fires` has **89 B WATCH**, **0 B ACTIVE**, **0 G** rows, but rescan finds 3 B episodes. Re-backfill DB with current detector? | `MACRO_REPORT_UPDATE_STATUS.md` |
| 5 | Should briefing PDF add G/B/SPX bottom date appendix and "G testable from 2007" footnote as Divyanshu requested in point 10? | MRU-06 TODO; Claude prompt only today |
| 6 | CFTC for Combo B/E still uses **156-week rolling** pctile in CONFIG while HY uses full history. Align CFTC to full history like HY? | Status "not yet ticketed" |
| 7 | E bearish hit rate **18.9% (12M)** is directionally correct now but still low. Show regime-conditional hit rates in PDF? | `runic_output_2026-06-09.json` |
| 8 | Internal JSON still uses `brave_fearful` key after EASY MONEY rename. OK for C++ consumer, or rename in next API version? | R-07 analysis |
| 9 | `test_combo_b_oct_2022.py` may not test full-history HY pctile gate. Update test to match MRU-02 finding? | Analysis Part 2 |
| 10 | Claude narrative tone (R-04): has anyone done a full read of post-fix PDF to confirm "commanding/dismal" are gone from body text? | Status: spot-check open |
| 11 | Smoke test left `combo_c_cancel.cancel_date=2026-07-03` in production DB. Reset on next real C episode or leave until natural rollover? | MRU-03 |
| 12 | Dec 2018 B-like stress: **456 bps**, **42.1st** pctile, fails dual gate. Same question as Oct 2022 for historical validation dates. | MRU-02 reference table |

---

## 18. Key artifact index

| File | Purpose |
|------|---------|
| `testing/macro_report_updates/Report update todo details.md` | Divyanshu's 11-point source spec |
| `testing/macro_report_updates/MACRO_REPORT_UPDATE_STATUS.md` | DONE/TODO snapshot |
| `testing/macro_report_updates/MACRO_REPORT_UPDATE_ANALYSIS.md` | Root cause, fixes, Part 2 MRU results |
| `testing/macro_report_updates/MACRO_REPORT_UPDATE_TODO.md` | MRU-01..06 tracker |
| `testing/macro_report_updates/MACRO_REPORT_UPDATE_PLAN.md` | Implementation phases |
| `testing/macro_report_updates/mru01_mru02_results.json` | G→B + HY audit numbers |
| `scripts/analyze_combo_g_b_cascade.py` | MRU-01/02 script |
| `testing/macro_report_updates/runic_briefing_2026-06-09.pdf` | Latest post-fix briefing |
| `macro_intelligence/output/runic_briefing_2026-07-03.pdf` | CANCELLED smoke test briefing |
| `src/macro_intelligence/engine/combo_metadata.py` | Per-combo horizons + bearish logic |

---

## 19. How this relates to work already done

**10 of 11** Divyanshu points are **live in production** nightly output (R-01 through R-09, R-11, plus Combo B HY dual). **Point 10 (R-10)** is **partial**: engine shows G as N/A and dual HY is coded, but empirical G→B validation failed (0 G fires), the HY dual gate conflicts with Oct 2022, and the requested G/B/SPX date appendix is not in the PDF yet. Three MRU tickets remain open (MRU-04..06). Fifteen unit tests passed at implementation time; PDF combo table layout was fixed separately on 2026-06-09.

---

*Understanding doc generated from `Report update todo details.md` + `MACRO_REPORT_UPDATE_STATUS.md` + `MACRO_REPORT_UPDATE_ANALYSIS.md` + `MACRO_REPORT_UPDATE_TODO.md`.*
