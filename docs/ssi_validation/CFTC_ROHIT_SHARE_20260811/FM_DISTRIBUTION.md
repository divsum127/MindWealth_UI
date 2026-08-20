# CFTC Fast Money Net Position — Fixed Distribution (for Rohit sign-off)

**Generated:** 2026-08-11
**Series:** CFTC TFF · S&P 500 (legacy STOCK INDEX → Consolidated stitch) · Leveraged Money
**Sample:** 2006-06-13 → 2026-08-04 · **n = 1052** weekly observations

## Sample start (answers Rohit row 75)

- Raw TFF FM/RM weekly prints from **2006-06-13**
- First rolling percentile (≥20 obs): **2006-10-24**
- First **full 156-week** rolling window: **2009-06-02**
- Grid analysis weeks: **1033** (2006-10-24 → 2026-08-04)
- **GFC 2008:** raw FM net exists (104 weeks in 2008–09) but **rolling-percentile grids exclude Sep 2008–May 2009** because the 156-week window is not full until mid-2009. Rebuild from 2003 would require legacy COT proxy (pre-TFF non-commercial) — not in current TFF pipeline.

## Fixed distribution percentiles (contracts)

| Percentile | FM net (contracts) |
|------------|-------------------:|
| min | -558,564 |
| **2.5th** | **-429,065** |
| **5th** | **-388,335** |
| **10th** | **-324,112** |
| median | -59,700 |
| max | 35,671 |

**Sign mix:** 96.0% net short · 4.0% net long.

PNG histogram: `ssi_validation/_generated/cftc_fm_net_distribution_histogram_20260811.png`

## Histogram (ASCII)

    -559k |#                                               |    1 (short)
    -534k |#                                               |    3 (short)
    -509k |#                                               |    5 (short)
    -484k |#                                               |    5 (short)
    -460k |#                                               |   11 (short)
    -435k |##                                              |   15 (short)
    -410k |##                                              |   15 (short)
    -385k |##                                              |   15 (short)
    -360k |###                                             |   21 (short)
    -336k |###                                             |   22 (short)
    -311k |###                                             |   19 (short)
    -286k |##                                              |   16 (short)
    -261k |##                                              |   12 (short)
    -237k |#                                               |    4 (short)
    -212k |#                                               |    5 (short)
    -187k |#                                               |    2 (short)
    -162k |#                                               |    7 (short)
    -138k |######                                          |   36 (short)
    -113k |####################                            |  113 (short)
     -88k |#############################                   |  166 (short)
     -63k |################################################|  266 (short)
     -39k |####################################            |  203 (short)
     -14k |############                                    |   69 (short)
      11k |###                                             |   21 (long)

## Proposed AND conditions for grid

| Variant | Condition |
|---------|-----------|
| Baseline | `FM net < 0` |
| Fixed 5th | `FM net < -388,335` |
| Fixed 10th | `FM net < -324,112` |
| Combined | `roll<10 AND net<0` |

