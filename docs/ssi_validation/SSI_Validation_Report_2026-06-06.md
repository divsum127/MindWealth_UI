# SSI Threshold Validation Report

**Source spec:** `SSI_OpenQuestions_DivyanshuTestList (1).pdf`
**Artifacts:** `macro_intelligence/analysis/ssi_validation/*_20260604.json`

---

## Overview (How I have structured the data and timeline details etc. )

SSI is a single daily score that summarises how risk-on or risk-off markets are feeling. It blends credit, volatility, sentiment surveys, and CFTC positioning into one composite number, which then feeds two downstream consumers: `positioning.json` (position sizing for the C++ engine) and `ssi_multiplier` (input into the Runic macro agent).

The source specification was candid about how thresholds were originally set. Most were round numbers chosen by practitioner consensus and informed analogy, not formal optimization over a full backtest. Given the limited number of extreme historical instances per variable (typically 5 to 10), the spec explicitly warned against overfitting but asked that every threshold methodology be made explicit and tested before going live.

This report documents the results of 14 completed tests and 2 pending tests from the validation suite run on 2026-06-04. The data window covers `2015-01-01` through `2026-06-04` with SPX (`^GSPC`) used as the forward-return benchmark throughout. The central finding is a clear and consequential asymmetry: long gates work well at the bottom quintile of the SSI distribution, but symmetric short gates at the top do not hold up in this sample.

---

## Key Findings

### Finding 1: The Long Level Gate Never Fires; Percentile Works

The original long entry rule (`SSI level < -0.6`) was set as a "symmetric extreme bearish" threshold meant to capture roughly the bottom 20% of the historical SSI distribution. In practise, the composite score almost never fell that far negative. Sweeping levels from -0.3 through -0.9 in 0.1 steps produced zero signal fires across the entire test window.

| Level threshold | n fires | 3m avg SPX % | 3m win % | Sharpe |
|-----------------|---------|--------------|----------|--------|
| <= -0.3         | 0       | n/a          | n/a      | n/a    |
| <= -0.6 (config)| 0       | n/a          | n/a      | n/a    |
| <= -0.9         | 0       | n/a          | n/a      | n/a    |

The percentile-based alternative (5-year rolling rank) performed meaningfully better and actually produced signals. At the `<= 20` threshold used in production CONFIG, 16 long-gate days were identified with 81.25% positive 3-month outcomes.

| Percentile gate | n fires | 3m avg SPX % | 3m median % | 3m win % | Worst 3m % | 3m Sharpe |
|-----------------|---------|--------------|-------------|----------|------------|-----------|
| <= 10           | 5       | +9.18%       | +8.85%      | 100%     | +7.70%     | 13.77     |
| <= 15           | 7       | +6.67%       | +7.99%      | 100%     | +0.40%     | 3.23      |
| <= 20 (config)  | 16      | +4.08%       | +0.40%      | 81.25%   | -0.34%     | 1.80      |
| <= 25           | 19      | +3.79%       | +0.40%      | 73.68%   | -0.34%     | 1.72      |

**Verdict:** The `<= 10` threshold looks strongest on paper (+9.18% avg, 100% win rate) but 5 events is too thin a sample to rely on. The production `long_entry_pctile: 20` is the right balance of frequency and edge. The raw level gate (`-0.6`) should be retained only as a secondary rule.

---

### Finding 2: Short Gate Asymmetry (Tops Are Not Mirrors of Bottoms)

This is the most important finding in the entire suite. The original `short_entry: +0.6` was set as a symmetric mirror of the long gate. The data shows that assumption is wrong. Markets after a +0.6 reading almost always kept grinding higher.

| Level threshold     | n fires | 3m avg SPX % | 3m win % (SPX down) | 1w win % (SPX down) |
|---------------------|---------|--------------|----------------------|----------------------|
| >= +0.6 (original)  | 57      | +5.73%       | 3.51%                | 14.04%               |
| >= +0.7             | 54      | +5.64%       | 3.70%                | 14.81%               |
| >= +0.8             | 34      | +5.20%       | 0%                   | 11.76%               |
| >= +0.85 (config)   | 30      | +6.34%       | 0%                   | 13.33%               |
| >= +0.9             | 23      | +7.37%       | 0%                   | 17.39%               |

At +0.6, SPX averaged +5.73% over the following 3 months and only 3.51% of episodes had SPX fall. Even tightening to +0.85 (30 events) or +0.9 (23 events) produced 0% 3-month short win. The index kept rising at a higher average after extreme greed reads, which is consistent with the momentum-driven bull market environment in this sample.

The percentile sweep tells a more nuanced story at shorter horizons.

| Percentile gate | n fires | 3m avg SPX % | 3m win % (SPX down) | 1w win % (SPX down) | 1w avg SPX % |
|-----------------|---------|--------------|----------------------|----------------------|--------------|
| >= 55           | 16      | +3.68%       | 0%                   | 25.0%                | +1.17%       |
| >= 70 / >= 75   | 11      | +3.31%       | 0%                   | 36.36%               | +0.98%       |
| >= 85 (config)  | 7       | +2.70%       | 0%                   | 57.14%               | +0.52%       |
| >= 90           | 5       | +2.50%       | 0%                   | 60.0%                | +0.29%       |

At `>= 85` percentile, 57% of the following weeks saw SPX fall. That is more useful than the level +0.6 gate (14% 1w win) even if 3-month performance stays unconvincing. Rohit may want to consider tightening to >= 90 (5 events, 60% 1w short win, lowest 3m average at +2.50%) for a more selective short filter.

**Verdict:** Reject `short_entry: 0.6` as the primary short trigger. The production `short_entry_pctile: 85` and `short_entry: 0.85` are more defensible. Short signals in this system work as fade/momentum tools at short horizons, not 3-month directional bets.

---

### Finding 3: CNN Fear Validates for Longs; Greed Data is Missing

CNN Fear and Greed was included in Layer 2 because it is a widely cited sentiment extreme indicator. The spec asked whether the standard thresholds (<20 = extreme fear, >80 = extreme greed) actually hold up in this system's data window.

| Rule          | n crossings | 1w avg SPX % | 1w win % | 3m avg SPX % | 3m win % | 6m avg SPX % |
|---------------|-------------|--------------|----------|--------------|----------|--------------|
| Fear < 20     | 3           | -0.75%       | 33.33%   | +9.73%       | 100%     | +12.58%      |
| Fear < 10     | 3           | +1.32%       | 66.67%   | +13.33%      | 100%     | +16.03%      |
| Greed > 80    | 0           | n/a          | n/a      | n/a          | n/a      | n/a          |
| Greed > 90    | 0           | n/a          | n/a      | n/a          | n/a      | n/a          |

The fear-side data shows confirms the "buy extreme fear" narrative. At fear < 20, the 1-week signal is still slightly negative (-0.75%) but by 3 months the average SPX gain is +9.73% with a 100% win rate. The problem is sample size: only 3 crossings in the test window (`2015-01-01` to `2026-06-04`). The spec expected approximately 22 crossings since 2011, which suggests the CNN data cache being used is incomplete.

The greed side produced zero crossings above 80 or 90 in this artifact. That means short-side CNN rules cannot be validated from this run and the contribution of the CNN input to Layer 2 short signals is currently untested.

**Verdict:** Fear validates for longs. Greed validation requires a re-run with a full CNN cache going back further. Production Layer 2 uses 25/75 (slightly wider than 20/80) which should produce more crossings; that data should be run before treating CNN as a confirmed short-gate contributor.

---

### Finding 4: HYG/LQD Tighter Cuts Give Faster Credit Stress Signals

The original "credit widening" definition was vague. The spec proposed using the 4-week percentage change in the HYG/LQD ratio (not raw spreads), with -1.5% as RARE and -3.0% as EXTREME.

| 4wk HYG/LQD change threshold | n crossings | 1w avg SPX % | 1w win % | Median days to VIX > 25 |
|-------------------------------|-------------|--------------|----------|--------------------------|
| < -1.0%                       | 110         | +0.46%       | 67.27%   | 10                       |
| < -1.5% (PDF RARE)            | 70          | +0.03%       | 61.43%   | 3                        |
| < -2.0%                       | 52          | +0.18%       | 57.69%   | 1                        |
| < -3.0% (PDF EXTREME)         | 28          | +1.68%       | 57.14%   | 1                        |

The standout number here is the "median days to VIX > 25" column. At the -1.0% cut, the median time to a VIX spike is 10 days. At -1.5%, that drops to 3 days. At -2.0% or -3.0%, the VIX spike follows within 1 day. That is a meaningful difference in terms of how much lead time the signal gives risk management.

Worth noting here is that the production Layer 2 uses ratio percentiles (70th/30th) rather than these fixed 4-week percentage cuts. Both approaches are defensible; the percentile method adjusts for regime changes in the ratio level, while the fixed cut is more transparent and directly matches the spec's proposed definition.

**Verdict:** The -1.5% / -3.0% bands from the spec are validated as stress indicators. Production can keep the percentile approach without contradiction; this test supports either method and confirms the directional logic.

---

### Finding 5: DBMF Beta is Context, Not a Standalone Short Trigger

The spec asked for a precise definition of "CTAs moving against the market": 21-day rolling beta of DBMF vs SPY below -0.10.

| Beta cutoff (21d DBMF/SPY) | n crossings | 2w avg SPX % | 2w median % | 2w win % | 2w worst % | 2w Sharpe |
|----------------------------|-------------|--------------|-------------|----------|------------|-----------|
| < -0.05                    | 27          | -0.10%       | +1.19%      | 55.56%   | -9.83%     | -0.15     |
| < -0.10 (PDF)              | 29          | +0.61%       | +1.19%      | 62.07%   | -7.78%     | 0.85      |
| < -0.15                    | 22          | +0.74%       | +1.13%      | 59.09%   | -4.35%     | 1.43      |
| < -0.20                    | 18          | +0.68%       | +1.26%      | 61.11%   | -4.86%     | 1.20      |

The data shows that when DBMF beta is negative (CTAs positioned against equities), SPX still tended to go up over the next 2 weeks: +0.61% avg at the -0.10 cut with a 62% win rate. The stricter -0.15 and -0.20 cutoffs reduce event count without improving Sharpe monotonically.

The production Layer 2 uses normalized beta bands (0.5 / 1.2) on a different scale, not raw -0.10 thresholds. That architecture is consistent with the test conclusion: DBMF belongs in Layer 2 as a confirming input in context with other signals, not as a standalone directional indicator.

**Verdict:** Keep DBMF in Layer 2. No basis to change production YAML to -0.10 threshold without a dedicated recalibration including the full normalized band design.

---

### Finding 6: Percentile Composite Captures Crises; Z-Score Misses Them

This is one of the more striking results in the suite. The production SSI uses z-scores to normalize individual inputs before combining them. The spec flagged that z-scores assume Gaussian tails, while financial markets have fat tails. In crises, multiple inputs spike simultaneously, causing z-scores to dilute each other right when the system should read EXTREME.

Test 9 built a parallel percentile-based SSI (3-year rolling rank instead of z-score) and compared the two in the two clearest crisis windows in the data: COVID (Feb-Apr 2020) and Oct 2022.

| SSI method     | Window           | Days in window | 6m avg SPX % | 6m win % | 12m avg SPX % |
|----------------|------------------|----------------|--------------|----------|---------------|
| Z-score (prod) | COVID Feb-Apr 2020 | 0            | n/a          | n/a      | n/a           |
| Percentile     | COVID Feb-Apr 2020 | 62           | +19.33%      | 93.55%   | +40.16%       |
| Z-score (prod) | Oct 2022         | 0              | n/a          | n/a      | n/a           |
| Percentile     | Oct 2022         | 84             | +7.98%       | 94.05%   | +15.78%       |

The z-score composite registered zero long-gate days in either crisis window. The percentile composite identified 62 days in the COVID window with a 6-month average SPX return of +19.33% and 93.55% win rate, and 84 days in Oct 2022 with +7.98% average and 94% win rate.

That is a significant gap. The system as currently wired with z-scores would have generated no long signals during two of the best buying opportunities in recent market history.

**Verdict:** Test 9 directly supports the spec's concern about z-score dilution in crises. The percentile composite is not deployed in production yet and requires Rohit sign-off before replacing `ssi_score.py`. This should be treated as a high-priority item for the next SIGNOFF review.

---

### Finding 7: Layer 2 Confirmation Threshold Holds at min_confirmed = 2

Layer 2 consists of four binary votes (HYG/LQD, DBMF, CNN F&G, VIX term structure). When two or more votes confirm, the position multiplier is 1.2x. Zero confirmations gives 0.8x.

Test 10 swept the `min_confirmed` parameter from 0 to 4 across the 16 historical long-gate days to see if requiring more confirmations would improve forward returns.

| min_confirmed | n long-gate days | 3m avg SPX % | 3m win % |
|---------------|------------------|--------------|----------|
| 0             | 16               | +4.07%       | 81.25%   |
| 1             | 16               | +4.07%       | 81.25%   |
| 2 (config)    | 16               | +4.07%       | 81.25%   |
| 3             | 16               | +4.07%       | 81.25%   |
| 4             | 0                | n/a          | n/a      |

All 16 long-gate days had 3 or fewer Layer 2 votes active, so the statistics were identical for min_confirmed 0 through 3. Requiring 4 out of 4 confirmations would eliminate every long-gate day in the sample.

**Verdict:** `layer2.min_confirmed: 2` is consistent with the data. There is no evidence to raise it to 3. The multiplier structure (1.2x / 1.0x / 0.8x) is appropriate given the test results.

---

### Finding 8: CFTC SQUEEZE and LIQUIDITY EXIT Grids Are Too Common for SSI Gates

Tests 3 and 4 performed a full grid search on the CFTC Fast Money / Real Money percentile combinations that define the SQUEEZE (FM low, RM high) and LIQUIDITY EXIT (RM low, FM high) patterns. The PDF asked whether round-number thresholds (FM < 30th, RM > 50th etc.) were justified.

SQUEEZE instances by grid cell (2006-2026):

| FM percentile | RM percentile | n instances |
|---------------|---------------|-------------|
| < 40          | > 40          | 191         |
| < 40          | > 45          | 187         |
| < 35          | > 40          | 177         |
| < 30          | > 40          | 161         |

LIQUIDITY EXIT instances:

| RM percentile | FM percentile | n instances |
|---------------|---------------|-------------|
| < 40          | > 45          | 123         |
| < 40          | > 50          | 114         |
| < 35          | > 45          | 112         |

Many of these cells fire 100 to 190 times over a 20-year window, which works out to roughly 5 to 10 instances per year. These are persistent macro regimes, not ultra-rare stress signals. Mapping them directly to SSI long or short gates would mean the gate is "on" for long stretches of time, which is not the intent.

**Verdict:** Use SQUEEZE and LIQUIDITY EXIT as Runic research flags and macro context markers. They should not become SSI CONFIG keys without Rohit selecting a specific FM/RM pair from the heatmap that he wants to use as a gating condition.

---

### Finding 9: VIX Bypass Logic Verified for Oct 2022

The spec raised what it called the "Dalio problem": a VIX > 35 regime multiplier (0.5x) would cut position size at the October 2022 bottom, exactly when Combo B was signaling maximum contrarian buy. The proposed fix was to bypass the VIX size cut when Combo B or F fired within the prior 4 weeks.

Test 11 verified this on the reference date of 2022-10-13.

| Check            | Value         |
|------------------|---------------|
| Reference date   | 2022-10-13    |
| combo_b active   | true          |
| vix_bypass       | true          |
| Avg multiplier   | 1.2x (Layer 2 CONFIRMED path) |

The wiring is correct. The full 2006-2026 equity curve comparison (with vs without the multiplier) was not run and was formally waived in SIGNOFF (WAIVER-VT-11).

**Verdict:** Bypass logic is implemented and verified at the key historical reference point. Economic magnitude over a full 20-year backtest remains unquantified.

---

### Finding 10: Test Completion Status

| Test | Description | Status |
|------|-------------|--------|
| 1 | SSI long threshold sweep (level) | Done |
| 2 | SSI short threshold sweep + asymmetry | Done |
| 3 | SQUEEZE FM/RM grid | Done |
| 4 | LIQUIDITY EXIT FM/RM grid | Done |
| 5 | TP/SL multiplier optimization | Pending (adapter only) |
| 6 | CNN Fear and Greed forward returns | Done (greed: 0 crossings, needs re-run) |
| 7 | DBMF rolling beta threshold | Done |
| 8 | HYG/LQD widening definition | Done |
| 9 | Z-score vs percentile SSI | Done (not in production) |
| 10 | Layer 2 confirmation threshold sweep | Done |
| 11 | VIX regime multiplier + Combo B bypass | Partial (bypass verified; full backtest waived) |
| 12 | Bollinger + SSI | Done (0 overlap at -0.6 level) |
| 13 | Stochastic + McClellan | Done (research only) |
| 14 | Gross/net divergence (3-condition) | Done (21 instances; return export gap) |
| 15 | SBI short signal validation | Pending (needs MindWealth) |
| 16 | Friday pull checklist | Done (10/12 PASS) |

14 of 16 tests are run and archived. Tests 5 and 15 require the MindWealth engine to complete.

---

### Finding 11: Friday Data Pull Automation, 10 of 12 Pass

Test 16 verified that each of the 18 data series in the Friday pull list were being fetched correctly at validation time.

| Variable                    | Status  | Notes                                          |
|-----------------------------|---------|------------------------------------------------|
| NFCI                        | PASS    |                                                |
| HY OAS                      | PASS    |                                                |
| VIX / VIX3M                 | PASS    |                                                |
| WTI / CNH / Gold-Silver     | PASS    |                                                |
| CFTC FM / RM                | PASS    |                                                |
| 10Y-2Y Curve / WALCL / CAPE | PASS    |                                                |
| HYG/LQD                     | PASS    |                                                |
| DBMF beta                   | PASS    |                                                |
| CNN F&G                     | PASS    |                                                |
| NAAIM                       | PASS    |                                                |
| CPI surprise                | WARN    | Investing.com blocked on AWS at run time; fixed via Trading Economics post-run |
| AAII bull-bear spread       | WARN    | Scrape blocked; fixed post-run via direct `sentiment.xls` urllib fetch |

**Verdict:** CPI and AAII have since been fixed. Test 16 should be re-run to confirm a clean 12/12 PASS before sign-off.

---

## Summary and Recommendations

The validation suite directly addresses the spec's core question: are the original judgment-based SSI thresholds defensible before go-live? The short answer is: most of them are defensible with adjustments, and a few need to change.

### What the data supports (keep in production)

| Parameter | Supported value | Key evidence |
|-----------|-----------------|--------------|
| `long_entry_pctile` | 20 | 16 fires, +4.08% avg 3m return, 81.25% win rate |
| `long_entry` (level) | -0.6 (secondary only) | 0 fires at any level threshold |
| `short_entry_pctile` | 85 (consider 90) | n=7 at 85, 57% 1w short win; n=5 at 90, 60% 1w short win |
| `short_entry` (level) | 0.85 | Reduces fires from 57 (at 0.6) to 30, cleaner set |
| `layer2.min_confirmed` | 2 | Identical stats for min 0-3; requiring 4 eliminates all signals |
| Layer 2 multipliers | 1.2x / 1.0x / 0.8x | Consistent with test outcomes |
| `vix_bypass` | On when Combo B or F active | Oct 2022 reference date verified |
| NFCI scope | Runic only | Waiver accepted per overlap doc Part 8 |

### What still needs action before sign-off

| Item | Action required |
|------|-----------------|
| Percentile SSI (Test 9) | Rohit decision: switch from z-score to 3yr percentile composite. Crisis windows (2020, 2022) show 0 z-score events vs 62-84 percentile events with strong forward returns. |
| Short gate percentile | Rohit choice between >= 85 (n=7) and >= 90 (n=5). |
| CNN greed (Test 6) | Re-run with full CNN cache; 0 crossings above 80 means greed-side Layer 2 vote is unvalidated. |
| Test 5 (TP/SL grid) | Run without `--skip-mindwealth`; adapter exists. |
| Test 15 (SBI short) | Run with MindWealth engine. |
| Test 16 (Friday pull) | Re-run after CPI + AAII fixes for clean 12/12 PASS. |
| TrendPulse (Part 7) | No dedicated sweep of 0.5/week deterioration rate threshold. Gap if TrendPulse sign-off is required by product. |

### Proved vs not proved summary

| Proved (with n and return data) | Not yet proved |
|---------------------------------|----------------|
| Long pctile <= 20: 16 fires, +4.08% avg 3m, 81.25% win | TP/SL optimal grid (Test 5 pending) |
| Short +0.6: 57 fires, only 3.51% 3m short win | Full 20-year multiplier equity curve (Test 11 waived) |
| Short >= 85 pctile: 7 fires, 57% 1w short win | Greed CNN crossings (0 in Test 6 artifact) |
| HYG/LQD -1.5%: 70 fires, 3 median days to VIX > 25 | SBI short signal (Test 15 pending) |
| Percentile SSI captures 2020 and 2022 crises; z-score does not | TrendPulse deterioration threshold (no sweep) |
| Layer 2 min_confirmed 2 gives identical results to 0, 1, or 3 | Production switch to percentile SSI (pending sign-off) |
| SQUEEZE/LIQUIDITY: 100+ instances per grid cell (too common for SSI gates) | |
| VIX bypass correctly wired for Oct 2022 | |

---

*Report generated from validation artifacts in `macro_intelligence/analysis/ssi_validation/`. For threshold justification detail see `SSI_THRESHOLD_JUSTIFICATION.md`. Sign-off checklist: `SIGNOFF.md`.*
