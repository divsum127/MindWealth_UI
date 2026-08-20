# CFTC — answers to your six points (13 Aug reply)

**Generated:** 20260820  
**Sample:** 1034 analysis weeks, 2006-10-24 → 2026-08-11 (raw TFF from 2006-06-13)

## First, a data bug that changed every number in the 11 Aug package

The 2006-2016 CFTC bulk file dates as `M/D/YYYY 12:00:00 AM` while the yearly files are ISO.
The parser tried ISO first and only fell back when *every* row failed, so in the combined
history the bulk rows silently became unparseable and were dropped: the sample started 2017
instead of 2006-06-13, and the grids ran on 483 weeks instead of 1034. Fixed
(`_parse_report_dates` now parses the leftovers), and every table below is on the full sample.

## Point 2 — does RM explain anything? No.

| Horizon | FM R² | FM p | RM R² | RM p | Δ adj R² adding RM to FM | RM p (joint) |
|---|---|---|---|---|---|---|
| 1w | 0.00100 | 0.312 | 0.00028 | 0.590 | -0.00089 | 0.767 |
| 2w | 0.00147 | 0.219 | 0.00039 | 0.526 | -0.00086 | 0.734 |
| 4w | 0.00038 | 0.534 | 0.00087 | 0.344 | -0.00032 | 0.414 |
| 8w | 0.00009 | 0.759 | 0.00438 | 0.034 | +0.00337 | 0.035 |

Neither percentile explains SPX forward returns. RM clears 5% only at 8 weeks (p=0.034) — one
horizon out of four, which is what you expect from testing four. Adding RM on top of FM makes
adjusted R² *worse* at 1, 2 and 4 weeks.

### The same cut with and without the RM leg (12-week horizon)

| Condition | Episodes | Mean | Median | Gap | Hit % | Excess mean | Excess hit % |
|---|---|---|---|---|---|---|---|
| FM_roll_pct<10 | 35 | 3.39 | 3.23 | 0.16 | 77.1 | 1.09 | 62.9 |
| FM_roll_pct<10 AND RM_roll_pct>55 | 21 | 3.35 | 3.01 | 0.34 | 81.0 | 1.05 | 61.9 |
| FM_roll_pct<5 | 21 | 2.27 | 3.33 | -1.06 | 65.0 | -0.04 | 55.0 |
| FM_roll_pct<5 AND RM_roll_pct>55 | 6 | 5.78 | 5.67 | 0.11 | 80.0 | 3.47 | 80.0 |
| PAR (unconditional) | — | 2.31 | 3.50 | -1.20 | 71.7 | -0.00 | 59.5 |

**Recommendation:** drop RM from SQUEEZE. It halves the sample (35 episodes → 21) and leaves the
mean and the excess essentially unchanged. You were right that FM is doing the work.

## Point 3 — episodes that coincide with economic events

Event set: CPI, FOMC and NFP releases — CPI 306, FOMC 502, NFP 242 dated releases in the sample. An episode counts as event-coincident when a release lands on
it or within the window before it. Floor of 3 episodes applied as you asked.

Coverage caveat: CPI and NFP cover the whole sample; FOMC dates only exist from 2011, because
FRED has no meeting-date calendar (the id we were using, release 19, is the weekly H.3 reserves
report — that bug is fixed). Pre-2011 gating therefore rests on CPI and NFP.

Read the window column carefully. COT episodes are dated on the Tuesday position date, so a 1 or
3 day backward window only catches releases falling Sunday to Tuesday — which is why those two
rows are identical. The 7 day window is the one that actually spans a normal release week.

| Cell | Window | Weeks (all) | Weeks (event) | Episodes | 12w mean | Excess | Hit % |
|---|---|---|---|---|---|---|---|
| SQUEEZE FM<10 (no RM) | ±1d | 169 | 14 | 13 | 2.57 | 0.26 | 75.0 |
| SQUEEZE FM<10 (no RM) | ±3d | 169 | 14 | 13 | 2.57 | 0.26 | 75.0 |
| SQUEEZE FM<10 (no RM) | ±7d | 169 | 110 | 52 | 3.18 | 0.87 | 78.4 |
| SQUEEZE FM<10 AND RM>55 | ±1d | 82 | 9 | 8 | 0.88 | -1.42 | 71.4 |
| SQUEEZE FM<10 AND RM>55 | ±3d | 82 | 9 | 8 | 0.88 | -1.42 | 71.4 |
| SQUEEZE FM<10 AND RM>55 | ±7d | 82 | 48 | 24 | 2.78 | 0.48 | 78.3 |
| SQUEEZE FM<5 (no RM) | ±1d | 76 | 8 | 7 | 4.17 | 1.87 | 83.3 |
| SQUEEZE FM<5 (no RM) | ±3d | 76 | 8 | 7 | 4.17 | 1.87 | 83.3 |
| SQUEEZE FM<5 (no RM) | ±7d | 76 | 50 | 28 | 3.75 | 1.44 | 81.5 |
| LIQ EXIT FM>=80 (no RM) | ±1d | 214 | 10 | 10 | 0.73 | -1.58 | 60.0 |
| LIQ EXIT FM>=80 (no RM) | ±3d | 214 | 10 | 10 | 0.73 | -1.58 | 60.0 |
| LIQ EXIT FM>=80 (no RM) | ±7d | 214 | 179 | 50 | 2.08 | -0.22 | 66.0 |
| LIQ EXIT RM<30 AND FM>60 (old) | ±1d | 162 | 8 | 8 | -3.00 | -5.31 | 37.5 |
| LIQ EXIT RM<30 AND FM>60 (old) | ±3d | 162 | 8 | 8 | -3.00 | -5.31 | 37.5 |
| LIQ EXIT RM<30 AND FM>60 (old) | ±7d | 162 | 120 | 59 | -0.17 | -2.47 | 59.3 |

Two things stand out. Event-gating does not improve SQUEEZE — FM<10 ungated already carries the
edge and gating only costs sample. But the **old** LIQUIDITY EXIT cut (RM<30 and FM>60) is
genuinely bearish around events: 8 episodes, 12-week mean −3.00%, excess −5.31%, hit 37.5%. The
FM≥80-only placeholder you asked to ship is much weaker (excess −1.58%). So on the evidence, RM
earns its place in LIQUIDITY EXIT even though it does not in SQUEEZE.

## Point 4 — pre-2006 from 2003

Built. Legacy COT non-commercial S&P 500 net, 417 weekly prints, 2003-01-07 → 2010-12-28, cached beside the TFF files.

It is **not** a like-for-like FM series, and the overlap says so:

| Measure | Value |
|---|---|
| Overlap | 2006-06-13 → 2010-12-28 (238 weeks) |
| Level correlation | 0.6414 |
| Weekly-change correlation | 0.5716 |
| Percentile correlation | 0.5396 |
| Mean absolute percentile difference | 23.1 points |
| Agreement on FM<10 weeks | 22 of 47 (jaccard 0.47) |
| Means | legacy -2,961 vs TFF -43,191 contracts |

Roughly half the extreme weeks disagree, and the two series sit at different levels entirely.
Stitching it into the grids would move cells for reasons that have nothing to do with the market,
so it ships as labelled context (`legacy_noncommercial`), available if you want to eyeball
2003-2006, and the recommendation below stays on the TFF sample.

**On the GFC specifically:** the earlier reports said the rolling grids excluded Sep 2008 – May
2009. That was wrong, and the wording has been corrected. Percentile cells run continuously from
2006-10-24, and the 2008 episodes are in the grids — they are the largest
negatives in the LIQ EXIT cells. The genuine caveat is that 2008 ranks against a partial ~115-week
lookback rather than a full three years.

## Points 1 and 5 — the cut, and what is shipped

**SQUEEZE recommendation: FM < 10th percentile, no RM leg.** 35 episodes, 12-week mean 3.39% vs 2.31% unconditional, excess +1.09%, hit 77.1%. FM<5 alone is *worse* (21 episodes, mean 2.27%, excess -0.04%), so tightening past 10 does not buy sharpness, it only removes the middle of the distribution. FM<5 with RM>55 shows mean 5.78% on 6 episodes, which is too thin to act on.

**Shipped as unvalidated display placeholders:** squeeze fm_pctile_max 10; liquidity exit fm_pctile_min 80. Squeeze fires on FM<10
with no RM condition, liquidity exit on FM≥80, both labelled unvalidated on the page and neither
touching sizing. Historical fire counts on the full sample: squeeze 169 weeks / 35 episodes (was
181 / 37 under FM<20 and RM>45); liquidity exit 214 weeks / 36 episodes (was 162 / 40 under RM<30
and FM>60).

**One thing to reconsider:** the event-gated table above says the RM leg matters for LIQUIDITY
EXIT even though it does not for SQUEEZE. Say the word and I will put RM<30 back on that flag only.

## Point 6 — reminder

This is the reminder. The results above are the ones you asked me to bring back to you; the open
decisions are the LIQUIDITY EXIT RM leg, and whether you want the legacy 2003 series shown
anywhere given how loosely it tracks.
