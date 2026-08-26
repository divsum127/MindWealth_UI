# CFTC Fast Money Net Position — Fixed Distribution (for Rohit sign-off)

**Generated:** 2026-08-26
**Series:** CFTC TFF · S&P 500 · Leveraged Money · units `emini_equivalent` (component contract lines at notional weight — no Consolidated-line stitch, no 2023 unit seam)
**Sample:** 2006-06-13 → 2026-08-18 · **n = 1054** weekly observations

## Sample start — one number, everywhere (Rohit row 75)

- Raw TFF FM/RM weekly prints from **2006-06-13**
- First **full 156-week** window — and therefore the analysis start, since partial windows are no longer ranked: **2009-06-02**
- Unit-break scan: **none**
- Grid analysis weeks: **899** (2009-06-02 → 2026-08-18)
- **GFC 2008:** **not** in the percentile grids, and the earlier wording here saying it was is withdrawn. Those 2008 cells existed only because `weekly_pctile_series()` would rank a 20-observation window and call the result a 3-year percentile. It now requires a full window, so the first rankable week is after the crash. Including 2008 needs a shorter window, an explicitly accepted partial one, or the legacy proxy — a decision, not a code change.
- **Pre-2006:** TFF Leveraged Money starts 2006-06-13. The legacy COT non-commercial series (2003+) is now built and cached (`fetch_cftc_legacy_noncommercial_net`), but on the 2006–2010 overlap it tracks TFF only loosely — level corr 0.64, percentile corr 0.54, mean absolute percentile difference 23 points, and barely half the FM<10 extreme weeks agree. It is therefore published as labelled context (`legacy_noncommercial`), **not** stitched into these grids.

## Fixed distribution percentiles (contracts)

| Percentile | FM net (contracts) |
|------------|-------------------:|
| min | -901,710 |
| **2.5th** | **-721,368** |
| **5th** | **-647,747** |
| **10th** | **-576,669** |
| median | -325,512 |
| max | 223,837 |

**Sign mix:** 96.6% net short · 3.4% net long.

PNG histogram: `ssi_validation/_generated/cftc_fm_net_distribution_histogram_20260826.png`

## Histogram (ASCII)

    -902k |#                                               |    4 (short)
    -855k |###                                             |    9 (short)
    -808k |##                                              |    5 (short)
    -761k |#####                                           |   12 (short)
    -714k |#####                                           |   12 (short)
    -667k |##########                                      |   24 (short)
    -620k |##################                              |   43 (short)
    -573k |#################                               |   42 (short)
    -527k |##########################                      |   63 (short)
    -480k |##################################              |   81 (short)
    -433k |#######################################         |   94 (short)
    -386k |##############################################  |  110 (short)
    -339k |###########################################     |  103 (short)
    -292k |################################################|  113 (short)
    -245k |###########################################     |  102 (short)
    -198k |###############################                 |   74 (short)
    -151k |#######################                         |   55 (short)
    -104k |###############                                 |   36 (short)
     -58k |#############                                   |   31 (short)
     -11k |########                                        |   19 (short)
      36k |####                                            |   11 (long)
      83k |##                                              |    6 (long)
     130k |#                                               |    2 (long)
     177k |#                                               |    3 (long)

## Proposed AND conditions for grid

| Variant | Condition |
|---------|-----------|
| Baseline | `FM net < 0` |
| Fixed 5th | `FM net < -647,747` |
| Fixed 10th | `FM net < -576,669` |
| Combined | `roll<10 AND net<0` |

