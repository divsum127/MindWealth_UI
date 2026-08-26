# CFTC SQUEEZE / LIQUIDITY EXIT — Rohit re-run (Aug 2026 spec)

Generated: 20260825

## Worked examples — why mean−median gap, not Sharpe or hit rate alone

**Example A (tail-driven squeeze is real):** +22%, +18%, +14%, +3%, +2%, +1%, −1%, −2%, −4%

- mean **5.8889%**, median **2.0%**, gap **3.8889%**, hit **66.67%**, worst **-4.0%**

**Example B (nothing there — market beta):** +6%, +5%, +4%, +3%, +3%, +2%, +1%, −1%, −2%

- mean **2.3333%**, median **3.0%**, gap **-0.6667%**, hit **77.78%**, worst **-2.0%**

B has higher hit rate and better worst case. Only the gap and dated top instances reveal A's tail edge.

## Data coverage

- CFTC TFF S&P 500, restated into emini_equivalent units (component contract lines at notional weight - E-mini 1.0, big 5.0, micro 0.1 - so CFTC's 2023-05-02 redefinition of the Consolidated line no longer puts a 5x seam mid-sample); raw 2006-06-13 to 2026-08-18 (1054 weekly prints); first full 156w window 2009-06-02; analysis weeks 899 (2009-06-02 to 2026-08-18); unit breaks detected: none.
- FM net distribution (fixed, full sample): `{'p2_5': -721368.35, 'p5': -647746.85, 'p10': -576668.6, 'min': -901710.0, 'max': 223837.0, 'median': -325511.9, 'n': 1054}`
- **Sample start — one number, everywhere:**
  - Raw TFF weekly prints from **2006-06-13** to **2026-08-18** (**1054** weeks).
  - First **full 156-week** window closes **2009-06-02**, and that *is* the analysis start — partial windows are no longer ranked, so there is no second, looser start date to quote. Analysis: **899** weeks (2009-06-02 → 2026-08-18).
  - **Units:** `emini_equivalent`. CFTC redefined the S&P 500 Consolidated line on 2023-05-02 (big-contract equivalents with micro excluded → E-mini equivalents with micro included), which put a ~5x seam mid-sample in every earlier version of this report. The series is now summed from the component contract lines at notional weight, so it is continuous by construction.
  - **Unit-break scan:** **none** — no week where every field scales by a common factor.
  - **GFC 2008:** **not** in the percentile grids. The first rankable week is **2009-06-02**, after the crash. Earlier statements that the GFC was included came from ranking partial windows from 20 observations; those ranks were labelled 3-year percentiles but were not. Including 2008 needs a shorter window, an explicitly accepted partial window, or the legacy proxy — a decision, not a code change.
  - **Pre-2006:** TFF Leveraged Money starts 2006-06-13, so there is nothing to rebuild from 2003 in this definition. The legacy COT non-commercial series is built and cached, but the 2006–2010 overlap (level corr 0.64, pctile corr 0.54, ~half of FM<10 weeks disagree) says it is not a like-for-like FM substitute — kept as labelled context, not stitched in.

## Executive summary — read this before the grids

- **FM percentile has no linear relationship with SPX forward returns.** R² tops out at **0.002989** across 4 horizons, with p-values as weak as **0.64**; nothing is significant at any horizon. That does not rule out a threshold effect in the tail — a linear fit would not show one — but it does settle the row 42 question: at that R², whether Layer 3 applies `invert=True` to `cot_fast_money` is immaterial either way.
- **Rank cells on excess-hit, not on the mean−median gap alone.** Both orderings are published below; where they disagree, the excess-hit table is the one to act on, and any cell below the PAR excess-hit is marked as such.
- **Any cell worth recommending carries a pre/post 2023-05-02 split** (see the seam-stability section). A cell that only works on one side of that date does not work.

## §6a PAR row (unconditional — every week in sample, no episode collapse)

Excess = SPX forward return minus mean SPX return across **all** weeks at that horizon.
excess_hit = share of observations that **beat the market** (excess > 0), not merely positive SPX.

- **4w** (bench 1.101533015715058%): n_wk=895 | mean=1.1015% med=1.569% | mean_excess=0.0% med_excess=0.4675% | hit=68.94% excess_hit=56.87%
- **8w** (bench 2.114854068983407%): n_wk=891 | mean=2.1149% med=2.6184% | mean_excess=0.0% med_excess=0.5035% | hit=72.73% excess_hit=54.1%
- **12w** (bench 3.1104724182402177%): n_wk=887 | mean=3.1105% med=3.8267% | mean_excess=-0.0% med_excess=0.7162% | hit=75.65% excess_hit=56.82%
- **6m** (bench 6.426804344829674%): n_wk=873 | mean=6.4268% med=7.0634% | mean_excess=-0.0% med_excess=0.6366% | hit=79.73% excess_hit=54.07%
- **12m** (bench 12.95799209482281%): n_wk=847 | mean=12.958% med=13.8926% | mean_excess=0.0% med_excess=0.9346% | hit=86.89% excess_hit=53.48%

## SQUEEZE — top cells by mean−median gap at 12w (rank metric; read with dated instances)

| FM < | RM > | n_wk | n_ep | mean % | median % | gap % | hit % | mean_ex % | med_ex % | ex_hit % | best_for_signal % | worst_for_signal % | top instances (date ret) |
|----|----|----|----|------|--------|-----|-----|---------|--------|--------|-----------------|------------------|------------------------|
| 5 | 45 | 11 | 5 | 5.3648 | 4.8651 | 0.4998 | 100.0 | 2.2544 | 1.7546 | 100.0 | 8.4371 | 3.2921 | 2023-04-18 +8.4371%; 2019-11-05 +5.6690%; 2023-05-30 +4.0611% |
| 5 | 50 | 10 | 4 | 6.0557 | 5.669 | 0.3867 | 100.0 | 2.9453 | 2.5585 | 100.0 | 8.4371 | 4.0611 | 2023-04-18 +8.4371%; 2019-11-05 +5.6690%; 2023-05-30 +4.0611% |
| 5 | 40 | 12 | 5 | 5.0201 | 4.8651 | 0.155 | 100.0 | 1.9096 | 1.7546 | 100.0 | 7.058 | 3.2921 | 2023-04-11 +7.0580%; 2019-11-05 +5.6690%; 2023-05-30 +4.0611% |

## SQUEEZE — all rolling cells by mean−median gap at 12w (reference)

| FM < | RM > | n_wk | n_ep | mean % | median % | gap % | hit % | mean_ex % | med_ex % | ex_hit % | best_for_signal % | worst_for_signal % |
|----|----|----|----|------|--------|-----|-----|---------|--------|--------|-----------------|------------------|
| 5 | 45 | 11 | 5 | 5.3648 | 4.8651 | 0.4998 | 100.0 | 2.2544 | 1.7546 | 100.0 | 8.4371 | 3.2921 |
| 5 | 50 | 10 | 4 | 6.0557 | 5.669 | 0.3867 | 100.0 | 2.9453 | 2.5585 | 100.0 | 8.4371 | 4.0611 |
| 5 | 40 | 12 | 5 | 5.0201 | 4.8651 | 0.155 | 100.0 | 1.9096 | 1.7546 | 100.0 | 7.058 | 3.2921 |
| 12.5 | 50 | 26 | 11 | 3.5686 | 3.6058 | -0.0372 | 90.91 | 0.4582 | 0.4953 | 72.73 | 11.2305 | -14.1928 |
| 30 | 45 | 120 | 31 | 3.1457 | 3.2921 | -0.1464 | 80.65 | 0.0352 | 0.1816 | 54.84 | 12.3439 | -15.0261 |
| 30 | 40 | 122 | 31 | 3.1012 | 3.2921 | -0.1909 | 80.65 | -0.0093 | 0.1816 | 54.84 | 12.3439 | -15.0261 |
| 30 | 60 | 93 | 29 | 2.7562 | 3.0904 | -0.3342 | 79.31 | -0.3542 | -0.0201 | 48.28 | 12.3439 | -15.0261 |
| 30 | 65 | 82 | 27 | 2.6501 | 3.0647 | -0.4146 | 77.78 | -0.4604 | -0.0458 | 48.15 | 12.3439 | -15.0261 |
| 10 | 60 | 14 | 7 | 1.4696 | 2.1428 | -0.6732 | 85.71 | -1.6409 | -0.9677 | 42.86 | 8.7829 | -14.1928 |
| 12.5 | 45 | 32 | 12 | 2.4182 | 3.2199 | -0.8017 | 83.33 | -0.6922 | 0.1094 | 58.33 | 8.7829 | -14.1928 |
| 30 | 50 | 111 | 30 | 3.3384 | 4.1483 | -0.8099 | 80.0 | 0.2279 | 1.0379 | 60.0 | 12.3439 | -15.0261 |
| 25 | 45 | 96 | 30 | 2.945 | 3.8183 | -0.8733 | 83.33 | -0.1654 | 0.7079 | 56.67 | 10.7851 | -15.0261 |
| 12.5 | 40 | 33 | 12 | 2.3033 | 3.2199 | -0.9166 | 83.33 | -0.8072 | 0.1094 | 58.33 | 8.7829 | -14.1928 |
| 25 | 60 | 71 | 25 | 2.3986 | 3.3172 | -0.9186 | 80.0 | -0.7118 | 0.2067 | 52.0 | 10.7851 | -15.0261 |
| 25 | 40 | 98 | 30 | 2.8991 | 3.8183 | -0.9193 | 83.33 | -0.2114 | 0.7079 | 56.67 | 10.7851 | -15.0261 |
| 12.5 | 65 | 16 | 8 | 1.7212 | 2.6452 | -0.924 | 87.5 | -1.3892 | -0.4652 | 50.0 | 8.7829 | -14.1928 |
| 25 | 65 | 62 | 25 | 2.3165 | 3.3172 | -1.0007 | 80.0 | -0.794 | 0.2067 | 52.0 | 10.7851 | -15.0261 |
| 10 | 50 | 21 | 9 | 3.2241 | 4.2369 | -1.0128 | 88.89 | 0.1136 | 1.1264 | 66.67 | 8.7829 | -14.1928 |
| 10 | 45 | 25 | 9 | 3.1892 | 4.2369 | -1.0477 | 88.89 | 0.0787 | 1.1264 | 66.67 | 8.7829 | -14.1928 |
| 10 | 65 | 13 | 6 | 1.0084 | 2.084 | -1.0756 | 83.33 | -2.1021 | -1.0265 | 33.33 | 8.7829 | -14.1928 |

## SQUEEZE — tight FM rolling percentiles (Rohit §2)

| FM roll pct | RM>40 12w | RM>45 12w | RM>50 12w |
|-------------|-----------|-----------|-----------|
| <5 | n=5 gap=0.155 | n=5 gap=0.4998 | n=4 gap=0.3867 |
| <7.5 | n=7 gap=-1.8943 | n=7 gap=-1.6973 | n=7 gap=-1.6525 |
| <10 | n=9 gap=-1.2009 | n=9 gap=-1.0477 | n=9 gap=-1.0128 |
| <12.5 | n=12 gap=-0.9166 | n=12 gap=-0.8017 | n=11 gap=-0.0372 |
| <15 | n=19 gap=-2.3318 | n=19 gap=-2.2592 | n=19 gap=-2.0131 |
| <20 | n=24 gap=-1.2627 | n=24 gap=-1.2053 | n=24 gap=-1.0857 |

## SQUEEZE absolute cuts (Rohit §4)

- `FM_roll_pct<10 AND FM_net<0`: n_ep=18 (wk=78) | mean=3.7799% med=4.9529% gap=-1.1731% | hit=77.78% excess_hit=61.11% | mean_excess=0.6694% med_excess=1.8425% | best_for_signal=13.001% worst_for_signal=-14.1928%
- `FM_roll_pct<7.5 AND FM_net<0`: n_ep=19 (wk=62) | mean=3.5611% med=4.2369% gap=-0.6758% | hit=73.68% excess_hit=63.16% | mean_excess=0.4506% med_excess=1.1264% | best_for_signal=16.6906% worst_for_signal=-14.1928%
- `FM_roll_pct<5 AND FM_net<0`: n_ep=14 (wk=43) | mean=2.9953% med=3.6465% gap=-0.6512% | hit=69.23% excess_hit=61.54% | mean_excess=-0.1151% med_excess=0.536% | best_for_signal=16.6906% worst_for_signal=-10.9659%
- `FM_net<fixed_p2.5`: n_ep=3 (wk=4) | mean=5.2955% med=5.9005% gap=-0.605% | hit=66.67% excess_hit=66.67% | mean_excess=2.185% med_excess=2.79% | best_for_signal=14.2014% worst_for_signal=-4.2154%
- `FM_net<fixed_p5`: n_ep=8 (wk=21) | mean=4.4608% med=6.1576% gap=-1.6967% | hit=75.0% excess_hit=62.5% | mean_excess=1.3504% med_excess=3.0471% | best_for_signal=12.0471% worst_for_signal=-6.1409%
- `FM_net<fixed_p10`: n_ep=15 (wk=55) | mean=1.675% med=2.2554% gap=-0.5804% | hit=73.33% excess_hit=40.0% | mean_excess=-1.4355% med_excess=-0.8551% | best_for_signal=11.3486% worst_for_signal=-12.9293%
- `FM_net/open_interest <= p2.5 (-0.2156)`: n_ep=8 (wk=23) | mean=2.305% med=1.7416% gap=0.5635% | hit=75.0% excess_hit=37.5% | mean_excess=-0.8054% med_excess=-1.3689% | best_for_signal=8.7119% worst_for_signal=-6.3695%
- `FM_net/open_interest <= p5.0 (-0.2022)`: n_ep=13 (wk=45) | mean=2.8815% med=2.7254% gap=0.1561% | hit=84.62% excess_hit=46.15% | mean_excess=-0.229% med_excess=-0.3851% | best_for_signal=10.5667% worst_for_signal=-6.3695%
- `FM_net/open_interest <= p10.0 (-0.1754)`: n_ep=15 (wk=90) | mean=3.3169% med=3.89% gap=-0.5731% | hit=80.0% excess_hit=66.67% | mean_excess=0.2064% med_excess=0.7795% | best_for_signal=14.4014% worst_for_signal=-12.7874%

## LIQUIDITY EXIT — top cells by mean−median gap at 4w (short side)

`best_for_signal` / `worst_for_signal` are relative to the side the pattern trades. SQUEEZE is long, so best = highest forward return. LIQUIDITY EXIT is short, so best = *most negative* forward return. The two tables therefore order these columns in opposite directions on purpose.

| RM < | FM > | n_wk | n_ep | mean % | median % | gap % | hit % | mean_ex % | med_ex % | ex_hit % | best_for_signal % | worst_for_signal % |
|----|----|----|----|------|--------|-----|-----|---------|--------|--------|-----------------|------------------|
| 15 | 75 | 39 | 15 | 0.1337 | 1.4562 | -1.3225 | 40.0 | -0.9678 | 0.3547 | 46.67 | -10.5122 | 10.0495 |
| 40 | 70 | 134 | 37 | 0.4458 | 1.6926 | -1.2468 | 32.43 | -0.6557 | 0.5911 | 45.95 | -13.9437 | 6.1655 |
| 35 | 45 | 219 | 48 | 0.7447 | 1.9759 | -1.2312 | 35.42 | -0.3568 | 0.8743 | 39.58 | -10.7794 | 8.8998 |
| 30 | 45 | 198 | 48 | 0.1286 | 1.3 | -1.1714 | 39.58 | -0.9729 | 0.1985 | 47.92 | -10.7794 | 7.3993 |
| 35 | 70 | 116 | 33 | 0.4116 | 1.5739 | -1.1623 | 33.33 | -0.6899 | 0.4724 | 45.45 | -10.5122 | 6.1655 |
| 40 | 55 | 196 | 49 | 0.5307 | 1.6769 | -1.1462 | 36.73 | -0.5708 | 0.5754 | 44.9 | -13.9437 | 8.6265 |
| 25 | 45 | 178 | 49 | 0.2077 | 1.3512 | -1.1435 | 38.78 | -0.8939 | 0.2497 | 46.94 | -10.7794 | 7.3993 |
| 30 | 70 | 102 | 32 | -0.0077 | 1.1178 | -1.1255 | 34.38 | -1.1092 | 0.0163 | 50.0 | -10.5122 | 6.1655 |
| 40 | 45 | 244 | 51 | 0.6454 | 1.724 | -1.0786 | 37.25 | -0.4561 | 0.6225 | 39.22 | -13.9437 | 8.8998 |
| 15 | 45 | 101 | 30 | 0.3175 | 1.375 | -1.0576 | 43.33 | -0.7841 | 0.2735 | 46.67 | -10.7794 | 10.0495 |
| 35 | 60 | 155 | 42 | 1.069 | 2.1118 | -1.0428 | 26.19 | -0.0325 | 1.0103 | 38.1 | -10.7419 | 8.6265 |
| 35 | 55 | 174 | 46 | 0.5891 | 1.6254 | -1.0363 | 34.78 | -0.5125 | 0.5239 | 43.48 | -10.7794 | 8.6265 |
| 25 | 70 | 90 | 32 | 0.1045 | 1.1363 | -1.0318 | 34.38 | -0.997 | 0.0348 | 50.0 | -10.5122 | 6.4949 |
| 40 | 50 | 220 | 54 | 0.6623 | 1.6848 | -1.0225 | 38.89 | -0.4393 | 0.5832 | 44.44 | -13.9437 | 8.6265 |
| 40 | 75 | 108 | 36 | 1.0357 | 2.0449 | -1.0092 | 36.11 | -0.0659 | 0.9434 | 41.67 | -13.9437 | 10.0495 |

### LIQUIDITY EXIT — dated instances for the cells above

- `RM_roll_pct<15 AND FM_roll_pct>75`: 2022-04-12 -10.5122%; 2015-12-08 -5.8393%; 2022-04-26 -5.5978%; 2022-02-08 -5.3889%; 2016-01-12 -4.4783%; 2016-04-26 -0.7477%; 2014-12-16 +1.0103%; 2015-04-21 +1.4562%; 2018-10-30 +2.2799%
- `RM_roll_pct<40 AND FM_roll_pct>70`: 2022-04-12 -10.5122%; 2012-05-01 -6.5798%; 2015-12-08 -5.8393%; 2018-10-16 -3.1225%; 2015-06-02 -2.2037%; 2015-04-14 +0.1565%; 2013-11-05 +1.6926%; 2018-07-31 +2.8843%; 2021-11-30 +4.9499%
- `RM_roll_pct<35 AND FM_roll_pct>45`: 2022-04-12 -10.5122%; 2011-07-05 -6.2659%; 2012-04-17 -4.3228%; 2011-05-03 -3.1011%; 2012-03-13 -1.9514%; 2015-11-24 -1.1895%; 2012-04-03 -0.7832%; 2018-07-31 +2.8843%; 2021-11-30 +4.9499%
- `RM_roll_pct<30 AND FM_roll_pct>45`: 2022-04-12 -10.5122%; 2011-07-05 -6.2659%; 2012-04-17 -4.3228%; 2018-10-23 -3.6049%; 2011-05-03 -3.1011%; 2012-03-13 -1.9514%; 2015-11-24 -1.1895%; 2012-04-03 -0.7832%; 2021-12-07 +0.2951%
- `RM_roll_pct<35 AND FM_roll_pct>70`: 2022-04-12 -10.5122%; 2012-05-01 -6.5798%; 2015-12-08 -5.8393%; 2018-10-23 -3.6049%; 2015-06-02 -2.2037%; 2015-04-14 +0.1565%; 2015-05-12 +0.2896%; 2018-07-31 +2.8843%; 2021-11-30 +4.9499%
- `RM_roll_pct<40 AND FM_roll_pct>55`: 2022-04-12 -10.5122%; 2011-07-05 -6.2659%; 2012-04-17 -4.3228%; 2018-10-16 -3.1225%; 2011-05-03 -3.1011%; 2015-12-01 -1.8677%; 2012-04-03 -0.7832%; 2018-07-31 +2.8843%; 2021-11-30 +4.9499%
- `RM_roll_pct<25 AND FM_roll_pct>45`: 2015-07-28 -10.7794%; 2022-04-12 -10.5122%; 2011-07-05 -6.2659%; 2012-04-17 -4.3228%; 2018-10-23 -3.6049%; 2012-03-13 -1.9514%; 2015-11-24 -1.1895%; 2012-04-03 -0.7832%; 2021-12-14 +1.9909%
- `RM_roll_pct<30 AND FM_roll_pct>70`: 2022-04-12 -10.5122%; 2012-05-01 -6.5798%; 2015-12-08 -5.8393%; 2018-10-23 -3.6049%; 2015-06-02 -2.2037%; 2015-04-14 +0.1565%; 2015-05-12 +0.2896%; 2021-12-07 +0.2951%; 2014-11-04 +3.0928%
- `RM_roll_pct<40 AND FM_roll_pct>45`: 2022-04-12 -10.5122%; 2011-07-05 -6.2659%; 2012-04-17 -4.3228%; 2018-10-16 -3.1225%; 2011-05-03 -3.1011%; 2012-03-13 -1.9514%; 2015-11-24 -1.1895%; 2012-04-03 -0.7832%; 2018-07-31 +2.8843%
- `RM_roll_pct<15 AND FM_roll_pct>45`: 2015-07-28 -10.7794%; 2022-04-12 -10.5122%; 2010-05-11 -8.6608%; 2011-07-05 -6.2659%; 2022-02-08 -5.3889%; 2015-08-18 -4.8457%; 2015-06-02 -2.2037%; 2015-11-24 -1.1895%; 2018-10-30 +2.2799%
- `RM_roll_pct<35 AND FM_roll_pct>60`: 2011-07-12 -10.7419%; 2022-04-12 -10.5122%; 2012-05-01 -6.5798%; 2018-10-23 -3.6049%; 2015-12-01 -1.8677%; 2012-04-03 -0.7832%; 2018-07-31 +2.8843%; 2012-02-28 +2.9398%; 2021-11-30 +4.9499%
- `RM_roll_pct<35 AND FM_roll_pct>55`: 2022-04-12 -10.5122%; 2011-07-05 -6.2659%; 2012-04-17 -4.3228%; 2018-10-23 -3.6049%; 2011-05-03 -3.1011%; 2015-12-01 -1.8677%; 2012-04-03 -0.7832%; 2018-07-31 +2.8843%; 2021-11-30 +4.9499%
- `RM_roll_pct<25 AND FM_roll_pct>70`: 2022-04-12 -10.5122%; 2012-05-01 -6.5798%; 2015-12-08 -5.8393%; 2018-10-23 -3.6049%; 2015-06-02 -2.2037%; 2015-04-14 +0.1565%; 2015-05-12 +0.2896%; 2021-12-14 +1.9909%; 2014-11-04 +3.0928%
- `RM_roll_pct<40 AND FM_roll_pct>50`: 2022-04-12 -10.5122%; 2011-07-05 -6.2659%; 2012-04-17 -4.3228%; 2018-10-16 -3.1225%; 2011-05-03 -3.1011%; 2012-03-13 -1.9514%; 2015-11-24 -1.1895%; 2012-04-03 -0.7832%; 2018-07-31 +2.8843%
- `RM_roll_pct<40 AND FM_roll_pct>75`: 2022-04-12 -10.5122%; 2015-12-08 -5.8393%; 2022-04-26 -5.5978%; 2018-10-16 -3.1225%; 2015-05-19 -1.2872%; 2013-11-05 +1.6926%; 2018-08-14 +1.7240%; 2018-07-31 +2.8843%; 2021-11-30 +4.9499%

## LIQUIDITY EXIT — FM>70 vs FM>75 episode dates (Rohit §7)

### RM<20 FM>70 (n_ep=25)
- 2022-04-12: 4w=-10.5122% excess_4w=-11.6138% 8w=-8.633% 12w=-12.3485%
- 2021-12-14: 4w=1.9909% excess_4w=0.8894% 8w=-2.8055% 12w=-9.2743%
- 2022-02-08: 4w=-5.3889% excess_4w=-6.4904% 8w=-0.8933% 12w=-8.2863%
- 2015-06-02: 4w=-2.2037% excess_4w=-3.3053% 8w=-0.0488% 12w=-8.0153%
- 2018-10-23: 4w=-3.6049% excess_4w=-4.7065% 8w=-9.9708% 12w=-3.933%
- 2012-05-01: 4w=-6.5798% excess_4w=-7.6813% 8w=-5.2617% 12w=-3.2579%
- 2015-12-08: 4w=-5.8393% excess_4w=-6.9409% 8w=-8.8942% 12w=-2.9962%
- 2015-04-14: 4w=0.1565% excess_4w=-0.945% 8w=0.4466% 12w=-2.1247%
- 2015-05-12: 4w=0.2896% excess_4w=-0.8119% 8w=-2.2776% 12w=-0.7413%
### RM<20 FM>75 (n_ep=21)
- 2022-04-12: 4w=-10.5122% excess_4w=-11.6138% 8w=-8.633% 12w=-12.3485%
- 2021-12-14: 4w=1.9909% excess_4w=0.8894% 8w=-2.8055% 12w=-9.2743%
- 2022-02-08: 4w=-5.3889% excess_4w=-6.4904% 8w=-0.8933% 12w=-8.2863%
- 2022-04-26: 4w=-5.5978% excess_4w=-6.6994% 8w=-9.0887% 12w=-5.1152%
- 2018-10-23: 4w=-3.6049% excess_4w=-4.7065% 8w=-9.9708% 12w=-3.933%
- 2015-12-08: 4w=-5.8393% excess_4w=-6.9409% 8w=-8.8942% 12w=-2.9962%
- 2014-11-04: 4w=3.0928% excess_4w=1.9913% 8w=2.2911% 12w=0.4349%
- 2015-04-21: 4w=1.4562% excess_4w=0.3546% 8w=0.1502% 12w=1.2874%
- 2015-02-03: 4w=2.3658% excess_4w=1.2643% 8w=0.4712% 12w=1.7307%
### RM<25 FM>70 (n_ep=32)
- 2022-04-12: 4w=-10.5122% excess_4w=-11.6138% 8w=-8.633% 12w=-12.3485%
- 2021-12-14: 4w=1.9909% excess_4w=0.8894% 8w=-2.8055% 12w=-9.2743%
- 2015-06-02: 4w=-2.2037% excess_4w=-3.3053% 8w=-0.0488% 12w=-8.0153%
- 2018-10-23: 4w=-3.6049% excess_4w=-4.7065% 8w=-9.9708% 12w=-3.933%
- 2012-05-01: 4w=-6.5798% excess_4w=-7.6813% 8w=-5.2617% 12w=-3.2579%
- 2015-12-08: 4w=-5.8393% excess_4w=-6.9409% 8w=-8.8942% 12w=-2.9962%
- 2015-04-14: 4w=0.1565% excess_4w=-0.945% 8w=0.4466% 12w=-2.1247%
- 2015-05-12: 4w=0.2896% excess_4w=-0.8119% 8w=-2.2776% 12w=-0.7413%
- 2014-11-04: 4w=3.0928% excess_4w=1.9913% 8w=2.2911% 12w=0.4349%
### RM<25 FM>75 (n_ep=28)
- 2022-04-12: 4w=-10.5122% excess_4w=-11.6138% 8w=-8.633% 12w=-12.3485%
- 2021-12-14: 4w=1.9909% excess_4w=0.8894% 8w=-2.8055% 12w=-9.2743%
- 2022-04-26: 4w=-5.5978% excess_4w=-6.6994% 8w=-9.0887% 12w=-5.1152%
- 2018-10-23: 4w=-3.6049% excess_4w=-4.7065% 8w=-9.9708% 12w=-3.933%
- 2015-12-08: 4w=-5.8393% excess_4w=-6.9409% 8w=-8.8942% 12w=-2.9962%
- 2015-05-19: 4w=-1.2872% excess_4w=-2.3888% 8w=-0.1664% 12w=-2.0885%
- 2014-11-04: 4w=3.0928% excess_4w=1.9913% 8w=2.2911% 12w=0.4349%
- 2022-01-25: 4w=-3.0059% excess_4w=-4.1074% 8w=2.2906% 12w=0.8541%
- 2015-04-21: 4w=1.4562% excess_4w=0.3546% 8w=0.1502% 12w=1.2874%
### RM<30 FM>70 (n_ep=32)
- 2022-04-12: 4w=-10.5122% excess_4w=-11.6138% 8w=-8.633% 12w=-12.3485%
- 2015-06-02: 4w=-2.2037% excess_4w=-3.3053% 8w=-0.0488% 12w=-8.0153%
- 2021-12-07: 4w=0.2951% excess_4w=-0.8064% 8w=-4.466% 12w=-7.636%
- 2018-10-23: 4w=-3.6049% excess_4w=-4.7065% 8w=-9.9708% 12w=-3.933%
- 2012-05-01: 4w=-6.5798% excess_4w=-7.6813% 8w=-5.2617% 12w=-3.2579%
- 2015-12-08: 4w=-5.8393% excess_4w=-6.9409% 8w=-8.8942% 12w=-2.9962%
- 2015-04-14: 4w=0.1565% excess_4w=-0.945% 8w=0.4466% 12w=-2.1247%
- 2015-05-12: 4w=0.2896% excess_4w=-0.8119% 8w=-2.2776% 12w=-0.7413%
- 2014-11-04: 4w=3.0928% excess_4w=1.9913% 8w=2.2911% 12w=0.4349%
### RM<30 FM>75 (n_ep=29)
- 2022-04-12: 4w=-10.5122% excess_4w=-11.6138% 8w=-8.633% 12w=-12.3485%
- 2021-12-07: 4w=0.2951% excess_4w=-0.8064% 8w=-4.466% 12w=-7.636%
- 2022-04-26: 4w=-5.5978% excess_4w=-6.6994% 8w=-9.0887% 12w=-5.1152%
- 2018-10-23: 4w=-3.6049% excess_4w=-4.7065% 8w=-9.9708% 12w=-3.933%
- 2015-12-08: 4w=-5.8393% excess_4w=-6.9409% 8w=-8.8942% 12w=-2.9962%
- 2015-05-19: 4w=-1.2872% excess_4w=-2.3888% 8w=-0.1664% 12w=-2.0885%
- 2014-11-04: 4w=3.0928% excess_4w=1.9913% 8w=2.2911% 12w=0.4349%
- 2022-01-25: 4w=-3.0059% excess_4w=-4.1074% 8w=2.2906% 12w=0.8541%
- 2015-04-21: 4w=1.4562% excess_4w=0.3546% 8w=0.1502% 12w=1.2874%

## FM percentile → SPX linear regression (continuous contrarian check)

| Horizon | n | R² | p-value | slope |
|---------|---|-----|---------|-------|
| 1w | 891 | 0.000372 | 0.565435 | -0.001417 |
| 2w | 891 | 0.000287 | 0.613837 | -0.001731 |
| 4w | 891 | 0.000249 | 0.638088 | 0.002175 |
| 8w | 891 | 0.002989 | 0.102946 | 0.010278 |

## PRIMARY robustness — 12-offset subsample stability (FM<7.5 focus)

Every 12th week × 12 offsets; see full tables in `cftc_robustness_subsample_*.md`.

### `FM_roll_pct<7.5 AND RM_roll_pct>45`

**Full sample (12w):** n_ep=7 | mean_excess=-0.5709% | hit_excess=71.43% | offsets_positive=7/9 | stable=False

Offsets carry a median of **2** episodes (min 0). **At that size the offset agreement is arithmetic, not evidence** — twelve subsamples of two or three episodes will agree on sign often enough by chance, so `stable` is withheld here regardless of how the signs fall.

| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |
|--------|------|--------|---------------|-------|--------------|
| 0 | 2 | 2.0252 | -1.0853 | 100.0 | 0.0 |
| 1 | 1 | None | None | None | None |
| 2 | 0 | None | None | None | None |
| 3 | 0 | None | None | None | None |
| 4 | 2 | 7.053 | 3.9426 | 100.0 | 100.0 |
| 5 | 1 | 8.4173 | 5.3068 | 100.0 | 100.0 |
| 6 | 2 | -3.0884 | -6.1989 | 50.0 | 50.0 |
| 7 | 2 | 4.16 | 1.0495 | 50.0 | 50.0 |
| 8 | 2 | 5.9546 | 2.8441 | 100.0 | 100.0 |
| 9 | 2 | 5.4008 | 2.2903 | 100.0 | 100.0 |
| 10 | 4 | 3.3817 | 0.2713 | 100.0 | 75.0 |
| 11 | 2 | 5.2245 | 2.114 | 100.0 | 100.0 |

Offset mean-excess spread: **11.5057%**
### `FM_roll_pct<7.5 AND RM_roll_pct>40`

**Full sample (12w):** n_ep=7 | mean_excess=-0.7679% | hit_excess=71.43% | offsets_positive=8/10 | stable=False

Offsets carry a median of **2** episodes (min 0). **At that size the offset agreement is arithmetic, not evidence** — twelve subsamples of two or three episodes will agree on sign often enough by chance, so `stable` is withheld here regardless of how the signs fall.

| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |
|--------|------|--------|---------------|-------|--------------|
| 0 | 2 | 2.0252 | -1.0853 | 100.0 | 0.0 |
| 1 | 1 | None | None | None | None |
| 2 | 0 | None | None | None | None |
| 3 | 1 | 7.058 | 3.9475 | 100.0 | 100.0 |
| 4 | 2 | 7.053 | 3.9426 | 100.0 | 100.0 |
| 5 | 1 | 8.4173 | 5.3068 | 100.0 | 100.0 |
| 6 | 2 | -3.0884 | -6.1989 | 50.0 | 50.0 |
| 7 | 2 | 4.16 | 1.0495 | 50.0 | 50.0 |
| 8 | 2 | 5.9546 | 2.8441 | 100.0 | 100.0 |
| 9 | 2 | 5.4008 | 2.2903 | 100.0 | 100.0 |
| 10 | 4 | 3.3817 | 0.2713 | 100.0 | 75.0 |
| 11 | 2 | 5.2245 | 2.114 | 100.0 | 100.0 |

Offset mean-excess spread: **11.5057%**
### `FM_roll_pct<7.5 AND FM_net<0`

**Full sample (12w):** n_ep=19 | mean_excess=0.4506% | hit_excess=63.16% | offsets_positive=2/12 | stable=False

Offsets carry a median of **4** episodes (min 3). **At that size the offset agreement is arithmetic, not evidence** — twelve subsamples of two or three episodes will agree on sign often enough by chance, so `stable` is withheld here regardless of how the signs fall.

| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |
|--------|------|--------|---------------|-------|--------------|
| 0 | 7 | 0.6313 | -2.4792 | 50.0 | 33.33 |
| 1 | 3 | -0.9638 | -4.0743 | 50.0 | 50.0 |
| 2 | 4 | 2.768 | -0.3425 | 75.0 | 50.0 |
| 3 | 4 | 2.9434 | -0.1671 | 75.0 | 75.0 |
| 4 | 4 | 3.0616 | -0.0489 | 75.0 | 75.0 |
| 5 | 3 | 0.8637 | -2.2468 | 66.67 | 66.67 |
| 6 | 4 | -1.6616 | -4.7721 | 50.0 | 50.0 |
| 7 | 7 | 4.0066 | 0.8961 | 57.14 | 42.86 |
| 8 | 7 | 6.1743 | 3.0638 | 85.71 | 85.71 |
| 9 | 6 | 2.0023 | -1.1082 | 66.67 | 50.0 |
| 10 | 8 | 2.5299 | -0.5806 | 75.0 | 62.5 |
| 11 | 5 | 1.4664 | -1.644 | 50.0 | 50.0 |

Offset mean-excess spread: **7.8359%**
### `FM_roll_pct<5 AND RM_roll_pct>45`

**Full sample (12w):** n_ep=5 | mean_excess=2.2544% | hit_excess=100.0% | offsets_positive=6/7 | stable=False

Offsets carry a median of **1** episodes (min 0). **At that size the offset agreement is arithmetic, not evidence** — twelve subsamples of two or three episodes will agree on sign often enough by chance, so `stable` is withheld here regardless of how the signs fall.

| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |
|--------|------|--------|---------------|-------|--------------|
| 0 | 1 | None | None | None | None |
| 1 | 1 | None | None | None | None |
| 2 | 0 | None | None | None | None |
| 3 | 0 | None | None | None | None |
| 4 | 2 | 7.053 | 3.9426 | 100.0 | 100.0 |
| 5 | 1 | 8.4173 | 5.3068 | 100.0 | 100.0 |
| 6 | 1 | 8.0159 | 4.9054 | 100.0 | 100.0 |
| 7 | 1 | -0.392 | -3.5025 | 0.0 | 0.0 |
| 8 | 1 | 3.2921 | 0.1816 | 100.0 | 100.0 |
| 9 | 0 | None | None | None | None |
| 10 | 1 | 4.0611 | 0.9506 | 100.0 | 100.0 |
| 11 | 2 | 5.2245 | 2.114 | 100.0 | 100.0 |

Offset mean-excess spread: **8.8093%**
### `FM_roll_pct<5 AND RM_roll_pct>40`

**Full sample (12w):** n_ep=5 | mean_excess=1.9096% | hit_excess=100.0% | offsets_positive=7/8 | stable=False

Offsets carry a median of **1** episodes (min 0). **At that size the offset agreement is arithmetic, not evidence** — twelve subsamples of two or three episodes will agree on sign often enough by chance, so `stable` is withheld here regardless of how the signs fall.

| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |
|--------|------|--------|---------------|-------|--------------|
| 0 | 1 | None | None | None | None |
| 1 | 1 | None | None | None | None |
| 2 | 0 | None | None | None | None |
| 3 | 1 | 7.058 | 3.9475 | 100.0 | 100.0 |
| 4 | 2 | 7.053 | 3.9426 | 100.0 | 100.0 |
| 5 | 1 | 8.4173 | 5.3068 | 100.0 | 100.0 |
| 6 | 1 | 8.0159 | 4.9054 | 100.0 | 100.0 |
| 7 | 1 | -0.392 | -3.5025 | 0.0 | 0.0 |
| 8 | 1 | 3.2921 | 0.1816 | 100.0 | 100.0 |
| 9 | 0 | None | None | None | None |
| 10 | 1 | 4.0611 | 0.9506 | 100.0 | 100.0 |
| 11 | 2 | 5.2245 | 2.114 | 100.0 | 100.0 |

Offset mean-excess spread: **8.8093%**
### `FM_roll_pct<5 AND RM_roll_pct>50`

**Full sample (12w):** n_ep=4 | mean_excess=2.9453% | hit_excess=100.0% | offsets_positive=5/6 | stable=False

Offsets carry a median of **1** episodes (min 0). **At that size the offset agreement is arithmetic, not evidence** — twelve subsamples of two or three episodes will agree on sign often enough by chance, so `stable` is withheld here regardless of how the signs fall.

| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |
|--------|------|--------|---------------|-------|--------------|
| 0 | 1 | None | None | None | None |
| 1 | 1 | None | None | None | None |
| 2 | 0 | None | None | None | None |
| 3 | 0 | None | None | None | None |
| 4 | 2 | 7.053 | 3.9426 | 100.0 | 100.0 |
| 5 | 1 | 8.4173 | 5.3068 | 100.0 | 100.0 |
| 6 | 1 | 8.0159 | 4.9054 | 100.0 | 100.0 |
| 7 | 1 | -0.392 | -3.5025 | 0.0 | 0.0 |
| 8 | 0 | None | None | None | None |
| 9 | 0 | None | None | None | None |
| 10 | 1 | 4.0611 | 0.9506 | 100.0 | 100.0 |
| 11 | 2 | 5.2245 | 2.114 | 100.0 | 100.0 |

Offset mean-excess spread: **8.8093%**
### `FM_roll_pct<40 AND RM_roll_pct>50`

**Full sample (12w):** n_ep=28 | mean_excess=0.3318% | hit_excess=75.0% | offsets_positive=3/12 | stable=False

Offsets carry a median of **13** episodes (min 11). That is enough for the agreement across offsets to mean something.

| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |
|--------|------|--------|---------------|-------|--------------|
| 0 | 13 | -0.5258 | -3.6362 | 66.67 | 41.67 |
| 1 | 11 | -0.9446 | -4.055 | 50.0 | 30.0 |
| 2 | 12 | 1.783 | -1.3275 | 54.55 | 45.45 |
| 3 | 13 | 1.1076 | -2.0028 | 58.33 | 50.0 |
| 4 | 15 | 1.288 | -1.8224 | 64.29 | 50.0 |
| 5 | 14 | 3.0259 | -0.0846 | 76.92 | 53.85 |
| 6 | 16 | 4.179 | 1.0685 | 87.5 | 75.0 |
| 7 | 14 | 2.6105 | -0.4999 | 78.57 | 71.43 |
| 8 | 13 | 3.8429 | 0.7324 | 84.62 | 61.54 |
| 9 | 15 | 2.5623 | -0.5482 | 86.67 | 53.33 |
| 10 | 16 | 4.3982 | 1.2878 | 93.75 | 56.25 |
| 11 | 12 | -0.2053 | -3.3158 | 72.73 | 45.45 |

Offset mean-excess spread: **5.3428%**
### `FM_roll_pct<12.5 AND RM_roll_pct>50`

**Full sample (12w):** n_ep=11 | mean_excess=0.4582% | hit_excess=72.73% | offsets_positive=7/11 | stable=False

Offsets carry a median of **2** episodes (min 0). **At that size the offset agreement is arithmetic, not evidence** — twelve subsamples of two or three episodes will agree on sign often enough by chance, so `stable` is withheld here regardless of how the signs fall.

| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |
|--------|------|--------|---------------|-------|--------------|
| 0 | 3 | 2.5865 | -0.524 | 100.0 | 50.0 |
| 1 | 2 | 2.1428 | -0.9677 | 100.0 | 0.0 |
| 2 | 0 | None | None | None | None |
| 3 | 2 | 5.1205 | 2.01 | 100.0 | 100.0 |
| 4 | 2 | 7.053 | 3.9426 | 100.0 | 100.0 |
| 5 | 1 | 8.4173 | 5.3068 | 100.0 | 100.0 |
| 6 | 3 | 1.6845 | -1.4259 | 66.67 | 66.67 |
| 7 | 2 | 4.16 | 1.0495 | 50.0 | 50.0 |
| 8 | 2 | 8.7 | 5.5895 | 100.0 | 100.0 |
| 9 | 2 | 6.643 | 3.5325 | 100.0 | 100.0 |
| 10 | 4 | 3.3817 | 0.2713 | 100.0 | 75.0 |
| 11 | 3 | 3.0968 | -0.0137 | 100.0 | 50.0 |

Offset mean-excess spread: **7.0154%**

## Why LIQUIDITY EXIT has been silent — it is the RM leg, not the FM units

The natural reading of four years of silence was that the FM unit seam pinned the FM percentile low, so a high-FM condition could never fire. Restating the units does not bring the pattern back. Split by leg, the cause is the **RM** side: asset managers have been persistently net long since 2023, so a 156-week rank of RM has not been near its floor.

| leg | % of weeks pre-2023-05-02 | % of weeks post | last fired | weeks since |
|-----|--------------------------:|----------------:|------------|------------:|
| `FM_pct>45` | 60.7 | 35.8 | 2026-08-18 | 0 |
| `FM_pct>70` | 36.8 | 12.7 | 2026-08-18 | 0 |
| `RM_pct<30` | 49.7 | 0.0 | 2023-03-28 | 177 |
| `RM_pct<15` | 28.1 | 0.0 | 2022-11-08 | 197 |

## SQUEEZE — pre/post 2023-05-02 stability (standing test, 12w)

The series no longer has a unit seam at this date, so this is a stability test, not a data check: a cell whose result lives entirely on one side of it has not been shown to work.

| condition | pre n_ep | pre mean_ex % | post n_ep | post mean_ex % | both sides | same sign | survives |
|-----------|---------:|--------------:|----------:|---------------:|:----------:|:---------:|:--------:|
| `FM_roll_pct<5 AND RM_roll_pct>40` | 3 | 2.2292 | 2 | 0.9506 | yes | yes | yes |
| `FM_roll_pct<5 AND RM_roll_pct>45` | 3 | 2.6889 | 2 | 0.9506 | yes | yes | yes |
| `FM_roll_pct<5 AND RM_roll_pct>50` | 2 | 3.9426 | 2 | 0.9506 | yes | yes | yes |
| `FM_roll_pct<40 AND RM_roll_pct>50` | 14 | -0.6768 | 14 | 1.3405 | yes | NO | **NO** |
| `FM_roll_pct<12.5 AND RM_roll_pct>50` | 5 | -1.5494 | 6 | 2.1311 | yes | NO | **NO** |
| `FM_roll_pct<7.5 AND RM_roll_pct>40` | 4 | -2.6539 | 3 | 1.7468 | yes | NO | **NO** |
| `FM_roll_pct<7.5 AND RM_roll_pct>45` | 4 | -2.3091 | 3 | 1.7468 | yes | NO | **NO** |
| `FM_roll_pct<7.5 AND RM_roll_pct>50` | 4 | -2.2307 | 3 | 1.7468 | yes | NO | **NO** |
| `FM_roll_pct<40 AND RM_roll_pct>55` | 13 | -1.0587 | 15 | 0.5939 | yes | NO | **NO** |
| `FM_roll_pct<45 AND RM_roll_pct>50` | 15 | 0.4424 | 15 | -0.3932 | yes | NO | **NO** |
| `FM_roll_pct<30 AND RM_roll_pct>45` | 20 | 0.5978 | 12 | -0.2286 | yes | NO | **NO** |
| `FM_roll_pct<30 AND RM_roll_pct>40` | 20 | 0.5288 | 12 | -0.2286 | yes | NO | **NO** |
| `FM_roll_pct<30 AND RM_roll_pct>60` | 16 | -0.1171 | 13 | -0.6461 | yes | yes | yes |
| `FM_roll_pct<30 AND RM_roll_pct>65` | 14 | -0.4172 | 13 | -0.5068 | yes | yes | yes |
| `FM_roll_pct<10 AND RM_roll_pct>60` | 2 | -7.3724 | 5 | 0.6517 | yes | NO | **NO** |
| `FM_roll_pct<12.5 AND RM_roll_pct>45` | 7 | -1.8534 | 6 | 2.1311 | yes | NO | **NO** |

### SQUEEZE — cells that are not independent

These cells fire on exactly the same episodes. They corroborate nothing; they are one result printed several times.

- **2 cells, 2 shared episodes:** `FM_roll_pct<5 AND RM_roll_pct>60`, `FM_roll_pct<5 AND RM_roll_pct>65`

## LIQUIDITY EXIT — pre/post 2023-05-02 stability (standing test, 4w)

The series no longer has a unit seam at this date, so this is a stability test, not a data check: a cell whose result lives entirely on one side of it has not been shown to work.

| condition | pre n_ep | pre mean_ex % | post n_ep | post mean_ex % | both sides | same sign | survives |
|-----------|---------:|--------------:|----------:|---------------:|:----------:|:---------:|:--------:|
| `RM_roll_pct<15 AND FM_roll_pct>70` | 17 | -1.0107 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<20 AND FM_roll_pct>70` | 25 | -0.812 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<25 AND FM_roll_pct>70` | 32 | -0.997 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<30 AND FM_roll_pct>50` | 52 | -0.7524 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<30 AND FM_roll_pct>55` | 48 | -0.8921 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<30 AND FM_roll_pct>70` | 32 | -1.1092 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<20 AND FM_roll_pct>65` | 29 | -0.3366 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<30 AND FM_roll_pct>45` | 48 | -0.9729 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<15 AND FM_roll_pct>65` | 21 | -0.3163 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<20 AND FM_roll_pct>45` | 38 | -0.5894 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<15 AND FM_roll_pct>75` | 15 | -0.9678 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<40 AND FM_roll_pct>70` | 37 | -0.6557 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<35 AND FM_roll_pct>45` | 48 | -0.3568 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<35 AND FM_roll_pct>70` | 33 | -0.6899 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<40 AND FM_roll_pct>55` | 49 | -0.5708 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<25 AND FM_roll_pct>45` | 49 | -0.8939 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<40 AND FM_roll_pct>45` | 51 | -0.4561 | 0 | — | NO | NO | **NO** |
| `RM_roll_pct<15 AND FM_roll_pct>45` | 30 | -0.7841 | 0 | — | NO | NO | **NO** |

## Sign-off status

- Rohit Aug 4: **do not sign off** prior grid; this re-run uses episode collapse,
  mean−median gap, excess-over-market (per-episode vs par benchmark), and extended FM axis.
- **PAR row** = every week unconditional; conditioned cells rank vs excess_hit not raw win %.
- **Do not wire into SSI composite** until thresholds confirmed after review.
- Display flags only (panel + Overwatch), no sizing.
