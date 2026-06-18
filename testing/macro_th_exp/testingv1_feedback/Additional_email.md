UNSENT EMAIL REFERRED TO EARLIER

Divyanshu,

Several architectural clarifications and action items following our review of the macro regime model. Please read this carefully before the next development sprint.

- --

1. HISTORY WINDOWS — CONFIRM THE CORRECT SPEC

Please confirm and implement the following window rules (these supersede any earlier drafts that said 3-year rolling for everything):

- All structural/level variables (CAPE, VIX, yield curve, NFCI, GSR): use FULL EXPANDING HISTORY from variable inception. Never rolling. You want 1970s inversion episodes in the yield curve distribution; you want 1881 CAPE data in the valuation distribution.

- Inflation/rate-of-change variables (WTI 4wk%, CNH 4wk%, WALCL MoM%, CPI surprise): use 3-year rolling. These are regime-dependent and lose meaning over long windows.

- New variable (if we add it): 2-year USD yield 8-week rate of change — 3-year rolling.

- Store both unconditional_pctile (full history) and regime_pctile (conditioned on fed_cycle) for each variable each day. Combo detection uses unconditional. Conviction modifier uses regime_pctile. Fallback to unconditional if regime-conditioned subset has fewer than 50 observations.

- --

2. WHAT "PERCENTILE RANK" MEANS AND WHY IT MATTERS

For each of the 13-14 Runic variables on any given day, you compute one number: where does today's reading sit within the full available history of that variable? VIX at 35 against a 1990-present history = approximately the 92nd percentile = 0.92. This is the percentile rank.

This number is used in two ways:

(a) Combo detection: is it above the RARE threshold (80th-95th percentile depending on variable)?

(b) HMM emission probability: the 13 percentile ranks become the observation vector fed into the HMM each day. The HMM then asks: given a vector like [VIX: 0.92, HY: 0.85, WTI: 0.70, CFTC: 0.12 ...], what is the posterior probability of being in each regime state?

The key difference from what we have now: currently, a variable below its threshold contributes NOTHING to the model. With emission probabilities, a VIX at 0.72 (below the 0.80 RARE threshold) still provides partial evidence for the Stressed state. Sub-threshold readings accumulate evidence week by week. The model becomes sensitive to regime buildup before any single variable crosses its threshold.

Implementation note: you do not need to build the full HMM in the first pass. Start by storing the 13 percentile vectors daily alongside combo_fires. The HMM training can come later once you have 6+ months of clean vectors.

- --

3. FEEDING POSTERIORS INTO THE REGIME CLASSIFIER PROMPT

Once the HMM is trained (even a simple 3-state: Risk-On / Risk-Off / Transition), you will have a daily posterior vector, e.g. [Risk-On: 0.65, Risk-Off: 0.25, Transition: 0.10].

This gets added to the Section 5.2 prompt as an additional input:

"HMM posterior state probabilities — Risk-On: 0.65, Risk-Off: 0.25, Transition: 0.10. Use these as a soft prior on regime. If HMM Risk-Off probability is above 0.40, weight toward tighter regime classifications even if individual variables have not crossed thresholds."

This makes the Claude API classifier materially smarter because it receives not just today’s individual readings but a model-synthesised view of whether the overall regime pattern matches historical stressed periods.

- --

4. THE GRIND AND SUPPRESSED PERSISTENCE SIGNALS — DEFINE AND IMPLEMENT

The Addendum mentions persistence signals but they are not yet formally defined. Please implement the following two as the first batch:

7WK_GRIND: SPX weekly close > prior week’s close by at least +0.5% for 7 consecutive weeks. Saturday job. Check last 7 weekly SPX closes. If condition met, flag streak and store in persistence_fires table with date and streak_length. Wire as AMPLIFIER to Combo E (valuation extreme) — when both fire simultaneously, the structural warning is elevated. Analysis confirms this is not a reliable standalone short signal (average 6m return after grind fires is +7.5%, 100% positive). Use only as amplifier, not trigger.

VIX_SUPPRESSED: VIX close < 15 for 10 consecutive trading days. Daily job. Store in persistence_fires table. Wire as PRECURSOR to Combo D (FOMO top/euphoria). Historical analysis: 12 instances since 1990, approximately half (6/12) were followed by VIX events above 30 within 12 months. The other half saw markets continue without a major shock. This is a WATCH LIST signal, not a sell trigger.

For both: store start_date, most_recent_date, streak_length, and combo_link in persistence_fires. Surface on the nightly briefing with explicit language: "[GRIND/VIX_SUPPRESSED] active for N days/weeks — monitor for Combo D/E confirmation."

- --

5. HIKING_LATE — PLEASE FORMALISE THE QUANTITATIVE DEFINITION

The current classifier prompt infers HIKING_LATE from context. This is not reproducible or testable. Please add explicit quantitative trigger rules to the prompt so the classification can be validated:

HIKING_LATE: FFR > 3.5% AND FFR has risen > 150bps in prior 12 months AND (10Y-2Y < -30bps OR rate of hike deceleration is negative over the last two Fed meetings).

HIKING_EARLY: FFR rising AND total hike cycle < 150bps.

CUTTING_EARLY: FFR falling AND first cut was within last 6 months.

CUTTING_LATE: FFR falling AND has fallen > 150bps from cycle peak.

PAUSING: FFR unchanged for 3+ consecutive meetings.

QE: WALCL rising, FFR at or near zero lower bound.

QT: WALCL falling at > $50bn/month rate.

October 2022 canonical example: FFR ~3.25%, risen 300bps in 9 months, curve -50bps = HIKING_LATE. March 2020: FFR at zero, WALCL expanding rapidly = QE. Please validate these labels against all historical backfill dates and report any inconsistencies.

- --

6. COMBO DETECTION — CONFIRM WE HAVE SWITCHED TO EXPANDING HISTORY

The spec previously said 3-year rolling percentile for all variables. The updated approach is full expanding history for structural variables (see item 1 above). Please confirm in code that combo detection for CAPE, VIX, NFCI, yield curve, and GSR uses full expanding history, not a 3-year rolling window. Update and re-run the historical backfill if this was not already the case. The change will affect percentile rankings for these variables, which will affect which combo fires are recorded historically.

- --

7. BETA ADJUSTMENT FOR UNNAMED COMBOS — UPDATED DEFINITION

When testing the 291 unnamed combos, the hit rate gate is 60% with minimum 3 fires (for surfacing) and 75% with minimum 5 fires (for naming). To deal with the risk that a combo is lucky due to market beta rather than genuine signal, add a directionality consistency test:

A bullish unnamed combo must show hit rate ≥50% in HIKING or INVERTED curve periods (not just in QE/bull periods) to be considered genuine. Define INVERTED period as: 10Y-2Y spread < -20bps sustained for at least 4 consecutive weeks. Define HIKING period as: FFR rising, total hike cycle > 100bps. A combo that performs well only in easy monetary conditions is picking up beta, not alpha.

The 55% threshold for this test (not 60%) is deliberate — HIKING/INVERTED periods are naturally adverse for longs, so requiring 60% there would eliminate most genuine signals too. 55% says the signal still works in hostile conditions, just modestly. You can test 55% vs 60% and report both.

- --

8. SAMPLE SIZE NOTE FOR REGIME-CONDITIONAL COMBOS

When you compute regime_pctile for a variable conditioned on fed_cycle, the regime-conditioned subset may have fewer than 50 observations for some variable-regime combinations. In that case, fall back to the unconditional percentile rank and log which was used. Do not make investment decisions based on a regime-conditional percentile rank computed from fewer than 30 observations. The 3-4 instances of a given combo firing in HIKING_LATE since 1990 is too few for statistical confidence alone — which is exactly why we use scenario analysis (does the outcome have an economic story?) alongside the quantitative hit rate.

Rohit

**CANCELLATION EXPLAINER - PLEASE ASK ME IF ANY QUESTIONS. I AM HAPPY TO EXPLAIN.**

!image.png

image.png

CANCEL OPTION MATH

Per-Friday digital put probability:

d2 = [ln(S/K) + (−σ²/2)·T] / (σ·√T)

P(WTI_Friday < K) = N(−d2)

Current inputs: S=$91, σ=35%, σ_weekly=4.85%

Strikes: K1=$99.8, K2=$101.9, K3=$99.8, K4=$95.5

Moneyness (S/K−1): -8.8%, -10.7%, -8.8%, -4.8%

Path dependency: 4 consecutive readings required (not just any 4 of 4).

Overlapping 4wk windows → ρ ≈ 0.75 between adjacent Fridays.

Monte Carlo (GBM, 20k paths) captures correlation exactly.

Joint P(cancel WTI leg) = 69.7% [MC estimate, ±0.6% 95% CI]

The cancel condition is a **path-dependent digital barrier** — similar to an Asian digital or a consecutive-touch barrier option. Vanilla N(d2) gives the marginal probability per Friday. The consecutive requirement introduces correlation across the four readings (overlapping 4-week windows share 3 of 4 weeks → ρ ≈ 0.75). Monte Carlo with GBM paths captures this exactly.

The CPI leg is an independent condition. Total P(combo C cancels fully) = P(all 4 WTI Fridays clear) × P(CPI non-hot for 2 consecutive prints). Treat the two legs as independent unless there is a structural link (e.g. oil-driven CPI).

AN EXPLAINER FROM CLAUDE

That's the rigorous version of what you described. A few notes on the framework:

**What makes this genuinely options-theoretic and not garbage**

Each Friday's cancel probability is computed as N(−d2) — exactly the risk-neutral probability that a log-normally distributed asset ends up below the strike at expiry. The "strike" is WTI_ref_k × 1.05. The "implied forward" is the current WTI price projected by GBM. The "vol" is the annualised WTI volatility (default 35%, calibrate to whatever your realized vol estimate is). The moneyness display tells you whether today's WTI is already below each strike and by how much.

**Why Monte Carlo rather than just multiplying the four marginals**

Multiplying the four N(−d2) values would assume independence — i.e. that Friday 1 and Friday 2 are unrelated events. They're not: consecutive 4-week windows share three of four weeks, so adjacent readings have ρ ≈ 0.75 under GBM. Monte Carlo generates full price paths, so the correlation structure is handled correctly without any approximation. The 95% confidence interval shown in the formula box tells you how precise the Monte Carlo estimate is — at 20k paths it's typically ±0.5-1.5%.

**Extending this to any Combo cancel condition**

The same framework generalises directly. For any condition of the form "variable X stays below/above threshold Y for N consecutive periods":

- S = current value of variable X
- K = threshold Y
- σ = historical volatility of X
- T_k = time horizon for period k
- Correlation between periods = overlap fraction

The CPI leg of Combo C is a separate digital binary — P(CPI print ≤ consensus for 2 consecutive releases). That's not a continuous price process but a discrete event, so it needs a different calibration: historically what fraction of CPI prints have come in ≤ consensus? That's your per-print probability, and since consecutive prints are largely independent, P(2 consecutive) ≈ p². Multiply that by the WTI leg probability to get total P(Combo C fully cancels).

**Why this matters for position sizing beyond Combo C**

This same logic applies to any time-based or level-based combo rule. Combo F's 26-week validity window = P(still active in week N) = 1 if N ≤ 26, 0 if N > 26 (deterministic, no probability needed). Combo D's 3-10 day short horizon = the digital put expires fast, so high vol makes it either clear quickly or fail quickly. Combo G's "leads vol spike 3-6 weeks" = you're estimating P(vol spike materialises within the window), which is essentially a variance option. The framework is the same in each case — what varies is the underlying process and the threshold structure.

**DOCUMENT SHARED EARLIER CONTAINS REGIME SCORE, FIT CALCULATIONS, ETC**

**JUNE 04 DOCUMENT –DIVYANSHU FINAL ADDENDUM REGIME SCORE FED CYCLE –**

**MACRO INTELLIGENCE AGENT — FINAL BUILD SPEC ADDENDUM**

**Divyanshu  |  June 4, 2026  |  Covers: Fed cycle classification · Regime score methodology · FM covering velocity · Combo predictive power testing · 291+ unnamed combo engine**

**Divyanshu,**

**This addendum consolidates all open specification items and introduces the final testing framework for the predictive power of the combo engine. Read alongside the main spec v2.2 and addendum already sent.**

# **SECTION A — FED CYCLE CLASSIFICATION (Python rules, final version)**

## **A1. The AND condition for HIKING_LATE and CUTTING_LATE**

**Important naming note: HIKING_LATE means LATE IN THE HIKING CYCLE (cycle is mature, >6 months old). It does NOT mean 'late to hike' or any comment on Fed policy timing.**

**The two conditions must BOTH be true (AND, not OR):**

- **Time condition: >6 months since first hike of this cycle (HIKING_LATE) or >9 months since first cut of this cycle (CUTTING_LATE)**
- **Market confirmation: 2-year UST yield 8-week change < −20bps (LATE in hiking = market pricing end of cycle) or > +20bps (LATE in cutting = market pricing end of cuts)**

**Why AND and not OR: Time alone can misclassify early — a 7-month-old hiking cycle where 2Y yields are still rising is not 'late'. Market confirmation via 2Y yield provides the forward-looking layer that the calendar-based rule misses. They are complementary, not redundant.**

**def classify_fed_cycle(fed_funds_rate_series, us2y_series, walcl_series):**

**current_rate = fed_funds_rate_series.iloc[-1]**

**us2y_change_8wk = (us2y_series.iloc[-1] - us2y_series.iloc[-40]) * 100  # bps**

**walcl_mom = (walcl_series.dropna().iloc[-1] / walcl_series.dropna().iloc[-5] - 1) * 100**

**if walcl_mom > 0.8:  return 'QE'**

**if walcl_mom < -0.8: return 'QT'**

**# Find first hike/cut of current cycle**

**rate_diff = fed_funds_rate_series.diff()**

**# HIKING LATE: >6 months AND 2Y already falling >20bps**

**if us2y_change_8wk > 20:  # market still pricing hikes**

	**first_hike = get_first_cycle_action(rate_diff, direction='hike')**

	**months = (fed_funds_rate_series.index[-1] - first_hike).days / 30**

	**if months > 6 and us2y_change_8wk > 20: return 'HIKING_LATE'**

	**if months <= 6: return 'HIKING_EARLY'**

**# CUTTING LATE: >9 months AND 2Y already rising >20bps**

**if us2y_change_8wk < -20:  # market still pricing cuts**

	**first_cut = get_first_cycle_action(rate_diff, direction='cut')**

	**months = (fed_funds_rate_series.index[-1] - first_cut).days / 30**

	**if months > 9 and us2y_change_8wk < -20: return 'CUTTING_LATE'**

	**if months <= 9: return 'CUTTING_EARLY'**

**# Pausing — use 2Y direction for sub-classification**

**if us2y_change_8wk < -15: return 'PAUSING_DOVISH'**

**if us2y_change_8wk > +15: return 'PAUSING_HAWKISH'**

**return 'PAUSING_NEUTRAL'**

## **A2. What to test / validate empirically**

**Divyanshu: once the historical database is populated, run the following validation. The goal is to confirm whether the AND condition (time + 2Y yield) improves regime-adjusted hit rates versus the time-only condition.**

| **Test** | **What to run** | **Expected finding** | **Which combos to test on** |
| --- | --- | --- | --- |
| **Test A1: Time-only classification** | **Classify each historical combo fire using time-based rule only (>6m = HIKING_LATE, >9m = CUTTING_LATE). Compute hit rate for Combo B and Combo F split by regime.** | **Baseline hit rates: B in HIKING_LATE ~68%, B in CUTTING_LATE ~91%** | **Combo B, Combo F primarily. Also C, E.** |
| **Test A2: AND condition classification** | **Reclassify using AND condition (time + 2Y yield 8wk change). Some HIKING_LATE dates will reclassify to HIKING_EARLY if 2Y not yet falling. Recompute hit rates.** | **Hit rate gap between LATE and EARLY should widen if AND condition is better. HIKING_LATE hit rate should increase.** | **Same combos. Compare directly to Test A1.** |
| **Test A3: 2Y yield only (no time condition)** | **Classify purely by 2Y yield 8wk direction (< -20bps = CUTTING, > +20bps = HIKING, ±20bps = PAUSING). Compute hit rates.** | **Should produce leading indicators. May show higher predictive power at short horizons (1-3m) but noisier.** | **All named combos.** |
| **Test A4: Union set analysis** | **Find dates where Time-only fires CUTTING_LATE AND 2Y-yield fires CUTTING simultaneously. Compute hit rate on intersection vs each alone.** | **Intersection should have highest hit rate — most conservative but most reliable.** | **Combo B (most important to validate).** |

# **SECTION B — REGIME SCORE: PROPER HEURISTIC METHODOLOGY**

## **B1. The problem with the earlier approach**

**The arbitrary direction weights (±0.5, ±0.8, ±0.6 etc.) and probability estimates had no formal basis. They were heuristic guesses. The correct approach uses the combo hit rates directly as weights, applies a time-decay for time-limited signals, and produces a score with a natural interpretation.**

## **B2. Correct formula**

**Score for each combo = (hit_rate − 0.5) × direction × active × time_decay**

**Where:**

- **(hit_rate − 0.5) = the 'edge above chance'. A 50% hit rate gives 0 edge. A 90% hit rate gives 0.40 edge. A 60% hit rate gives 0.10 edge. This is the only defensible weight — it is derived directly from empirical data.**
- **direction = +1 for bullish combos (B, F, A-EASY), −1 for bearish combos (C, D, E, G, A-TIGHT)**
- **active = 1 if all required conditions met (per combo spec), 0 otherwise. If E requires 2 of 3 and 2 are met, active = 1. Not fractional.**
- **time_decay = for time-limited signals: remaining_window / total_window. Combo F week 10 of 26 = 16/26 = 0.615. For unlimited signals (E, A): time_decay = 1.0. For approaching-cancellation signals (C): time_decay = weeks_remaining_before_likely_cancel / median_duration.**

**# Today June 4, 2026 — computed regime score**

**combos = {**

**'C': {'hit_rate': 0.83, 'direction': -1, 'active': 1,**

	**'time_decay': 0.25},  # wk12 of 16 MEDIUM, 4wks to cancel window**

**'E': {'hit_rate': 0.73, 'direction': -1, 'active': 1,**

	**'time_decay': 1.00},  # no time limit**

**'F': {'hit_rate': 0.85, 'direction': +1, 'active': 1,**

	**'time_decay': 0.615}, # wk10 of 26**

**'B': {'hit_rate': 0.91, 'direction': +1, 'active': 0,**

	**'time_decay': 1.00},  # CFTC met but VIX and HY not**

**}**

**score = sum((v['hit_rate']-0.5) * v['direction'] * v['active'] * v['time_decay']**

	**for v in combos.values())**

**# = (0.33×-1×1×0.25) + (0.23×-1×1×1.0) + (0.35×+1×1×0.615) + (0.41×+1×0×1.0)**

**# = -0.083 + -0.230 + +0.215 + 0.000**

**# = -0.098   →  MILDLY BEARISH (scale approx -1 to +1)**

**Why this is better: Every weight traces directly to an empirical hit rate. Time decay prevents expired signals from dominating. The scale [-1, +1] has natural meaning: 0 = no edge, +1 = all bullish combos firing at maximum hit rate simultaneously.**

**Important: The direction weights and hit rates will be refined once the historical database has 30+ instances per combo. Until then, use the confirmed hit rates from the spec (B=0.87-0.91, F=0.78-0.85, C=0.83, E=0.73, D=0.72-0.85, G=0.75).**

# **SECTION C — FM SHORT COVERING VELOCITY**

## **C1. What to compute from CFTC historical data**

**Fast Money (FM) = Leveraged Funds in the CFTC TFF report. Current FM net position as of May 26, 2026: −2,071,353 contracts (5th–8th percentile of 3yr rolling window = extreme short). SPX has rallied ~25% since April 2025 low yet FM has barely covered. This divergence is unusual and important for Combo F.**

**Divyanshu: pull the full CFTC TFF historical CSV for S&P 500 E-mini futures (2006–2026) from cftc.gov annual files. Compute the following:**

| **Metric** | **Method** | **Output** |
| --- | --- | --- |
| **All weeks FM < 10th pctile (3yr rolling)** | **Compute FM net = Lev_Long - Lev_Short for each week. Compute 3yr rolling percentile. Find all weeks < 10th pctile.** | **List of episode start dates** |
| **Weeks from trough to 50th pctile (neutral)** | **For each episode: count weeks from first sub-10th reading until FM crosses 50th pctile. Record how fast covering occurred.** | **Distribution of covering duration: min, median, max weeks** |
| **Weekly covering rate (contracts/week)** | **(50th pctile level − trough level) ÷ weeks elapsed for each episode** | **Avg weekly covering rate** |
| **SPX return during covering window** | **SPX close at episode start vs SPX close when FM reached 50th pctile** | **Confirms whether SPX gain drives covering or covering drives SPX gain** |
| **Current anomaly flag** | **Current episode: 10 weeks elapsed, FM moved from ~2nd to ~7th pctile. Compare velocity to historical avg.** | **If current velocity < historical avg by >50%: flag as anomaly — covering phase has further to run** |

**Why this matters for Combo F: Combo F's +9.46% average 6m return is driven mechanically by short covering. If FM covering velocity is historically 8 weeks to neutral and we are at week 10 with FM still at 7th pctile, one of two things is true: (a) this episode's covering phase will be unusually prolonged and SPX will continue higher, or (b) the covering has stalled because funds are right to stay short. Distinguishing these two cases requires knowing historical velocity. That is what this analysis provides.**

# **SECTION D — REGIME SCORE VALIDATION TESTS**

## **D1. How to validate the regime score formula**

**Once the historical database is populated (combo_fires + forward_returns + macro_regime), run:**

| **Test** | **Method** | **Success criterion** |
| --- | --- | --- |
| **Regime score vs forward SPX returns** | **For each historical date in combo_fires, compute regime score using the (hit_rate−0.5)×direction×active×time_decay formula. Run Spearman correlation between score and SPX 3m/6m forward return.** | **Spearman ρ > 0.30 at 3m, > 0.35 at 6m. p-value < 0.05.** |
| **AND condition improvement test** | **Recompute regime score using time-only fed cycle vs AND condition. Compare correlations.** | **AND condition should produce higher ρ at 6m horizon.** |
| **Hit rate weight calibration** | **Test alternative weights: equal weighting (all combos weight 1), hit-rate weighting (current proposal), and optimised weighting (minimise MSE on forward returns). Compare out-of-sample performance on held-out 20% of dates.** | **Hit-rate weighting should outperform equal weighting. Optimised weighting may overfit — report both.** |
| **Time decay sensitivity** | **Test regime score with time_decay=1.0 (no decay) vs proposed decay formula. Compare predictive power.** | **Decay should improve predictive power at short horizons (3m) by preventing stale signals from dominating.** |

# **SECTION E — 291+ UNNAMED COMBO ENGINE: PREDICTIVE POWER FRAMEWORK**

## **E1. The problem: how do we know which unnamed combos are signal vs noise?**

**The 298-combo engine will discover combos that fire with high hit rates by chance — especially at small N (3-5 instances). We need a rigorous gating framework that distinguishes genuine signal from statistical noise.**

## **E2. The three-gate framework**

| **Gate** | **Condition** | **Rationale** |
| --- | --- | --- |
| **Gate 1: Minimum instances** | **≥5 historical fires (not 3) before a combo is considered for naming. At N=3 the 80% hit rate threshold (2.4 successes) has a p-value of ~0.10 under the null of 50% hit rate — not significant. At N=5 with 80% hit rate, p-value ~0.03.** | **Statistical minimum for significance given fat-tailed financial data** |
| **Gate 2: Hit rate threshold** | **≥80% hit rate at 3m for bullish combos, ≥75% at 6m. For bearish combos: ≥75% at 3m. These thresholds ensure the hit rate is meaningfully above the unconditional SPX return frequency (~60% of 3m periods are positive).** | **Ensures edge above unconditional baseline** |
| **Gate 3: Economic mechanism check (Claude API)** | **Pass every Gate 1+2 combo to Claude API with: 'What causal economic mechanism explains why these two/three variables being simultaneously extreme predicts SPX forward returns?' If Claude cannot articulate a plausible mechanism, flag as STATISTICAL — do not name it.** | **Prevents spurious correlations from entering the rule library** |
| **Gate 4: Out-of-sample validation** | **Split historical data 80/20. Gate 1-3 applied on training set only. Validate hit rate on held-out 20%. If hit rate drops >15pp out-of-sample, mark combo as OVERFIT — do not use.** | **Prevents overfitting on small samples** |

## **E3. Persistence signals (separate from cross-sectional combos)**

**The 298-combo engine detects cross-sectional extremes (multiple variables extreme on the same day). Persistence signals detect time-series patterns within a single variable. These are architecturally separate but feed the same output JSON. Build the persistence engine as a separate weekly job:**

| **Signal name** | **Variable** | **Condition** | **Consecutive periods** | **Gate condition** |
| --- | --- | --- | --- | --- |
| **7WK_GRIND** | **SPX weekly return** | **>+0.5%** | **7 weeks** | **≥3 historical instances, SPX forward return distribution shows mean reversion signal** |
| **3WK_SURGE** | **SPX weekly return** | **≥+3%** | **3 consecutive weeks** | **2 instances since 1980 — too few for Gate 1. Store as WATCH only, do not promote to named combo.** |
| **VIX_SUPPRESSED** | **VIX daily close** | **<15** | **10 trading days** | **≥5 instances. Test whether VIX suppression >10 days predicts higher vol realization in next 30 days.** |
| **HY_GRIND_TIGHT** | **HY OAS 4wk change** | **tightening (≥−20bps)** | **8 consecutive weeks** | **≥5 instances. Test forward HY spread reversion and SPX return.** |
| **OIL_VOLATILE** | **WTI weekly** | **±5%+ alternating** | **4 consecutive weeks** | **Directional volatility — test whether this precedes trend resolution.** |

**E4. Variable count clarification**

**The system now has 13 variables (12 original + 2-year UST yield as an additional variable used for fed_cycle classification). The 2Y yield is NOT added to the combinatorial engine as a 13th combo variable — it is used only in the regime classifier. The combo engine remains 12C1+12C2+12C3 = 298 combinations. If the 2Y yield is later added as a combo variable, the engine becomes 13C1+13C2+13C3 = 13+78+286 = 377 combinations. That is a v2 decision.**

**SECTION F — COMBO A NAMING CHANGE**

**Final naming for Combo A: EASY MONEY (when FCI variables signal loose/expanding conditions) and TIGHT MONEY (when FCI variables signal tight/contracting conditions). Replace all instances of BRAVE/FEARFUL/BULLISH ENVIRONMENT in the code and output JSON.**

| **Old label** | **New label** | **JSON field value** |
| --- | --- | --- |
| **Combo A BRAVE** | **EASY MONEY** | **combo_a_regime: 'EASY_MONEY'** |
| **Combo A FEARFUL** | **TIGHT MONEY** | **combo_a_regime: 'TIGHT_MONEY'** |
| **NFCI 'BRAVE extreme' zone** | **EASY EXTREME (NFCI < −0.6)** | **nfci_zone: 'EASY_EXTREME'** |
| **NFCI 'RARE LOOSE' zone** | **EASY (NFCI < −0.3)** | **nfci_zone: 'EASY'** |
| **NFCI 'RARE TIGHT' zone** | **TIGHT (NFCI > +0.3)** | **nfci_zone: 'TIGHT'** |
| **NFCI 'EXTREME TIGHT' zone** | **CREDIT STRESS EXTREME (NFCI > +0.8)** | **nfci_zone: 'STRESS_EXTREME'** |

**Divyanshu — this addendum + the main spec v2.2 + the data source PDF = complete build specification. If anything is unclear, ask before building. The testing framework in Section D and E is particularly important — do not skip it.**

**Rohit**