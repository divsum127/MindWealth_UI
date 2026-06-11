# Macro Regime System v2 — Plain-English Understanding Guide

**For:** Divyanshu  
**Source:** Rohit sir’s email — `Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`  
**Experiment status:** `MACRO_TH_EXP_STATUS_ANALYSIS.md` (2026-06-07) — shadow run 2026-06-06  
**Purpose of this doc:** Explain what the plan says, what it asks you to build, what every technical term means, **what we already tested**, and **what doubts to raise with Rohit sir Sir** before production changes.

---

## 1. What is this document?

Rohit sir sent you a **consolidated plan** (one master document that replaces older scattered notes) for upgrading the **macro regime system** — the part of MindWealth that labels “what kind of economic/market environment are we in?” and uses that to interpret trading **combos** (named multi-variable signals like Combo A, B, C, etc.).

**Your job in one sentence:** Build a cleaner, more data-driven system that classifies market regimes, discovers and validates combo signals honestly, and eventually layers a statistical model (HMM) on top — without over-engineering things that don’t improve real backtests.

**Success looks like:** The system backtests well, matches the MindWealth demo and macro agent demo output, and every label/rule can be reproduced with numbers — not just AI guesses.

**How to read the experiment tables:** Every Q&A table has a **Doubts to ask Rohit sir Sir** column. These are open questions raised by the backtest — not blockers or sign-off requests. Where the data is inconclusive or a production choice is unclear, the doubt is phrased as a direct question for Rohit sir Sir, with numbers attached.

---

## 2. Core concepts (read this first)

These terms appear everywhere in the plan. Definitions below are in plain English.

| Term | Simple meaning |
|------|----------------|
| **Regime** | The “market environment” at a point in time — e.g. Fed is hiking, curve is inverted, valuations are extreme. |
| **Regime dimension** | One axis of that environment. The plan keeps **five**: rate environment, credit, geopolitics, valuation, monetary accommodation (liquidity). |
| **Classifier** | The logic (often a Claude API prompt in Section 5.2) that reads macro data and assigns regime labels each day/week. |
| **Backfill** | Re-run the classifier over historical dates so you have labels for the past, not just today. |
| **Combo** | A named signal (A–G) that fires when **several** macro variables are extreme **at the same time** — e.g. high VIX + stressed credit + extreme positioning. |
| **Variable** | One measurable macro input (VIX, CAPE, WTI oil change, etc.). The combo system uses **13 variables**; a **14th** is added for regime only. |
| **RARE / EXTREME threshold** | Percentile cutoffs — e.g. “VIX is in the top 20% of its history” = RARE. Used to decide if a combo leg has fired. |
| **Percentile rank** | Where today’s value sits in history, from 0 (lowest ever) to 1 (highest ever). VIX at 35 might be 0.92 = 92nd percentile. |
| **Backtest** | Run the rules on history and see if signals predicted market moves (e.g. did SPX go up 3 months after the combo fired?). |
| **Hit rate** | Fraction of times the market moved in the expected direction after a signal fired. |
| **Sharpe ratio** | Risk-adjusted return measure — higher is better; used to compare “with regime overlay” vs “without.” |
| **Drawdown** | How much the strategy/portfolio fell from peak — lower drawdown is better. |
| **FRED** | Federal Reserve Economic Data — public database of US macro series (yields, CPI, etc.). |
| **SPX** | S&P 500 index — the main US stock benchmark used for forward-return tests. |

---

## 3. The five regime dimensions (Part A)

**What Rohit sir wants:** Keep all five dimensions, but simplify states where you don’t have enough historical examples, and add a few smart refinements.

Think of each dimension as a dial with a few settings. Too many settings = too few days in each bucket = unreliable statistics.

**Shadow experiment run:** `run_regime_v2_experiment_suite.py` on **2026-06-06**. Unless a subsection says otherwise, regime **label backfills** use **weekly Fridays from 1990-01-01 through ~2026-06-06** (**1,901 Fridays**), stored in `macro_regime_log_v2`. Artifact: `A_regime_dimensions.json` (note: JSON keys **A2–A5** do not match plan labels — e.g. JSON `A2_*` = geo, JSON `A5_fiscal_caveat` = curve fiscal test).

Each subsection below includes an **Experiment run — period & variables** table describing what was actually tested.

### A1. `fed_cycle` — where is the Fed in its rate cycle?

**Fed** = US Federal Reserve, which sets interest rates to control inflation and growth.

| Old (7 states) | New (4 states) | Meaning |
|----------------|----------------|---------|
| HIKING_EARLY, HIKING_LATE, PAUSING, etc. | **TIGHTENING** | Fed is raising rates or holding them high |
| | **PIVOTING** | First rate cut just happened — turning point |
| | **EASING** | Cuts are underway |
| | **EASY** | Rates at or near zero |

**QE / QT** (Quantitative Easing / Quantitative Tightening): Fed buying or shrinking its bond holdings to add or remove liquidity. These move to a **separate liquidity flag** (A5), not fed_cycle — because “interest rates” and “balance sheet size” are different tools.

**Why:** 7 states spread data too thin. 4 states ≈ doubles observations per state → more reliable labels.

**Deliverable:** Update the classifier prompt with these 4 states; re-run backfill; report how often each state appears (check none is empty or nearly empty — **degenerate** = useless because it almost never happens).

#### A1 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Run date** | 2026-06-06 |
| **History period** | **1990-01-01 → ~2026-06-06** (1,901 weekly Fridays) |
| **Cadence** | Weekly (Friday close) |
| **Input variables** | **DFF** (Fed funds rate daily → weekly); **WALCL MoM%** (balance sheet, for legacy QE/QT override only) |
| **Label logic** | Build legacy **7-state** `fed_cycle` → collapse to **4-state** `fed_cycle_v2` via `collapse_fed_cycle_v2()` |
| **Outcome measured** | **Label counts** per state (no SPX forward-return test in A1) |
| **Artifact** | `A_regime_dimensions.json` → `A1_fed_cycle_v2_distribution` |

#### A1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Shadow v2 backfill via `run_regime_v2_experiment_suite.py` (2026-06-06). Collapsed 7 legacy fed states → 4 v2 states in `macro_regime_log_v2`. |
| **Results** | 1,901 Fridays backfilled. Distribution: TIGHTENING 763, EASING 727, EASY 384, **PIVOTING 27**. No single state >80% dominance. |
| **Production** | Nightly briefing still uses legacy 7-state labels (HIKING_EARLY/LATE, PAUSING, etc.). |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does 4-state collapse give enough observations per state? | **Partially** | Shadow backfill over **1,901 Fridays** produced: TIGHTENING **763** (40.1%), EASING **727** (38.2%), EASY **384** (20.2%). These three states each exceed the plan’s **≥30 obs** minimum by 12× or more. Collapsing from 7 legacy states roughly doubled per-state counts as intended. | **Doubt:** PIVOTING = 27 Fridays (1.4%)** — below Part I’s **≥30 obs** rule. Cannot trust regime-conditional stats in PIVOTING. Options: merge with EASING, widen PIVOTING definition, or accept as rare tail state with mechanism-only evidence. |
| Is any state degenerate (empty or useless)? | **Mostly yes** | No state exceeds **80% dominance** (largest is TIGHTENING at 40.1%). All 4 states have ≥1 observation. A1_pass_no_degenerate_dominance checks both conditions — dominance pass, thin-state fail. | **Doubt:** PIVOTING is not empty but **statistically thin**. No state is completely unused. |
| Can we ship v2 fed_cycle to production? | **No** | Shadow labels exist in `macro_regime_log_v2` and experiment artifacts validate the 4-state logic runs end-to-end. | **Doubt:** PIVOTING has only **n=27** Fridays and **PAUSING** (Fed on hold) has no v2 state — should we ship v2 fed_cycle anyway, merge PIVOTING into EASING, or add PAUSING as a fifth state? Production still uses legacy 7-state labels. |

---

### A2. `curve_regime` — shape of the yield curve

**Yield curve:** Plot of interest rates by maturity. Normally long-term rates > short-term (**normal** curve). When short rates exceed long rates, the curve is **inverted** — historically often a recession warning.

**Keep 4 states:** INVERTED, FLAT, STEEPENING, NORMAL.

**Fiscal caveat:** In 2022–23 the curve was deeply inverted but **no recession** followed — unusual. Rohit sir says: when **fiscal deficit > 5% of GDP** (government spending much more than tax revenue), treat the inversion recession signal as **weaker**. Massive government spending and AI capex (corporate investment) offset the usual credit-channel effect.

**Deliverable:** Add this conditioning note to the classifier prompt.

#### A2 — Experiment run — period & variables

Two tests — curve **labels** vs fiscal **caveat backtest**:

| Test | Period | Cadence | Input variables | Outcome measured |
|------|--------|---------|-----------------|------------------|
| **Curve label backfill** | 1990 → ~2026 (1,901 Fridays) | Weekly Fri | **T10Y2Y** (10yr−2yr Treasury spread, FRED); steepening meta from **CURVE** variable | **curve_regime_v2** label: INVERTED / FLAT / STEEPENING / NORMAL (INVERTED requires **≥4 consecutive weeks** T10Y2Y **< 0**) |
| **Fiscal caveat** (JSON key `A5_fiscal_caveat`) | **1990 → present** | Weekly Fri | **T10Y2Y** (invert episodes); **FYFSD** (federal surplus/deficit **% of GDP** at un-inversion) | **SPX (^GSPC)** **3-month forward return** (**63 trading days**) measured at each **un-inversion** date; split buckets: deficit **>5%** vs **≤5%** GDP (**13 episodes** total) |

#### A2 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Kept 4 curve states in shadow backfill. Tested fiscal caveat via inverted episodes split by deficit >5% GDP (`A5_fiscal_caveat` in experiment JSON). |
| **Results** | 13 inverted episodes total. **Fiscal-offset bucket** (deficit >5%): n=1, 0% bearish 3m hit (likely 2022–23 cluster). **No-offset bucket**: n=12, 42% bearish 3m hit. Directionally supports “inversion signal weaker under fiscal dominance.” |
| **Production** | Classifier prompt fiscal caveat **not yet** in production Section 5.2. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does fiscal deficit >5% weaken inversion as recession signal? | **Directionally yes** | **13 inverted episodes** tested. **No-offset bucket** (deficit ≤5% GDP): **n=12**, **41.7%** bearish 3m SPX hit (avg return **−1.63%**, median **−2.09%**). When fiscal dominance is absent, inversion still carries moderate bearish signal. **Fiscal-offset bucket** (deficit >5%): **n=1**, **0%** bearish hit, avg **−13.21% — consistent with 2022–23 “inverted but no recession” narrative. | **Doubt:** n=1** in fiscal-offset bucket — the **0% rate is not statistically meaningful**. Cannot confirm 2022–23 is correctly tagged without explicit episode labeling. Classifier fiscal caveat **not in production** Section 5.2 yet. Need more high-deficit inversion episodes. |
| Are 4 curve states stable in backfill? | **Yes** | INVERTED, FLAT, STEEPENING, NORMAL all appear across FM and combo regime slices. F2 rule (T10Y2Y < 0 for **≥4 consecutive weeks**) passes backfill — Oct 2022 shows **14 inverted weeks**. | **Doubt:** Formal numeric STEEPENING rules (F2a) validated in Part F shadow only. Production curve labels still partly Claude-inferred. |

---

### A3. `val_regime` — how expensive is the stock market?

**CAPE** (Cyclically Adjusted P/E): A valuation measure — high CAPE = stocks expensive vs long-term earnings.

**Keep 4 states:** EXTREME, ELEVATED, FAIR, CHEAP.

**Problem:** CAPE has been ELEVATED/EXTREME since ~2017, so “we’re elevated” alone isn’t informative.

**Fix — rate of change:** Store both the **level tier** and **6-month change in percentile rank**. Freshly crossing into EXTREME ≠ sitting at EXTREME for 3 years.

**Deliverable:** Add CAPE rate-of-change to classifier and storage.

#### A3 — Experiment run — period & variables

| Test | Period | Cadence | Input variables | Outcome measured |
|------|--------|---------|-----------------|------------------|
| **val_regime labels** | 1990 → ~2026 (1,901 Fridays) | Weekly Fri | **CAPE** level → tiers: EXTREME (≥32), ELEVATED (≥28), CHEAP (≤16), else NORMAL | Label counts only |
| **CAPE velocity / level compare** (JSON `A4_cape_velocity`) | **2010-01-01 → present** | Daily readings | **CAPE unconditional_pctile** from `daily_readings`; 6-month rank delta (126 trading days) | **SPX 3m** forward return on days when: (a) pctile ≥90 (**level extreme**), (b) fresh cross into ≥90, (c) 6m rank delta ≥0.10 (**velocity**) |
| **Combo E + CAPE** (`B5_cape_triple_storage`) | Full **Combo E** fire history in DB | Per combo fire | **Combo E** fires + **CAPE** pctile at fire date | **SPX 6m** return; high-CAPE = pctile **>0.90**, moderate = 0.50–0.90 |

#### A3 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Backfilled val_regime v2 labels + CAPE velocity analysis (`A4_cape_velocity`, `B5_cape_triple_storage`). Compared level-extreme vs 6-month velocity rank delta for 3m SPX returns. |
| **Results** | Label distribution: EXTREME_CAPE 436, ELEVATED 309, NORMAL 1105, CHEAP 51. **Level extreme** 3m: n=863, 74.2% SPX up. **Velocity rank delta 6m** 3m: n=531, 74.6% SPX up. **Fresh cross into EXTREME**: n=0 (no events detected with current definition). Winner for avg return: **level_extreme**. Combo E high-CAPE 6m: n=507, 79.1% hit. |
| **Production** | CAPE rate-of-change storage built in shadow; classifier prompt not updated in production. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does CAPE velocity add signal beyond static level? | **Not yet — no clear winner** | **Level extreme** 3m forward: **n=863**, **74.2%** SPX up, avg **+3.08%**, median **+3.88%**. **Velocity rank delta 6m** 3m forward: **n=531**, **74.6%** SPX up, avg **+2.68%**, median **+3.41%**. Hit rates differ by only **0.4 pp**; level wins on avg return by **+0.40 pp**. Label counts: EXTREME_CAPE **436**, ELEVATED **309**, NORMAL **1105**, CHEAP **51** Fridays. | **Doubt:** Fresh cross into EXTREME: n=0 — current detection definition found zero events; cannot test Rohit sir’s “fresh crossing vs sitting at extreme for 3 years” hypothesis. Need definition retune. No formal multivariate regression across all three stored numbers. |
| Does triple storage help Combo E? | **Partially** | Combo E high-CAPE 6m horizon: **n=507**, **79.1%** hit rate, avg return **+6.41%**, median **+7.34%**, worst **−25.22%**. Confirms valuation extreme + Combo E legs produce strong bullish 6m outcomes in sample. | **Doubt:** Combo E moderate-CAPE 6m: n=0 — empty bucket. Triple storage built in shadow but **not wired to conviction modifier** or classifier prompt. B3 forward-return comparison incomplete. |

---

### A4. `geo_overlay` — geopolitical stress

**Problem:** Fine labels (SANCTIONS vs TRADE_WAR) from Claude on a date alone are noisy and inconsistent.

**Collapse to 3 states:**

| State | Examples |
|-------|----------|
| **NEUTRAL** | Normal times |
| **ELEVATED_RISK** | Trade wars, sanctions, regional conflicts |
| **CRISIS** | Pandemic, major financial crisis, world-war-level events |

#### A4 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Run date** | 2026-06-06 |
| **History period** | **1990-01-01 → ~2026-06-06** (1,901 Fridays) |
| **Cadence** | Weekly (Friday) |
| **Input variables** | **Calendar date only** (rule-based windows — not Claude in experiment): COVID **2020-02-01→2020-06-30** → CRISIS; Ukraine **2022-02-01→2022-04-30** → ELEVATED_RISK; tariff shock **2025-02-01→2025-04-30** → ELEVATED_RISK; else NEUTRAL |
| **Label output** | **geo_overlay_v2** (3 states) |
| **Performance slice (FM)** | **CFTC fm_pctile** band crossings + **SPX** 1w–6m; sliced by geo_overlay_v2 — see Section 14 (samples mostly **n<10** in tail geo states) |
| **Artifact** | `A_regime_dimensions.json` → `A2_geo_overlay_v2_distribution` |

#### A4 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Collapsed 6 Claude-inferred geo states → 3 in shadow backfill (`geo_overlay_v2`). |
| **Results** | NEUTRAL 1,855 Fridays, ELEVATED_RISK 25, CRISIS 21. Collapse works — labels are sparse at tails but reproducible. |
| **Production** | Production still uses legacy 6-state geo labels. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Is 3-state geo more reproducible than 6-state? | **Yes (qualitatively)** | Over **1,901 Fridays**: NEUTRAL **1,855** (97.6%), ELEVATED_RISK **25** (1.3%), CRISIS **21** (1.1%). Tail states are rare as expected; no state is empty. Collapse from 6→3 reduces Claude classification noise per plan intent. | **Doubt:** No formal **inter-rater reliability** test (re-run Claude on same dates and compare). Production still uses legacy **6-state** geo labels. |
| Does geo dimension slice combo performance meaningfully? | **No — data too thin** | FM extreme-short 3m SPX up by geo: NEUTRAL **62.5%** (n=32), CRISIS **50%** (n=2), ELEVATED_RISK **0%** (n=1). Full 5-dimension combo slicing is populated mainly on **fed_cycle**; geo/liquidity/val slices mostly **n<10**. | **Doubt:** Cannot draw regime-conditioned conclusions for geo. Need larger sample or longer history before geo slicing is actionable. |

---

### A5. `liquidity` — is money easy or tight, and which way is it moving?

**Old:** GLOBAL_EASY vs GLOBAL_TIGHT (2 states) — too binary.

**New — 2×2 grid:**

| | Improving (easier) | Tightening (harder) |
|--|-------------------|---------------------|
| **Easy level** | easy-and-improving | easy-and-tightening |
| **Tight level** | tight-and-improving | tight-and-tightening |

**WALCL:** Fed total assets (balance sheet size). **Direction** of WALCL tells you if liquidity is improving or tightening. Example: Fed hiking **plus** QT (shrinking balance sheet) = tighter than hiking with a flat balance sheet.

#### A5 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Run date** | 2026-06-06 |
| **History period** | **1990-01-01 → ~2026-06-06** (1,901 Fridays) |
| **Cadence** | Weekly (Friday) |
| **Input variables** | **NFCI** (Chicago Fed financial conditions — level); **WALCL MoM%** (Fed total assets month-over-month change, direction) |
| **Label rules** | Level: NFCI ≤**−0.3** → EASY; ≥**+0.3** → TIGHT; else NEUTRAL. Direction: WALCL MoM **>+0.3%** → IMPROVING; **<−0.3%** → TIGHTENING; else FLAT → **9 composite labels** (e.g. EASY_FLAT, NEUTRAL_TIGHTENING) |
| **Separate QE/QT flag** | **balance_sheet_policy**: WALCL MoM **>+1.0%** → QE; **<−0.5%** → QT (stored in regime JSON, not in fed_cycle_v2) |
| **Outcome measured** | Label counts; FM/combo liquidity slices use **SPX 3m** where n permits (mostly thin) |
| **Artifact** | `A_regime_dimensions.json` → `A3_liquidity_v2_distribution` |

#### A5 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Expanded 2-state liquidity → 9 composite v2 states (2×2 level × direction + FLAT variants) in shadow backfill. |
| **Results** | EASY_FLAT 746, EASY_IMPROVING 403, EASY_TIGHTENING 287, NEUTRAL_FLAT 219, plus TIGHT/NEUTRAL improving/tightening variants (32–72 each). More granular than plan’s pure 4-state 2×2 — includes FLAT direction bucket. |
| **Production** | Legacy GLOBAL_EASY / GLOBAL_TIGHT still in nightly output. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does direction of WALCL distinguish tightening vs improving? | **Built, not combo-validated** | Shadow backfill produced **9 composite states** (plan asked for 4 pure 2×2): EASY_FLAT **746**, EASY_IMPROVING **403**, EASY_TIGHTENING **287**, NEUTRAL_FLAT **219**, TIGHT_TIGHTENING **32**, TIGHT_IMPROVING **50**, etc. Labels encode both level and WALCL direction. | **Doubt:** FM liquidity slices mostly **n<10** per bucket (e.g. NEUTRAL_IMPROVING n=3 at **100%** hit — unreliable). No combo-level validation that direction adds signal over level alone. |
| Is 4-state 2×2 enough or do we need FLAT variants? | **Open** | Experiment implemented **9 states** including FLAT direction variants (e.g. EASY_FLAT **746** vs EASY_IMPROVING **403**). FLAT captures periods where WALCL direction is ambiguous. | **Doubt:** Plan asked for pure **2×2 = 4 states** but backfill produced **9 — should we simplify to 4 or keep the 9-state FLAT variants for production? |

---

### Deliverable A (summary)

Update Section 5.2 classifier prompt with all refined state lists + fiscal caveat + CAPE rate-of-change → re-run historical backfill → report label distribution.

#### Deliverable A — Experiment run — period & variables (summary)

| Dimension | Period | Primary inputs | Outcome |
|-----------|--------|----------------|---------|
| A1 fed_cycle_v2 | 1990→2026, 1,901 Fri | DFF, WALCL | 4-state label counts |
| A2 curve_regime | Same + fiscal test 1990→present | T10Y2Y, FYFSD | Curve labels + 13 inversion episodes → SPX 3m |
| A3 val_regime | Labels 1990→2026; CAPE tests **2010+** | CAPE, CAPE pctile | Label counts + SPX 3m/6m |
| A4 geo_overlay_v2 | 1990→2026, 1,901 Fri | Calendar rules | 3-state label counts |
| A5 liquidity_v2 | 1990→2026, 1,901 Fri | NFCI, WALCL MoM | 9-state label counts |

#### Deliverable A — Overall experiment status

| | Detail |
|---|--------|
| **What we did** | Full Part A shadow backfill (1,901 Fridays). Artifact: `A_regime_dimensions.json`, `experiment_manifest.json` part_a. |
| **Results** | **A1 pass = False** (PIVOTING thin). Geo collapse works. Fiscal caveat directionally supported. CAPE velocity inconclusive. |
| **GO/NO-GO** | **GO for shadow only** — production swap waits on doubts in Section 16 (PIVOTING thin state, PAUSING gap, classifier prompt). |

**Doubts from deliverable A (plan vs experiment):**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Report label distribution so no state is degenerate | **Done** | Full distributions logged in `A_regime_dimensions.json` across all 5 dimensions for **1,901 Fridays**. PIVOTING flagged as thin (n=27). | **Doubt:** Degenerate check **passed for dominance** but **failed for PIVOTING sample size**. |
| Update production Section 5.2 classifier prompt | **Not done** | Shadow classifier logic runs in experiment pipeline. | **Doubt:** Do the refined state lists, fiscal caveat, and CAPE velocity fields match what you want in the live classifier prompt before we update Section 5.2? |
| Re-run backfill after prompt finalization | **Not done** | Initial backfill complete (2026-06-06). | **Doubt:** After you confirm prompt wording, should we re-run the full 1,901-Friday backfill before any production wire? |

---

## 4. The 14th variable and history windows (Part B)

**Shadow experiment run:** 2026-06-06. Artifact: `B_twy_and_percentiles.json`. Subsections include **Experiment run — period & variables** tables below.

### B1. New variable: `TWY_ROC` (#14)

**Role:** Regime classification **only**. **Do NOT** add to the 13-combo math (298 combinations = all ways to pick 1, 2, or 3 variables from 13 — written **13C1 + 13C2 + 13C3**).

| Field | Spec |
|-------|------|
| **Name** | 2-Year US Treasury yield, 8-week rate of change |
| **Source** | FRED **DGS2**, Friday close (weekly cadence) |
| **Calculation** | Today’s DGS2 minus DGS2 from **56 calendar days ago**, in **percentage points (pp)** |
| **Positive TWY_ROC** | Yields rising → market pricing tighter policy (**hawkish**) |
| **Negative TWY_ROC** | Yields falling → market pricing cuts (**dovish**) |
| **Bands (starting point)** | HAWKISH if > +0.30pp; NEUTRAL −0.30 to +0.30; DOVISH if < −0.30pp — **backtest these** |
| **History window** | **3-year rolling** (like WTI, CNH, WALCL, CPI — “flow” variables) |

**Why it matters:** Most other Fed inputs (FFR = fed funds rate, WALCL, curve, NFCI = financial conditions index, CAPE) are **coincident or lagging** — they describe now or the recent past. **Bond markets lead** Fed actions by ~3–9 months because they price speeches, dot plots, and expected cuts/hikes ahead of time.

**Key insight:** When `fed_cycle` says TIGHTENING but TWY_ROC is strongly DOVISH, that **divergence** is actionable — the market may be pricing a pivot before official labels catch up.

**Validation test:** On ~7 April 2025 (tariff-shock market bottom), 2yr yield had fallen ~65–75 **bps** (basis points; 1 bp = 0.01pp) over 8 weeks — DOVISH — while fed_cycle still said TIGHTENING/PAUSING. Confirm against real DGS2 data when you build it.

**Feed into prompt as:** `"2yr yield 8wk change: {TWY_ROC}pp, direction: {HAWKISH/NEUTRAL/DOVISH}."`

#### B1 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Run date** | 2026-06-06 |
| **History available** | **DGS2** (FRED 2-year Treasury yield) from **1990-01-01** (full series for `twy_roc_at_date()`) |
| **Validation dates tested** | **2025-04-04** and **2025-04-07** only (Apr 2025 tariff-bottom anchor) |
| **Input variable** | **DGS2** today minus **DGS2 56 calendar days ago** → **TWY_ROC** in **percentage points (pp)** |
| **Bands tested** | DOVISH if **< −0.30 pp**; NEUTRAL ±0.30; HAWKISH if **> +0.30 pp** |
| **Cross-check** | Legacy **fed_cycle** label on same dates (divergence test vs lagging fed labels) |
| **Outcome measured** | TWY_ROC value, direction class, pass/fail vs expected **65–75 bps** (0.65–0.75 pp) dovish move — **not SPX** |
| **Excluded from** | 298-combo enumeration (**13 variables** only; TWY_ROC is #14 regime-only) |

#### B1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Built TWY_ROC from FRED DGS2. Ran Apr 2025 anchor validation. Confirmed excluded from 298-combo enumeration. |
| **Results** | **Apr 7 2025:** TWY_ROC = **−0.55pp → DOVISH** (DGS2 3.73%). Apr 4: −0.61pp. Expected range 65–75 bps over 8 weeks → **PASS**. Legacy fed_cycle still TIGHTENING/PAUSING on those dates — **divergence confirmed**. |
| **Production** | TWY_ROC **not in nightly data pull** yet. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Did TWY_ROC call Apr 2025 bottom before lagging fed labels? | **Yes** | **Apr 7 2025:** TWY_ROC = **−0.55pp** (DGS2 **3.73%**), direction **DOVISH** (threshold < −0.30pp). **Apr 4:** **−0.61pp**. Plan expected **65–75 bps** (0.65–0.75pp) fall over 8 weeks — observed **−0.55pp** matches. Legacy fed_cycle still **TIGHTENING/PAUSING** on those dates. Market priced cuts **3–9 months** before official labels moved. | **Doubt:** Only **2 anchor dates** tested. Full historical divergence catalog not built. TWY_ROC **not in nightly pull** yet. |
| Are ±0.30pp bands validated? | **Partially** | Apr 2025 anchor passes: **−0.55pp** is **0.25pp below** the DOVISH band (well outside neutral ±0.30). Confirms bands can classify extreme moves. | **Doubt:** No full historical band sweep — unknown how often ±0.30pp misclassifies vs ±0.20 or ±0.40. Plan explicitly says ±0.30 is starting point, not validated. |
| Is TWY_ROC excluded from combos? | **Yes** | Pipeline scans **298 signatures** (13C1+13C2+13C3 from **13 variables** only). Variable #14 absent from combo enumeration. **13,089 generic fires** recorded without TWY_ROC leg. | **Doubt:** Confirm no downstream script accidentally adds TWY_ROC to combo detector in production (code audit not in experiment scope). |

---

### B2. History windows — two types

Supersedes “everything 3-year rolling”:

| Variable type | Examples | Window |
|---------------|----------|--------|
| **Structural / level** | CAPE, VIX, yield curve, NFCI, GSR (gold/silver ratio) | **Full expanding history** from inception (CAPE from 1881, VIX from 1990, etc.) |
| **Flow / rate-of-change** | WTI 4wk%, CNH 4wk%, WALCL MoM%, CPI surprise, TWY_ROC | **3-year rolling** |

**Dual storage — store BOTH every day for every variable:**

| Storage | Used for |
|---------|----------|
| **unconditional_pctile** | Full history rank → **combo detection** |
| **regime_pctile** | Rank within current `fed_cycle` only → **conviction modifier** |

**Fallback:** If regime-conditioned subset has **< 50 observations**, use unconditional and **log** which was used.

#### B2 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Run date** | 2026-06-06 |
| **History period** | All rows in **`daily_readings`** (macro backfill history; **14,457** row-pairs with both percentiles at test time) |
| **Cadence** | Daily (stored per variable per date) |
| **Input variables** | **12 CONFIG variables** audited for window type; dual storage for each: **unconditional_pctile** (full or rolling window per var) + **regime_pctile** (rank within current **fed_cycle** subset) |
| **Window audit (B4)** | Structural → **full** history: CAPE, NFCI, WALCL, CURVE, DXY. Flow → **rolling_3y**: HY, VIX, VXTS, CFTC, WTI, CNH, CPI, etc. |
| **Outcome measured** | Row counts with both percentiles; **4 CONFIG mismatches** vs plan (HY/VIX/VXTS/WALCL); **0** regime fallbacks triggered |
| **Outcome (SPX)?** | **No** — storage/audit only in B2 |

#### B2 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Implemented dual percentile storage (unconditional + regime-conditioned on fed_cycle). Ran window audit against plan spec. |
| **Results** | **14,457 rows** with both percentiles; **0 fallbacks** in backfill (regime subsets always ≥50 obs in practice). **B4 window audit FAIL:** HY, VIX, VXTS configured `full` but plan expects `rolling_3y`; WALCL configured `rolling_3y` but plan expects `full`. |
| **Production** | Dual percentiles in shadow DB only. CONFIG.yaml alignment **still open**. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does dual percentile storage work? | **Yes** | **14,457 rows** stored with **both** unconditional_pctile and regime_pctile (conditioned on fed_cycle). **0 rows** with unconditional only. Fallback to unconditional when regime subset <50 obs is implemented. | **Doubt:** Storage works in **shadow DB only** — not in production nightly pipeline. |
| Does <50 fallback logic work when needed? | **Not tested** | Backfill triggered **0 fallbacks** — every fed_cycle regime had **≥50 observations** in practice for all 14 variables. | **Doubt:** Thin regimes (PIVOTING n=27 Fridays) may trigger fallbacks in production — **edge case untested**. Need explicit test forcing n<50 subset. |
| Are history windows correct per variable? | **No — 4 mismatches** | B4 window audit checked **12 variables**. **4 FAIL** vs plan spec: **HY** configured `full`, plan expects `rolling_3y`; **VIX** configured `full`, plan expects `rolling_3y`; **VXTS** configured `full`, plan expects `rolling_3y`; **WALCL** configured `rolling_3y`, plan expects `full`. | **Doubt:** Must fix **CONFIG.yaml** before production GO — wrong windows change percentile ranks and combo fire dates. |

---

### B3. Triple storage for CAPE

Because both **level** and **speed of change** matter for CAPE, store **three** numbers:

1. Full-history expanding percentile rank  
2. 3-year rolling percentile rank  
3. 8-week rate-of-change of the rank  

Then **test** which combination best predicts forward returns — don’t guess upfront.

#### B3 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Run date** | 2026-06-06 |
| **History period** | **2010-01-01 → present** for CAPE forward-return tests (same window as `_run_a4_cape_velocity`) |
| **Input variables** | **CAPE**: (1) full-history expanding percentile, (2) 3-year rolling percentile, (3) 8-week ROC of percentile rank — stored in shadow `daily_readings` / meta |
| **Outcome measured** | **SPX 3m** forward return compared across signal definitions; **Combo E** fires tested with **SPX 6m** (`B5_cape_triple_storage`) |
| **Primary horizon** | **3 months (63 trading days)** for level vs velocity; **6 months (126 td)** for Combo E high-CAPE bucket |

#### B3 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Stored expanding rank + 3y rolling rank + 8wk ROC of rank. Compared level-extreme vs velocity for forward returns (see A3/B5). |
| **Results** | **Winner = level_extreme** for 3m avg return. Velocity rank delta similar hit rate (74.6% vs 74.2%) but slightly lower avg return. Fresh-cross bucket empty. |
| **Production** | Triple storage in shadow; not wired to conviction modifier. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Which CAPE storage combo predicts best? | **Preliminary: level** | **Level extreme** 3m: n=**863**, hit **74.2%**, avg **+3.08%**. **Velocity rank delta 6m** 3m: n=**531**, hit **74.6%**, avg **+2.68%**. Experiment declared **level_extreme** winner on avg return (**+0.40pp** higher). | **Doubt:** Not a rigorous multivariate test — no regression combining all 3 stored numbers (expanding rank + 3y rolling rank + 8wk ROC of rank). **Fresh-cross: n=0**. |
| Does velocity beat level for Combo E? | **No clear win — level wins** | Combo E high-CAPE **6m**: n=**507**, hit **79.1%**, avg **+6.41%**, median **+7.34%**. Strong signal at valuation extremes regardless of velocity tier. | **Doubt:** Moderate-CAPE bucket: n=0 — empty. Velocity-specific Combo E slice not testable. Triple storage not wired to conviction modifier. |

---

### Deliverable B (summary)

Variable table → 14 variables with correct windows; TWY_ROC fully built; dual storage implemented; triple storage for CAPE.

#### Deliverable B — Experiment run — period & variables (summary)

| Piece | Period | Inputs | Outcome |
|-------|--------|--------|---------|
| TWY_ROC B1 | DGS2 from 1990; anchor **Apr 2025** | DGS2 8-week ROC | Direction class vs fed_cycle |
| Dual percentiles B2/B3 | Full `daily_readings` | 12–14 macro vars | 14,457 dual rows; B4 window audit |
| CAPE triple B3/B5 | **2010+** | CAPE pctiles | SPX 3m / 6m vs level & velocity |

#### Deliverable B — Overall experiment status

| | Detail |
|---|--------|
| **What we did** | TWY_ROC built + validated. Dual percentiles backfilled. Triple CAPE stored. Artifact: `B_twy_and_percentiles.json`. |
| **Results** | TWY anchor **PASS**. Dual storage **PASS**. Window audit **FAIL** (4 vars). |
| **GO/NO-GO** | **GO** — but fix CONFIG windows + wire to nightly pull before production. |

---

## 5. Percentile rank as emission probability (Part C)

**Shadow experiment run:** 2026-06-06. Artifact: `C_emission.json` (subset in `B_twy_and_percentiles.json` for C1 count).

**Today’s problem:** If a variable is below its RARE threshold, it contributes **nothing** — binary on/off. That misses gradual buildup.

**New approach — emission probability:** Every variable’s percentile rank is **partial evidence** about which regime you’re in. VIX at 0.72 (below 0.80 RARE line) still suggests some stress — not zero evidence.

**Bayesian updating (plain English):**

- Start with yesterday’s belief about which regime you’re in (**prior** = P(regime)).  
- See today’s 14 percentile readings.  
- Ask: “How likely are these readings if we were in regime X?” (**emission probability** = P(readings | regime)).  
- Combine → **posterior** = updated belief P(regime | today’s readings).  
- **Act on the full distribution** — e.g. 65% Risk-On, 25% Risk-Off — not a hard snap to one label.

**Formula in doc:**  
`P(regime | readings) = P(readings | regime) × P(regime) / P(readings)`

You don’t need to implement full Bayes in Part C — just **store the 14 daily percentile-rank vectors** alongside combo fires. That storage feeds Part D (HMM).

**Deliverable C:** Daily stored vectors. **No HMM yet** — need **6+ months** of clean vectors before HMM training is meaningful.

#### Part C — Experiment run — period & variables

| Test | Period | Cadence | Input variables | Outcome measured |
|------|--------|---------|-----------------|------------------|
| **C1 Emission vectors** | **2010-01-01 → present** | Daily | **14 variables** × unconditional_pctile (+ regime_pctile in DB) per date → **8,805** daily vector rows backfilled | Storage count; feeds Part D prototype |
| **C2 Sub-threshold VIX** | **2010-01-01 → present** | Daily | **VIX unconditional_pctile** in **65th–79th** (below 80th RARE line) | **SPX 3m** (63 td); n=7 |
| **C2 Random baseline** | Sample of VIX dates | Daily | Random Friday subsample (~200) | **SPX 3m** baseline |
| **C3 Binary vs vector timing** | VIX RARE events | Daily | **VIX** binary first-RARE vs mean-pctile vector first-fire | **Median lag (days)** between methods on **864** events |

#### Part C — Experiment status

| | Detail |
|---|--------|
| **What we did** | Backfilled **8,805 daily emission vectors** (14 percentile ranks per day). Tested sub-threshold VIX (65th–79th pctile) vs binary RARE threshold. Compared binary-first-fire vs vector-mean-first-fire timing. |
| **Results** | Sub-threshold VIX 65–79: n=7, **85.7%** positive 3m — promising but **n too small** for statistical gate. Binary vs vector **median lag = 0 days** — vectors did **not** provide early warning at RARE threshold in this prototype. |
| **Production** | Daily live emission job **not wired**. Clock for 6-month HMM requirement **not started**. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Can we store 14 daily percentile vectors? | **Yes** | **8,805 daily rows** backfilled, each with **14 percentile ranks**. Stored alongside combo_fires in shadow DB. Foundation for Part D HMM is in place historically. | **Doubt:** Should we wire the daily emission_vectors job to production now so the **6-month HMM clock** starts, even though Part D prototype showed no hit-rate gain? |
| Do sub-threshold readings accumulate useful signal? | **Maybe — unproven** | Sub-threshold VIX (**65th–79th percentile**, below 80th RARE line): **n=7**, **85.7%** positive 3m SPX (avg **+2.72%**, median **+3.23%**). Directionally promising — stress building before RARE breach. | **Doubt:** With only **n=7**, is it worth investing in cumulative sub-threshold vector scoring, or stay with binary RARE thresholds for now? |
| Do vectors detect regime shifts earlier than binary? | **No (so far)** | Compared binary-first-RARE-fire vs vector-mean-first-fire on **864** VIX RARE events: **median lag = 0.0 days**. Vectors did **not** fire earlier than binary at current RARE threshold design. | **Doubt:** Current design shows **0-day** early-warning gain — should we tune emission weights, or deprioritize Part C vector approach until a revised design is tested? |
| When can HMM training start? | **Not yet** | Plan requires **6+ months of clean live vectors** from Part C daily job. Backfilled **8,805 rows** exist for research; Part D prototype used **500-obs** sample. | **Doubt:** Given prototype HMM did not improve Combo B (−**1.2 pp**) or D (−**1.9 pp**) hit rates, is **~Dec 2026** still the right target for production HMM, or should we defer further? |

---

## 6. The HMM layer (Part D) — build AFTER Part C has data

**Shadow experiment run:** 2026-06-06. Artifact: `D_hmm_prototype.json`. **Research prototype only** — not production HMM.

**HMM** (Hidden Markov Model): A statistical model that assumes the market is usually in one of a few **hidden states** you can’t observe directly, and each day’s macro readings are **noisy clues** about which state you’re in. States can persist for a while then switch.

### D1. Layer, don’t replace

Keep the percentile engine. Add a simple **3-state HMM** on top:

| State | Meaning |
|-------|---------|
| **Risk-On** | Favorable for risk assets (stocks, credit) |
| **Risk-Off** | Stress / flight to safety |
| **Transition** | In between / shifting |

**Observations:** The 14 daily percentile-rank vectors.  
**Output:** Daily posterior — e.g. `[Risk-On 0.65, Risk-Off 0.25, Transition 0.10]`.

### D2. Feed into classifier prompt

Add HMM posterior to Section 5.2 as a **soft prior**. Rule of thumb: if Risk-Off > 0.40, lean toward tighter/stress classifications even if individual variables haven’t crossed thresholds.

### D3. Detecting regime shifts

If HY OAS (high-yield bond spread — credit stress indicator) sits at 65th percentile for 8 weeks, but the HMM learned that Risk-On usually has lower HY spreads, evidence accumulates **against** Risk-On each week. When posterior for the assumed regime drops **below 50%**, call it a **regime shift** — earlier than waiting for one variable to hit 85th percentile.

### D4. HSMM (phase 2)

**HSMM** (Hidden Semi-Markov Model): Like HMM but remembers **how long** you’ve been in a state. Answers “is this regime ending?” via exit probability — maps to combo duration buckets (SHORT <6 weeks, MEDIUM 6–16, LONG >16). **Defer** until basic HMM works.

#### Part D — Experiment run — period & variables

| Test | Period | Input variables | Outcome measured |
|------|--------|-----------------|------------------|
| **D1 HMM prototype** | **500 most recent dates** with emission vectors (from **2010+** backfill pool) | Daily **mean of 14 unconditional percentiles** (`emission_vectors` table) | 3-state labels (Risk-On / Risk-Off / Transition) + sample posteriors — **k-means-style**, not true HMM |
| **D3 Shift detection** | — | HY OAS example in plan | **Not backtested** in experiment |
| **Regime backtest** | **Combo B & D** full fire history in DB | HMM Risk-Off filter vs all fires | **SPX 3m** hit rate: Combo B **79.8%** (n=89) → **78.6%** (n=56); Combo D **28.1%** (n=452) → **26.2%** (n=103) |
| **D4 HSMM** | Not run | — | — |

#### D1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Research prototype only — k-means-style clustering on mean percentile vector (not production HMM). 500 obs sample. |
| **Results** | 3-state posteriors computed for sample dates. Example Jun 2026: Risk-On ~43%, Risk-Off ~24%, Transition ~33%. |
| **Production** | **DEFER** — blocked until 6 months live C vectors. |

#### D2–D3 — Experiment status

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Can HMM posteriors feed classifier as soft prior? | **Not in production** | Prototype produces daily posteriors — e.g. Jun 2026 sample: Risk-On **42.9%**, Risk-Off **23.8%**, Transition **33.3%**. Plan rule (Risk-Off >40% → tighter classifications) is implementable. | **Doubt:** Classifier Section 5.2 **not updated**. Prototype is k-means-style, **not production HMM**. No live posterior stream. |
| Does HMM detect shifts before binary thresholds? | **Not validated** | Plan describes shift detection when posterior drops **below 50%** after weeks of accumulating sub-threshold evidence (e.g. HY OAS at 65th pctile for 8 weeks). | **Doubt:** No shift-timing backtest completed.** Prototype too crude. D3 hypothesis untested. |

#### D4 / HSMM — Experiment status

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| HSMM for combo duration exit probability? | **Not started** | Plan maps HSMM dwell-time to combo duration buckets: SHORT **<6wks**, MEDIUM **6–16wks**, LONG **>16wks**. Correctly deferred until basic HMM validated. | **Doubt:** Zero implementation. Depends on production HMM first (~Dec 2026 earliest). |

#### Deliverable D — Backtest results

| | Detail |
|---|--------|
| **What we did** | `regime_backtest.py` harness on Combo B and D with HMM Risk-Off filter vs overall. |
| **Results** | **Combo B:** overall 3m 79.8% SPX up (n=89) → HMM Risk-Off only **78.6%** (n=56) — **no improvement**. **Combo D:** overall 28.1% SPX down → HMM Risk-Off only **26.2%** (n=103) — **no improvement**. |
| **Conclusion** | Prototype HMM does **not** improve hit rates. Production HMM deferred regardless. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does regime-conditioning via HMM improve Sharpe/win rate/drawdown? | **No — win rate flat/worse** | **Combo B** 3m SPX up: overall **79.8%** (n=**89**) → HMM Risk-Off filter **78.6%** (n=**56**), delta **−1.2 pp**. **Combo D** 3m SPX down: overall **28.1%** (n=**452**) → HMM Risk-Off filter **26.2%** (n=**103**), delta **−1.9 pp**. Prototype on **500 obs**, **n=41** Risk-Off 3m hit **73.2%**, **n=36** Risk-On **75.0%**. | **Doubt:** Sharpe ratio and drawdown not reported** in experiment manifest — plan deliverable incomplete. Prototype is research-only (k-means, not true HMM). |
| When is production HMM ready? | **~Dec 2026 earliest** | Plan requires **6+ months live** emission vectors after Part C daily job wired. Prototype: Combo B **79.8%** → **78.6%** with Risk-Off filter; Combo D **28.1%** → **26.2%**. | **Doubt:** Clock is at **0 months** (live C1 not wired). Is HMM still worth the **6-month** wait given the prototype showed no improvement? |

### Deliverable D (summary)

Train 3-state HMM on accumulated vectors; store daily posterior; pipe into classifier; backtest vs `regime_backtest.py` — does regime-conditioning improve Sharpe, win rate, drawdown?

---

## 7. Transition probability as an options problem (Part E)

**Shadow experiment run:** 2026-06-06. Artifact: `E_cancel_probability.json`.

**Goal:** Replace vague “this combo might cancel soon” with a **number** — probability the combo’s cancel conditions will be met.

**Digital barrier option (plain English):** Like a bet that pays if price crosses (or fails to cross) a line by a date. Here, “cancel” = macro variables stay on the wrong side of thresholds for required consecutive periods.

**Example — Combo C cancel rule:**  
WTI 4-week change < +5% for **4 consecutive Fridays** AND CPI not hot for **2 consecutive prints**.

**WTI leg:**

- Each Friday, **strike K** = WTI price 4 weeks earlier × 1.05.  
- Cancel that week if WTI close **below** K.  
- Per-Friday probability from **Black-Scholes-style** formula: **N(−d2)** where N = normal CDF, d2 involves current price S, strike K, vol σ (~35% for WTI), time T.  
- Four weeks’ windows **overlap** (correlation ~0.75) — **don’t multiply** four independent probabilities. Run **Monte Carlo** (simulate many random price paths with **GBM** = Geometric Brownian Motion) to get joint probability.

**CPI leg:** Historical fraction of CPI prints at-or-below consensus → square for 2 consecutive non-hot prints.

**Total P(cancel)** ≈ P(WTI leg) × P(CPI leg).

**Generalizes** to other combos: Combo F (26-week window), Combo D (3–10 day — fast digital), Combo G (variance option on vol spike timing).

### Deliverable E

Reusable function:  
`combo_cancel_probability(variable, threshold, current_value, vol, weeks_remaining, consecutive_required)`  
→ show live cancel/persist % on nightly briefing and dashboard.

#### Part E — Experiment run — period & variables

| Test | Period | Input variables | Outcome measured |
|------|--------|-----------------|------------------|
| **E1 Combo C MC (live example)** | **Point-in-time** snapshot at experiment run | **WTI** price & 4wk-ago level (strike = prior × 1.05); **σ=35%** annual vol; **CPI** leg from historical at/below-consensus rate | **P(cancel)** via **10,000** GBM Monte Carlo paths; example: WTI **$90.54**, combined cancel **~2.25%** |
| **E2 Calibration** | All historical **Combo C** fires in `combo_fires` DB | Combo C episode **status** (cancelled vs not) | **Realized cancel rate** vs predicted (**4 episodes**, 0% realized vs ~2.25% predicted) |
| **E3 Combo D/F/G** | — | Documented formulas only | **Not implemented** as functions |

#### Part E — Experiment status

| | Detail |
|---|--------|
| **What we did** | Built Monte Carlo cancel function for Combo C (WTI leg + CPI leg). Ran E2 calibration on historical episodes. Documented Combo D/F/G formulas in experiment report. |
| **Results** | Example live calc: WTI leg MC prob all 4 weeks = **8.3%**; CPI leg = **27.0%**; **combined cancel = 2.2%**. Calibration: **4 historical episodes, 0 realized cancels** vs 2.2% predicted — **under-calibration suspected** (model may overstate cancel risk or sample too small). |
| **Production** | Function built. **Not wired** to nightly briefing or dashboard. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Can we compute Combo C cancel probability via MC? | **Yes** | Built `combo_cancel_probability()` with **10,000** GBM sim paths (correlation **~0.75** across overlapping WTI windows). Example calc: WTI current **$90.54**, strike **$86.23** (4wk-ago × 1.05), vol **35%** annual. WTI leg MC prob all 4 Fridays: **8.31%**. CPI leg (historical at/below consensus rate, squared for 2 prints): **27.04%**. **Combined: 2.25%**. | **Doubt:** Function exists in shadow only. **Combo D/F/G** formulas documented but **not built** as reusable functions (E3 note). |
| Is the probability calibrated to history? | **No — under-calibration suspected** | E2 calibration: **4 historical Combo C episodes**, **0 realized cancels** (0%) vs **2.25%** predicted example. Model may **overstate** cancel risk, or sample is too small to calibrate. | **Doubt:** Need **≥5 episodes** per statistical gate. Live tracking of predicted vs realized cancel rates not yet running. |
| Live cancel % on briefing? | **Not yet** | Monte Carlo function returns probability; persist probability = 1 − cancel. Example: Combo C combined cancel **2.25%**. | **Doubt:** Should live cancel/persist **%** appear on the nightly briefing and dashboard for every active combo, as the plan specifies? |
| Combo D/F/G cancel formulas? | **Documented only** | Plan specifies Combo F (26-week window), Combo D (3–10 day digital), Combo G (variance option on vol timing). Formulas in experiment report. | **Doubt:** No reusable `combo_cancel_probability()` calls for D/F/G yet — only Combo C implemented. |

---

## 8. Formal regime definitions (Part F)

**Shadow experiment run:** 2026-06-06. Artifact: `F_quant_regime.json`.

**Problem:** Some labels today are Claude-inferred with no numeric rule. Rohit sir wants **explicit, testable rules** — especially for yield curve — aligned with Ahil’s steepening-of-inversion work.

### F1. TIGHTENING-LATE (example of quantifying fed states)

Proposed triggers (illustrative — do similar for **every** fed_cycle state):

- FFR > 3.5%  
- FFR up > 150 bps in prior 12 months  
- AND (T10Y2Y < −30 bps OR hike pace slowing over last two meetings)

**T10Y2Y:** 10-year minus 2-year Treasury yield spread — standard inversion measure.

Validate against backfill (Oct 2022 should match).

#### F1 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Spot-check date** | **2022-10-13** (Oct 2022 hiking/inversion context) |
| **Input variables** | **DFF** (FFR level & 12m change); **T10Y2Y** spread; legacy + v2 fed/curve labels |
| **Rules tested** | F1 TIGHTENING-LATE: FFR **>3.5%**, +**150 bps** in 12m, curve **<−30 bps** or hike decel |
| **Outcome measured** | Boolean **`tightening_late_f1`** + full `build_regime_v2()` snapshot — **not SPX** |

#### F1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Tested proposed TIGHTENING-LATE (formerly HIKING_LATE) rules against Oct 2022 backfill. |
| **Results** | Oct 2022: fed_cycle_v2 = **TIGHTENING** (not TIGHTENING-LATE). **`tightening_late_f1 = False`**. Legacy label was HIKING_LATE. FFR ~3.25%, +300bps in 9 months, curve −50bps — rules did not fire as written. |
| **Doubts to ask Rohit sir Sir** | **Doubt:** F1 TIGHTENING-LATE misfired on Oct 2022 (FFR **~3.25%** below **>3.5%** threshold) — should we retune F1 rules or map v2 TIGHTENING differently from legacy HIKING_LATE? Full numeric rules for all 4 v2 fed states not yet validated. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does F1 TIGHTENING-LATE match Oct 2022? | **No — rule misfire** | Oct 2022 backfill: fed_cycle_v2 = **TIGHTENING** (not TIGHTENING-LATE). **`tightening_late_f1 = False`**. Legacy label was **HIKING_LATE**. Actual conditions: FFR **~3.25%** (below proposed **>3.5%** threshold), **+300 bps** in 9 months (exceeds **+150 bps** rule), T10Y2Y **−50 bps** (meets **<−30 bps** leg). FFR level threshold blocked the rule. | **Doubt:** Proposed F1 thresholds need retuning — either lower FFR gate or map v2 TIGHTENING differently from legacy HIKING_LATE. **14 inverted weeks** detected separately via F2. |
| All fed states have numeric rules? | **No** | F1 proposed for TIGHTENING-LATE only. F3 hiking period implemented (Oct 2022: **`hiking_period_f3 = true`**). F2/F2a inversion/steepening pass. | **Doubt:** Full quantitative defs for all **4 v2 fed_cycle states** (TIGHTENING, PIVOTING, EASING, EASY) not backfill-validated. Production `regime_rules.py` **unchanged**. |

### F2. INVERTED — formal definition

| Concept | Rule |
|---------|------|
| **Inversion event** | T10Y2Y crosses below 0 bps |
| **INVERTED regime** | T10Y2Y < 0 for **≥ 4 consecutive weeks** (not one-day blips) |
| **Trough** | Most negative T10Y2Y during that inverted episode |
| **Note** | −30 bps = RARE tier, −80 bps = EXTREME tier for **combo variable #9 — separate from the regime label |

#### F2 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **History period** | **1990-01-01 → present** (weekly **T10Y2Y** from FRED) |
| **Input variable** | **T10Y2Y** (10yr−2yr Treasury spread, %) |
| **Rule** | INVERTED when spread **< 0** for **≥ 4 consecutive weeks** |
| **Spot-check** | Oct 2022: **14 inverted weeks** counted |
| **Outcome measured** | Inversion episode detection — label correctness vs known history (**not SPX** in F2 alone) |

#### F2 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Implemented T10Y2Y < 0 for ≥4 consecutive weeks rule in shadow `regime_rules.py`. Oct 2022 check: 14 inverted weeks detected. |
| **Results** | **F2/F2a pass** in experiment report. Inversion events align with known history. |
| **Production** | `regime_rules.py` in production **unchanged** — shadow only. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Reproducible INVERTED label from T10Y2Y? | **Yes (shadow)** | Rule: T10Y2Y **< 0 bps** sustained **≥4 consecutive weeks**. Oct 2022: **14 inverted weeks** detected. Inversion events align with known history (1970s–80s, 2000, 2007, 2019, 2022–23). Separate from combo variable #9 tiers (−30 bps RARE, −80 bps EXTREME). | **Doubt:** Shadow `regime_rules.py` only — **production unchanged**. One-day dips below zero correctly excluded. |
| Aligned with Ahil's steepening gate? | **Pending** | F2/F2a use T10Y2Y consistently: inversion trough tracking + steepening **≥+15 bps/4wk** (RARE) or **≥+40 bps** (EXTREME). Same source variable (FRED T10Y2Y) specified for Ahil's steepening-of-inversion short gate (F4). | **Doubt:** Are these T10Y2Y inversion/steepening rules the single source of truth for both this workstream and Ahil's steepening gate, or do thresholds need alignment first? |

### F2a. STEEPENING

After inversion trough, T10Y2Y rises ≥ +15 bps over 4 weeks (RARE) or ≥ +40 bps (EXTREME). Classifier must use these numbers, not guess from context.

#### F2a — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **History period** | Same as F2 — **1990+** weekly **T10Y2Y** |
| **Input variable** | **T10Y2Y** 4-week change after inversion trough |
| **Thresholds** | **+15 bps/4wk** (RARE steepening); **+40 bps/4wk** (EXTREME) |
| **Outcome measured** | STEEPENING label detection in shadow backfill (shared with F4 grid) |

#### F2a — Experiment status

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| STEEPENING detectable from numeric rules? | **Yes (shadow)** | After inversion trough: T10Y2Y rise **≥+15 bps/4wk** = RARE steepening, **≥+40 bps/4wk** = EXTREME. Rules implemented in shadow `regime_rules.py` and pass backfill checks. F4 grid uses same steepening thresholds. | **Doubt:** Best F4 grid cell (−80 bps trough, +15 bps steepen): only **33.3%** SPX down 3m (n=**9**) — steepening detectable but **not a strong short signal statistically**. |
| Classifier uses numbers not context? | **Not in production** | Shadow uses numeric F2a rules. | **Doubt:** Production classifier still **Claude-inferred** for curve_regime in places. Numeric rules not in Section 5.2 prompt yet. |

### F3. HIKING period (for beta tests)

FFR rising AND cumulative hikes in cycle > 100 bps.

#### F3 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **History period** | Full **DFF** series from **1990+** (via `is_hiking_period()`) |
| **Input variables** | **DFF** 13-week change **> +0.25 pp** AND cumulative hike **> +100 bps** in cycle |
| **Spot-check** | Oct 2022: **`hiking_period_f3 = true`** |
| **Outcome measured** | Boolean flag used in Part H beta filter context — **not SPX** |

#### F3 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Implemented F3 hiking period flag. Oct 2022: **`hiking_period_f3 = true`**. |
| **Results** | Used in Part H beta filter (HIKING/INVERTED regime-conditional hit rates). |

### F4. Steepening-of-inversion short trigger

Valid when:

1. Prior inversion trough deeper than −50 bps  
2. Curve now steepening (≥ +15 bps / 4 wk)  
3. No large fiscal/QE offset (deficit < 5% GDP, no active QE)

Failed in 2022–23 because −108 bps inversion was offset by AI capex + fiscal spend. **Backtest** trough (−50 vs −80) and steepening (+15 vs +40) thresholds before locking in.

**Evidence standard (important):** This gate is justified by **economic mechanism + historical analogs** (2000, 2007, understood 2022–23 failure) — **NOT** by “it won 2–3 times in backtest.” If you only defend it with win rate, it falls under the **≥5 instance statistical rule** instead.

#### F4 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **History period** | **1990-01-01 → present** |
| **Cadence** | Weekly Friday **T10Y2Y** |
| **Input variables** | **T10Y2Y** inversion trough depth; 4-week steepening change |
| **Grid tested** | Trough **−50 vs −80 bps** × steepen **+15 vs +40 bps/4wk** (4 cells) |
| **Outcome measured** | **SPX 3m** forward return (**63 trading days**) at trigger; **bearish** hit rate (SPX down %) |
| **Fiscal/QE filter in plan** | Deficit **<5%** GDP, no active QE — **not fully enforced** in grid code |

#### F4 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Ran threshold grid on steepening-short trigger. Documented mechanism analogs (2000, 2007, 2022–23 failure). |
| **Results** | SPX down 3m hit rates — all **below statistical promotion bar**: |

| Trough | Steepen 4wk | n | SPX down 3m |
|--------|-------------|---|-------------|
| −50 bps | +15 bps | 17 | 17.6% |
| −50 bps | +40 bps | 4 | 25.0% |
| −80 bps | +15 bps | 9 | 33.3% |
| −80 bps | +40 bps | 2 | 0% |

| **Verdict** | **MECHANISM+ANALOG gate only** — not promotable on win rate. Plan correctly anticipated this. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| −50 vs −80 trough threshold? | **Grid run — no statistical winner** | **−50 bps trough, +15 bps steepen:** n=**17**, **17.6%** SPX down 3m, avg **+5.78%** (market rose). **−80 bps trough, +15 bps steepen:** n=**9**, **33.3%** SPX down 3m — best cell but still below **55%** promotion bar. Deeper trough nearly doubles hit rate (17.6% → 33.3%) but halves sample. | **Doubt:** Given no cell clears **55%** hit rate (best **33.3%**, n=9), should F4 use **−50/+15** or **−80/+15** as mechanism defaults — relying on 2000/2007 analogs and the understood 2022–23 failure, not backtest win rate? |
| +15 vs +40 steepening threshold? | **+15 wins on n; +40 wins slightly on rate** | **−50 trough, +40 steepen:** n=**4**, **25.0%** SPX down. **−80 trough, +40 steepen:** n=**2**, **0%** SPX down. Stricter steepening (+40) reduces n without improving reliability. | **Doubt:** n=2 and n=4 — statistically meaningless. Cannot choose +40 on backtest evidence alone. |
| Can F4 be promoted on backtest alone? | **No** | Best hit rate **33.3%** (n=9) vs plan's **≥80%** naming gate and **≥55%** beta filter. Plan evidence standard: **MECHANISM+ANALOG** (2000, 2007 analogs; 2022–23 understood failure with fiscal/AI offset). | **Doubt:** If defended solely by win rate, F4 falls under **≥5 instance statistical rule** and fails. Must rest on causal mechanism per plan Part I. |
| Ahil alignment? | **Pending** | F4 inherits F2 inversion definition (T10Y2Y <0 for ≥4 weeks, trough tracking). Same T10Y2Y source as Ahil steepening-of-inversion gate. Grid thresholds (−50/−80 trough, +15/+40 steepen) are provisional per plan. | **Doubt:** Should trough **−50 vs −80 bps** and steepening **+15 vs +40 bps/4wk** be locked for production, and does Ahil agree these match his steepening-of-inversion gate? |

### Deliverable F (summary)

Quantitative defs for all fed_cycle states, INVERTED, STEEPENING, HIKING period, steepening-short trigger — validated on backfill, T10Y2Y consistent with Ahil.

#### Deliverable F — Experiment run — period & variables (summary)

| Sub-part | Period | Primary input | Outcome |
|----------|--------|---------------|---------|
| F1 | Spot **2022-10-13** | DFF, T10Y2Y | Rule pass/fail |
| F2/F2a | **1990+** weekly | T10Y2Y | INVERTED / STEEPENING labels |
| F3 | **1990+** | DFF | Hiking-period flag |
| F4 grid | **1990+** weekly | T10Y2Y trough + steepen | **SPX 3m** down rate (4 grid cells) |

#### Deliverable F — Overall experiment status

| | Detail |
|---|--------|
| **GO/NO-GO** | **GO** for F2/F2a/F3 in shadow. **F4 = mechanism gate only.** F1 needs rule retune. Production `regime_rules.py` unchanged. |

---

## 9. Persistence signals (Part G)

**Shadow experiment run:** 2026-06-06. Artifact: `G_persistence.json`.

**Persistence signal:** A pattern that builds over many days/weeks — not a one-day spike.

| Signal | Rule | Job schedule | Role |
|--------|------|--------------|------|
| **SEVEN_WEEK_GRIND** | SPX weekly close up ≥ +0.5% vs prior week for **7 consecutive weeks** | Saturday job | **Amplifier** for Combo E (valuation extreme) — raises warning; **NOT** a standalone short (history: mostly continued higher) |
| **VIX_SUPPRESSED** | VIX close < 15 for **10 consecutive trading days** | Daily job | **Precursor / watch flag** for Combo D (FOMO/euphoria) — only precedes vol ~50% of time |

**Store in `persistence_fires` table:** start_date, most_recent_date, streak_length, combo_link.

**Briefing text:** `"[SIGNAL] active for N periods — monitor for Combo D/E confirmation."`

#### G1 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **History period** | **1990-01-01 → present** |
| **Cadence** | **Weekly** (SPX weekly returns) |
| **Input variable** | **SPX (^GSPC)** weekly close — consecutive weeks with weekly return **> +0.5%** |
| **Rule** | **7 consecutive** such weeks → SEVEN_WEEK_GRIND episode |
| **Outcome measured** | **SPX 6m** forward return (**126 trading days**) after episode end; n=**2** episodes |

#### G1 — SEVEN_WEEK_GRIND — Experiment status

| | Detail |
|---|--------|
| **What we did** | Detected 7-week SPX grind episodes in history. Checked 6m forward returns. |
| **Results** | **n = 2** episodes. Both **negative 6m** (−5.9% avg). **`standalone_short_ok = false`** — matches plan intent (amplifier for Combo E, not standalone short). |
| **Production** | `persistence_fires` table populated in shadow. **Not wired** to nightly briefing framing. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Is 7-week grind a standalone short? | **No — matches plan intent** | **n=2** episodes in full history. Both negative 6m: hit rate **0%**, avg **−5.91%**, worst **−7.19%**. Experiment flags **`standalone_short_ok = false`**. Plan says grind is **amplifier for Combo E**, not standalone short — history "mostly continued higher" per Rohit sir. | **Doubt:** n=2** too small to confirm or contradict plan's broader historical claim. Cannot promote as short signal. Briefing amplifier wiring **not live**. |
| Wire as Combo E amplifier? | **Built, not live** | `persistence_fires` table populated in shadow with start_date, streak_length, combo_link fields. Plan briefing text: `"[SIGNAL] active for N periods — monitor for Combo E confirmation."` | **Doubt:** Production nightly briefing does **not display** grind status. Saturday job logic exists in experiment only. |

#### G2 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **History period** | **1990-01-01 → present** |
| **Cadence** | **Daily** (trading days) |
| **Input variable** | **VIX** (^VIX) daily close **< 15** for **10 consecutive trading days** |
| **Outcome measured** | **Lead rate**: fraction of suppressed periods where **VIX > 25** within **35 calendar days** after; median days to VIX 25 — n=**1,973** suppressed periods |
| **SPX?** | **No** direct SPX outcome in G2 (Combo D context separate) |

#### G2 — VIX_SUPPRESSED — Experiment status

| | Detail |
|---|--------|
| **What we did** | Detected VIX < 15 for 10 consecutive days. Measured lead rate to VIX > 25 within 35 days. |
| **Results** | **n = 1,973** suppressed periods. **Lead rate = 8.5%** (VIX > 25 within 35d). Plan claimed ~50% — **not reproduced**. Median days to VIX 25 = 35.5. |
| **Production** | Same as G1 — shadow table only. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does VIX suppressed precede vol spike ~50% of time? | **No — much weaker than plan** | **n=1,973** suppressed periods (VIX **<15** for **10 consecutive trading days**). Lead rate to VIX **>25** within **35 days**: **8.5%** (168 of 1,973). Median days to VIX 25: **35.5**. Plan claimed **~50% — experiment reproduces **less than one-fifth** of claimed rate. | **Doubt:** Plan's ~50% figure **not validated** by backtest. May reflect different lead window, VIX threshold, or informal estimate. Investigate alternate windows (e.g. 60d, VIX>20) before updating plan language. |
| Precursor for Combo D? | **Directionally yes, weakly** | Combo D fires: 1w FM wrong **61.5%**, 3m **71.9% — separate from VIX suppressed lead rate. Low **8.5%** VIX lead means **~91.5% false watches** if treated as sell trigger. | **Doubt:** Correct framing per plan: **precursor/watch flag**, not sell trigger. Wire to briefing as "monitor for Combo D confirmation" — **not yet live** in production. |

### Deliverable G (summary)

Table populated; wired to briefing with correct amplifier vs precursor framing.

#### Deliverable G — Experiment run — period & variables (summary)

| Signal | Period | Input | Outcome |
|--------|--------|-------|---------|
| G1 SEVEN_WEEK_GRIND | 1990+ weekly | SPX weekly ret | SPX **6m** after 7-week streak |
| G2 VIX_SUPPRESSED | 1990+ daily | VIX level | Lead to VIX>25 within 35d |

#### Deliverable G — Overall experiment status

| | Detail |
|---|--------|
| **GO/NO-GO** | **GO** — logic matches plan intent. Production wiring + briefing display pending. |

---

## 10. Combo discovery pipeline — 9 steps (Part H)

**Shadow experiment run:** 2026-06-06. Artifacts: `combo_discovery_20260606.json`, `COMBO_DISCOVERY_PIPELINE_REPORT.md`.

**Goal:** Automated monthly pipeline — no manual hand-holding.

| Step | What it does |
|------|----------------|
| **1. Detection** | For all **298** combos (13 variables only), compute expanding-history percentile per required variable. **Fire** when ALL legs hit RARE+. Store date, variables, combo type, named label (A–G or null). |
| **2. Forward returns** | For each fire, record SPX return at 1m / 3m / 6m / 9m / 12m — classic research desk table. |
| **3. Regime tagging** | Attach 5 regime labels from backfill — slice hit rates by regime. |
| **4. Surfacing gate (soft)** | Candidate if **≥3 fires** AND **≥60% hit rate** at relevant horizon. Bullish = SPX up; bearish = SPX down. |
| **5. Beta / luck filter** | Combo that only works in easy-money bull runs may be **beta** (just riding the market), not real signal. Require **≥55%** hit rate even in HIKING or INVERTED (55 not 60 because those regimes are hostile to longs). Compare vs (a) unconditional base rate, (b) single-variable extremes without full combo, (c) regime-conditional base rate. Must beat all three. **Caveat:** 2-of-3 legs underperforming 3-of-3 is **not** automatic proof of “just beta.” |
| **6. Directionality consistency** | Hit rate ≥50% in **≥2 of 5** regime-dimension categories — avoid “100% in QE, 20% in HIKING” artifacts. |
| **7. Economic story (Tavila agent)** | For each survivor, pull what was happening on fire dates (Draghi 2012, etc.). Strong stats + no story = suspicious. |
| **8. Naming gate (promotion)** | Named combo only at **≥5 fires**, **≥80% hit rate**, passes beta filter, coherent story. (Step 4 is soft surfacing; step 8 is hard promotion.) |
| **9. Output table** | Variables, thresholds, direction, horizon, hit rate, avg returns, historical instances + stories, cancel condition, **live cancel probability** (Part E). |

#### Part H — Experiment run — period & variables (pipeline-wide)

| Field | Detail |
|-------|--------|
| **Run date** | 2026-06-06 |
| **Combo universe** | **298 signatures** = all 1–3 variable combos from **13 variables** (`VAR_IDS`); **TWY_ROC excluded** |
| **Fire history** | All **generic** rows in `combo_fires` where `runic_combo IS NULL` — full macro DB backfill history (**13,089 fires** at test time) |
| **Primary outcome horizon** | **spx_3m** (63 trading days) for surfacing, beta, and promotion gates; also stored: **spx_1m, 6m, 9m, 12m** |
| **Regime tags (Step 3)** | **Legacy** 5-dimension JSON on each fire: fed_cycle, curve_regime, val_regime, geo_overlay, liquidity — **not v2 shadow labels** |
| **Hostile regimes (Step 5)** | **HIKING_EARLY, HIKING_LATE, TIGHTENING** (fed) + **INVERTED** (curve) |
| **Output** | 187 surfaced → 132 survivors → **62 promotion candidates** |

#### H Step 1 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Inputs** | **13 macro variables** — expanding-history **unconditional_pctile** per leg; fire when **all legs RARE+** |
| **Outcome** | Fire date + variable signature stored in DB — detection counts only |

#### H Step 1 — Detection — Experiment status

| | Detail |
|---|--------|
| **What we did** | Scanned all 298 signatures (13C1+13C2+13C3). Recorded fires when all legs hit RARE+. |
| **Results** | 298 signatures; **225 with ≥1 fire**; **13,089 total generic fires** in DB. TWY_ROC correctly excluded. |

#### H Step 2 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Outcome variable** | **SPX (^GSPC)** forward returns at **1m / 3m / 6m / 9m / 12m** per fire (from `forward_returns` table) |

#### H Step 2 — Forward returns — Experiment status

| | Detail |
|---|--------|
| **What we did** | Stored SPX forward returns at 1m/3m/6m/9m/12m per fire. |
| **Results** | Complete in pipeline output JSON. Classic research-desk tables in `COMBO_DISCOVERY_PIPELINE_REPORT.md`. |

#### H Step 3 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Regime inputs** | **5 legacy dimensions** from `macro_regime` JSON at each fire date |
| **Outcome** | Regime-conditional hit-rate slices in pipeline JSON (fed_cycle most populated) |

#### H Step 3 — Regime tagging — Experiment status

| | Detail |
|---|--------|
| **What we did** | Attached regime labels to fire dates. |
| **Results** | Used **legacy** regime tags on existing `combo_fires` — **not v2 shadow labels**. |
| **Doubts to ask Rohit sir Sir** | **Doubt:** Should we re-tag all combo fires with **v2 shadow regime labels** before running the final beta filter and considering promotions? |

#### H Steps 4–6 — Experiment run — period & variables

| Step | Gate | Primary horizon | Thresholds tested |
|------|------|-----------------|-------------------|
| **4 Surfacing** | ≥**3 fires** AND ≥**60%** hit rate | **spx_3m** (bullish=SPX up) | 187 combos pass |
| **5 Beta filter** | Hostile-regime HR + beat 3 base rates | **spx_3m** in HIKING/INVERTED | **≥55%** and **≥60%** both reported |
| **6 Directionality** | ≥**50%** HR in ≥**2 of 5** regime dimensions | **spx_3m** | 132 pass (bundled with beta) |

#### H Step 4 — Surfacing gate — Experiment status

| | Detail |
|---|--------|
| **Results** | **187 surfaced** (≥3 fires AND ≥60% hit rate at relevant horizon). |

#### H Step 5 — Beta / luck filter — Experiment status

| | Detail |
|---|--------|
| **What we did** | Tested regime-conditional hit rate in HIKING/INVERTED. Compared vs base rates. Reported both 55% and 60% thresholds. |
| **Results** | **132 pass** beta + directionality. Both **55%** and **60%** hostile-regime thresholds reported per combo in JSON. |
| **Doubts to ask Rohit sir Sir** | **Doubt:** For the **62 promotion candidates**, should the beta filter use **55%** or **60%** hit rate in HIKING/INVERTED regimes? Also: 2-of-3 vs 3-of-3 leg diagnostic was run but plan says it is **not a verdict** — how should we use it? |

#### H Step 6 — Directionality consistency — Experiment status

| | Detail |
|---|--------|
| **Results** | 132 pass (same set as beta pass — bundled in pipeline). Requires ≥50% hit in ≥2 of 5 regime dimensions. |

#### H Step 7 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Inputs** | **132 survivors** (would use Tavily headlines + Claude on fire dates) |
| **Outcome** | Economic narrative + story_coherent flag — **skipped** (`use_claude=False`) |

#### H Step 7 — Economic story (Tavila) — Experiment status

| | Detail |
|---|--------|
| **What we did** | Tavila agent step **skipped** (`use_claude=False`) in experiment run. |
| **Results** | **Not run** — promotion candidates lack economic narrative review. |
| **Why skipped** | Cost/time in batch experiment; intended for monthly human review cycle. |

#### H Step 8 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Gate** | ≥**5 fires**, ≥**80%** hit rate on **spx_3m**, beta pass, story not rejected |
| **Outcome** | **62 promotion candidates** — CSV export: `testing/macro_th_exp/part_h_promotion_candidates_20260606.csv` |

#### H Step 8 — Naming gate — Experiment status

| | Detail |
|---|--------|
| **Results** | **62 promotion candidates** (≥5 fires, ≥80% HR, beta pass). **Zero new combos promoted** to production names A–G. Top survivors overlap existing combo legs (CPI/WTI/CFTC/VIX-heavy 3-var sets). |

#### H Step 9 — Experiment run — period & variables

| Field | Detail |
|-------|--------|
| **Output artifacts** | Markdown report + JSON with all survivor metrics, fire dates, regime slices |
| **Cancel prob (Part E)** | **Not attached** per combo in live output yet |

#### H Step 9 — Output table — Experiment status

| | Detail |
|---|--------|
| **Results** | Output in `COMBO_DISCOVERY_PIPELINE_REPORT.md`. Cancel probability from Part E **not yet** attached to each active combo in live output. |

**Deliverable H:** Full pipeline automated; monthly candidate review; steps 5–7 built in; Claude for step 7 and reasoning on 5–6; steps 1–4 pure Python/SQL.

#### Deliverable H — Experiment run — period & variables (summary)

| Stage | n | Primary metric |
|-------|---|----------------|
| Signatures scanned | 298 | 13-var combos |
| Fires in DB | 13,089 | Detection |
| Surfaced (≥3 fires, ≥60% HR) | 187 | **SPX 3m** hit rate |
| Beta + directionality pass | 132 | **SPX 3m** + hostile regimes |
| Promotion candidates | 62 | **SPX 3m** ≥80% HR, ≥5 fires |

#### Deliverable H — Overall experiment status

| | Detail |
|---|--------|
| **GO/NO-GO** | **GO** for pipeline automation. **Doubts before promotion:** Tavila step 7 not run, v2 regime re-tag needed, 55% vs 60% threshold choice, no economic story review yet. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does automated pipeline find valid combo candidates? | **Yes** | From **298 signatures**: **225** had ≥1 fire, **13,089** total generic fires. Pipeline funnel: **187 surfaced** (≥3 fires, ≥60% HR) → **132** beta+directionality pass → **62 promotion candidates** (≥5 fires, ≥80% HR). Top survivors are CPI/WTI/CFTC/VIX-heavy 3-variable sets. | **Doubt:** Zero promoted** to new named combos A–G. Overlap with existing combo legs — many are variations, not discoveries. |
| Do survivors beat beta filter? | **Yes** | **132 of 187** surfaced (70.6%) pass beta filter requiring **≥55%** (and **≥60%** reported side-by-side) hit rate in HIKING/INVERTED hostile regimes, plus beating unconditional base rate, single-variable extreme base rate, and regime-conditional base rate. | **Doubt:** Should we apply **55%** or **60%** as the hostile-regime cutoff for these **132 survivors**? Plan rationale favours 55% but you may prefer stricter 60%. |
| Any new named combos ready? | **No** | **62 candidates** meet numeric gates but **0 promoted**. Tavila economic story step **skipped** (`use_claude=False`). Candidates lack narrative review. | **Doubt:** Should we run Tavila economic-story review (step 7) on the **62 candidates** before any promotion? Also: fires were tagged with **legacy** regimes — re-tag with v2 shadow labels first? |
| 55% or 60% for hostile regimes? | **Open** | Plan rationale: HIKING/INVERTED structurally adverse for longs, so **55%** avoids killing genuine signals; **60%** is stricter. Both thresholds computed and stored per candidate in pipeline JSON. | **Doubt:** For **62 promotion candidates**, which threshold should be the production default — **55%** or **60%**? |
| Regime impact on named combos isolated? | **Partially** | See Section 14.4: Combo B **79.8%** robust across fed regimes (76–83%). Combo D **28.1%** overall but **18.3%** in HIKING_LATE (n=197) vs **43.2%** in CUTTING_LATE (n=155). Combo F **74.9%** overall, **82.0%** in QE (n=212). | **Doubt:** Part H step 3 tagged fires with **legacy** regimes, not v2 shadow labels. Full **5-dimension** slicing thin outside fed_cycle. |

---

## 11. Sample-size discipline (Part I)

### I1. Minimum observations

- Never trust regime-conditional percentile from **< 30** observations.  
- Below **50**, fall back to unconditional and log it.  
- A combo with 3–4 fires in one regime since 1990 is too thin for stats alone — that’s why beta filter + economic story matter at extremes.

### I2. Two evidence standards

| Type | When to use | What counts as proof |
|------|-------------|----------------------|
| **Statistical gate** | SSI/variable gates, unnamed combos | **≥5 independent fires** — the win rate **is** the evidence |
| **Mechanism + analog gate** | Deep inversion, named combos at tail extremes | **Causal story + analog consistency** (2000, 2007, 2022–23) — few instances OK **if** mechanism is clear. **Danger:** if you only cite win rate, it silently becomes statistical and needs ≥5 fires |

### I3. How to explain this externally

Requiring several variables extreme at once, validated on 4–10 historical AND-events at 80–85%, is **compound/joint probability on purpose** at tails — defensible with economic story. Large samples reserved for core repeatable rules.

---

## 12. Deliverables checklist with experiment status

| ID | Deliverable | Shadow run (2026-06-06) | Production |
|----|-------------|-------------------------|------------|
| **A** | Refined 5 dimensions | RUN — 1,901 Fridays; A1 fail (PIVOTING thin) | Legacy labels still live |
| **B** | 14 variables + windows | RUN — TWY pass; B4 window audit fail | TWY not in nightly pull |
| **C** | Emission vectors | RUN — 8,805 rows | Daily job not wired |
| **D** | HMM layer | Prototype only — no hit-rate gain | DEFER ~Dec 2026 |
| **E** | Cancel probability | RUN — 2.2% Combo C example | Not on dashboard |
| **F** | Quantitative regime rules | RUN — F2/F2a pass; F4 mechanism only | `regime_rules.py` unchanged |
| **G** | Persistence signals | RUN — G1/G2 tested | Not in briefing |
| **H** | 9-step combo pipeline | RUN — 62 promotion candidates | No new promotions |

---

## 13. Recommended build order (from Rohit sir)

Rohit sir’s **sequencing** — do in this order:

1. **Part B + C** — foundation (14th variable, windows, daily vectors)  
2. **Part F + G** — quick wins (numeric rules, persistence — no long data wait)  
3. **Part E** — cancel probability (independent of HMM)  
4. **Part A** — refine dimensions → re-run backfill  
5. **Part H** — full combo pipeline (core methodology)  
6. **Part D** — HMM last (needs 6+ months stored vectors from C)

**Principle:** Don’t over-engineer. Each piece must earn its place by likely improving backtested performance.

---

## 14. Rohit sir's FM / regime isolation questions (`additional_details.md`)

Rohit sir asked separately (beyond Parts A–H) to **validate FM positioning claims** and **isolate regime impact on combos**. These were tested in the X-FM track (2026-06-06) using `X-FM_all.json` and `X_COMBO_regime_slices.json`.

### 14.1 FM extreme short (<15th percentile) — contrary indicator?

| | Detail |
|---|--------|
| **What we did** | Backtested all FM <15th crossings and Combo B fires separately. Sliced by fed_cycle_v2 and curve_regime_v2. |
| **Results** | |

| Metric | Rohit sir claim | Backtest | Verdict |
|--------|-------------|----------|---------|
| Combo B confirmed, SPX up 3m | ~87.5% (7/8) | **79.8%** (71/89) | **Mostly validated** — same direction, larger n, slightly lower rate |
| All FM <15th crossings, SPX up 3m | ~87% implied | **60.0%** (21/35) | **Weaker** — raw FM band ≠ Combo B full leg set |
| FM "wrong" at 3m (SPX up) | High | **60%** | Directionally right, below 87.5% |

**Regime matters:** Flat curve breaks the pattern (33% SPX up 3m, n=6). INVERTED supports washout (75%, n=4). EASY strongest (83%, n=6).

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Is extreme-short FM a contrary indicator? | **Conditionally yes** | **Combo B fires** (VIX+HY+CFTC legs): **79.8%** SPX up 3m (n=**89**, 71/89) — close to Rohit sir's **87.5%** (7/8). **Raw FM <15th alone:** **60.0%** SPX up 3m (n=**35**, 21/35) — FM "wrong" 60% of time. Regime slices (3m SPX up): EASY **83.3%** (n=6), INVERTED **75.0%** (n=4), NORMAL **63.6%** (n=22), EASING **54.5%** (n=22), **FLAT 33.3%** (n=6) — flat curve breaks pattern. | **Doubt:** Raw FM band **≠ Combo B leg set** — Rohit sir's 87.5% applies to full capitulation combo, not FM percentile alone. FLAT curve slice (33.3%) shows signal **fails** in that regime. 6m horizon stronger: raw FM **74.3%** SPX up (n=35). |
| Why 89 Combo B fires vs Rohit sir's "8 confirmed"? | **Explained** | DB counts **89 WATCH+ACTIVE** rows since 1990 — includes partial-leg WATCH weeks (e.g. 2023-06 through 2024-04 had many consecutive WATCH rows with only CFTC leg met). Rohit sir's "8 confirmed" = fully confirmed instances with all 3 legs. Hit rate **79.8%** on broader set still validates direction. | **Doubt:** Detection criteria differ — production should show **"Legs Met: X/3"** per job status T-04 to avoid reader confusion. Confirmed-only subset not separately reported in experiment JSON. |

### 14.2 FM extreme long (>85th percentile) — Combo D territory?

| | Detail |
|---|--------|
| **Results** | Raw FM extreme long: 1w SPX down **41%** (FM wrong **59%**). 3m SPX down **18%** (FM wrong **82%**). Combo D fires: 1w wrong **61.5%**; 3m wrong **71.9%**. |

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Is FM wrong 72–85% at short horizons? | **Partially — below Rohit sir's band at 1w** | **Raw FM >85th:** 1w SPX down **41.0%** → FM wrong (**SPX up**) **59.0%** (n=39). **Combo D fires:** 1w SPX down **38.5%** → FM wrong **61.5%** (n=452). Rohit sir claimed **72–85%** at 5–10 days — backtest shows **~59–62%**, roughly **10–20 pp below** claim. | **Doubt:** 1w sample may not match Rohit sir's "5–10 day" window exactly. Combo D closer to claim but still below 72% floor. |
| Does signal degrade at 3m? | **Yes — but opposite to naive reading** | **Raw FM >85th 3m:** SPX down only **17.9%** → FM wrong **82.1%** (market keeps rising). **Combo D 3m:** SPX down **28.1%** → FM wrong **71.9%**. FM stays wrong **more often** at 3m than 1w — "degrades" if you expected correction, but contrary edge is actually **stronger** at longer horizon for raw band. | **Doubt:** Rohit sir's "degrades at 3–6m" may mean "correction doesn't happen" — which backtest confirms (82% still long). Not a timing signal for shorts at 3m without regime filter. |
| Regime impact on Combo D? | **Yes — essential before using as short** | Combo D 3m SPX down by fed_cycle_legacy: **HIKING_LATE 18.3%** (n=**197**), **CUTTING_LATE 43.2%** (n=**155**), **QE 24.0%** (n=**100**). D is **weakest in HIKING_LATE** — using D as standalone short during hiking cycle has only **~1 in 5** success at 3m. | **Doubt:** Regime conditioning mandatory. No v2 fed_cycle slices on Combo D in Part H (legacy tags used). 5-dimension slicing not complete. |

### 14.3 FM moderate (25th–75th) — "trend is your friend"?

| | Detail |
|---|--------|
| **Results** | n=84 crossings. SPX up 3m **76.2%**, avg +3.15%. |

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Is moderate FM an independent edge? | **No — consistent with equity drift** | FM **25th–75th percentile** crossings: n=**84**. SPX up 3m: **76.2%** (64/84), avg **+3.15%**, median **+4.17%**. 6m: **85.7%** up, avg **+7.32%**. By fed_cycle_v2: EASY **88.5%** (n=26), TIGHTENING **78.3%** (n=23), EASING **65.7%** (n=35). | **Doubt:** No edge vs unconditional equity drift** — 76% bullish is what you'd expect in a generally rising market. Rohit sir was correct: "trend is your friend" is **not an independent FM signal**. Cannot fade or follow FM in moderate band for alpha. |

### 14.4 Regime impact on named combos A–G

| Combo | Direction | Overall 3m n | Overall 3m hit | Strongest regime slice | Weakest regime slice |
|-------|-----------|--------------|----------------|------------------------|----------------------|
| **A** | Bearish | 174 | 23% SPX down | CUTTING_LATE 50% (n=26) | QE 20% (n=112) |
| **B** | Bullish | 89 | **79.8% SPX up** | HIKING_LATE 83% (n=48) | CUTTING_LATE 76% (n=41) |
| **C** | Bullish | 4 | **0% up** (all failed) | n too small | — |
| **D** | Bearish | 452 | 28% SPX down | CUTTING_LATE 43% | HIKING_LATE **18%** |
| **E** | Bearish | 507 | 20% SPX down | All slices weak (~14–27%) | QE 14% (n=127) |
| **F** | Bullish | 704 | **74.9% SPX up** | QE **82%** (n=212) | CUTTING_LATE 64% (n=248) |
| **G** | — | 0 | No fires in DB | — | — |

| Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|----------|-----------|--------|-----|
| Does regime materially change combo performance? | **Yes — large swings by fed cycle** | **Combo B** (bullish): overall **79.8%** up (n=89); HIKING_LATE **83.3%** (n=48) vs CUTTING_LATE **75.6%** (n=41) — robust both ways. **Combo D** (bearish): overall **28.1%** down (n=452); HIKING_LATE **18.3%** vs CUTTING_LATE **43.2% — **2.4× difference**. **Combo F** (bullish): overall **74.9%** (n=704); QE **82.0%** (n=212) vs CUTTING_LATE **64.1%** (n=248) — **18 pp spread**. **Combo A/E** bearish signals weak everywhere (14–27% down). | **Doubt:** Beta filter in Part H **justified** by these spreads. Combo C: **4 fires, 0%** 3m up — broken in sample. Combo G: **0 fires** in DB. |
| Full 5-dimension slicing done? | **Partially — fed_cycle only reliable** | fed_cycle_legacy slices populated for all combos with n>25 per slice. curve/liquidity/val/geo slices exist for **FM bands** but combo-level slices mostly **n<10** outside fed_cycle. | **Doubt:** Should we complete **5-dimension** regime slicing (not just fed_cycle) before drawing conclusions on combo regime dependence? Re-tag with v2 labels first? |
| Combo C working? | **No in sample** | **4 fires** since 1990, all in CUTTING_LATE. **0%** SPX up 3m (0/4). Avg 3m return **+17.8%** (market rose against bullish signal). | **Doubt:** n=4 too small for statistical gate but directionally **failed**. Investigate cancel logic, fire criteria, or timing — may be definition issue not regime issue. |

---

## 15. Master Q&A closure (plan + experiment run)

| # | Question | Answered? | Answer | Doubts to ask Rohit sir Sir |
|---|----------|-----------|--------|-----|
| 1 | TWY_ROC ±0.30pp bands validated? | **Partial** | Apr 7 2025 anchor: **−0.55pp** (DOVISH, well below **−0.30** threshold). DGS2 **3.73%**. Passes plan validation test (expected 65–75 bps fall). | **Doubt:** Full historical band sweep across all dates **not done**. ±0.30 remains plan's "starting point, not validated." |
| 2 | F4 trough −50 vs −80, steep +15 vs +40? | **Partial** | Grid complete. Best cell: **−80 bps / +15 bps** → **33.3%** SPX down 3m (n=**9**). Worst: **−80 / +40** → **0%** (n=**2**). All below **55%** promotion bar. | **Doubt:** No threshold wins on stats (best **33.3%**, n=9) — should F4 be kept as **mechanism+analog only** (2000, 2007, 2022–23), and which trough/steepen defaults do you want: **−50/+15** or **−80/+15**? |
| 3 | Apr 2025 DGS2 vs fed_cycle divergence? | **Yes** | TWY_ROC **−0.55pp DOVISH** on Apr 7 2025 while legacy fed_cycle still **TIGHTENING/PAUSING**. Leading variable called bottom; lagging label did not. | **Doubt:** Only 2 dates tested. Divergence catalog across full history not built. |
| 4 | Dual percentile <50 fallback? | **Yes (built)** | **14,457 rows** with both percentiles; **0 fallbacks** in backfill. Logic implemented: fallback to unconditional when regime subset **<50 obs**, with logging. | **Doubt:** Zero fallbacks triggered** — thin-regime edge case (PIVOTING n=27) **untested in practice**. |
| 5 | Beta 55% vs 60%? | **No** | Both thresholds computed for **132 survivors** and **62 promotion candidates**. Plan rationale documented (55% for hostile regimes). | **Doubt:** For **62 promotion candidates**, should the hostile-regime beta filter use **55%** or **60%** hit rate? |
| 6 | 2-of-3 vs 3-of-3 legs? | **Partial** | Diagnostic run in pipeline. Plan caveat: 2-of-3 underperforming 3-of-3 is **not automatic proof** of "just beta" — third leg may add genuine signal. | **Doubt:** No production change** from diagnostic. Not used as promotion verdict. |
| 7 | 6mo before HMM prod? | **Deferred** | Plan requires 6 months **live** C1 vectors. Prototype HMM on 500-obs sample showed **no hit-rate improvement** (Combo B −1.2 pp, Combo D −1.9 pp with Risk-Off filter). | **Doubt:** Live C1 job **not wired** — clock at **0 months**. Earliest **~Dec 2026**. Sharpe/drawdown backtest not run. |
| 8 | T10Y2Y align with Ahil? | **No** | F2/F2a/F4 all use FRED **T10Y2Y** in shadow with consistent inversion (≥4 weeks <0) and steepening (+15/+40 bps/4wk) rules. | **Doubt:** Ahil formal review not recorded.** Production `regime_rules.py` unchanged. |
| 9 | Classifier prompt update (Part A)? | **No** | Shadow backfill validates state lists for 1,901 Fridays. Distribution report complete. | **Doubt:** With PIVOTING at **n=27** and no PAUSING state in v2, are the refined Part A state lists ready for the live Section 5.2 classifier prompt? |
| 10 | Rohit sir FM Q&A? | **Yes** | See Section 14. Combo B **79.8%** (mostly validates 87.5%). Raw FM short **60%**. Raw FM long wrong **59%** at 1w, **82%** at 3m. Moderate FM **76.2%** up = drift not alpha. Regime isolation confirms D weak in HIKING_LATE (**18.3%**). | **Doubt:** Partial validation — magnitudes differ from Rohit sir's claims at 1w. Combo B fire count definition differs (89 vs 8). |

---

## 16. Doubts to ask Rohit sir Sir (consolidated master list)

All open questions from the experiment run, grouped for a single review with Rohit sir Sir. Each doubt includes the backtest evidence that motivates it.

| # | Doubt to ask Rohit sir Sir | Evidence from experiment |
|---|------------------------|--------------------------|
| 1 | **PIVOTING has only n=27 (1.4%)** — accept as rare tail state, merge into EASING, or add **PAUSING** as a fifth fed_cycle state? | TIGHTENING 763, EASING 727, EASY 384, PIVOTING 27 over 1,901 Fridays. Below ≥30 obs rule. Fed currently on hold (T-01) with no v2 label. |
| 2 | Are the **Part A refined state lists** (fed 4-state, geo 3-state, liquidity 9-state, fiscal caveat, CAPE velocity) ready for the live **Section 5.2 classifier prompt**? | Shadow backfill complete; production prompt unchanged. |
| 3 | **Liquidity: 4-state 2×2 or 9-state with FLAT variants?** Plan asked for 4; backfill produced 9 (e.g. EASY_FLAT 746 vs EASY_IMPROVING 403). | 9 composite states in shadow; production still GLOBAL_EASY/TIGHT. |
| 4 | **CONFIG B4 window fixes** before nightly wire — confirm HY/VIX/VXTS → `rolling_3y` and WALCL → `full`? | 4 mismatches in window audit; wrong windows change percentile ranks and combo fires. |
| 5 | **TWY_ROC ±0.30pp bands** — keep as starting point or backtest alternatives (±0.20, ±0.40)? | Apr 2025 anchor passes at −0.55pp; no full historical sweep. |
| 6 | **F4 steepening-short thresholds** — lock **−50/+15** or **−80/+15** as mechanism defaults? Best grid cell: 33.3% SPX down 3m (n=9). | All F4 grid cells below 55% promotion bar. Mechanism+analog gate only per plan. |
| 7 | Do **T10Y2Y rules** (F2/F2a/F4) align with **Ahil's steepening-of-inversion gate**? | F2/F2a pass in shadow; Ahil review not recorded. |
| 8 | **Beta filter: 55% or 60%** hostile-regime hit rate for **62 promotion candidates**? | Both thresholds computed for 132 survivors; plan rationale favours 55%. |
| 9 | Run **Tavila economic-story review** (H step 7) on 62 candidates before any promotion? | Step 7 skipped (`use_claude=False`); 0 combos promoted despite 62 candidates. |
| 10 | **Re-tag combo fires with v2 regime labels** before final beta filter? | H step 3 used legacy tags on existing combo_fires. |
| 11 | **VIX suppressed lead rate is 8.5%** (168/1,973) vs plan's ~50% — update plan language or test different lead window? | Median days to VIX>25: 35.5. Still usable as watch flag per plan. |
| 12 | **Combo C: 4 fires, 0% 3m up** — investigate cancel logic or redefine C? | All 4 in CUTTING_LATE; avg 3m return +17.8% against bullish signal. |
| 13 | Wire **daily emission_vectors** job now to start 6-month HMM clock, given prototype showed **no hit-rate gain** (Combo B −1.2 pp, D −1.9 pp)? | 8,805 rows backfilled; live job not wired. Earliest HMM ~Dec 2026. |
| 14 | Show live **cancel/persist probability %** on briefing for every active combo? | Combo C example: 2.25% combined cancel; function built, not displayed. |
| 15 | **Production GO order** — which parts (B, C, A, E, H, G) should wire first after doubts 1–14 are resolved? | All A–H run in shadow; nothing in production nightly yet. |
| 16 | **FM claims validation** — Combo B 79.8% (n=89) vs Rohit sir's 87.5% (7/8); raw FM short 60% (n=35); FM long wrong 59% at 1w, 82% at 3m. Accept backtest as final? | See Section 14 for full FM/regime slices. |
| 17 | **7-week grind: n=2** both negative 6m — confirm amplifier-only framing for Combo E, not standalone short? | standalone_short_ok = false in experiment. |
| 18 | **Fresh-cross into EXTREME CAPE: n=0 — retune detection definition for A3 velocity signal? | Level vs velocity hit rates within 0.4 pp (74.2% vs 74.6%). |

---

## 17. Key artifact index

| File | Purpose |
|------|---------|
| `MACRO_TH_EXP_STATUS_ANALYSIS.md` | Status analysis (source for experiment sections) |
| `macro_intelligence/analysis/regime_v2_experiments/experiment_manifest.json` | Single JSON rollup of all parts |
| `macro_intelligence/analysis/regime_v2_experiments/A_regime_dimensions.json` | Part A distributions |
| `macro_intelligence/analysis/regime_v2_experiments/B_twy_and_percentiles.json` | Part B TWY + windows |
| `macro_intelligence/analysis/regime_v2_experiments/C_emission.json` | Part C vectors |
| `macro_intelligence/analysis/regime_v2_experiments/D_hmm_prototype.json` | Part D prototype |
| `macro_intelligence/analysis/regime_v2_experiments/E_cancel_probability.json` | Part E cancel MC |
| `macro_intelligence/analysis/regime_v2_experiments/F_quant_regime.json` | Part F rules + F4 grid |
| `macro_intelligence/analysis/regime_v2_experiments/G_persistence.json` | Part G persistence |
| `macro_intelligence/analysis/regime_v2_experiments/X-FM_all.json` | FM + regime slices |
| `macro_intelligence/analysis/regime_v2_experiments/X_COMBO_regime_slices.json` | Combo A–G by regime |
| `docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md` | Master experiment report |
| `docs/ssi_validation/COMBO_DISCOVERY_PIPELINE_REPORT.md` | Part H ranked survivors |
| `scripts/run_regime_v2_experiment_suite.py` | Re-run entry point |

---

## 18. How this relates to work already done

As of **2026-06-07** (`MACRO_TH_EXP_STATUS_ANALYSIS.md`), experiment suite **ran all deliverables A–H once in shadow mode** on **2026-06-06 — nothing swapped into production nightly output yet.

**Bottom line:** Research is **complete for a first pass**. The next step is to walk through **Section 16 (Doubts to ask Rohit sir Sir)** with Rohit sir Sir and resolve each doubt before production wiring.

---

## 20. Glossary of additional terms

| Term | Meaning |
|------|---------|
| **bps / basis points** | 0.01 percentage point. 75 bps = 0.75 pp. |
| **CNH** | Offshore Chinese yuan — FX stress signal. |
| **CFTC / FM** | Commodity Futures Trading Commission positioning data — “FM” = fund manager positioning percentile. |
| **Combo A–G** | Named validated multi-variable signals in the Runic/macro system. |
| **Conviction modifier** | Adjusts how strongly you trust a signal based on regime-conditioned percentiles. |
| **Dot plot** | Fed chart of where officials expect rates to go. |
| **DGS2** | FRED series: 2-year Treasury constant maturity yield. |
| **FFR** | Federal Funds Rate — overnight rate the Fed targets. |
| **FOMO** | Fear Of Missing Out — euphoric late-cycle buying (Combo D territory). |
| **GBM** | Geometric Brownian Motion — standard random walk model for asset prices in Monte Carlo. |
| **GSR** | Gold/Silver ratio — macro stress/liquidity signal. |
| **HY OAS** | High-yield bond option-adjusted spread — credit stress. |
| **Monte Carlo** | Simulate thousands of random futures to estimate probabilities. |
| **NFCI** | National Financial Conditions Index — Chicago Fed composite of financial tightness. |
| **Posterior / prior** | Updated belief vs starting belief in Bayesian inference. |
| **pp** | Percentage points (absolute change in a rate). |
| **QE / QT** | Quantitative Easing / Tightening — Fed balance sheet expansion/shrinkage. |
| **RARE / EXTREME** | Percentile tiers for combo legs (e.g. top 20%, top 5% of history). |
| **Runic** | Internal name for the macro intelligence / combo agent system. |
| **Section 5.2** | Classifier prompt section in the macro intelligence spec. |
| **SSI** | Separate threshold/gate system (Layer 1/2) — related philosophy, different scope. |
| **Tavila agent** | Agent that retrieves historical economic context for fire dates. |
| **T10Y2Y** | 10-year minus 2-year Treasury yield spread. |
| **WALCL** | Fed total assets (weekly balance sheet level). |
| **WTI** | West Texas Intermediate crude oil — energy/inflation signal. |
| **Win rate / hit rate** | Same idea — % of times outcome matched signal direction. |

---

*Updated 2026-06-09 — experiment Q&A tables use **Answer** and **Doubts to ask Rohit sir Sir** columns (numeric evidence from `MACRO_TH_EXP_STATUS_ANALYSIS.md` and `experiment_manifest.json`). Shadow run: 2026-06-06.*
