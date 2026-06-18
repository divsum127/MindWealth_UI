# Rohit Feedback Sectionwise Answers — Plain-English Understanding Guide

**For:** Anyone implementing macro regime v2 changes or preparing follow-ups for Rohit Sir  
**Source spec (questions):** `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_details.md`  
**Status / answers:** `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md` (prepared 2026-06-16)  
**Execution log:** `testing/macro_th_exp/testingv1_feedback/testingv4_status.md`  
**Purpose:** Explain what Rohit Sir asked, what experiments we ran to answer him, what the numbers show, and what is still open.

---

## Summary — experiments performed and outcomes

Brief map of every test run to answer the 32 feedback blocks. **28 answered with data; 4 still pending.**

| # | Experiment / query | What we did | Outcome |
|---|-------------------|-------------|---------|
| **§1** | **Combo horizons (not uniform 3M)** | Re-queried `combo_fires` + `forward_returns` at each combo’s validated horizon with PW columns | **B** 3M: n=89, 79.8% hit, +2.53pp excess. **F** 6M: n=704, 78.8%, +0.54pp. **E** 12M: n=507, 18.9% bear hit, +0.93pp. **D** 5D: n=452, 38.5% bear, −0.34pp. **C** 6M: n=**4** only. **G**: no return table. Old PDF uniform 3M was wrong for D/E/F. |
| **§2 / B2** | **History windows + dual pctile** | Audited CONFIG vs Rohit’s June 11 correction; checked `daily_readings` for unconditional + regime pctile | **14,457** rows with both pctiles; **0** fallbacks. VIX/HY/VXTS = **full** expanding (not rolling). WALCL/WTI/CNH/CPI/TWY = **rolling_3y**. Old B4 FAIL was obsolete spec. |
| **T2** | **9-state liquidity SPX returns** | Joined `macro_regime_log_v2` → `combo_fires` → `forward_returns` at 1M/3M/6M/9M/12M | **NEUTRAL_IMPROVING** strongest 3M (91.3% up). **TIGHT_FLAT** weakest (48.1% up 3M, −8.52% avg). **EASY_TIGHTENING** strong 12M (94.9% up, +17.18%). |
| **T3** | **TIGHT_* named combo fires** | All fires in TIGHT_FLAT / TIGHT_IMPROVING / TIGHT_TIGHTENING | **46** named fires, **all Combo A**. GFC cluster 2008–2009. No B/C/D/E/F/G in TIGHT_*. |
| **T4 / T11** | **Combo E multi-horizon + CAPE buckets** | 6M–18M in 3M steps (T11); CAPE buckets at 6M/12M | Bear hit 19.7%→14.5% (6M→18M); **keep 12M primary** (18.9% bear, n=507). EXTREME CAPE weakest. |
| **T5** | **Geo overlay combo slice** | All combos A–G on non-neutral geo dates (CRISIS + ELEVATED_RISK) | **70** named-combo rows on **46** non-neutral dates. Thin per cell but informative (e.g. CRISIS Apr 2020 A +27.77% 3M). Recommend **2-state geo** (NEUTRAL / ELEVATED). |
| **T6** | **TWY_ROC band sweep** | 7 bands on calendar Fridays + combo-fire dates; Apr 2025 anchor | ±0.30pp bands distinguish direction. **Neutral** TWY beats DOVISH for 3M returns. Apr 7 2025: −0.55pp DOVISH before legacy fed caught up. |
| **T10** | **Yield curve inversion episodes** | T10Y2Y < 0 for ≥4 consecutive weeks, 1990–2026 | **5 episodes** (not just Oct 2022). Longest: **2022–2024**, 112 weeks, −106 bps trough. |
| **A1** | **Fed cycle / PIVOTING / 9 vs 4 liquidity** | Shadow backfill counts; collapse rules documented | **PIVOTING n=27** (1.4%) — artefact of v2 collapse; do **not** merge into EASING. **Store 9 states**, collapse to **4** for thin analytics slices. |
| **A3** | **CAPE triple storage** | Confirmed 3 representations in DB; Combo E by CAPE bucket | Level beats velocity by **+0.40pp** preliminary. Triple storage **confirmed**. |
| **B1 ablation** | **TWY_ROC within Combo A** | Post-hoc slice on Combo A dates | TWY DOVISH subset **worse** bear framing (71.4% “hit” wrong direction). TWY excluded from combo **firing** by design. |
| **C** | **HMM reframe** | K-means prototype vs walk-forward scaffold | Wrong test was 3M hit-rate overlay (−1.2pp B). Correct test: **regime detector** with walk-forward lead. Scaffold done; **median lead 0w** — tuning needed. |
| **13k fires** | **Generic combo_fires explanation** | Counted named vs unnamed | **1,893** named A–G; **13,089** unnamed pair fires (failed naming gates). Not a bug. |

**One-line takeaway:** Rohit’s feedback pushed us to fix **wrong horizons**, prove **9-state liquidity** with full SPX tables, sweep **TWY_ROC** and **inversions**, and clarify **CAPE / geo / HMM** framing. Combo E **6M–18M horizon sweep (T11)** confirms **12M primary**. **i3 cheatsheet compare**, **WALCL FM threshold sweep**, and **production prompt updates** remain open.

**How to read the experiment tables:** Every Q&A table has a **Doubts to ask Rohit Sir** column. These are open questions raised by the backtest, not sign-off requests.

---

## 1. What is this document?

Rohit Sir reviewed the **Macro Regime Threshold Experiments Report** (June 2026) and left **32 TODO blocks** in `feedback_sectionwise_details.md` — questions about horizons, liquidity states, CAPE, geo, TWY_ROC, HMM, and more.

`feedback_sectionwise_answers.md` is Divyanshu’s point-by-point response with inline tables. **testingv4** ran six DB queries (T2–T6, T10) and patched the main report.

Your job when reading this guide: understand **what was asked**, **what we measured**, **whether CONFIG/production should change**, and **what to ask Rohit Sir** next.

---

## 2. Core concepts (read this first)

| Term | Simple meaning |
|------|----------------|
| **Validated horizon** | The forward-return window that matches how a combo is meant to work (e.g. Combo E = slow valuation → **12M**, not 3M). |
| **PW (probability-weighted) expected return** | `(hit% × avg win) + ((1−hit%) × avg loss)` — blends frequency and size of wins/losses. |
| **Excess** | PW expected minus a drift benchmark (e.g. +2.5% at 3M). |
| **combo_fires** | Database table of dates when a named combo (A–G) or unnamed pair fired. |
| **liquidity_v2** | 9-state label: **LEVEL** (EASY / NEUTRAL / TIGHT from NFCI ±0.3) × **DIRECTION** (IMPROVING / TIGHTENING / FLAT from WALCL MoM ±0.3%). |
| **Shadow** | Code ran and wrote `macro_regime_log_v2`, but nightly PDF still uses **legacy** labels — not live for users yet. |
| **unconditional_pctile** | Variable rank vs full history — used for **combo detection**. |
| **regime_pctile** | Rank within current **fed_cycle** — used for **conviction** modifier; falls back if n<50. |
| **TWY_ROC** | 8-week change in 2-year Treasury yield (DGS2) — regime classifier, **not** a combo leg. |
| **Generic / unnamed fires** | ~13k pair events that did not pass naming gates (≥5 fires, ≥80% hit, mechanism) — not 13k Combo B’s. |
| **i3 Invest cheatsheet** | Rohit’s external reference table for combo hit rates — **not in repo**; side-by-side compare blocked. |
| **HMM (hidden Markov model)** | Regime **state detector** (Risk-On/Off), not a tool to lift one combo’s 3M hit rate by 2pp. |

---

## 3. §1 — Validated horizons per combo

**What the spec asks:** Stop showing every combo at 3M. Use B=3M, F=6M, C=6M primary, D=5D, E=12M, G=no returns.

### §1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | SQL on `combo_fires` + `forward_returns` at specified horizons |
| **Results** | See summary table §1 above |
| **Production** | Report PDF updated; combo engine horizons unchanged unless CONFIG edited |

#### §1 — Old vs new

| Aspect | Old report | Corrected | Status |
|--------|------------|-----------|--------|
| Combo E horizon | 3M shown | 12M primary | ✅ Answered |
| Combo D | 3M | 5D | ✅ Answered |
| Combo F | 3M only | 6M primary, 3M secondary | ✅ Answered |
| Combo G | Hit rate shown? | Timing warning only | ✅ No return table |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Are per-combo horizons now correct in the data? | **Yes** | Full PW table in answers §1: B n=89 +2.53pp 3M; F n=704 +0.54pp 6M; E n=507 +0.93pp 12M; D n=452 −0.34pp 5D; C n=4 at 6M (too small). | **Doubt:** Combo C has only **n=4** fires — should we keep 6M as primary or wait for more energy-shock episodes before locking horizon? |
| Do our hit rates match i3 Invest cheatsheet? | **Deferred** | Combo B: we show **79.8%** on **89** WATCH rows vs your **~87.5%** on **8** strict 3-of-3 confirmed instances. | **Doubt:** Please reshare i3 cheatsheet numbers so we can add a diff column — DB counts partial-leg WATCH, not only CONFIRMED 3-of-3. |

---

## 4. §2 / B2 — History windows and dual percentiles

**What the spec asks:** Structural variables = full expanding history. Flow/ROC = 3-year rolling. Store both unconditional and regime-conditioned percentiles daily.

### §2 — Experiment status

| | Detail |
|---|--------|
| **What we did** | CONFIG audit + row counts on `daily_readings` |
| **Results** | All 14 variables match corrected June 11 spec; 14,457 dual-pctile rows |
| **Production** | CONFIG already correct; B4 JSON still shows stale FAIL vs old expected map |

#### §2 — Old vs new

| Variable class | Examples | Window | CONFIG status |
|----------------|----------|--------|---------------|
| Structural / level | VIX, HY, VXTS, CAPE, CURVE, NFCI, GSR | Full expanding | ✅ |
| Flow / ROC | WTI, CNH, WALCL MoM, CPI surprise, TWY_ROC | 3-year rolling | ✅ |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Are VIX/HY/VXTS on rolling 3y? | **No** (corrected) | June 11 note: they are **structural** → `full` in CONFIG. Old audit FAIL was wrong expectation. | None — aligned with your correction. |
| Is dual pctile storage live? | **Yes** | 14,457 rows both fields; 0 unconditional-only; 0 regime fallbacks triggered yet. | **Doubt:** When regime cells go &lt;50 obs in live data, should we log fallback events to Slack or only DB? |

---

## 5. A1 — Fed cycle, PIVOTING, 9 vs 4 liquidity states

**What the spec asks:** TIGHTENING includes holding tight; PIVOTING ≠ EASING; store 9 liquidity states, collapse to 4 only for analytics.

### A1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Shadow backfill frequency table; documented collapse rules for NEUTRAL_FLAT / EASY_FLAT |
| **Results** | TIGHTENING 763 (40.1%), EASING 727 (38.2%), EASY 384 (20.2%), PIVOTING 27 (1.4%) |
| **Production** | 9-state storage in shadow; briefing still legacy |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Should PIVOTING merge into EASING? | **No** | Withdrawn — pivot is direction-change bucket; n=27 is v2 collapse artefact (`CUTTING_EARLY` only). Will re-label to match Addendum. | **Doubt:** With PIVOTING **n=27**, widen definition or accept as rare tail with mechanism-only evidence? |
| 9 states storage vs 4 for analytics? | **Yes** | Store **9** (39.2% of Fridays are EASY_FLAT alone). Collapse to **4** for hit-rate tables when slices too thin. | **Doubt:** For NEUTRAL_FLAT collapse, confirm NFCI-sign split vs keeping NEUTRAL as third level in classifier prompt only. |

---

## 6. A3 — CAPE triple storage and Combo E buckets

**What the spec asks:** Confirm three CAPE representations; define moderate vs extreme using 5Y/10Y distributions; show Combo E impact.

### A3 — Experiment status

| | Detail |
|---|--------|
| **What we did** | T4 query; CAPE bucket table at 6M/12M |
| **Results** | MODERATE (25–30): 85.8% up 6M historically but **pre-2018 only**. EXTREME &gt;35: weakest (70.9% up 6M). Level beats velocity +0.40pp. |
| **Production** | Triple storage confirmed in pipeline |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| What is “moderate” CAPE for Combo E? | **Partial** | MODERATE = CAPE 25–35 from 5Y/10Y dist; median ~28–32. Modern fires all HIGH/EXTREME since 2018. | **Doubt:** Should Combo E sizing use **EXTREME-only** fires now that MODERATE bucket has zero modern episodes? |
| Regime score / transition probability tests? | **Deferred** | Documented in `Additional_email.md`; Section D validation **PENDING**. HMM scaffold done. | **Doubt:** Priority order — regime score validation vs 18M forwards vs production geo prompt? |

---

## 7. A4 — Geo overlay

**What the spec asks:** Move to 2-state geo; show which combos were tested on elevated geo dates.

### A4 — Experiment status

| | Detail |
|---|--------|
| **What we did** | T5 query; Bridgewater/Druckenmiller framing for 2-state prompt |
| **Results** | NEUTRAL 97.6%; ELEVATED_RISK 1.3%; CRISIS 1.1%. 70 combo rows on 46 non-neutral dates. |
| **Production** | Still **3-state** classifier — prompt update pending |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does geo slice change combo performance? | **Partial** | Not a reliable **filter** (n&lt;10 per cell) but row data useful (Ukraine 2022 E negative; Apr 2020 A bottom +27.77%). | **Doubt:** Adopt proposed 2-state prompt (NEUTRAL / ELEVATED, no CRISIS tier) for production classifier? |
| Which combos on geo dates? | **Yes** | Full table: CRISIS hits A/D/E/F; ELEVATED_RISK hits B/D/E/F — see answers §A4. | None — data delivered. |

---

## 8. A6 — Liquidity v2 / WALCL direction

**What the spec asks:** Define v2; SPX tables 1M–12M per band; show TIGHT_* data; don’t dismiss small n; WALCL threshold sensitivity.

### A6 — Experiment status

| | Detail |
|---|--------|
| **What we did** | T2 (9-state returns), T3 (TIGHT_* fires), FM-band slices, WALCL ±0.3% distribution |
| **Results** | T2 table: 9 states × 5 horizons. T3: 46 named TIGHT_* = all Combo A. FM moderate: EASY_IMPROVING **83.3%** vs EASY_TIGHTENING **65.2%** (n=30 vs 23). |
| **Production** | liquidity_v2 in shadow only |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| What is liquidity v2? | **Yes** | 3×3 grid: NFCI ±0.3 for level, WALCL MoM ±0.3% for direction → `{LEVEL}_{DIRECTION}`. | None. |
| Do we have 1M–12M per state? | **Yes** | T2 table: e.g. NEUTRAL_IMPROVING 91.3% up 3M; TIGHT_FLAT 48.1% up 3M, −8.52% avg. | **Doubt:** TIGHT_FLAT n=52 fires — treat as stand-alone bearish context in briefing copy? |
| WALCL 0.1 / 0.2 / 0.3 FM hit-rate sweep? | **Not yet** | Friday **distribution** shown at three gates; formal FM-event hit sweep **PENDING**. | **Doubt:** Should next pass sweep ±0.1/0.2/0.3 for **FM event** hit rates, not just label counts? |
| All combos A–G vs your table? | **Partial** | All 7 tested at validated horizons; **PENDING** i3 side-by-side. B: 89 WATCH vs 8 strict confirmed. | **Doubt:** Should reporting separate **WATCH** vs **CONFIRMED 3-of-3** for Combo B hit stats? |

---

## 9. B1 — TWY_ROC (variable #14)

**What the spec asks:** Validate ±0.30pp bands; explain 13,089 fires; test TWY within Combo A if excluded from combos.

### B1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | T6 band sweep; Apr 2025 anchor; Combo A ablation (`X_testingv2_ablations.json`) |
| **Results** | 7 bands on calendar + combo-fire dates. Neutral TWY best 3M on combo dates (84.3% up). 13,089 = unnamed pair fires. TWY DOVISH on Combo A: worse bear slice. |
| **Production** | TWY excluded from combo firing logic |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Did TWY call Apr 2025 bottom early? | **Yes** | Apr 7 2025: −0.55pp DOVISH while legacy fed still tightening/pausing. | None. |
| Are ±0.30pp bands validated? | **Partial** | Direction correct; DOVISH bands do **not** beat Neutral for excess 3M return. | **Doubt:** Use TWY primarily as **regime label**, not as return predictor — agree? |
| What are 13,089 fires? | **Yes** | Unnamed 2–3 variable pair fires failing naming gates; **1,893** named A–G total. | None. |

---

## 10. B3 — Combo E maturities

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Test 6–18M for Combo E? | **Yes** | T11 sweep: bear hit 19.7% (6M), 18.9% (12M), 14.5% (18M); n_mature 507→413. **Keep 12M primary** — stable bear framing, full sample. | **Doubt:** Persist spx_15m/spx_18m in `forward_returns` for nightly pipeline, or on-demand Yahoo only? |

---

## 11. C — HMM (regime detector, not hit-rate booster)

**What the spec asks:** Reframe HMM per Rohit’s June 11 note — not a 3M combo overlay.

### C — Experiment status

| | Detail |
|---|--------|
| **What we did** | K-means prototype (wrong test); `hmm_walk_forward.py` scaffold |
| **Results** | Prototype hurt B/D hit rates in-sample. Walk-forward 2015–2025: **median lead 0w** — needs tuning |
| **Production** | December target deferred; live emission cron wired |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Should HMM improve Combo B 3M hit rate? | **No** | Wrong metric. Correct test: does Risk-Off posterior **precede** bearish combo fires by 2+ weeks out-of-sample? | **Doubt:** Is ~Dec 2026 still the right HMM go-live if walk-forward lead stays 0w after tuning? |

---

## 12. F2 — INVERTED curve definition

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Only Oct 2022 inversion? | **No** | **5 episodes** 1990–2026; longest 2022–2024 (112 wks, −106 bps). T10 query in report F2. | None — full episode table delivered. |
| What is “shadow”? | **Yes** | Validated in `macro_regime_log_v2`, **not** on production nightly PDF yet. | **Doubt:** Which shadow labels (INVERTED, liquidity_v2, geo_v2) promote to production first? |

---

## 13. Deliverables checklist (feedback vs status)

| ID | Rohit ask | Experiment / answer | Production |
|----|-----------|---------------------|------------|
| §1 | Per-combo horizons | ✅ PW table | Report fixed |
| §2 | Window rules + dual pctile | ✅ CONFIG + counts | Live CONFIG OK |
| T2 | 9-state SPX 1M–12M | ✅ 14,878 fire joins | Shadow data |
| T3 | TIGHT_* all observations | ✅ 46 named Combo A | In report A5 |
| T4 / T11 | Combo E 6M–18M + CAPE buckets | ✅ n=508 | T11 JSON + report B3 |
| T5 | Geo combo slice | ✅ 70 rows | In report A4 |
| T6 | TWY full band sweep | ✅ 1,098 fire dates | In report B1 |
| T10 | Inversion episodes | ✅ 5 episodes | In report F2 |
| — | i3 cheatsheet compare | ⏳ Blocked | Need reference file |
| — | 18M forward returns in DB | 🔄 Optional | T11 computes via Yahoo; schema extension deferred |
| — | WALCL 0.1/0.2/0.3 FM sweep | ⏳ Distribution only | Next pass |
| — | 2-state geo prompt | ⏳ Proposed | Classifier unchanged |
| — | Regime score Section D tests | ⏳ Documented | Not run |

---

## 14. Recommended follow-up order

1. Rohit Sir shares **i3 Invest cheatsheet** → add diff column for combos A–G.
2. Decide **WALCL FM threshold sweep** (0.1/0.2/0.3) on event hit rates.
3. Optional: persist **spx_15m/spx_18m** in `forward_returns` (T11 already computes via Yahoo).
4. Production prompts: **2-state geo**, **9-state liquidity** wording, **PIVOTING** label fix.
5. HMM walk-forward tuning before December target.
6. Cross-link to **testingv2** threshold validation (separate workstream) for CONFIG RARE/EXTREME — only **WTI down** flagged there.

---

## 15. Doubts to ask Rohit Sir (consolidated master list)

| # | Doubt to ask Rohit Sir | Evidence from status |
|---|------------------------|----------------------|
| 1 | Please reshare **i3 Invest cheatsheet** hit rates for A–G so we can diff against DB (B: 89 WATCH vs 8 confirmed). | Answers §1, §A6.f — compare **PENDING** |
| 2 | Combo B stats: report **WATCH** vs **CONFIRMED 3-of-3** separately? | B n=89 all WATCH; strict gate n≈8–9 in testingv2 |
| 3 | Adopt **2-state geo** prompt (NEUTRAL / ELEVATED)? | 97.6% NEUTRAL; 3-state still in production |
| 4 | **Store 9 liquidity states** in production with **4-state collapse** for analytics only? | EASY_FLAT 39.2% of Fridays; FM slices n=6–30 |
| 5 | **PIVOTING n=27** — widen fed collapse or keep rare tail? | 1.4% of sample; merge-into-EASING withdrawn |
| 6 | Combo E: size on **EXTREME CAPE only** now that MODERATE has no modern fires? | MODERATE 127 fires all pre-2018 |
| 7 | Persist **spx_15m/spx_18m** in DB for nightly vs on-demand Yahoo (T11 done)? | 18M bear hit 14.5%, n=413 — 12M primary validated |
| 8 | Run **WALCL ±0.1/0.2/0.3** on FM **event** hit rates (not just Friday counts)? | Formal sweep **PENDING** |
| 9 | Promote which **shadow** labels to production PDF first? | liquidity_v2, geo_v2, INVERTED all shadow |
| 10 | HMM: still **Dec 2026** target if walk-forward **median lead 0w**? | `D_hmm_walk_forward.json` scaffold |
| 11 | **TWY_ROC** as regime label only (not return predictor)? | Neutral band beats DOVISH at 3M on combo dates |
| 12 | Priority: **regime score** Section D tests vs geo prompt vs 18M schema? | Multiple **PENDING** in A3 |
| 13 | Combo C **n=4** — lock 6M horizon or wait for more oil shocks? | 0% hit both 3M and 6M in tiny sample |
| 14 | **TIGHT_FLAT** (n=52) as explicit bearish liquidity callout in briefing? | 48.1% up 3M, −8.52% avg |
| 15 | Align **Combo B HY leg** production AND vs CONFIG OR? | testingv2 found n=0 before OR fix |

---

## 16. Key artifact index

| File | Purpose |
|------|---------|
| `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_details.md` | Rohit’s 32 TODO / questions |
| `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md` | Full answers + inline tables |
| `testing/macro_th_exp/testingv1_feedback/Macro_Regime_Threshold_Experiments_Report_2026-06-09.md` | Main report (v4 inline edits) |
| `testing/macro_th_exp/testingv1_feedback/testingv4_status.md` | T2–T10 execution log |
| `testing/macro_th_exp/testingv1_feedback/Additional_email.md` | Regime score, transition probability notes |
| `macro_intelligence/data/runic.db` | combo_fires, forward_returns, macro_regime_log_v2 |
| `macro_intelligence/analysis/regime_v2_experiments/*.json` | HMM, ablations, combo sweeps |
| `testing/macro_th_exp/testingv2/threshold_validation_report.md` | Separate CONFIG threshold validation (WTI, etc.) |

---

## 17. How this relates to work already done

**testingv4** answered Rohit’s report feedback with six DB queries and prose fixes. **testingv2** (threshold validation) is a **separate** experiment that sweeps RARE/EXTREME CONFIG cutoffs for all 12 variables — see `Threshold_Validation_v2_Understanding.md` in `testingv2/understanding_and_research/`. Together: v4 = “are we measuring and explaining regimes correctly?”; v2 = “are our threshold numbers optimal?”

Production nightly briefing still uses **legacy** labels for several dimensions; shadow tables hold the v2 truth until promotion decisions above are made.

---

*Understanding doc generated from `feedback_sectionwise_details.md` + `feedback_sectionwise_answers.md` + `testingv4_status.md`.*
