# Point-in-time S&P 500 BQ replay — results

Scored 20,099 name-dates across 67 quarter-ends (2010-03-31 to 2026-09-30). Coverage of index members: 24% on the first date, 93% on the last; missing names are mostly companies later acquired or delisted, so results flatter weak names.

## BQ distribution (share of scored members)

| Date | BQ < 0 | 0 ≤ BQ < 5 | BQ ≥ 5 | scored |
|---|---:|---:|---:|---:|
| latest (2026-09-30) | 15% | 57% | 28% | 470 |
| 2011 (euro crisis) (2011-09-30) | 10% | 66% | 24% | 157 |
| 2015-16 (oil / China) (2016-03-31) | 21% | 65% | 14% | 216 |
| 2018 Q4 (2018-12-31) | 18% | 58% | 23% | 255 |
| 2020 (COVID) (2020-03-31) | 21% | 58% | 21% | 393 |
| 2022 (2022-09-30) | 13% | 52% | 35% | 427 |

## Forward excess return vs S&P 500 by BQ bucket

| bq_bucket | rows | dates | excess_3m_mean | excess_3m_median | beat_spx_3m | excess_6m_mean | excess_6m_median | beat_spx_6m | excess_12m_mean | excess_12m_median | beat_spx_12m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 ≤ BQ < 5 | 11083 | 67 | -0.16% | -0.79% | 47% | -0.42% | -1.38% | 47% | -0.23% | -1.96% | 47% |
| BQ < 0 | 4041 | 67 | -0.08% | -0.78% | 47% | -0.21% | -1.15% | 47% | +0.52% | -2.72% | 45% |
| BQ ≥ 5 | 4975 | 67 | +0.20% | +0.05% | 50% | +0.32% | -0.23% | 49% | +0.95% | -1.05% | 48% |

## Bear-market troughs only (5 dates: 2011-09-30, 2016-03-31, 2018-12-31, 2020-03-31, 2022-09-30)

| bq_bucket | rows | dates | excess_3m_mean | excess_3m_median | beat_spx_3m | excess_6m_mean | excess_6m_median | beat_spx_6m | excess_12m_mean | excess_12m_median | beat_spx_12m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 ≤ BQ < 5 | 845 | 5 | +1.90% | +0.98% | 53% | +0.36% | -0.85% | 48% | +3.85% | -1.33% | 48% |
| BQ < 0 | 245 | 5 | +1.71% | +1.27% | 56% | -0.83% | -0.73% | 49% | +6.53% | +1.16% | 53% |
| BQ ≥ 5 | 358 | 5 | +3.09% | +3.49% | 62% | +4.43% | +4.80% | 57% | +4.44% | +0.14% | 50% |

## By sell-ladder label (names a quant SELL would hit; conviction < +2)

| sell_label | rows | dates | excess_3m_mean | excess_3m_median | beat_spx_3m | excess_6m_mean | excess_6m_median | beat_spx_6m | excess_12m_mean | excess_12m_median | beat_spx_12m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| COVERAGE INCOMPLETE | 2610 | 67 | -0.38% | -1.34% | 44% | -0.83% | -1.13% | 47% | -0.97% | -1.64% | 46% |
| FULL EXIT | 6955 | 67 | -0.42% | -0.96% | 47% | -0.98% | -1.89% | 45% | -1.15% | -2.80% | 45% |
| HARD EXIT | 2942 | 67 | -0.11% | -0.63% | 48% | -0.11% | -1.31% | 47% | +0.84% | -3.25% | 44% |
| PARTIAL EXIT | 1536 | 65 | -0.51% | -0.75% | 48% | -1.08% | -1.44% | 47% | -3.47% | -4.54% | 42% |

## HARD EXIT vs FULL EXIT (date-level)

| Horizon | HARD − FULL mean excess | SE | t | dates |
|---|---:|---:|---:|---:|
| 3m | +0.30% | 0.38% | +0.81 | 66 |
| 6m | +0.66% | 0.57% | +1.16 | 65 |
| 12m | +0.31% | 1.04% | +0.30 | 63 |

**Recommendation:** Merge HARD and FULL EXIT: the replay shows no consistent, significant difference between them.

## Sell-ladder cut points (CE-30)

Names with conviction below +2 only. For each candidate BQ cut: mean 12-month excess of names below the cut minus names at or above it, averaged across dates.

| BQ cut | below − above (12m) | SE | t | dates |
|---:|---:|---:|---:|---:|
| -4 | +3.61% | 1.85% | +1.95 | 63 |
| -3 | +1.42% | 1.08% | +1.31 | 63 |
| -2 | -0.21% | 0.71% | -0.29 | 63 |
| -1 | +1.31% | 1.04% | +1.26 | 63 |
| 0 | +0.22% | 0.89% | +0.25 | 63 |
| 1 | +0.02% | 0.82% | +0.02 | 63 |
| 2 | -0.41% | 0.87% | -0.47 | 63 |
| 3 | +0.21% | 1.32% | +0.16 | 63 |
| 4 | -2.03% | 1.41% | -1.44 | 63 |
| 5 | -0.30% | 1.50% | -0.20 | 61 |
| 6 | -0.65% | 1.88% | -0.35 | 56 |
| 7 | +3.97% | 2.31% | +1.72 | 54 |
| 8 | +4.51% | 3.46% | +1.30 | 51 |

Strongest separation at BQ < 4 (t = -1.44). Current cuts: quality collapse below 0, valuation stretch at +5 and above. A cut is worth keeping only where its t-stat is clearly negative (names below it really do worse).

## What is neutral by construction

- Insider ownership, the five agentic dimensions, the P/E-percentile part of the valuation tax and the dividend-cut penalty score 0 (not replayable point-in-time, or switched off live).
- Forward revenue is trailing revenue; business type is today's store type where held, else the SEC SIC code.
- Rows at the same date overlap at 6 and 12 months; the HARD vs FULL test is done across dates for that reason.
