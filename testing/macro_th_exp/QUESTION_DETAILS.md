# Question Details — Macro Regime & Threshold Experiments

**For:** Divyanshu (and Rohit sir for review)  
**Companion report:** [`Macro_Regime_Threshold_Experiments_Report_2026-06-09.md`](Macro_Regime_Threshold_Experiments_Report_2026-06-09.pdf)  
**Source plan:** [`Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`](Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf)  
**How to read this doc:** Each block has (1) the question in plain English, (2) why it came up, (3) what I actually ran, (4) the answer with numbers, (5) terms explained, (6) my doubt for Rohit sir if I still have one.

---

## How these questions arose

Rohit sir's consolidated plan asks us to rebuild the **macro regime system** (the labels that describe "what kind of market environment are we in?") and validate every rule with **backtests** before swapping production.

On **2026-06-06** I ran the full shadow experiment suite:

```bash
.venv/bin/python scripts/run_regime_v2_experiment_suite.py
```

That script:

1. Re-labelled **1,901 historical Fridays** with new v2 regime rules (stored in shadow table `macro_regime_log_v2`, not in the live nightly PDF yet).
2. Backfilled **8,805 daily emission vectors** (14 percentile ranks per day).
3. Ran FM positioning tests (Fast Money / CFTC fund positioning) and combo A–G regime slices.
4. Ran the 298-combo discovery pipeline.

Every question below is either **directly from the plan**, **from Rohit sir's WhatsApp follow-up** (`additional_details.md` on FM/regimes), or **a gap I found while checking whether the plan's rules actually work on history**.

**Shadow vs production:** "Shadow" means the new logic runs in analysis tables only. Production nightly briefing still shows old labels like `CUTTING_LATE` and `GLOBAL_EASY` until Rohit sir signs off.

---

## Quick glossary (terms reused everywhere)

| Term | Simple meaning |
|------|----------------|
| **Regime** | The market "environment" label for a date (e.g. Fed hiking, curve inverted). |
| **Backfill** | Re-run labels over past dates so we have history, not just today. |
| **Shadow** | New logic tested offline; not yet in live nightly output. |
| **Hit rate** | % of times SPX moved the way the signal predicted after it fired. |
| **n** | Number of times something happened (sample size). |
| **SPX** | S&P 500 index; we measure if it went up or down after a signal. |
| **3m / 6m** | Forward return 3 or 6 months after the signal date. |
| **Percentile (pctile)** | Where today's value sits in history (0 = lowest ever, 100 = highest). |
| **RARE / EXTREME** | Threshold tiers (e.g. top 20% or top 5% of history). |
| **Combo** | Named multi-variable signal (A through G) when several legs fire together. |
| **FM (Fast Money)** | CFTC positioning data for leveraged funds; we use its **percentile rank**. |
| **Contrary indicator** | When FM is extreme short, market often goes **up** (FM was "wrong"). |
| **Degenerate state** | A label that almost never fires or dominates >80% of days (useless for stats). |
| **≥30 obs rule** | Plan says do not trust regime-conditional stats with fewer than 30 examples. |
| **Mechanism + analog gate** | Justify a rule with economic story + historical episodes (2000, 2007), not win rate alone. |
| **pp (percentage points)** | Absolute change in a rate (e.g. yield fell 0.55pp). |
| **bps (basis points)** | 0.01pp (55 bps = 0.55pp). |

---

# Part A — Five regime dimensions

Rohit sir wants **five dimensions** (fed cycle, curve, valuation, geo, liquidity) with **fewer, cleaner states** so each bucket has enough history to backtest.

---

## A1 — fed_cycle: 7 states → 4 states

### Q1: Does collapsing to 4 fed states give enough observations per state?

**Why this question exists:**  
Old system had 7 fed labels (`HIKING_EARLY`, `HIKING_LATE`, `PAUSING`, etc.). Too many buckets = too few Fridays in each = unreliable hit rates. Plan collapses to **TIGHTENING, PIVOTING, EASING, EASY**.

**What I did:**  
Ran shadow backfill over 1,901 Fridays. Mapped legacy 7-state labels → 4 v2 states in `regime_v2_shadow.py`. Counted how many Fridays landed in each state.

**Answer:**  
Mostly yes, except PIVOTING.

| State | Fridays | % |
|-------|---------|---|
| TIGHTENING | 763 | 40.1% |
| EASING | 727 | 38.2% |
| EASY | 384 | 20.2% |
| PIVOTING | 27 | 1.4% |

TIGHTENING, EASING, and EASY each have **763, 727, 384** examples (plan wants ≥30). **PIVOTING only has 27**, below the 30-observation rule.

**Terms:**  
- **Fed cycle:** Where the Fed is in raising/cutting/holding rates.  
- **PIVOTING:** First cut after a hiking cycle (turning point).

**My doubt for Rohit sir:**  
PIVOTING is real economically but thin in our sample. Should I (a) merge PIVOTING into EASING, (b) widen the PIVOTING definition to catch more weeks, or (c) add **PAUSING** as a fifth state? Right now the Fed is on hold after cuts and production still says `CUTTING_LATE` (job tracker T-01). There is no v2 label for "paused but hike risk rising."

---

### Q2: Is any state degenerate (empty or useless)?

**Why this question exists:**  
Plan deliverable A says: report label distribution and check no state is empty or dominates >80% of all days.

**What I did:**  
Same backfill counts. Checked A1_pass flag in `experiment_manifest.json`.

**Answer:**  
No state is empty. No state exceeds 80% dominance (largest is TIGHTENING at 40.1%). **But** PIVOTING is "statistically thin" (n=27), which is a softer failure of the same idea.

**My doubt for Rohit sir:**  
Is n=27 acceptable for a rare tail state if we only use it for narrative, not hit-rate tables?

---

### Q3: Can we ship v2 fed_cycle to production?

**Why this question exists:**  
After shadow validation, the next step is swapping live nightly labels.

**What I did:**  
Compared shadow table vs production `macro_regime_log` / nightly PDF output.

**Answer:**  
**Not yet.** Shadow v2 labels exist and the pipeline runs end-to-end. Production still uses legacy 7-state names. Blockers: thin PIVOTING, missing PAUSING, classifier prompt (Section 5.2) not updated, Rohit sign-off pending.

**My doubt for Rohit sir:**  
What is the go-live order: update prompt first, re-backfill, then swap production? Or swap TIGHTENING/EASING/EASY first and defer PIVOTING?

---

## A2 — curve_regime + fiscal caveat

### Q4: Does fiscal deficit >5% GDP weaken the inversion recession signal?

**Why this question exists:**  
2022–23 had a deeply **inverted yield curve** but no recession. Rohit sir's plan says: when government deficit is **>5% of GDP**, treat inversion as a **weaker** recession warning (fiscal spending and AI capex offset the usual credit-channel effect).

**What I did:**  
Split inverted-curve episodes into two buckets using fiscal data (`A5_fiscal_caveat` in experiment JSON): deficit >5% vs not. Measured **bearish 3m SPX hit rate** (did market fall?) in each bucket.

**Answer:**  
Directionally yes, but sample is tiny for the fiscal bucket.

| Bucket | n | Bearish 3m SPX hit | Avg 3m return |
|--------|---|-------------------|---------------|
| No fiscal offset (deficit ≤5%) | 12 | 41.7% | −1.63% |
| Fiscal offset (deficit >5%) | 1 | 0% | −13.21% |

The single fiscal-offset episode behaves like 2022–23 (inverted, bad sentiment, but no clean recession trade). The no-offset bucket still shows moderate bearish signal.

**Terms:**  
- **Yield curve inversion:** Short-term rates above long-term (T10Y2Y < 0). Historically a recession warning.  
- **Fiscal deficit >5% GDP:** Government spending much larger than tax revenue relative to economy size.

**My doubt for Rohit sir:**  
n=1 in fiscal-offset bucket is not proof. Can we explicitly tag 2022–23 episodes and grow that bucket before wiring the fiscal caveat into the live classifier prompt?

---

### Q5: Are the 4 curve states stable in backfill?

**Why this question exists:**  
Plan keeps INVERTED, FLAT, STEEPENING, NORMAL. Need to confirm all four appear in history and formal F2 rules work.

**What I did:**  
Applied F2 rule: T10Y2Y < 0 for **≥4 consecutive weeks** = INVERTED. Checked Oct 2022 anchor.

**Answer:**  
Yes. All four states appear. Oct 2022 shows **14 inverted weeks**. F2/F2a pass in shadow.

**Terms:**  
- **T10Y2Y:** 10-year minus 2-year Treasury yield spread (FRED series). Standard inversion measure.

**My doubt for Rohit sir:**  
F2 is validated in shadow only. Production curve labels are still partly Claude-inferred. When do we switch production to numeric F2/F2a only?

---

## A3 — val_regime + CAPE velocity

### Q6: Does CAPE velocity add signal beyond static CAPE level?

**Why this question exists:**  
CAPE has been "elevated" since ~2017. Plan says: store **6-month change in CAPE percentile rank**, not just level, because **freshly** crossing into EXTREME is different from sitting there for 3 years.

**What I did:**  
Compared forward 3m SPX returns for (a) **level extreme** CAPE vs (b) **velocity rank delta over 6 months**. Also tried "fresh cross into EXTREME" bucket.

**Answer:**  
Not yet a clear winner for velocity.

| Measure | n | SPX up 3m | Avg 3m % |
|---------|---|-----------|----------|
| Level extreme | 863 | 74.2% | +3.08% |
| Velocity rank delta 6m | 531 | 74.6% | +2.68% |

Hit rates differ by only **0.4 percentage points**. Level wins slightly on average return (+0.40pp).

**Terms:**  
- **CAPE:** Cyclically Adjusted P/E; high = expensive vs long-term earnings.  
- **Velocity:** Speed of change in valuation rank, not just the level.

**My doubt for Rohit sir:**  
**Fresh cross into EXTREME: n=0** with my current detection definition. I cannot test your "fresh vs sitting 3 years" story until we retune that rule. Do you have a preferred definition (e.g. cross above 90th pctile within last 8 weeks)?

---

### Q7: Does triple CAPE storage help Combo E?

**Why this question exists:**  
Plan stores three CAPE numbers (expanding rank, 3y rolling rank, 8-week ROC of rank) and tests which helps **Combo E** (valuation extreme bearish signal).

**What I did:**  
Sliced Combo E fires by high-CAPE vs moderate-CAPE at 6m horizon (`B5_cape_triple_storage`).

**Answer:**  
High-CAPE Combo E is strong; moderate bucket empty.

| Slice | n | Hit rate 6m | Avg return |
|-------|---|-------------|------------|
| Combo E + high CAPE | 507 | 79.1% | +6.41% |
| Combo E + moderate CAPE | 0 | n/a | n/a |

**My doubt for Rohit sir:**  
Triple storage is built in shadow but not wired to conviction modifier or classifier. Is Combo E the right primary test, or should we test all combos?

---

## A4 — geo_overlay: 6 → 3 states

### Q8: Is 3-state geo more reproducible than 6-state?

**Why this question exists:**  
Fine geo labels (SANCTIONS vs TRADE_WAR) from Claude alone were noisy. Plan collapses to **NEUTRAL, ELEVATED_RISK, CRISIS**.

**What I did:**  
Shadow backfill with collapsed geo_overlay_v2. Counted label frequencies.

**Answer:**  
Yes qualitatively. Labels are sparse at tails but stable.

| State | Fridays | % |
|-------|---------|---|
| NEUTRAL | 1,855 | 97.6% |
| ELEVATED_RISK | 25 | 1.3% |
| CRISIS | 21 | 1.1% |

**Terms:**  
- **Geo overlay:** Geopolitical stress layer on top of macro regimes.

**My doubt for Rohit sir:**  
I did not re-run Claude on the same dates twice to measure consistency (inter-rater test). Production still uses 6-state geo. OK to collapse live?

---

### Q9: Does geo slice combo performance meaningfully?

**Why this question exists:**  
Part H step 6 wants hit rates stable across regime **dimensions**. If geo only works in one bucket with n=2, it is not actionable.

**What I did:**  
Sliced FM extreme-short events by geo_overlay_v2 at 3m.

**Answer:**  
No. Data too thin.

| Geo state | n (FM extreme short) | SPX up 3m |
|-----------|----------------------|-----------|
| NEUTRAL | 32 | 62.5% |
| CRISIS | 2 | 50% |
| ELEVATED_RISK | 1 | 0% |

**My doubt for Rohit sir:**  
Should geo stay in the classifier for narrative only, and be excluded from combo beta filter until we have more tail events?

---

## A5 — liquidity: 2 → 4/9 states

### Q10: Does WALCL direction distinguish tightening vs improving liquidity?

**Why this question exists:**  
Plan replaces binary GLOBAL_EASY/TIGHT with a **2×2 grid**: easy/tight **level** (from NFCI) × improving/tightening **direction** (from Fed balance sheet WALCL month-over-month change). Example: Fed hiking **plus** QT (shrinking balance sheet) is tighter than hiking with flat balance sheet.

**What I did:**  
Implemented `liquidity_v2()` in `regime_v2_shadow.py`. Backfilled 1,901 Fridays. Sliced FM positioning events by liquidity state at 3m.

**Answer:**  
Labels work descriptively; **performance signal unproven** at event level.

Distribution (9 states = 3 levels × 3 directions):

| State | Count | % |
|-------|-------|---|
| EASY_FLAT | 746 | 39.2% |
| EASY_IMPROVING | 403 | 21.2% |
| EASY_TIGHTENING | 287 | 15.1% |
| NEUTRAL_* (combined) | 501 | 26.4% |
| TIGHT_* (combined) | 112 | 5.9% |

FM slices (extreme short FM, SPX up 3m): EASY_FLAT 50% (n=6), EASY_IMPROVING 60% (n=10), EASY_TIGHTENING 50% (n=10). Spread is noise, not alpha.

**Terms:**  
- **NFCI:** Chicago Fed National Financial Conditions Index; negative = easy, positive = tight.  
- **WALCL:** Fed total assets (balance sheet size). MoM = month-over-month % change.  
- **QT / QE:** Quantitative tightening (shrinking balance sheet) / easing (expanding).

**My doubt for Rohit sir:**  
See Q11 below on 4 vs 9 states.

---

### Q11: Is 4-state 2×2 enough, or do we need FLAT/NEUTRAL variants (9 states)?

**Why this question exists:**  
Plan draws a clean 2×2. My code produced **9 labels** because NFCI often sits between easy/tight thresholds and WALCL MoM often sits in a ±0.3% dead zone.

**What I did:**  
Audited rule logic and full distribution. ~50.8% of Fridays are `*_FLAT` direction; ~26.4% are `NEUTRAL_*` level. Forcing pure 4-state would mislabel roughly half of history.

**Answer (my recommendation):**  
**Two-tier approach:**

1. **Store 9 states in production regime log and classifier** (honest to data; thinnest cell still n=30).  
2. **Collapse to 4 buckets for combo hit-rate tables and beta filter** (9-way slices too thin at events).

Collapse rules documented in main report (EASY_IMPROVING → EASY+IMPROVING, etc.).

**My doubts for Rohit sir:**  
- Final decision: 4 vs 9 for live labels?  
- For NEUTRAL level: fold into EASY (most NEUTRAL Fridays have slightly negative NFCI) or keep as third level in prompt only?  
- For EASY_FLAT / NEUTRAL_FLAT: use prior 4-week WALCL trend to assign direction, or leave as "no direction call"?

---

# Part B — 14th variable and history windows

---

## B1 — TWY_ROC (variable #14)

### Q12: Did TWY_ROC call the Apr 2025 bottom before lagging fed labels?

**Why this question exists:**  
Plan adds **TWY_ROC**: 2-year Treasury yield change over 8 weeks. Bond markets **lead** Fed labels by months. Validation anchor: ~7 Apr 2025 tariff bottom, yields fell ~65–75 bps while fed_cycle still said TIGHTENING/PAUSING.

**What I did:**  
Pulled FRED DGS2. Computed TWY_ROC = today minus 56 calendar days ago, in pp. Checked Apr 4 and Apr 7 2025 vs legacy fed label.

**Answer:**  
Yes.

| Date | TWY_ROC | Direction | DGS2 | Legacy fed_cycle |
|------|---------|-----------|------|------------------|
| 2025-04-07 | −0.55pp | DOVISH | 3.73% | TIGHTENING/PAUSING |
| 2025-04-04 | −0.61pp | DOVISH | 3.68% | TIGHTENING/PAUSING |

Market priced cuts before official labels moved.

**Terms:**  
- **DGS2:** FRED 2-year Treasury yield.  
- **DOVISH / HAWKISH:** Falling yields = dovish (easier policy expected); rising = hawkish.  
- **TWY_ROC excluded from combos:** Used for regime only, not in 298 combo math (13 variables).

**My doubt for Rohit sir:**  
Only 2 anchor dates tested. Should I build a full historical catalog of TWY/fed divergences before nightly pull?

---

### Q13: Are ±0.30pp TWY_ROC bands validated?

**Why this question exists:**  
Plan gives starting bands: HAWKISH > +0.30pp, DOVISH < −0.30pp, else NEUTRAL. Says **backtest these**.

**What I did:**  
Checked Apr 2025 (−0.55pp, well outside band). Did not sweep all history at ±0.20, ±0.30, ±0.40.

**Answer:**  
Partially. Anchor passes. Full sweep not done.

**My doubt for Rohit sir:**  
Keep ±0.30 as starting point, or run grid now?

---

### Q14: Is TWY_ROC excluded from combo enumeration?

**What I did:**  
Verified pipeline scans 298 signatures from **13 variables** only; 13,089 generic fires recorded.

**Answer:**  
Yes in experiment scope.

**My doubt for Rohit sir:**  
Confirm no production script accidentally adds var #14 to combo detector (code audit item).

---

## B2 — Dual percentile storage

### Q15: Does dual percentile storage work?

**Why this question exists:**  
Plan stores **two ranks every day** for every variable: (1) **unconditional** = vs full history (for combo detection), (2) **regime** = vs history **within current fed_cycle only** (for conviction modifier).

**What I did:**  
Backfilled dual columns. Counted rows with both vs unconditional-only.

**Answer:**  
Yes. **14,457 rows** with both percentiles. **0** unconditional-only rows in backfill.

**Terms:**  
- **Unconditional percentile:** Rank vs all history.  
- **Regime percentile:** Rank vs days when fed was in same cycle state.  
- **Fallback:** If regime subset has <50 obs, use unconditional and log it.

---

### Q16: Does the <50 obs fallback work when needed?

**What I did:**  
Checked `fallback_used` counts in backfill.

**Answer:**  
**Not tested in practice.** Zero fallbacks triggered because every fed_cycle had ≥50 obs for all variables. PIVOTING (n=27 Fridays) might trigger fallbacks in production for regime-conditioned percentiles.

**My doubt for Rohit sir:**  
Should I force a unit test with synthetic thin regime to prove fallback logging?

---

### Q17: Are history windows correct per variable (B4 audit)?

**Why this question exists:**  
Plan splits variables: **structural** (CAPE, VIX, curve) use **full expanding history**; **flow** (WTI 4wk, WALCL MoM, CPI surprise) use **3-year rolling**.

**What I did:**  
Compared `CONFIG.yaml` vs plan spec (`B4_window_audit`).

**Answer:**  
**4 mismatches:**

| Variable | CONFIG now | Plan expects |
|----------|------------|--------------|
| HY | full | rolling_3y |
| VIX | full | rolling_3y |
| VXTS | full | rolling_3y |
| WALCL | was rolling_3y | full |

WALCL fixed in production nightly **2026-06-09** (full-history MoM). B4 audit **not re-run** after fix.

**My doubt for Rohit sir:**  
Fix HY/VIX/VXTS windows and re-run full suite before any production GO? Wrong windows change which days combos fire.

---

## B3 — Triple CAPE storage

### Q18: Which CAPE storage combo predicts best?

**Covered in A3/Q6.** Level wins preliminarily; not rigorous multivariate regression across all three stored numbers.

---

### Q19: Does velocity beat level for Combo E?

**Covered in A3/Q7.** High-CAPE Combo E strong; moderate bucket empty.

---

# Part C — Emission probability vectors

Plan idea: instead of binary "fire / no fire," store **all 14 percentile ranks daily** as partial evidence. Feeds future HMM (Part D).

### Q20: Can we store 14 daily percentile vectors?

**What I did:**  
Backfilled one row per trading day with 14 ranks.

**Answer:**  
Yes. **8,805 rows**.

---

### Q21: Do sub-threshold readings accumulate useful signal?

**Why this question exists:**  
Example: VIX at 72nd percentile (below 80th RARE line) might still show building stress.

**What I did:**  
Counted days VIX in 65th–79th percentile. Measured 3m SPX return after.

**Answer:**  
Maybe, but n too small.

| Slice | n | Positive 3m SPX |
|-------|---|-----------------|
| VIX 65th–79th pctile | 7 | 85.7% |

**My doubt for Rohit sir:**  
Worth building cumulative sub-threshold scoring, or stay binary RARE for now?

---

### Q22: Do vectors detect regime shifts earlier than binary thresholds?

**What I did:**  
Compared first day VIX crossed RARE (binary) vs first day vector mean crossed threshold. **864** VIX RARE events.

**Answer:**  
No gain so far. **Median lag = 0.0 days.**

**My doubt for Rohit sir:**  
Tune emission weights, or deprioritize Part C until redesigned?

---

### Q23: When can HMM training start?

**Plan rule:** 6+ months of **live** daily vectors after wiring Part C to nightly job.

**Answer:**  
Not yet. Backfill has 8,805 rows for research, but **live clock = 0 months** (daily job not wired).

**My doubt for Rohit sir:**  
Prototype HMM **hurt** Combo B (−1.2 pp) and D (−1.9 pp) hit rates. Is Dec 2026 HMM target still worth it?

---

# Part D — HMM layer

**HMM (Hidden Markov Model):** Statistical model that assumes market is usually in one of a few hidden states (Risk-On, Risk-Off, Transition) and daily macro readings are noisy clues.

### Q24: Can HMM posteriors feed the classifier as a soft prior?

**What I did:**  
Research prototype only (k-means-style, not production HMM). Sample Jun 2026 posteriors.

**Answer:**  
Not in production. Example posterior: Risk-On 42.9%, Risk-Off 23.8%, Transition 33.3%. Plan rule "if Risk-Off > 40%, lean tighter" is implementable but not wired.

---

### Q25: Does HMM detect shifts before binary thresholds?

**What I did:**  
D3 shift-timing backtest **not completed**.

**Answer:**  
Not validated.

---

### Q26: Does HMM improve Sharpe / win rate / drawdown?

**What I did:**  
`regime_backtest.py` on Combo B and D with HMM Risk-Off filter vs overall.

**Answer:**  
**No improvement on win rate.**

| Combo | Overall 3m | HMM Risk-Off filter 3m | Delta |
|-------|------------|------------------------|-------|
| B (bullish, SPX up) | 79.8% (n=89) | 78.6% (n=56) | −1.2 pp |
| D (bearish, SPX down) | 28.1% (n=452) | 26.2% (n=103) | −1.9 pp |

Sharpe and drawdown **not reported** in manifest.

**My doubt for Rohit sir:**  
Defer HMM entirely until live vectors + proper HMM training, or keep research track?

---

# Part E — Cancel probability

Plan: show a **number** for "probability this combo cancels" (e.g. Combo C WTI leg stays weak 4 Fridays in a row).

### Q27: Can we compute Combo C cancel probability via Monte Carlo?

**What I did:**  
Built `combo_cancel_probability()` with 10,000 simulated WTI paths (GBM), overlapping 4-week windows, correlation ~0.75. Combined with CPI leg probability.

**Answer:**  
Yes. Example: WTI leg 8.31%, CPI leg 27.04%, **combined 2.25%**.

**Terms:**  
- **Monte Carlo:** Simulate thousands of random futures to estimate probability.  
- **GBM:** Standard random-walk model for prices.

---

### Q28: Is the probability calibrated to history?

**What I did:**  
E2 calibration: 4 historical Combo C episodes vs model prediction.

**Answer:**  
No. **0 realized cancels** vs ~2.25% predicted. Under-calibration suspected (or sample too small).

**My doubt for Rohit sir:**  
Need ≥5 episodes per statistical gate. Start live tracking predicted vs realized?

---

### Q29: Live cancel % on briefing?

**Answer:**  
Function built. **Not displayed** on nightly PDF/dashboard yet.

**My doubt for Rohit sir:**  
Show cancel/persist % for every active combo as plan specifies?

---

### Q30: Combo D/F/G cancel formulas?

**Answer:**  
Documented in experiment report. **Only Combo C** implemented as reusable function.

---

# Part F — Formal regime definitions

Goal: replace Claude guesses with **numeric rules** testable on backfill.

### Q31: Does F1 TIGHTENING-LATE match Oct 2022?

**Why this question exists:**  
Proposed rule: FFR > 3.5%, FFR up >150 bps in 12mo, AND (T10Y2Y < −30 bps OR hike pace slowing). Oct 2022 should match "late hiking + inverted."

**What I did:**  
Ran F1 check on Oct 2022 backfill row.

**Answer:**  
**No.** `tightening_late_f1 = False`. FFR was ~**3.25%** (below 3.5% threshold). Legacy label was HIKING_LATE. **`hiking_period_f3 = true`** (alternate flag fired).

**My doubt for Rohit sir:**  
Retune F1 (lower FFR gate?) or accept v2 TIGHTENING ≠ legacy HIKING_LATE?

---

### Q32: Do all fed states have numeric rules?

**Answer:**  
No. F1 drafted for TIGHTENING-LATE only. F3 hiking period works. Full quant defs for all 4 v2 states not backfill-validated.

---

### Q33: Reproducible INVERTED from T10Y2Y?

**What I did:**  
F2: T10Y2Y < 0 for ≥4 consecutive weeks.

**Answer:**  
Yes in shadow. Oct 2022: 14 inverted weeks.

---

### Q34: F4 steepening-of-inversion short grid

**Why this question exists:**  
Short trigger after deep inversion trough when curve steepens (+15 or +40 bps/4wk). Plan says justify by **mechanism + analogs** (2000, 2007), not win rate alone, because 2022–23 failed with fiscal offset.

**What I did:**  
Grid over trough depth (−50 vs −80 bps) and steepening speed.

| Trough | Steepen 4wk | n | SPX down 3m |
|--------|-------------|---|-------------|
| −50 bps | +15 bps | 17 | 17.6% |
| −50 bps | +40 bps | 4 | 25.0% |
| −80 bps | +15 bps | 9 | 33.3% |
| −80 bps | +40 bps | 2 | 0% |

**Answer:**  
No cell clears 55% promotion bar. Best 33.3% (n=9). **Mechanism gate only**, not statistical promotion.

**My doubt for Rohit sir:**  
Lock −50/+15 or −80/+15 as mechanism defaults? Win rate cannot choose.

---

# Part G — Persistence signals

Patterns that build over weeks, not one-day spikes.

### Q35: Is 7-week SPX grind a standalone short?

**Rule:** SPX weekly close up ≥+0.5% vs prior week for **7 consecutive weeks**.

**What I did:**  
Detected episodes in history. Measured 6m forward return.

**Answer:**  
**No.** n=**2** episodes. Both negative 6m (avg −5.91%). Plan says use as **Combo E amplifier**, not standalone short. Matches plan intent.

**My doubt for Rohit sir:**  
n=2 too small to confirm broader historical claim. Wire to briefing as amplifier text?

---

### Q36: Does VIX suppressed precede vol spike ~50% of the time?

**Rule:** VIX < 15 for **10 consecutive trading days**. Plan claimed ~50% lead rate to vol spike (Combo D precursor).

**What I did:**  
n=1,973 suppressed periods. Measured how often VIX > 25 within **35 days**.

**Answer:**  
**No.** Lead rate **8.5%** (168/1,973). Median days to VIX>25: 35.5. Far below plan's ~50%.

**My doubt for Rohit sir:**  
Wrong measurement window? Try 60d or VIX>20? Or update plan language to "weak watch flag"?

---

# Part H — Nine-step combo discovery pipeline

Automated pipeline to find and validate new combo candidates from 298 variable triples.

| Step | Question (plain English) | What I did | Answer |
|------|--------------------------|------------|--------|
| 1 | Do all 298 combos get scanned? | Full enumeration 13C1+13C2+13C3 | Yes. 225 had ≥1 fire. 13,089 total fires. |
| 2 | Are forward returns stored? | SPX 1m–12m after each fire | Yes, in pipeline JSON. |
| 3 | Are v2 regime labels attached? | Tag each fire date | **Partially.** Used **legacy** tags on existing combo_fires. |
| 4 | Surfacing gate (≥3 fires, ≥60% HR)? | Filter candidates | 187 surfaced. |
| 5 | Beta filter (works in hostile regimes)? | HIKING/INVERTED hit rate ≥55% and ≥60% reported | 132 pass. |
| 6 | Directionality (≥2 of 5 dimensions)? | Avoid QE-only artifacts | 132 pass (same set). |
| 7 | Tavila economic story? | Claude historical context | **Skipped** (use_claude=False). |
| 8 | Naming gate (≥5 fires, ≥80% HR)? | Promote to named combo | 62 candidates. **0 promoted.** |
| 9 | Output table with cancel prob? | Wire Part E per combo | Not in live output. |

**Terms:**  
- **Beta filter:** Reject combos that only work in easy bull markets.  
- **Tavila agent:** Pulls historical news/context for fire dates.

**My doubts for Rohit sir:**  
- Beta bar **55% or 60%** for 62 candidates?  
- Re-tag all fires with **v2 regimes** before final review?  
- Run Tavila step 7 before any promotion?  
- Many of 62 candidates overlap existing A–G legs: new discoveries or relabels?

---

# Part I — Sample-size discipline

| Rule | Meaning | What happened |
|------|---------|---------------|
| ≥30 obs | Don't trust regime-conditional stats below 30 | PIVOTING failed (27) |
| <50 fallback | Use unconditional percentile if regime subset thin | 0 fallbacks in backfill |
| ≥5 fires (statistical gate) | Win rate is evidence | FM bands, unnamed combos |
| 2–4 fires OK (mechanism gate) | Story + analogs enough | F4 steepening-short |

---

# FM and regime isolation (Rohit sir WhatsApp ask)

Separate from Parts A–H. Rohit sir asked: **How often is Fast Money right vs wrong, and does it vary by regime?**

**What I did:**  
Used CFTC FM percentile history + `X-FM_all.json` + combo fires. Sliced by fed_cycle, curve, liquidity, etc.

---

## Extreme short FM (<15th percentile)

**Story:** When leveraged funds are extremely short, they are often wrong; SPX tends to rally (contrary indicator). Combo B = capitulation washout.

### Q37: Is extreme-short FM a contrary indicator?

| Test | n | SPX up 3m |
|------|---|-----------|
| Combo B fires (incl. WATCH) | 89 | **79.8%** |
| Raw FM <15 alone | 35 | **60.0%** |

Rohit sir cited ~87.5% (7/8 on strict Combo B). My 79.8% on 89 fires validates **direction** with larger n, slightly lower rate.

**Regime matters:**

| Regime (extreme short, 3m) | n | SPX up |
|----------------------------|---|--------|
| EASY fed_cycle | 6 | 83.3% |
| FLAT curve | 6 | **33.3%** (breaks) |
| INVERTED curve | 4 | 75.0% |

**Answer:** Conditionally yes. Works best with **full Combo B legs** (VIX + HY + CFTC), not FM percentile alone.

---

### Q38: Why 89 Combo B fires vs Rohit sir's "8 confirmed"?

**How this arose:**  
Rohit sir counted **fully confirmed** Combo B instances. My DB counts every **WATCH** week where partial legs fired (e.g. 2023–2024 many consecutive WATCH rows with only CFTC leg met).

**Answer:**  
Detection criteria differ. Hit rate 79.8% still valid on broader set.

**My doubt for Rohit sir:**  
Show **"Legs met: X/3"** in briefing (job T-04). I still owe **confirmed-only (3/3 ACTIVE) re-slice** (open P0 task).

---

## Extreme long FM (>85th percentile)

Combo D territory. FM extremely long often precedes correction at **short** horizons; at **long** horizons market can keep grinding up.

| Horizon | Raw FM: SPX down | FM "wrong" (SPX up) | Combo D: wrong |
|---------|------------------|---------------------|----------------|
| 1 week | 41.0% | 59.0% | 61.5% |
| 3 months | 17.9% | 82.1% | 71.9% |

### Q39: Is FM wrong 72–85% at 5–10 days?

**Answer:**  
Partially. Backtest ~**59–62%** at 1w, roughly **10–20 pp below** Rohit sir's 72–85% band.

### Q40: Does signal degrade at 3m?

**Answer:**  
If you expected a correction, yes: **82%** of the time SPX still up at 3m for raw extreme long (FM wrong).

### Q41: Regime impact on Combo D?

| fed_cycle (Combo D, 3m SPX down) | n | Hit rate |
|----------------------------------|---|----------|
| HIKING_LATE | 197 | **18.3%** |
| CUTTING_LATE | 155 | **43.2%** |

**Answer:** Regime conditioning **mandatory** before using D as standalone short.

---

## Moderate FM (25th–75th percentile)

Rohit sir said trend-following FM is " broadly correct" in the middle band; he was **not sure** that is accurate.

| Metric | Value |
|--------|-------|
| Crossings | 84 |
| SPX up 3m | 76.2% |
| Avg 3m return | +3.15% |

**Answer:**  
Looks like **normal equity drift**, not an independent FM edge. Rohit sir's skepticism was right.

**My doubt for Rohit sir:**  
I have not subtracted buy-and-hold baseline. Should I run that before closing this question?

---

## Named combos A–G by fed cycle

### Q42: Does regime materially change combo performance?

**Answer:** Yes. Examples:

| Combo | Overall | Best slice | Worst slice |
|-------|---------|------------|-------------|
| B (bull) | 79.8% up | HIKING_LATE 83% | CUTTING_LATE 76% (robust) |
| D (bear) | 28% down | CUTTING_LATE 43% | HIKING_LATE **18%** (2.4× spread) |
| F (bull) | 74.9% up | QE 82% | CUTTING_LATE 64% (18 pp spread) |

### Q43: Full 5-dimension slicing done?

**Answer:** Partially. **fed_cycle** reliable. curve/liquidity/geo mostly n<10 outside fed.

### Q44: Is Combo C working?

**Answer:** No in sample. **4 fires, 0%** SPX up 3m; avg +17.8% (market rose against bullish C signal).

**My doubt for Rohit sir:**  
Investigate C fire criteria and cancel logic, or hide C hit rates until n≥5?

---

# Master doubts list (consolidated for Rohit review)

| # | Doubt | Why it matters |
|---|-------|----------------|
| 1 | PIVOTING n=27: merge, widen, or add PAUSING? | Blocks clean 4-state fed promotion |
| 2 | Part A state lists ready for Section 5.2 prompt? | Production classifier unchanged |
| 3 | Liquidity: 9 states live, 4 collapsed for analytics? | 50% of history is FLAT/NEUTRAL |
| 4 | CONFIG B4: fix HY/VIX/VXTS windows before GO? | Changes combo fire dates |
| 5 | TWY_ROC ±0.30pp: keep or grid? | Only Apr 2025 anchor tested |
| 6 | F4 defaults: −50/+15 or −80/+15 on mechanism only? | Win rate cannot decide |
| 7 | Wire daily emission_vectors to start HMM clock? | Prototype hurt hit rates |
| 8 | Show live cancel % on briefing? | Part E built, not displayed |
| 9 | Beta filter 55% or 60% for 62 candidates? | Human decision per plan |
| 10 | Re-tag combo fires with v2 regimes? | Part H used legacy tags |
| 11 | Run Tavila step 7 before promotion? | 0 combos promoted despite 62 candidates |
| 12 | VIX suppressed 8.5% vs plan ~50%: remeasure or rewrite plan? | Weak precursor |
| 13 | Combo B: confirmed-only re-slice + "Legs X/3" in PDF? | 89 vs 8 confusion |
| 14 | Combo C: investigate or hide hit rates? | n=4, 0% hit |
| 15 | Production GO order: which parts wire first? | Nothing from v2 in nightly yet |
| 16 | Rollback plan if v2 labels confuse readers? | Legacy names in use for months |
| 17 | NEUTRAL liquidity: fold to EASY or third level? | Judgment on collapse rules |
| 18 | Fresh CAPE cross: retune definition (n=0 today)? | Velocity story untested |

---

# What I would do next (for my own clarity)

1. Re-slice Combo B as **confirmed-only (3/3 legs ACTIVE)**.  
2. Fix CONFIG B4 windows and **re-run** `run_regime_v2_experiment_suite.py`.  
3. Walk Rohit sir through **Section "Master doubts list"** above and get written decisions.  
4. Only then wire TWY_ROC, emission daily job, cancel % on briefing, and regime label swap.

---

*Created 2026-06-09. Companion to [`Macro_Regime_Threshold_Experiments_Report_2026-06-09.md`](Macro_Regime_Threshold_Experiments_Report_2026-06-09.md). Shadow run: 2026-06-06. Artifacts: `macro_intelligence/analysis/regime_v2_experiments/`.*
