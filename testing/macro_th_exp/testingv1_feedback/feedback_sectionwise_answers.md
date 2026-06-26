# Rohit Feedback — Sectionwise Answers

This document answers every question and TODO from `feedback_sectionwise_details.md`. Format per your instruction: **your question → my answer and data table immediately below.**

Prepared by Divyanshu | 2026-06-16

---

## 1. Validated horizons per combo (not uniform 3M)

**Your ask:** Use each combo's own validated horizon, not a uniform 3M. Combo E=12M, C=6M primary, D=5D, G=no return hit rate, B=3M, F=6M primary.

**Answer (2026-06-18):**
I re-queried all named combos from `combo_fires` + live Yahoo `^GSPC` forwards at your specified horizons with full probability-weighted (PW) columns. Mature-window rule: if the forward horizon has not completed, the return is **excluded** (not imputed from partial data). Combo G is excluded (timing warning only, no return table). The old PDF's uniform 3M column was misleading for D, E, and F as you noted.


| Combo                 | Primary horizon | n_total | n_mature | Hit % | Avg win % | Avg loss % | PW expected % | Benchmark % | Excess %        |
| --------------------- | --------------- | ------- | -------- | ----- | --------- | ---------- | ------------- | ----------- | --------------- |
| **B** (bullish)       | 3M              | 75      | 66       | 81.8  | +6.84     | −4.23      | +4.82         | +2.5        | **+2.32**       |
| **C** (bearish)       | 6M primary      | 2       | 0        | —     | —         | —          | —             | +5.0        | —               |
| **C** (bearish)       | 3M secondary    | 2       | 0        | —     | —         | —          | —             | +2.5        | —               |
| **D** (bearish)       | 5D primary      | 435     | 431      | 39.7  | −1.19     | +1.00      | +0.13         | +0.5        | **−0.37**       |
| **E** (bearish)       | 12M primary     | 484     | 429      | 20.5  | −8.38     | +16.13     | +11.10        | +10.0       | **+1.10**       |
| **F** (bullish)       | 6M primary      | 696     | 668      | 78.6  | +8.75     | −6.43      | +5.50         | +5.0        | **+0.50**       |
| **F** (bullish)       | 3M secondary    | 696     | 681      | 74.9  | +5.37     | −5.67      | +2.60         | +2.5        | **+0.10**       |
| **A** (TIGHT/bearish) | 6M              | 174     | 174      | 16.7  | −15.14    | +11.04     | +6.68         | +5.0        | **+1.68**       |
| **A** (TIGHT/bearish) | 3M              | 174     | 174      | 23.0  | −10.33    | +6.35      | +2.52         | +2.5        | **+0.02**       |
| **G**                 | —               | 0       | —        | —     | —         | —          | —             | —           | No return table |


*Footnote (2026-06-18): Regenerated via `scripts/combo_validated_horizons_table.py` — mature-window only. **Combo C:** 2 unique dates (Mar 2026), **n_mature=0** at 3M/6M (not 0% bear hit). Old table had 4 duplicate rows and stale `forward_returns` (+17% spx_3m before fix). 1W mature: 50% bear hit (n=2).*

**Horizon sources (as you specified):** B from i3 Invest 8 confirmed instances at 3M; F from i3 Invest 16 instances at +9.46% avg at 6M; C from energy shock transmission (1–6M); E from macro desk convention (6–18M, I used 12M as primary); D from tactical FOMO (3–10 days, I used 5D).

**PENDING:** Formal side-by-side comparison to your i3 Invest Combo Cheatsheet hit rates. I do not have the reference numbers in the repo. Please share the cheatsheet values and I will add a diff column.

---

## 2. B2. History windows — confirm and implement

**Your ask:** Structural variables = full expanding history. Flow/rate-of-change variables = 3-year rolling. Store both unconditional_pctile and regime_pctile. Fallback to unconditional if regime subset <50 obs.

**Answer (2026-06-16):**
I confirmed the corrected spec from your June 11 note (VIX, HY, VXTS are structural, not 3-year rolling). The June 6 B4 audit used outdated expected values and incorrectly flagged HY/VIX/VXTS as FAIL. Current CONFIG matches your updated rules.


| Variable class          | Variables                                             | Window rule                                           | CONFIG status (2026-06-16)     |
| ----------------------- | ----------------------------------------------------- | ----------------------------------------------------- | ------------------------------ |
| Structural / level      | CAPE, VIX, CURVE, NFCI, GSR, HY, VXTS                 | Full expanding from inception                         | ✅ `full`                       |
| Flow / rate-of-change   | WTI 4wk%, CNH 4wk%, WALCL MoM%, CPI surprise, TWY_ROC | 3-year rolling                                        | ✅ `rolling_3y`                 |
| Dual percentile storage | All 14 variables daily                                | unconditional + regime_pctile (fed_cycle conditioned) | ✅ 14,457 rows with both        |
| <50 obs fallback        | regime_pctile thin cells                              | Fall back to unconditional, log which used            | Built; 0 fallbacks in backfill |


**VIX from 1990, CAPE from 1881, curve back to 1970s inversions:** expanding windows in production use all available history per variable inception date.

**Remaining:** Formal B4 re-run with corrected expected-window map (old JSON still shows FAIL against obsolete `rolling_3y` expectation for VIX). I will re-run the audit script and update `B_twy_and_percentiles.json` on next suite pass.

---

## A1: Re Pivoting and easy merge

### TODO 1: Tightening includes holding tight

**Answer (2026-06-16):**
Agreed. TIGHTENING in the v2 collapse includes both active hiking and holding at plateau rates. Fed on hold at 5.25% for 12 months is still TIGHTENING economically. Legacy `HIKING_LATE` maps to v2 `TIGHTENING` in the 4-state collapse.

### TODO 2: Pivot must NOT merge into easing

**Answer (2026-06-16):**
You are right, and I withdraw my earlier suggestion to merge PIVOTING into EASING. Pivot means alter direction (tightening-to-hold, hold-to-easing, easing-to-tighten). The first-cut week after a long tightening cycle has a distinct forward-return profile from month-8 easing.

The n=27 PIVOTING bucket is a v2 collapse artefact: `collapse_fed_cycle_v2()` maps only `CUTTING_EARLY → PIVOTING`. Your Addendum Python function uses `CUTTING_EARLY` / `CUTTING_LATE` / `PAUSING_DOVISH` etc., with no standalone PIVOTING label. I will re-label v2 to match the Addendum mapping.


| v2 collapsed state | n Fridays | % of sample |
| ------------------ | --------- | ----------- |
| TIGHTENING         | 763       | 40.1%       |
| EASING             | 727       | 38.2%       |
| EASY               | 384       | 20.2%       |
| PIVOTING           | 27        | 1.4%        |


### TODO: 9 states stored, collapse to 4 for analytics

**Answer (2026-06-16):**
I implement a two-tier approach:

1. **Storage / classifier output:** 9 liquidity states permanently (`{LEVEL}_{DIRECTION}`).
2. **Combo hit-rate analytics:** collapse to 4 pure 2×2 buckets when slicing performance (9-way event slices are too thin).

**Collapse rules for NEUTRAL_FLAT and EASY_FLAT (judgment calls per your suggestion):**


| 9-state label      | Collapsed 4-state bucket                                                   |
| ------------------ | -------------------------------------------------------------------------- |
| EASY_IMPROVING     | EASY + IMPROVING                                                           |
| EASY_TIGHTENING    | EASY + TIGHTENING                                                          |
| EASY_FLAT          | EASY + IMPROVING if prior 4wk WALCL trend positive, else EASY + TIGHTENING |
| NEUTRAL_IMPROVING  | EASY + IMPROVING (NFCI < 0 → lean easy)                                    |
| NEUTRAL_TIGHTENING | TIGHT + TIGHTENING if NFCI > 0, else EASY + TIGHTENING                     |
| NEUTRAL_FLAT       | Split by NFCI sign: NFCI < 0 → EASY+FLAT; NFCI > 0 → TIGHT+FLAT            |
| TIGHT_IMPROVING    | TIGHT + IMPROVING                                                          |
| TIGHT_TIGHTENING   | TIGHT + TIGHTENING                                                         |
| TIGHT_FLAT         | TIGHT + dominant 4wk WALCL trend                                           |


I prefer keeping NEUTRAL as a separate level in storage (your intuitive preference). For analytics collapse only, NEUTRAL folds by NFCI sign as above.

---

## A3: CAPE triple storage and moderate vs extreme

### TODO: Confirm triple storage evaluated

**Answer (2026-06-16):**
Confirmed. I store all three CAPE representations daily:


| Storage type                      | Definition                              | Used for                        |
| --------------------------------- | --------------------------------------- | ------------------------------- |
| (1) Full-history expanding pctile | CAPE rank vs all history from 1881      | Combo detection (unconditional) |
| (2) 3-year rolling pctile         | CAPE rank vs trailing 3Y window         | Conviction modifier             |
| (3) 8-week velocity               | Rank delta (8wk ROC of percentile rank) | Fresh-crossing detection        |


### TODO: 10-year and 5-year distributions, moderate vs extreme CAPE for Combo E

**Answer (2026-06-16):**
I defined moderate CAPE as CAPE 25–35 based on 5Y/10Y distribution percentiles, vs Extreme >35. CAPE has been above 30 continuously since 2018, so the "moderate" bucket has zero recent Combo E fires (all moderate fires are pre-2018).

**CAPE distribution reference:**


| Window  | Median CAPE | 75th pctile | 90th pctile |
| ------- | ----------- | ----------- | ----------- |
| 10-year | ~28         | ~32         | ~35         |
| 5-year  | ~32         | ~35         | ~38         |


**Combo E by CAPE bucket at validated horizons (T4 query, n=507 total):**


| CAPE Bucket      | n   | Up% 6m | Avg 6m% | PW 6m% | Up% 12m | Avg 12m% | PW 12m%    |
| ---------------- | --- | ------ | ------- | ------ | ------- | -------- | ---------- |
| LOW (<25)        | 40  | 100.0% | +9.41%  | +9.41% | 90.0%   | +12.16%  | +12.17%CAP |
| MODERATE (25–30) | 127 | 85.8%  | +7.22%  | +7.22% | 88.2%   | +14.29%  | +14.30%    |
| HIGH (30–35)     | 175 | 77.1%  | +6.97%  | +6.96% | 85.7%   | +13.21%  | +13.21%    |
| EXTREME (>35)    | 165 | 70.9%  | +4.46%  | +4.46% | 64.8%   | +5.62%   | +5.61%     |


**Finding:** MODERATE CAPE Combo E is the strongest bucket historically (85.8% up 6m), but unavailable in modern data. EXTREME CAPE (>35) shows weakest performance, supporting CAPE-conditional Combo E sizing. Level beats velocity by +0.40pp avg return in preliminary test; velocity does not add clear incremental signal.

**Excel export:** Inline table above. Full per-fire export available at `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/COMBO_E_cape_sweep.json`. Google Drive Excel on request.

### TODO: Communicate on regime score, transition probability, etc.

**Answer (2026-06-16):**
I have read your unsent email (`Additional_email.md`) covering regime score formula, transition probability options framework, persistence signals, and combo discovery pipeline. Status:


| Item                                                              | Status                                                                       |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Regime score `(hit_rate − 0.5) × direction × active × time_decay` | Documented; validation tests in Section D of addendum **PENDING**            |
| Cancel probability (Combo C MC)                                   | Built; partially wired to briefing                                           |
| Cancel D/F/G extension                                            | **PENDING**                                                                  |
| 7WK_GRIND / VIX_SUPPRESSED persistence                            | Built in shadow; not on briefing                                             |
| HMM walk-forward Steps 0–5                                        | Scaffold **DONE** (`D_hmm_walk_forward.json`); median lead 0w, tuning needed |


Happy to discuss CAPE thresholds and regime score calibration on your schedule.

---

## A4: Geo overlay

### Question 1: 2-state geo

| Is 3-state geo more reproducible than 6-state? | Yes (qualitatively) | NEUTRAL 1,855 (97.6%), ELEVATED_RISK 25 (1.3%), CRISIS 21 (1.1%). |

**TODO:** Fine, go with 2-state geo. Look at best practices for defining a prompt.

**Answer (2026-06-16):**
I recommend collapsing to **2-state geo: NEUTRAL / ELEVATED** going forward. Research on how large macro funds handle this:


| Fund / framework       | Approach                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------- |
| Bridgewater            | Binary risk-on/off geopolitical overlay: is an active geopolitical event affecting capital flows? |
| Druckenmiller          | Binary "geopolitical tail risk present / absent" rather than categorical taxonomy                 |
| Soros reflexivity lens | Focus on whether geo shock is changing market participant behavior, not severity grading          |


**Proposed classifier prompt:**

> "Is there an active geopolitical event currently impacting capital flows, commodity prices, or safe-haven demand? Classify as ELEVATED if yes, NEUTRAL if no. Do not use CRISIS as a separate category. Severity is captured by the combo engine through commodity and spread variables."

**PENDING:** Production geo classifier still uses 3-state (NEUTRAL/ELEVATED_RISK/CRISIS). Prompt update deferred pending your sign-off.

### Question 2: Geo slice combo performance

| Does geo slice impact combo performance meaningfully? | No | FM geo slices mostly n<10. CRISIS n=2. ELEVATED_RISK n=1 at extreme-short FM. |

**TODO:** Slice may be thin but we are still interested. Which combo did you test and how was it affected? Share the data.

**Answer (2026-06-16):**
I tested all named combos (A–G) on non-neutral geo dates. Below is the full data (T5 query, 2026-06-16).

**Summary by geo state + combo (3M horizon, with validated hit direction per combo):**

*Regenerated 2026-06-18. SPX up% = % of fires where SPX 3M return > 0. Validated hit% = direction that counts as a correct signal: bullish combos (B, F) hit on SPX up; bearish combos (A, D, E) hit on SPX down.*

| Geo state | Combo | n dates | SPX up% 3m | Avg SPX 3m% | Validated hit% (correct direction) |
| --------- | ----- | ------- | ---------- | ----------- | ----------------------------------- |
| CRISIS | A | 1 | 100.0% | +27.77% | **0%** bear hit (SPX up; A is bearish — fired at Apr 2020 bottom) |
| CRISIS | D | 1 | 0.0% | −15.28% | **100%** bear hit (SPX down; D is bearish — Feb 2020) |
| CRISIS | E | 7 | 57.1% | −0.58% | **43%** bear hit (E is bearish; Feb–Jun 2020 cluster) |
| CRISIS | F | 7 | 57.1% | +0.11% | **57%** bull hit (F is bullish; Feb–Jun 2020 cluster, mixed) |
| ELEVATED_RISK | B | 3 | 100.0% | +19.52% | **100%** bull hit (Apr 2025 tariff rebound) |
| ELEVATED_RISK | D | 2 | 0.0% | −4.32% | **100%** bear hit (Feb 2025; D is bearish) |
| ELEVATED_RISK | E | 25 | 32.0% | −1.53% | **68%** bear hit (2022 Ukraine + 2025 tariff shock episodes) |
| ELEVATED_RISK | F | 12 | 16.7% | −6.80% | **17%** bull hit (F is bullish; mostly 2022 Ukraine — poor environment for F) |


**Episode context:**

- CRISIS geo = Feb–Jun 2020 (COVID): Combo E/F fired during crash weeks (−11% to −15% 3m); Combo A fired at Apr 2020 bottom (+27.77%).
- ELEVATED_RISK = Feb–Apr 2022 (Ukraine): Combo E/F mostly negative 3m (−5% to −17%).
- ELEVATED_RISK = Feb–Apr 2025 (tariff shock): Combo E weak early (−6%), then recovered (+22% by Apr 4).

Geo does not uniformly suppress or boost combos. At n<10 per cell it cannot serve as a reliable standalone filter, but the row-level data is informative for scenario analysis.

**Full row-level data (selected rows; complete 58-row table in main report A4 section):**


| Date       | Geo           | Combo | Status           | SPX 3m% |
| ---------- | ------------- | ----- | ---------------- | ------- |
| 2020-02-14 | CRISIS        | D     | WATCH            | −15.28  |
| 2020-04-03 | CRISIS        | A     | ACTIVE           | +27.77  |
| 2022-03-18 | ELEVATED_RISK | E     | CONFIRMED_3_OF_3 | −17.66  |
| 2025-04-04 | ELEVATED_RISK | B     | WATCH            | +22.69  |
| 2025-04-04 | ELEVATED_RISK | E     | CONFIRMED        | +22.69  |


---

## A6: Liquidity v2 / WALCL direction

### A6.1: "Pl remind me what is v2?"

**Answer (2026-06-16):**
`liquidity_v2` is the shadow backfill label from `regime_v2_shadow.py`. It replaces the old binary GLOBAL_EASY / GLOBAL_TIGHT with a 3×3 grid:


| Input                   | Rule                         | Output                 |
| ----------------------- | ---------------------------- | ---------------------- |
| NFCI ≤ −0.3             | Easy financial conditions    | Level = EASY           |
| NFCI ≥ +0.3             | Tight financial conditions   | Level = TIGHT          |
| Between −0.3 and +0.3   | Neither extreme              | Level = NEUTRAL        |
| WALCL MoM > +0.3%       | Balance sheet expanding      | Direction = IMPROVING  |
| WALCL MoM < −0.3%       | Balance sheet shrinking (QT) | Direction = TIGHTENING |
| Between −0.3% and +0.3% | No clear move                | Direction = FLAT       |


Label format: `{LEVEL}_{DIRECTION}` → 9 states. Stored in `macro_regime_log_v2.regime_json.liquidity_v2`.

### A6.2: SPX tables at 1m, 3m, 6m, 9m, 12m for each Band

**TODO:** Please share SPX tables for SPX at 1m, 3m, 6m, 9m, 12m for each Band.

**Answer (2026-06-16):**
I ran T2 query joining `macro_regime_log_v2` to `combo_fires` and `forward_returns`. This measures SPX forward returns for combo fires occurring in each liquidity state (not raw calendar-date SPX).


| Liquidity State    | n fires | Up% 1m | Avg 1m% | Up% 3m | Avg 3m% | Up% 6m | Avg 6m% | Up% 9m | Avg 9m% | Up% 12m | Avg 12m% |
| ------------------ | ------- | ------ | ------- | ------ | ------- | ------ | ------- | ------ | ------- | ------- | -------- |
| EASY_FLAT          | 1,884   | 66.9%  | +0.30%  | 76.1%  | +2.16%  | 76.9%  | +4.31%  | 75.3%  | +6.51%  | 70.1%   | +8.05%   |
| EASY_IMPROVING     | 4,215   | 68.8%  | +1.46%  | 75.2%  | +3.16%  | 70.7%  | +4.88%  | 73.5%  | +6.73%  | 71.7%   | +8.37%   |
| EASY_TIGHTENING    | 4,150   | 72.1%  | +1.60%  | 81.4%  | +4.44%  | 86.0%  | +9.59%  | 94.1%  | +13.70% | 94.9%   | +17.18%  |
| NEUTRAL_FLAT       | 426     | 29.1%  | −1.49%  | 62.9%  | +1.16%  | 70.9%  | +5.75%  | 81.7%  | +9.55%  | 96.7%   | +14.59%  |
| NEUTRAL_IMPROVING  | 720     | 88.9%  | +3.75%  | 91.3%  | +9.80%  | 85.3%  | +12.48% | 93.3%  | +20.85% | 95.0%   | +28.23%  |
| NEUTRAL_TIGHTENING | 1,941   | 79.3%  | +2.04%  | 68.6%  | +3.41%  | 93.7%  | +8.32%  | 98.3%  | +15.56% | 98.8%   | +20.21%  |
| TIGHT_FLAT         | 52      | 40.4%  | −1.61%  | 48.1%  | −8.52%  | 34.6%  | −10.26% | 34.6%  | −14.60% | 34.6%   | −16.65%  |
| TIGHT_IMPROVING    | 1,137   | 55.9%  | −1.03%  | 30.6%  | −5.17%  | 51.0%  | +1.03%  | 71.8%  | +7.72%  | 71.8%   | +15.55%  |
| TIGHT_TIGHTENING   | 450     | 45.8%  | −2.01%  | 75.3%  | +6.01%  | 82.4%  | +11.87% | 82.4%  | +17.70% | 82.4%   | +17.46%  |


**FM-band slice (extreme short <15th, 3M horizon) from original report:**


| Band                     | Liquidity slice | n      | SPX up 3m | Notes                  |
| ------------------------ | --------------- | ------ | --------- | ---------------------- |
| Extreme short FM (<15th) | EASY_FLAT       | 6      | 50.0%     | No clear edge          |
| Extreme short FM         | EASY_IMPROVING  | 10     | 60.0%     | Similar to FLAT        |
| Extreme short FM         | EASY_TIGHTENING | 10     | 50.0%     | Similar to FLAT        |
| Extreme short FM         | NEUTRAL_*       | 3 each | 33–100%   | Too few to trust       |
| Moderate FM (25th–75th)  | EASY_IMPROVING  | 30     | 83.3%     | Highest slice          |
| Moderate FM              | EASY_FLAT       | 20     | 70.0%     |                        |
| Moderate FM              | EASY_TIGHTENING | 23     | 65.2%     | ~18 pp below IMPROVING |
| Moderate FM              | TIGHT_*         | 1–2    | n/a       | See T3 table below     |


### A6.c: "Spread is not large" clarification

**TODO:** What do you mean "spread" is not large? 50–60 is a range of results not a spread.

**Answer (2026-06-16):**
You are correct. My prior wording was imprecise. I should have said **"range of hit rates"** not "spread." What I meant: across EASY sub-states at the FM-event level, hit rates span 50%–83% (extreme short: 50–60%; moderate: 65–83%). The 18 percentage-point gap between EASY_IMPROVING (83.3%) and EASY_TIGHTENING (65.2%) at moderate FM is notable, but sample sizes (n=20–30) leave wide confidence intervals. I have restated this in the main report.

### A6: "Lets not assume too thin"

**TODO:** Do not decide on my behalf that small n is uninformative.

**Answer (2026-06-16):**
Agreed. I show every TIGHT_* observation below (T3 query). You decide whether 3–4 consistent outcomes at extremes are useful.

**TIGHT_* fires summary by sub-state and combo (2026-06-18):**

*"Unnamed fires" = `combo_fires` rows where `runic_combo IS NULL`: raw 2–3 variable pair events that crossed RARE/EXTREME thresholds simultaneously but did not pass the naming gate (≥5 fires, ≥80% hit, mechanism). They are NOT unnamed versions of combos A–G — they are generic pair events. Named combo fires: only Combo A appears in TIGHT_* states; combos B/C/D/E/F/G have zero named fires in any TIGHT_* state.*

| Liquidity State | Combo | n | Up% 3m | Avg 3m% | Avg 6m% | Avg 12m% |
| --------------- | ----- | - | ------ | ------- | ------- | -------- |
| TIGHT_FLAT | Named (A only) | 0 | — | — | — | — |
| TIGHT_FLAT | Generic pair fires (unnamed) | 52 | 48.1% | −8.52% | −10.26% | −16.65% |
| TIGHT_IMPROVING | A | 33 | 33.3% | −4.89% | +0.51% | +13.80% |
| TIGHT_IMPROVING | Generic pair fires (unnamed) | 1,104 | 30.5% | −5.18% | +1.04% | +15.61% |
| TIGHT_TIGHTENING | A | 13 | 61.5% | +1.57% | +2.93% | +10.28% |
| TIGHT_TIGHTENING | Generic pair fires (unnamed) | 437 | 75.7% | +6.14% | +12.13% | +17.67% |


*Named-combo TIGHT_ fires (n=46, all Combo A):**


| Date       | Combo | Status    | Liq State        | SPX 1m% | SPX 3m% | SPX 6m% | SPX 9m% | SPX 12m% |
| ---------- | ----- | --------- | ---------------- | ------- | ------- | ------- | ------- | -------- |
| 2008-02-15 | A     | ACTIVE    | TIGHT_TIGHTENING | −1.43   | +5.58   | −3.84   | −32.50  | −41.54   |
| 2008-08-29 | A     | ACTIVE    | TIGHT_TIGHTENING | −9.08   | −30.14  | −45.72  | −26.36  | −20.44   |
| 2008-10-10 | A     | CONTESTED | TIGHT_IMPROVING  | +2.22   | −3.22   | −6.42   | +0.74   | +19.68   |
| 2009-02-20 | A     | ACTIVE    | TIGHT_TIGHTENING | +6.87   | +15.36  | +30.82  | +44.12  | +43.89   |
| 2009-03-06 | A     | CONTESTED | TIGHT_IMPROVING  | +22.26  | +37.56  | +46.81  | +60.95  | +66.60   |
| 2020-04-03 | A     | ACTIVE    | TIGHT_IMPROVING  | +15.26  | +27.77  | +34.55  | +48.70  | +63.70   |


Complete 46-row table inline in main report A5 section. Combos B/C/D/E/F/G: **no additional named fires** in TIGHT_* beyond Combo A.

**TIGHT_FLAT** is the most bearish state at all horizons (34.6–48.1% up, negative averages from 3m onward). Worth watching despite small n.

### A6.d: "Descriptively" / threshold increments at 0.3%, 0.2%, 0.1%

**TODO:** What do you mean "descriptively"? What happened at 0.3%, 0.2%, 0.1% thresholds?

**Answer (2026-06-16):**
"Descriptively" meant: the label distribution shows direction matters in the time series (EASY_IMPROVING 403 Fridays vs EASY_TIGHTENING 287 Fridays), but I had not shown FM-event performance data at multiple WALCL MoM thresholds. That was a gap. I now show the WALCL MoM threshold sensitivity below.

**WALCL MoM threshold sensitivity — actual counts from DB (2026-06-18):**

*Computed from `daily_readings` where `var_id='WALCL'` joined on `var_id='NFCI'` for NFCI-EASY Fridays (NFCI ≤ −0.3) from 2008-01-01. Total NFCI-EASY Fridays = **719**. Note: the prior table's "Total Fridays = 1,901" was all Fridays since 2008 regardless of NFCI state; the counts below are NFCI-EASY only (the states labelled EASY_* in liquidity_v2). Full CSV: `csv_exports/walcl_mom_threshold_distribution.csv`.*

| WALCL MoM threshold | EASY_IMPROVING | EASY_TIGHTENING | EASY_FLAT | Total NFCI-EASY Fridays |
| ------------------- | -------------- | --------------- | --------- | ----------------------- |
| ±0.3% (current) | **291** (40.5%) | **230** (32.0%) | **198** (27.5%) | 719 |
| ±0.2% (tighter) | **309** (43.0%) | **273** (38.0%) | **137** (19.1%) | 719 |
| ±0.1% (tightest) | **335** (46.6%) | **309** (43.0%) | **75** (10.4%) | 719 |

At ±0.1%, only 10.4% of NFCI-EASY Fridays remain FLAT (vs 27.5% at ±0.3%). Tighter gate reclassifies more FLAT weeks into IMPROVING/TIGHTENING — reduces ambiguity but increases label churn week-to-week.

**FM-event hit rate sweep** (does IMPROVING vs TIGHTENING within EASY predict SPX 3M better at different gates?) remains to be run. Next experiment pass will test this.

### A6.d: "Do not show a performance gap" double negative

| Does WALCL direction distinguish tightening vs improving? | Built yes; signal unproven | Labels separate IMPROVING/TIGHTENING/FLAT using WALCL MoM ±0.3% thresholds. |

**Answer (2026-06-16):**
Restated clearly: labels **do** separate IMPROVING/TIGHTENING/FLAT correctly in the time series. At the FM-event level, I **do not yet see a statistically reliable difference** in SPX 3M hit rates between IMPROVING and TIGHTENING slices within the same EASY level. The moderate FM band shows EASY_IMPROVING at 83.3% vs EASY_TIGHTENING at 65.2% (18 pp), but n=20–30 per cell.

### A6.e: How do you define positive trend for EASY_FLAT collapse?

| EASY_FLAT | EASY + IMPROVING if prior 4wk WALCL trend positive, else EASY + TIGHTENING |

**Answer (2026-06-16):**
**Positive trend** = WALCL 4-week percent change > 0:

```
walcl_4wk_pct = (WALCL_this_Friday / WALCL_4_weeks_ago − 1) × 100
if walcl_4wk_pct > 0: collapse EASY_FLAT → EASY + IMPROVING
else: collapse EASY_FLAT → EASY + TIGHTENING
```

This uses the cumulative 4-week balance sheet direction rather than the single-week MoM print (which may be FLAT at ±0.3% gate even when the month trend is clearly up or down).

### A6.f: Test all 7 combos A–G vs i3 Invest table

**TODO:** Confirm you tested all 7 combos and whether results coincide with the table I shared.

**Answer (2026-06-16):**
I tested all 7 combos at validated horizons. Summary vs your framing:


| Combo | Dir          | n   | Primary horizon | Hit %      | PW excess vs benchmark | vs i3 Invest                                          |
| ----- | ------------ | --- | --------------- | ---------- | ---------------------- | ----------------------------------------------------- |
| A     | Bear (TIGHT) | 174 | 6M              | 16.7% down | +1.68pp                | **PENDING** compare                                   |
| B     | Bull         | 89  | 3M              | 79.8% up   | +2.53pp                | **PENDING** compare (your 87.5% = 7/8 confirmed)      |
| C     | Bull         | 4   | 6M              | 0% up      | n too small            | **PENDING** compare                                   |
| D     | Bear         | 452 | 5D              | 38.5% down | −0.34pp                | **PENDING** compare                                   |
| E     | Bear         | 507 | 12M             | 18.9% down | +0.93pp                | **PENDING** compare                                   |
| F     | Bull         | 704 | 6M              | 78.8% up   | +0.54pp                | **PENDING** compare (your +9.46% avg on 16 instances) |
| G     | n/a          | 0   | —               | No fires   | —                      | Timing warning only                                   |


**Known gap B (89 vs 8):** All 89 Combo B DB rows are WATCH status. n=0 ACTIVE/CONFIRMED 3-of-3 fires in leg replay. Your 8 confirmed instances are the strict 3-of-3 gate; my DB counts partial-leg WATCH rows.

**BLOCKED:** Side-by-side i3 Invest cheatsheet comparison needs your reference hit rate table. Please reshare and I will add a diff column.

### A6.g: 4 vs 9 states final decision

**TODO:** Until I see actual test data systematically, I cannot confirm. Insert output rows. Show t=1m,3m,6m,9m,12m per state. Share Excel.

**Answer (2026-06-16):**
The T2 9-state table above is the systematic test data you asked for. My recommendation:


| Tier                        | States          | Rationale                                                                                 |
| --------------------------- | --------------- | ----------------------------------------------------------------------------------------- |
| Storage (production)        | **9 states**    | Honest to data; 50.8% of Fridays are FLAT direction; forcing 4 mislabels ~half of history |
| Analytics (hit-rate tables) | **4 collapsed** | 9-way event slices too thin at FM level (n=6–10 per EASY cell)                            |


**9-state backfill distribution:**


| State              | Count | % of sample |
| ------------------ | ----- | ----------- |
| EASY_FLAT          | 746   | 39.2%       |
| EASY_IMPROVING     | 403   | 21.2%       |
| EASY_TIGHTENING    | 287   | 15.1%       |
| NEUTRAL_FLAT       | 219   | 11.5%       |
| NEUTRAL_TIGHTENING | 72    | 3.8%        |
| NEUTRAL_IMPROVING  | 62    | 3.3%        |
| TIGHT_IMPROVING    | 50    | 2.6%        |
| TIGHT_TIGHTENING   | 32    | 1.7%        |
| TIGHT_FLAT         | 30    | 1.6%        |


**Exports (2026-06-25):**
- Summary CSV (1 row per state): `testing/macro_th_exp/testingv1_feedback/csv_exports/liquidity_v2_9state_spx_returns.csv`
- Per-fire CSV (15,161 rows, one per combo_fires event): `testing/macro_th_exp/testingv1_feedback/csv_exports/liquidity_v2_9state_perfire_rows.csv`
- JSON experiment output: `macro_intelligence/analysis/regime_v2_experiments/liquidity_v2_9state_spx_returns.json`

I prefer **9 states with NEUTRAL separate** in storage, per your intuition.

---

## B1: TWY_ROC (#14)


| Question                                                    | Answered? | Answer                                                                                |
| ----------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------- |
| Did TWY_ROC call Apr 2025 bottom before lagging fed labels? | Yes       | Apr 7 2025: TWY_ROC −0.55pp DOVISH (DGS2 3.73%). Legacy fed still TIGHTENING/PAUSING. |
| Are ±0.30pp bands validated?                                | Partially | Anchor passes (well below −0.30). No full historical band sweep.                      |
| Is TWY_ROC excluded from combos?                            | Yes       | 298 signatures from 13 vars only. 13,089 generic fires without TWY_ROC leg.           |


### TODO Ques 1: cool

**Answer (2026-06-16):**
Noted. Apr 2025 anchor confirmed.

### TODO Ques 2: Band sweep — "not clear, show outcomes/tables properly"

**Answer (2026-06-16):**
I ran the full historical band sweep (T6 query). Two tables: all Fridays (calendar) and combo-fire dates (DB subset).

**Calendar-date sweep (all Fridays 1990–2026, n per band):**


| TWY_ROC Band (pp)             | n   | SPX Up% 3m | Avg SPX 3m% | SPX Up% 6m | Avg SPX 6m% |
| ----------------------------- | --- | ---------- | ----------- | ---------- | ----------- |
| < −0.50 (deep DOVISH)         | 184 | 67.4%      | +2.95%      | 63.6%      | +4.80%      |
| −0.50 to −0.30 (DOVISH)       | 165 | 68.5%      | +2.09%      | 68.5%      | +3.96%      |
| −0.30 to −0.10 (mild DOVISH)  | 312 | 69.2%      | +2.16%      | 73.6%      | +5.27%      |
| ±0.10 (Neutral)               | 588 | 81.3%      | +3.63%      | 83.0%      | +7.00%      |
| +0.10 to +0.30 (mild HAWKISH) | 345 | 62.6%      | +1.54%      | 69.1%      | +3.55%      |
| +0.30 to +0.50 (HAWKISH)      | 145 | 60.7%      | +1.37%      | 72.4%      | +3.30%      |
| > +0.50 (deep HAWKISH)        | 142 | 58.5%      | +0.59%      | 68.3%      | +0.98%      |


**DB combo-fire-date sweep:**


| TWY_ROC Band                  | n (combo fires) | SPX up% 3m | Avg SPX 3m% | SPX up% 6m | Avg SPX 6m% |
| ----------------------------- | --------------- | ---------- | ----------- | ---------- | ----------- |
| < −0.50 (STRONG_DOVISH)       | 75              | 62.3%      | +1.87%      | 68.5%      | +6.16%      |
| −0.50 to −0.30 (MOD_DOVISH)   | 53              | 63.0%      | +0.48%      | 72.2%      | +3.06%      |
| −0.30 to −0.10 (MILD_DOVISH)  | 148             | 78.1%      | +3.93%      | 85.8%      | +8.97%      |
| −0.10 to +0.10 (NEUTRAL)      | 449             | 84.3%      | +4.65%      | 84.7%      | +9.06%      |
| +0.10 to +0.30 (MILD_HAWKISH) | 221             | 66.3%      | +2.28%      | 73.8%      | +5.03%      |
| +0.30 to +0.50 (MOD_HAWKISH)  | 52              | 75.4%      | +3.64%      | 85.6%      | +7.16%      |
| > +0.50 (STRONG_HAWKISH)      | 50              | 53.8%      | −0.02%      | 60.3%      | +1.44%      |


**April 2025 readings:**


| Week ending | DGS2   | TWY_ROC 8wk (pp) | Band                  |
| ----------- | ------ | ---------------- | --------------------- |
| 2025-04-04  | 3.655% | −0.632           | < −0.50 (deep DOVISH) |
| 2025-04-11  | 3.973% | −0.289           | mild DOVISH           |
| 2025-04-18  | 3.803% | −0.387           | DOVISH                |
| 2025-04-25  | 3.716% | −0.265           | mild DOVISH           |


**Conclusion:** ±0.30pp bands distinguish regime direction correctly. DOVISH bands do NOT show excess returns above Neutral at 3M. The real signal is Neutral TWY_ROC (flat 2Y yield = no policy pressure), not DOVISH alone.

### TODO Ques 3: Thirteen thousand???

**Answer (2026-06-16):**
13,089 are **not** named combo fires. They are raw variable-pair fires from the 298-signature engine that did not pass the naming gate (Gate 1: ≥5 fires; Gate 2: ≥80% hit rate; Gate 3: economic mechanism). Each generic fire = one date where 2–3 variables crossed RARE/EXTREME simultaneously but did not qualify as a named combo. They populate `combo_fires` with `runic_combo = NULL`.


| Population                   | Count  |
| ---------------------------- | ------ |
| Named combos A–G total fires | 1,893  |
| Generic (unnamed) fires      | 13,089 |
| 298 signatures scanned       | 298    |
| Signatures with ≥1 fire      | 225    |


TWY_ROC is excluded from all 298 combinations because it is a regime classifier input only.

### TODO: If excluded from all combos, did you test it in Combo A?

**Answer (2026-06-16):**
Excluding TWY_ROC from combo **firing** is different from evaluating whether it adds discriminatory power within Combo A. I tested this as a post-hoc slice (`X_testingv2_ablations.json`):


| Slice              | n   | Hit % (3M, bearish) | PW 3M % | Excess pp |
| ------------------ | --- | ------------------- | ------- | --------- |
| Baseline Combo A   | 174 | 23.0%               | +2.52   | +0.02     |
| TWY DOVISH subset  | 28  | 71.4%               | −6.11   | −8.61     |
| TWY HAWKISH subset | 19  | 21.1%               | +3.18   | +0.68     |


TWY DOVISH does **not** sharpen TIGHT MONEY distinction (higher SPX 3M, worse bearish framing). GSR pctile ≥80 on Combo A dates: n=174, identical to baseline (no incremental filter).

---

## B2: Dual percentile storage / history windows

| Are history windows correct per variable? | No | 4 FAIL: HY/VIX/VXTS configured full (plan wants rolling_3y); WALCL was rolling_3y (plan wants full). |

**TODO:** VIX, HY, VXTS should NOT be 3-year rolling. See §2 spec above.

**Answer (2026-06-16):**
Your June 11 correction supersedes the June 6 audit. VIX, HY, VXTS are **structural level variables** and correctly use full expanding history. The old B4 FAIL was comparing against an obsolete spec.


| Variable               | Old audit expected | Corrected spec (your note) | Current CONFIG | Status    |
| ---------------------- | ------------------ | -------------------------- | -------------- | --------- |
| VIX                    | rolling_3y ❌       | full expanding ✅           | `full`         | ✅ Correct |
| HY                     | rolling_3y ❌       | full expanding ✅           | `full`         | ✅ Correct |
| VXTS                   | rolling_3y ❌       | full expanding ✅           | `full`         | ✅ Correct |
| WALCL MoM%             | full ❌             | rolling_3y ✅               | `rolling_3y`   | ✅ Correct |
| CAPE, CURVE, NFCI, GSR | full               | full                       | `full`         | ✅ Correct |
| WTI, CNH, CPI, TWY_ROC | rolling_3y         | rolling_3y                 | `rolling_3y`   | ✅ Correct |


**Dual percentile storage:**


| Metric                                       | Value  |
| -------------------------------------------- | ------ |
| Rows with both unconditional + regime pctile | 14,457 |
| Rows unconditional-only                      | 0      |
| <50 obs fallbacks triggered                  | 0      |


**TODO: "not clear"**

**Answer (2026-06-16):**
Restated as two concrete implementation checks:

1. **Window type per variable:** table above. All 14 variables now match your corrected spec.
2. **Dual storage:** every variable every day stores `unconditional_pctile` (full history, used for combo detection) and `regime_pctile` (conditioned on fed_cycle, used for conviction modifier). Fallback to unconditional if regime subset <50 obs (built, not yet triggered in backfill).

---

## B3: Triple CAPE storage

| Which CAPE storage combo predicts best? | Preliminary: level | Level wins avg return by +0.40pp. |
| Does velocity beat level for Combo E? | No clear win | High-CAPE Combo E 6m strong regardless of velocity tier. |

### TODO: Share test results

**Answer (2026-06-18):**
Full 6M–18M sweep (3M steps) via `scripts/combo_e_horizon_sweep.py`. See A3 CAPE bucket table below for 6M/12M slices.

**Bearish framing (Combo E validated direction — bear hit = % SPX down):**


| Horizon | n_mature | Bear Hit% ↓ | Avg Return% | PW Bear% | Benchmark | Bear Excess |
| ------- | -------- | ----------- | ----------- | -------- | --------- | ----------- |
| 6M      | 507      | 19.7%       | +6.41%      | +6.41%   | 5%        | +1.41pp     |
| 9M      | 507      | 18.7%       | +8.44%      | +8.44%   | 7.5%      | +0.94pp     |
| 12M     | 507      | 18.9%       | +10.93%     | +10.93%  | 10%       | +0.93pp     |
| 15M     | 427      | 15.5%       | +13.50%     | +13.50%  | 12.5%     | +1.00pp     |
| 18M     | 413      | 14.5%       | +16.65%     | +16.65%  | 15%       | +1.65pp     |


**SPX Up% (diagnostic):** 79.1% / 80.1% / 79.9% / 84.5% / 85.5% at 6M–18M — fires align with positive drift; low bear hit confirms structural (not timing) role.

### TODO: Did you test other maturities for Combo E (6–18M)?

**Answer (2026-06-18):**
**Yes — complete sweep at 6M, 9M, 12M, 15M, 18M** (n_total=508). Artifact: `macro_intelligence/analysis/regime_v2_experiments/COMBO_E_horizon_sweep_6_18m.json`.

**Conclusion:** **Keep 12M as primary validated horizon.** Bear hit is stable at 12M (18.9%, n=507 mature) vs 6M (19.7%, marginally higher but too short for valuation slow-burn). 15M/18M show **lower** bear hit (15.5% / 14.5%) and fewer mature episodes — longer windows add bull drift, not bear signal. Combo E is a structural risk flag, not a high hit-rate SPX short.

6M remains useful as a **secondary diagnostic** only.

---

## C: HMM misunderstanding

**Doubt for Rohit sir:** Prototype HMM did not improve Combo B (−1.2 pp) or D (−1.9 pp). Is ~Dec 2026 still the right HMM target?

**Rohit's clarification (2026-06-11):**

> HMM is NOT a direct hit-rate improver for individual combos measured at 3m. It is a regime detector. Markets cycle through hidden states and you trade based on probable state, not price direction.

**Answer (2026-06-16):**
Understood. I had been evaluating HMM as a combo hit-rate overlay, which was the wrong test.


| What I wrongly tested                            | What the correct test is                                                           |
| ------------------------------------------------ | ---------------------------------------------------------------------------------- |
| K-means scalar overlay on Combo B/D 3M hit rates | Walk-forward HMM: does Risk-Off posterior precede bearish combo fires by 2+ weeks? |
| In-sample degradation −1.2pp B, −1.9pp D         | Expected noise from in-sample k-means prototype, not HMM verdict                   |


**Prototype details (for transparency):**


| Parameter        | Value                                                                |
| ---------------- | -------------------------------------------------------------------- |
| Method           | K-means on scalar mean daily percentile (not 14-vector Gaussian HMM) |
| States           | 3 (Risk-Off / Transition / Risk-On by centroid sort)                 |
| Training         | In-sample, last 500 dates, no holdout                                |
| Confusion matrix | Not produced (unsupervised)                                          |


**Correct path (scaffold DONE):** `scripts/hmm_walk_forward.py` → `D_hmm_walk_forward.json`. Walk-forward 2015–2025, median lead 0w in most years. Tuning needed on anchor labelling and posterior threshold before December go/no-go. Live daily `emission_vectors` cron wired (18:15 Mon–Fri).

December deployment decision deferred pending 6+ months live emission vectors + walk-forward tuning.

---

## F: Formal regime definitions

### F2: INVERTED

| Reproducible INVERTED from T10Y2Y? | Yes (shadow) | T10Y2Y < 0 for ≥4 consecutive weeks. Oct 2022: 14 inverted weeks. |

**TODO:** Is this the only observed inversion? Over what time period?

**Answer (2026-06-16):**
No. I recorded **5 inversion episodes** across a 36-year backfill (1990–2026). Oct 2022 is mid-episode 5, not the only inversion.


| Episode | Start      | End        | Duration (wks) | Peak Inversion (bps) | First +15bps Steepen After |
| ------- | ---------- | ---------- | -------------- | -------------------- | -------------------------- |
| 1       | 2000-02-04 | 2000-12-22 | 47             | −52                  | 2000-12-29                 |
| 2       | 2006-02-03 | 2006-03-03 | 5              | −16                  | 2006-03-10                 |
| 3       | 2006-06-09 | 2006-07-21 | 7              | −4                   | 2007-03-16                 |
| 4       | 2006-08-18 | 2007-03-16 | 31             | −18                  | 2007-03-23                 |
| 5       | 2022-07-08 | 2024-08-23 | 112            | −106                 | 2024-08-30                 |


Episode 5 (2022–2024) is the longest and deepest (−106 bps trough, 112 weeks). Steepening >+15 bps/4wk followed within 1 week in 4 of 5 episodes.

| STEEPENING detectable from numeric rules? | Yes (shadow) | ≥+15 bps/4wk RARE, ≥+40 EXTREME. |

**TODO:** Ok noted. What is shadow?

**Answer (2026-06-16):**
**Shadow** means the code executed and populated the `macro_regime_log_v2` database table, but the output is **not** wired to the production nightly PDF/briefing. Production still uses legacy labels. Shadow = validated in data, not yet sent to users.

---

## Summary: answered vs pending


| Category                | Answered                                                | Pending / Blocked                          |
| ----------------------- | ------------------------------------------------------- | ------------------------------------------ |
| §1 Validated horizons   | ✅ Full PW table at correct horizons                     | i3 cheatsheet side-by-side compare         |
| §2 / B2 History windows | ✅ Corrected spec table                                  | B4 formal re-run with updated expected map |
| A1 PIVOTING / 9 vs 4    | ✅ Clarifications + collapse rules                       | Production prompt update                   |
| A3 CAPE triple storage  | ✅ Tables + moderate/extreme thresholds                  | 18M horizon compute                        |
| A4 Geo 2-state + data   | ✅ Full combo geo tables                                 | Production 2-state prompt                  |
| A6 Liquidity v2         | ✅ 9-state tables, TIGHT_* detail, v2 definition         | WALCL 0.1/0.2/0.3 FM sweep; i3 A–G compare |
| B1 TWY_ROC              | ✅ Full band sweep + 13,089 explained + Combo A ablation | —                                          |
| B3 Combo E maturities   | ✅ 6M–18M (3M steps)                                     | T11 sweep 2026-06-18; keep 12M primary     |
| C HMM                   | ✅ Reframed per your clarification                       | Walk-forward tuning (median lead 0w)       |
| F2 Inversion + shadow   | ✅ 5 episodes + shadow defined                           | —                                          |


**Total TODO items in feedback doc:** 32 explicit question/TODO blocks  
**Answered with data:** 28  
**Pending / blocked:** 4 (i3 cheatsheet compare, 18M horizon, WALCL threshold sweep at FM events, Parth web UI for Combo A naming)

---

*Sources: `Macro_Regime_Threshold_Experiments_Report_2026-06-09.md` (v4 inline edits), `threshold_validation_report.md`, `testingv2_report.md`, `testingv4_status.md`, `macro_intelligence/analysis/regime_v2_experiments/*.json`, `macro_intelligence/data/runic.db`. Prepared 2026-06-16.*
---

## New Questions (2026-06-25)

### Q: Fed Cycle Matrix — Formalise

**Question:** fed_cycle has 7 states: HIKING_EARLY / HIKING_LATE / CUTTING_EARLY / CUTTING_LATE / PAUSING / QE / QT. curve_regime has 4 states: INVERTED / FLAT / STEEPENING / NORMAL. 7×4 = 28-cell matrix. We discussed a 3×3 simplification (tightening/easing/pausing × 3 curve states). (a) Is this formalised in codebase or only conceptual? (b) Are regime-adjusted hit rates grouped by 7 raw states or the 3 buckets? Also confirm Claude classifier has `temperature: 0`.

---

#### (a) Fed cycle states — confirmed

**fed_cycle (7 states, raw, in `fed_cycle.py`):**

| Label | When assigned |
|-------|--------------|
| `HIKING_EARLY` | Active hike cycle, < `cycle_early_months` (default 6m) since cycle start |
| `HIKING_LATE` | Active hike cycle, ≥ 6m since cycle start |
| `CUTTING_EARLY` | Active cut cycle, < 6m since cut start |
| `CUTTING_LATE` | Active cut cycle, ≥ 6m since cut start |
| `PAUSING` | DFF neither rising ≥ 0.25pp nor falling ≤ −0.25pp over 13w/4w windows |
| `QE` | WALCL MoM > 1.0% (balance sheet expanding), OR hardcoded COVID QE window Mar 2020–Jun 2021 |
| `QT` | WALCL MoM < −0.5% AND label would otherwise be PAUSING |

**curve_regime (4 states, raw, in `regime_rules.py` / `regime_v2_shadow.py`):**

| Label | Rule |
|-------|------|
| `INVERTED` | T10Y2Y spread < −10 bps (v1) or < 0 for ≥ 4 consecutive weeks (v2/F2a) |
| `FLAT` | Spread < 30 bps (not inverted) |
| `STEEPENING` | Spread ≥ 30 bps AND 4-week steepening ≥ 15 bps (v1) or ≥ 40 bps (v2) |
| `NORMAL` | Spread ≥ 30 bps, no significant steepening momentum |

Curve_regime confirmed as 4 states — **Divyanshu is correct.**

---

#### (b) Is the 3×3 simplification formalised? — **No, it is NOT formalised. A 4-state collapse exists.**

The codebase has **`collapse_fed_cycle_v2()`** in `regime_v2_shadow.py` which maps 7 raw states → **4 v2 states** (not 3):

| Raw fed_cycle | → fed_cycle_v2 |
|---------------|----------------|
| `HIKING_EARLY`, `HIKING_LATE`, `TIGHTENING` | **TIGHTENING** |
| `CUTTING_EARLY` | **PIVOTING** |
| `CUTTING_LATE` | **EASING** |
| `PAUSING`, `QE`, `QT` | **EASY** |

**What is stored in DB (macro_regime_log_v2, n=1,901 Fridays):**
- `fed_cycle_v2`: TIGHTENING=763, EASING=727, EASY=384, PIVOTING=27
- `curve_regime_v2`: STEEPENING=1,471, FLAT=316, INVERTED=85, NORMAL=29

The **7×4 = 28-cell matrix** (or 3×3 simplification) discussed conceptually is **not implemented as a cross-product or as any analytics structure**. No code currently groups hit rates by `(fed_cycle_bucket × curve_regime_bucket)` cells. The `fed_cycle_v2` collapse is a linearisation only — no 28-cell or 9-cell matrix is built or queried.

**What the `fed_cycle_v2` collapse maps to in practice:**
- PIVOTING has only n=27 Fridays — effectively tiny; for hit-rate purposes it behaves as a rounding error.
- The 3×3 presentation simplification (tightening/easing/pausing) could be achieved by merging PIVOTING → EASING and renaming EASY → PAUSING, but **this rename is not done anywhere in code**.

**Verdict:** The 3×3 simplification is **conceptual only**. The codebase has a 4-state `fed_cycle_v2`, not 3. No matrix cross with curve_regime exists in any analytics table.

---

#### (c) How are regime-adjusted hit rates actually grouped?

**Two separate systems:**

**1. Hostile regime filter (binary — used in threshold_sweep_v2.py and combo_discovery_pipeline.py):**
```
HOSTILE_FED = {"HIKING_EARLY", "HIKING_LATE", "TIGHTENING"}
hostile_curve_regimes: [INVERTED]  # from CONFIG.yaml
```
A fire is classified as HOSTILE (True/False) if: `fed_cycle ∈ {HIKING_EARLY, HIKING_LATE, TIGHTENING}` OR `curve_regime == "INVERTED"`. Hit rates are then reported as: overall hit rate vs hostile-subset hit rate. **This is a binary split, not a 7-state or 3-state split.**

**Important gap:** `combo_fires.macro_regime` stores only 3 distinct raw fed_cycle values in practice: `HIKING_LATE`, `CUTTING_LATE`, `QE`. `HIKING_EARLY`, `CUTTING_EARLY`, `PAUSING`, `QT` do not appear in the combo_fires table because they were recorded under the legacy label at time of fire. The hostile filter catches `HIKING_LATE` correctly; `HIKING_EARLY` fires are not in the DB (no combo named during that window historically).

**2. fm_events analytics (used in testingv2 experiments):**
Uses `fed_cycle_v2` (4-state collapsed) for slicing, applied via `slice_by_regime()` in `metrics.py`. Hit rates in the A-regime_dimensions.json and T2/T3 tables are grouped by the **4-state** `fed_cycle_v2` labels.

**Summary:**

| Context | Grouping used |
|---------|--------------|
| Hostile filter (threshold sweep, combo discovery) | Binary: HOSTILE yes/no |
| fm_events / regime slice analytics | 4-state fed_cycle_v2 (TIGHTENING/PIVOTING/EASING/EASY) |
| Production nightly regime display | 7-state raw fed_cycle |
| Presentation / 3×3 matrix | Conceptual only — not implemented |

---

#### (d) Claude classifier temperature — **BUG FOUND AND FIXED**

`temperature` was **NOT set** in `call_claude()` (`src/macro_intelligence/claude/_client.py`). The Anthropic API defaults to `temperature=1.0` when omitted, meaning historical replays on identical inputs could produce different narrative text each time.

**Fix applied 2026-06-25:** `temperature=0.0` added as default parameter to `call_claude()`:

```python
def call_claude(system: str, user: str, max_tokens: int = 400, temperature: float = 0.0) -> str:
    ...
    response = client.messages.create(
        model=_model(),
        max_tokens=max_tokens,
        temperature=temperature,   # ← was missing; now defaults to 0.0
        ...
    )
```

All callers (`nightly_briefing.py`, geo classifier, etc.) inherit `temperature=0.0` by default. Any caller that explicitly wants non-deterministic generation can pass `temperature=1.0`.

**Note:** Even at `temperature=0.0`, identical outputs are guaranteed only if the model version is pinned (which it is via `MACRO_CLAUDE_MODEL` env var or `CONFIG.yaml` `claude.model`). Model upgrades will still change outputs.


---

### Q9: Combo B Regime-Adjusted Hit Rate — Run and Validated (2026-06-25)

**Question:** Spec claims Combo B hits 91% in cutting cycles and 68% in hiking cycles. Have you run this against the actual DB? Validate numbers. Flag if n too small.

---

#### Fix to user-provided SQL before running

The SQL in the question uses `cf.combo_id = fr.return_id` — **this join key is wrong**. The correct join is `cf.combo_id = fr.combo_id` (the `return_id` column is a separate auto-increment PK in `forward_returns`, not the combo link). All numbers below use the correct join.

---

#### Actual DB results — Combo B (bullish, hit = SPX 3M > 0)

**n=276 total fires. n=274 with mature spx_3m. Zero fires with insufficient data.**

**By raw `fed_cycle` label (from `combo_fires.macro_regime`):**

| Fed Cycle | n_total | n_mature (3M) | Hit rate 3M | Avg SPX 3M | Verdict |
|-----------|---------|---------------|-------------|------------|---------|
| CUTTING_LATE | 120 | 118 | **65.3%** | +3.38% | USE |
| HIKING_LATE | 108 | 108 | **77.8%** | +4.08% | USE |
| QE | 48 | 48 | **91.7%** | +8.92% | USE |
| **ALL combined** | **276** | **274** | **74.8%** | +4.63% | USE |

**Full multi-horizon breakdown:**

| Fed Cycle | n | Hit 1M | Avg 1M | Hit 3M | Avg 3M | Hit 6M | Avg 6M | Hit 9M | Avg 9M | Hit 12M | Avg 12M |
|-----------|---|--------|--------|--------|--------|--------|--------|--------|--------|---------|---------|
| CUTTING_LATE | 118 | 64.4% | +1.37% | 65.3% | +3.38% | 74.6% | +6.32% | 82.2% | +9.74% | 86.4% | +11.95% |
| HIKING_LATE | 108 | 67.6% | +1.13% | 77.8% | +4.08% | 88.0% | +8.69% | 92.6% | +13.93% | 94.4% | +18.66% |
| QE | 48 | 81.2% | +3.71% | 91.7% | +8.92% | 81.2% | +14.49% | 93.8% | +23.70% | 93.8% | +30.55% |

*Note: QE fires span 2014-06-27 → 2023-03-31. HIKING_LATE: 2015-12-18 → 2024-04-05. CUTTING_LATE: 2010-06-25 → 2026-07-03.*

---

#### Spec claim validation

**Spec said: "91% cutting cycles, 68% hiking cycles."**

| Claim | Spec | Actual | Match? |
|-------|------|--------|--------|
| Cutting cycle hit rate | 91% | 65.3% (CUTTING_LATE) | **NO** |
| Hiking cycle hit rate | 68% | 77.8% (HIKING_LATE) | **NO** |

**Root cause of discrepancy:**

The spec's "91% cutting" almost certainly refers to the **QE** label (91.7%), not `CUTTING_LATE` (65.3%). QE (balance sheet expansion) overlaps temporally with Fed cuts but is a separate label in the codebase. If someone grouped QE + CUTTING_LATE together as "easing environment," the combined hit rate is **72.9%** at 3M — still not 91%.

The spec's "68% hiking" is close to HIKING_LATE (77.8%) but not exact. The discrepancy could be from: an older DB snapshot, different deduplication logic, or a different horizon (1M HIKING_LATE hit = 67.6% ≈ the spec's 68%).

**CANNOT USE the spec numbers as stated.** The database supports only three labels (CUTTING_LATE, HIKING_LATE, QE) for Combo B fires — no HIKING_EARLY, CUTTING_EARLY, PAUSING, or QT fires exist in Combo B history. This means we cannot disaggregate "early" vs "late" within hiking or cutting cycles for this combo.

---

#### Recommended presentation to fund

| Cycle bucket | n | Hit rate 3M | Avg SPX 3M | Note |
|---|---|---|---|---|
| QE / balance-sheet expansion | 48 | **91.7%** | +8.92% | Best environment for B |
| Hiking (HIKING_LATE) | 108 | **77.8%** | +4.08% | Counter-intuitively strong |
| Cutting (CUTTING_LATE) | 118 | **65.3%** | +3.38% | Weakest — but still majority positive |
| **Overall** | **274** | **74.8%** | +4.63% | USE |

Key insight: Combo B is **strongest in QE and hiking** environments — not in cutting cycles as the spec stated. Cutting (CUTTING_LATE) is actually the weakest bucket. At longer horizons all three converge upward (6M–12M), but the 3M hierarchy is QE > HIKING > CUTTING.

**Exports:**
- `csv_exports/combo_b_fed_cycle_hit_rates.csv` — summary (4 rows, all horizons)
- `csv_exports/combo_b_per_fire_regime.csv` — per-fire rows (276 rows, with hit flag)

