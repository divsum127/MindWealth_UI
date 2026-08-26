# CFTC robustness — non-overlapping subsample stability (PRIMARY)

Generated: 20260825

Method: partition analysis calendar into 12 non-overlapping subsamples (every 12th week at offsets 0–11). Re-run episode collapse + 12w SPX metrics at each offset. **Stable** = positive mean excess at ≥8 offsets and ≥67% of offsets with data.

- CFTC TFF S&P 500, restated into emini_equivalent units (component contract lines at notional weight - E-mini 1.0, big 5.0, micro 0.1 - so CFTC's 2023-05-02 redefinition of the Consolidated line no longer puts a 5x seam mid-sample); raw 2006-06-13 to 2026-08-18 (1054 weekly prints); first full 156w window 2009-06-02; analysis weeks 899 (2009-06-02 to 2026-08-18); unit breaks detected: none.

## `FM_roll_pct<7.5 AND RM_roll_pct>45` (n_qual_weeks=20)

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

*Block bootstrap: not run or insufficient data.*
## `FM_roll_pct<7.5 AND RM_roll_pct>40` (n_qual_weeks=21)

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

*Block bootstrap: not run or insufficient data.*
## `FM_roll_pct<7.5 AND FM_net<0` (n_qual_weeks=62)

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

*Block bootstrap: not run or insufficient data.*
## `FM_roll_pct<5 AND RM_roll_pct>45` (n_qual_weeks=11)

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

*Block bootstrap: not run or insufficient data.*
## `FM_roll_pct<5 AND RM_roll_pct>40` (n_qual_weeks=12)

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

*Block bootstrap: not run or insufficient data.*
## `FM_roll_pct<5 AND RM_roll_pct>50` (n_qual_weeks=10)

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

*Block bootstrap: not run or insufficient data.*
## `FM_roll_pct<40 AND RM_roll_pct>50` (n_qual_weeks=164)

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

*Block bootstrap: not run or insufficient data.*
## `FM_roll_pct<12.5 AND RM_roll_pct>50` (n_qual_weeks=26)

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

*Block bootstrap: not run or insufficient data.*

## Interpretation guide

- **Clustered episode:** strong at offset 0 only, collapses at offsets 3+7 → one-time cluster.
- **Real signal:** holds across most/all 12 offsets with similar mean excess.
- Bootstrap percentile near 50 = indistinguishable from resampled null; >90 or <10 = tail outcome.
