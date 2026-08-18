# CFTC Fast Money Net Position — Fixed Distribution (for Rohit sign-off)

**Generated:** 2026-08-07  
**Series:** CFTC TFF · S&P 500 Consolidated · Leveraged Money (Fast Money)  
**Sample:** 2006-06-13 → 2026-07-28 · **n = 1051** weekly observations

## Fixed distribution percentiles (contracts)

| Percentile | FM net (contracts) |
|------------|-------------------:|
| min | -558,564 |
| **2.5th** | **-429,091** |
| **5th** | **-388,363** |
| **10th** | **-321,801** |
| 25th | -97,810 |
| median | -59,697 |
| 75th | -35,826 |
| 90th | -16,365 |
| max | 35,671 |

**Sign mix:** 96.0% net short · 4.0% net long.

PNG histogram: `docs/ssi_validation/_generated/cftc_fm_net_distribution_histogram_20260807.png`

## Histogram (ASCII)

```
   -559k |                                                |   1 (short)
   -537k |#                                               |   3 (short)
   -516k |#                                               |   3 (short)
   -495k |#                                               |   4 (short)
   -474k |#                                               |   6 (short)
   -452k |##                                              |   8 (short)
   -431k |###                                             |  15 (short)
   -410k |###                                             |  12 (short)
   -389k |###                                             |  12 (short)
   -368k |####                                            |  19 (short)
   -346k |####                                            |  21 (short)
   -325k |##                                              |  11 (short)
   -304k |####                                            |  21 (short)
   -283k |##                                              |  11 (short)
   -261k |##                                              |  10 (short)
   -240k |#                                               |   5 (short)
   -219k |#                                               |   3 (short)
   -198k |#                                               |   5 (short)
   -177k |                                                |   0 (short)
   -155k |##                                              |  11 (short)
   -134k |#######                                         |  32 (short)
   -113k |###################                             |  90 (short)
    -92k |#############################                   | 137 (short)
    -70k |#########################################       | 195 (short)
    -49k |################################################| 230 (short)
    -28k |###########################                     | 128 (short)
     -7k |#########                                       |  41 ← zero
     14k |####                                            |  17 (long)
```

## Why absolute cuts matter

During sustained bull runs, FM rolling 20th percentile can still be **net long** (positive contracts).  
Rolling percentile alone does not guarantee genuinely short crowding.

| Rolling FM pct | n weeks | % net short | % net long | median net |
|----------------|--------:|------------:|-----------:|-----------:|
| < 5 | 76 | 100.0% | 0.0% | -103,905 |
| < 10 | 169 | 100.0% | 0.0% | -115,430 |
| < 15 | 226 | 100.0% | 0.0% | -112,832 |
| < 20 | 286 | 100.0% | 0.0% | -109,480 |
| < 25 | 334 | 100.0% | 0.0% | -105,622 |
| < 30 | 398 | 100.0% | 0.0% | -99,997 |

**Historical note:** 0 weeks in sample have roll<20 AND net>0. Net-long weeks (n=42) occur at roll percentiles 87–100 (GFC rebound, 2018, COVID, 2021–22). Rohit's guard is forward-looking for regime shift.

## Proposed AND conditions for grid (pending Rohit confirm)

| Variant | Condition | n weeks |
|---------|-----------|--------:|
| A | roll<10 AND net<0 | 169 |
| A | roll<7.5 AND net<0 | 128 |
| A | roll<5 AND net<0 | 76 |
| B | net<fixed_p2.5 (-429,091) | 27 |
| B | net<fixed_p5 (-388,363) | 53 |
| B | net<fixed_p10 (-321,801) | 105 |
| C | roll<10 AND net<p10 | 46 |
| C | roll<15 AND net<p10 | 56 |
| C | roll<20 AND net<p10 | 73 |

## Recommendation (pre-grid)

1. **Baseline absolute gate:** `FM net < 0` — minimum bar for "genuinely short"; essential AND guard in bull regimes even though only 4% of historical weeks are net long.
2. **Primary fixed cut for grid:** **5th percentile (~−388k contracts)** — ~5% of weeks; balances rarity vs sample size (n≈53).
3. **Sensitivity bounds:** 2.5th (~−429k, n≈27) and 10th (~−322k, n≈105).
4. **Preferred combined SQUEEZE runs:** `FM roll pct < 10 AND FM net < 0` (baseline) plus `roll < 10 AND net < fixed_p10` (stricter).

Awaiting Rohit confirm before full grid re-run.
