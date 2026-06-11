# Macro Regime System v2 — Consolidated Plan Summary

**Audience:** Divyanshu, Rohit, ops, and anyone implementing or validating Runic / macro regime logic  
**Source document:** [`macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`](../../macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf)  
**From:** Rohit → Divyanshu  
**Subject:** Macro regime system v2 — refinements, transition states, HMM layer, and combo discovery methodology  
**Status:** Consolidated plan; supersedes earlier piecemeal notes

**Related docs:**

- [SSI_THRESHOLD_JUSTIFICATION.md](SSI_THRESHOLD_JUSTIFICATION.md) — production SSI and Layer 2 thresholds (separate from Runic variable RARE/EXTREME tiers)
- [SSI_OPEN_QUESTIONS_SUMMARY.md](SSI_OPEN_QUESTIONS_SUMMARY.md) — SSI validation tests; Part I of this mail aligns with its sample-size and evidence-standard framing
- [../MACRO_INTELLIGENCE_MASTER.md](../MACRO_INTELLIGENCE_MASTER.md) — full Runic build reference (12 variables, 7 combos A–G as of June 2026)

---

## 1. Document purpose and context

This email is Rohit’s **single consolidated roadmap** for evolving the macro regime model after a joint review. It is not a threshold sweep report in the SSI validation sense; it is an **architecture and methodology plan** covering:

- Refining the **five regime dimensions** (fed cycle, curve, valuation, geopolitical overlay, liquidity)
- Adding a **14th macro variable** (`TWY_ROC`) for regime classification only
- Moving from **binary threshold firing** to **percentile-rank emission probabilities** and a future **HMM layer**
- Formalizing **quantitative regime definitions** (especially yield-curve inversion and steepening)
- Building an **automated 9-step combo discovery pipeline** with beta and narrative filters
- Applying **two evidence standards** — statistical (≥5 instances) vs mechanism + analog — shared with SSI/Runic gate philosophy

**Goal:** A regime system that is clean, dynamic, and likely to backtest well — consistent with the MindWealth demo and macro agent demo output.

---

## 2. Key findings and recommendations

| Area | Recommendation |
|------|----------------|
| **Regime dimensions** | Keep five dimensions; reduce state granularity where sample sizes are too thin (fed_cycle 7→4, geo_overlay 6→3); expand liquidity 2→4 (2×2 level × direction) |
| **14th variable** | Add `TWY_ROC` (2-year Treasury 8-week rate of change) for **regime classification and conviction modifier only** — **not** in 13Cn combo enumeration |
| **History windows** | Structural/level variables: **full expanding history**; flow/ROC variables: **3-year rolling**; store **both** unconditional and regime-conditioned percentiles daily |
| **Threshold philosophy** | Replace binary “fire or not” with **daily percentile-rank vectors** as partial evidence; accumulate sub-threshold readings over time |
| **HMM** | Layer a **3-state HMM** (Risk-On / Risk-Off / Transition) **after** 6+ months of stored vectors — do not replace the percentile engine |
| **Cancel probability** | Model combo cancel conditions as **digital barrier options** (Monte Carlo for overlapping WTI windows); display live cancel/persist probability on dashboard |
| **Combo promotion** | Soft surface at **≥3 fires, ≥60% hit rate**; hard promotion at **≥5 fires, ≥80% hit rate** plus beta filter and economic story |
| **Evidence discipline** | Statistical gates need **≥5 instances**; tail/mechanism gates (deep inversion, steepening short) justified by **causal logic + analogs**, not win-rate alone |
| **Sequencing** | Do B + C first (foundational), then F + G (quick wins), E early, A (backfill re-run), H (pipeline), D last (HMM) |

---

## 3. Threshold and parameter values discussed

### 3.1 Regime dimension state counts (Part A)

| Dimension | Current | Proposed | Notes |
|-----------|---------|----------|-------|
| `fed_cycle` | 7 states | **4:** TIGHTENING, PIVOTING, EASING, EASY | QE/QT moved to separate liquidity flag |
| `curve_regime` | 4 | **Keep 4:** INVERTED, FLAT, STEEPENING, NORMAL | Fiscal caveat: inversion signal weaker when deficit **>5% GDP** |
| `val_regime` | 4 | **Keep 4:** EXTREME, ELEVATED, FAIR, CHEAP | Add **6-month CAPE percentile rank change** alongside level |
| `geo_overlay` | 6 | **3:** NEUTRAL, ELEVATED_RISK, CRISIS | Reduce Claude API classification noise |
| `liquidity` | 2 | **4 (2×2):** easy/tight × improving/tightening | WALCL direction distinguishes combinations |

### 3.2 Variable #14 — TWY_ROC (Part B)

| Parameter | Value |
|-----------|--------|
| Source | FRED **DGS2** (Friday close) |
| Calculation | DGS2(today) − DGS2(**56 calendar days** ago), in **percentage points (pp)** |
| Direction bands (starting point) | **HAWKISH** if > +0.30pp; **NEUTRAL** if −0.30 to +0.30; **DOVISH** if < −0.30pp |
| History window | **3-year rolling** (flow/ROC group) |
| Combo enumeration | **Excluded** — regime input only |

**Validation anchor:** On ~7 Apr 2025 (tariff-shock bottom), DGS2 fell ~65–75 bps over prior 8 weeks (strongly DOVISH) while fed_cycle still read TIGHTENING/PAUSING — leading variable called bottom before lagging labels.

### 3.3 Percentile storage rules (Part B)

| Storage type | Variables | Window |
|--------------|-----------|--------|
| Unconditional percentile | All 14 | Full expanding (structural) or 3y rolling (flow) per variable |
| Regime percentile | All 14 | Conditioned on `fed_cycle`; fallback to unconditional if **<50** obs |
| Triple storage | CAPE (velocity-sensitive) | Expanding rank + 3y rolling rank + **8-week ROC of rank** |

### 3.4 Yield curve — formal definitions (Part F)

| Concept | Rule | Source |
|---------|------|--------|
| **Inversion event** | T10Y2Y crosses below **0 bps** | FRED T10Y2Y |
| **INVERTED regime** | T10Y2Y **< 0** sustained **≥4 consecutive weeks** | Same |
| **Trough** | Most negative T10Y2Y during inverted regime | — |
| **Variable #9 RARE / EXTREME** (combo detection) | **−30 bps** / **−80 bps** | Separate from regime label |
| **STEEPENING (regime)** | After inversion trough: T10Y2Y rises **≥+15 bps / 4wk** (RARE) or **≥+40 bps / 4wk** (EXTREME) | Align with variable #9 |
| **TIGHTENING-LATE** | FFR **>3.5%** AND FFR up **>150 bps** in 12mo AND (T10Y2Y **<−30 bps** OR hike pace decelerating) | fed_cycle quant rule |
| **HIKING period** (beta test) | FFR rising AND cumulative hike cycle **>100 bps** | — |

### 3.5 Steepening-of-inversion short trigger (Part F4)

| Condition | Threshold |
|-----------|-----------|
| Prior inverted trough | Deeper than **−50 bps** (backtest −50 vs −80) |
| Current curve | Steepening **≥+15 bps/4wk** (backtest +15 vs +40) |
| Offsets inactive | Fiscal deficit **<5% GDP** AND no active QE |
| Evidence standard | **Mechanism + analog** (2000/2007; 2022–23 failure explained by fiscal/AI capex) — **not** win-rate alone |

### 3.6 HMM layer (Part D)

| Parameter | Value |
|-----------|--------|
| States | **Risk-On**, **Risk-Off**, **Transition** |
| Observations | 14 daily percentile-rank vectors |
| Classifier prior rule | If **Risk-Off > 0.40**, weight toward tighter classifications |
| Regime shift signal | Posterior for assumed regime **< 50%** |
| HSMM (phase 2) | Dwell-time distributions mapped to combo durations (SHORT <6w / MEDIUM 6–16w / LONG >16w) |

### 3.7 Combo discovery gates (Part H)

| Stage | Fires required | Hit rate | Other filters |
|-------|----------------|----------|---------------|
| **Surface candidate** | **≥3** | **≥60%** at relevant horizon | Bullish: SPX return >0; bearish: <0 |
| **Regime beta filter** | — | **≥55%** (report 60% side-by-side) in HIKING or INVERTED | Must beat unconditional, single-variable extreme, and regime base rates |
| **Directionality** | — | **≥50%** in **≥2 of 5** regime dimensions | Avoid QE-only artifacts |
| **Promotion (named combo)** | **≥5** | **≥80%** | Beta filter + coherent Tavila economic story |

### 3.8 Persistence signals (Part G)

| Signal | Definition | Role |
|--------|------------|------|
| **SEVEN_WEEK_GRIND** | SPX weekly close **+0.5%** vs prior week for **7** consecutive weeks | **Amplifier** for Combo E — not standalone short |
| **VIX_SUPPRESSED** | VIX **<15** for **10** consecutive trading days | **Precursor/watch** for Combo D — ~50% lead rate historically |

### 3.9 Sample-size and fallback rules (Part I)

| Rule | Threshold |
|------|-----------|
| Regime-conditional percentile for decisions | **Never <30** observations |
| Fallback to unconditional | If regime subset **<50** obs — log which was used |
| Statistical gate (SSI, unnamed combos) | **≥5** independent fires to trust win rate |
| Mechanism gate (deep inversion, named extremes) | Fewer instances OK if causal story + analog consistency hold |

### 3.10 Combo cancel probability — Combo C example (Part E)

| Leg | Rule |
|-----|------|
| WTI | 4-week change **< +5%** for **4 consecutive Fridays** — Monte Carlo with **~35%** annual vol, **~0.75** window correlation |
| CPI | Historical fraction of at-or-below-consensus prints, squared for **2 consecutive** non-hot prints |
| Output | `combo_cancel_probability(...)` wired to nightly briefing |

---

## 4. Methodology and experiments to run

### Part A — Regime dimension refinement

- Update classifier prompt (Section 5.2) with refined state lists, fiscal caveat, CAPE rate-of-change
- Re-run historical backfill; report label distribution (check for degenerate states)

### Part B — 14th variable and windows

- Implement `TWY_ROC` per spec; validate Apr 2025 tariff bottom against DGS2 series
- Dual percentile storage (unconditional + regime); triple storage for CAPE
- Confirm history window split: expanding vs 3y rolling per variable class

### Part C — Emission probability foundation

- Store **14 percentile-rank vectors daily** alongside combo fires
- No HMM until **6+ months** of clean vectors accumulated

### Part D — HMM layer (deferred)

- Train 3-state HMM on accumulated vectors; pipe posterior into classifier prompt
- Backtest via `regime_backtest.py`: Sharpe, win rate, drawdown vs no regime overlay

### Part E — Options-style cancel probability

- Reusable Monte Carlo function for overlapping observation windows
- Live cancel/persist probability on dashboard for every active combo

### Part F — Quantitative regime definitions

- Explicit rules for all `fed_cycle` states, INVERTED, STEEPENING, HIKING period, steepening-short trigger
- Validate against backfill; **T10Y2Y consistent with Ahil’s steepening-of-inversion gate**

### Part G — Persistence signals

- `persistence_fires` table: start_date, streak_length, combo_link
- Saturday job (SEVEN_WEEK_GRIND); daily job (VIX_SUPPRESSED)

### Part H — 9-step combo discovery pipeline

1. **Detection** — 298 combos (13C1+C2+C3); fire when all legs at-or-beyond RARE threshold on full expanding percentile
2. **Forward returns** — SPX 1m/3m/6m/9m/12m after each fire
3. **Regime tagging** — attach 5 regime labels per fire date
4. **Surfacing** — ≥3 fires, ≥60% hit rate
5. **Beta / luck filter** — regime-conditional performance vs base rates
6. **Directionality** — ≥50% hit rate in ≥2 regime dimensions
7. **Economic story** — Tavila agent historical context review
8. **Naming gate** — ≥5 fires, ≥80% hit rate, beta + story pass
9. **Output table** — thresholds, direction, horizon, instances, cancel condition, cancel probability

---

## 5. Implementation sequencing

| Priority | Parts | Rationale |
|----------|-------|-----------|
| 1 | **B + C** | Foundational: 14th variable, windows, daily percentile vectors |
| 2 | **F + G** | Quick wins; no long data accumulation |
| 3 | **E** | Independent of HMM; early user-facing value |
| 4 | **A** | Re-runs backfill after dimension refinement |
| 5 | **H** | Core combo methodology |
| 6 | **D** | Last — needs 6+ months from Part C |

**Guiding principle:** Do not over-engineer; each item must plausibly improve backtested performance.

---

## 6. Open questions and action items

| # | Item | Owner / note |
|---|------|--------------|
| 1 | Validate **TWY_ROC ±0.30pp** bands — starting point only | Backtest when built |
| 2 | Backtest steepening-short **trough −50 vs −80** and **+15 vs +40 bps/4wk** | Before committing F4 |
| 3 | Confirm **7 Apr 2025** DGS2 8-week move vs fed_cycle labels | TWY_ROC validation |
| 4 | Implement dual percentile with **<50 obs fallback** and logging | Part B |
| 5 | Decide per-combo **55% vs 60%** regime beta bar after side-by-side report | Part H step 5 |
| 6 | Clarify 2-of-3 vs 3-of-3 leg performance — diagnostic only, not automatic verdict | Part H caveat |
| 7 | Accumulate **6+ months** percentile vectors before HMM training | Part D gate |
| 8 | Align **T10Y2Y inversion/steepening rules** with Ahil’s steepening-of-inversion workstream | Part F2 / F4 |
| 9 | Update Section **5.2 classifier prompt** for all Part A dimension changes | Deliverable A |
| 10 | Rohit: “Read all of it and ask me your questions” | Divyanshu follow-up |

---

## 7. Relationship to SSI and existing validation docs

| Topic in this mail | SSI / validation doc connection |
|--------------------|----------------------------------|
| **Percentile rank vs binary thresholds** | Aligns with [SSI_OPEN_QUESTIONS_SUMMARY.md](SSI_OPEN_QUESTIONS_SUMMARY.md) Part 1.2 (z-score vs percentile) and Test 9 — Runic moving toward percentile emission vectors system-wide |
| **≥5 instance statistical rule** | Same discipline as [SSI_THRESHOLD_JUSTIFICATION.md](SSI_THRESHOLD_JUSTIFICATION.md) status labels and Open Questions Part 1 — unnamed gates need enough fires |
| **Mechanism + analog at tails** | Mirrors steepening-short and deep-inversion framing in Ahil/SSI open questions — win rate alone insufficient at extremes |
| **SSI vs Runic scope** | This mail is **Runic regime + combo pipeline**; SSI thresholds (long/short gates, Layer 2, SQUEEZE) remain in SSI docs unless explicitly cross-wired (e.g. `ssi_multiplier`) |
| **Variable count** | Master doc lists **12 variables** + 7 combos; this plan adds **#14 TWY_ROC** and keeps combo math at **13 variables** |
| **RARE / EXTREME tiers** | Curve variable #9 (−30 / −80 bps) referenced here; full production table in CONFIG and [MACRO_INTELLIGENCE_MASTER.md](../MACRO_INTELLIGENCE_MASTER.md) §6 |

---

## 8. Deliverables checklist (from source)

| ID | Deliverable |
|----|-------------|
| **A** | Updated classifier prompt + backfill distribution report |
| **B** | 14-variable table, TWY_ROC spec, dual/triple percentile storage |
| **C** | Daily 14-vector percentile storage (no HMM yet) |
| **D** | 3-state HMM, posterior in prompt, regime_backtest comparison |
| **E** | `combo_cancel_probability()` + dashboard wiring |
| **F** | Quantitative fed_cycle, INVERTED, STEEPENING, HIKING, steepening-short definitions |
| **G** | `persistence_fires` table + briefing integration |
| **H** | Full 9-step automated combo pipeline (monthly candidate review) |

---

*Summary prepared from Rohit’s consolidated macro regime v2 mail. For production threshold values currently in code, see `macro_intelligence/CONFIG.yaml`, `macro_intelligence/SSI_CONFIG.yaml`, and [SSI_THRESHOLD_JUSTIFICATION.md](SSI_THRESHOLD_JUSTIFICATION.md).*
