# D5 — Fed-Cycle Re-Slicing on Recalibrated Thresholds

**Date:** 2026-07-21  
**Task:** Re-run named-combo-by-fed-cycle tables using recalibrated D/E configs at validated horizons (not legacy production thresholds @ uniform 3M).

## Configs (recalibrated)

| Combo | Thresholds | Legs | Validated horizon(s) |
|-------|------------|------|----------------------|
| **D** | VXTS ≥1.18 / CFTC ≥95 / VIX ≤13 | 2-of-3 | **1W** (also **2W**) |
| **E** | CAPE ≥32 / NFCI ≤-0.15 / CFTC ≥85 | 3-of-3 | **6M / 9M / 12M** |

E note: 3-of-3 gate includes CFTC>=85; escalation alert is briefing overlay when CFTC pctile rises during active E episode.

**Sample rule:** Combo D slices with n < 9 → CANNOT USE; Combo E n < 10 → CANNOT USE (QE n=9 approved for D per Divyanshu 2026-07-21).

## (a) Combo D — CUTTING_LATE vs HIKING_LATE spread

### Legacy baseline (superseded)

Production CONFIG @ **3M**: overall **28.1%** bear hit (n=452).

| fed_cycle | n | bear hit 3M |
|-----------|---|-------------|
| CUTTING_LATE | 155 | **43.2%** |
| HIKING_LATE | 197 | **18.3%** |
| Spread (CUTTING − HIKING) | | **24.9 pp** (2.36×) |

### Recalibrated @ validated horizons

#### 1W (validated primary)

| fed_cycle | n | verdict | bear hit % |
|-----------|---|---------|------------|
| CUTTING_LATE | 13 | USE | 92.31 |
| HIKING_LATE | 24 | USE | 41.67 |
| Spread | | | **50.64 pp** (2.22×) vs legacy 24.9 pp |

**Verdict:** Spread **survives** recalibration (wider vs legacy).

#### 2W (secondary)

| fed_cycle | n | verdict | bear hit % |
|-----------|---|---------|------------|
| CUTTING_LATE | 13 | USE | 69.23 |
| HIKING_LATE | 24 | USE | 33.33 |
| Spread | | | **35.9 pp** (2.08×) vs legacy 24.9 pp |

**Verdict:** Spread **survives** recalibration (wider vs legacy).

## (b) Full fed-cycle tables

### Combo D

| fed_cycle | horizon | n | n_mature | bear hit % | avg SPX % | verdict |
|-----------|---------|---|----------|------------|-----------|---------|
| CUTTING_LATE | 1W | 13 | 13 | 92.31 | -1.5923 | USE |
| HIKING_LATE | 1W | 24 | 24 | 41.67 | -0.0516 | USE |
| OVERALL | 1W | 46 | 46 | 56.52 | -0.3499 | USE |
| QE | 1W | 9 | 9 | 44.44 | 0.649 | USE |
| CUTTING_LATE | 2W | 13 | 13 | 69.23 | -0.6773 | USE |
| HIKING_LATE | 2W | 24 | 24 | 33.33 | -0.0861 | USE |
| OVERALL | 2W | 46 | 46 | 43.48 | -0.1314 | USE |
| QE | 2W | 9 | 9 | 33.33 | 0.536 | USE |

### Combo E

| fed_cycle | horizon | n | n_mature | bear hit % | avg SPX % | verdict |
|-----------|---------|---|----------|------------|-----------|---------|
| CUTTING_LATE | 12M | 2 | 1 | — | — | CANNOT USE |
| HIKING_LATE | 12M | 5 | 5 | — | — | CANNOT USE |
| OVERALL | 12M | 10 | 9 | 66.67 | -6.5376 | USE |
| QE | 12M | 3 | 3 | — | — | CANNOT USE |
| CUTTING_LATE | 6M | 2 | 1 | — | — | CANNOT USE |
| HIKING_LATE | 6M | 5 | 5 | — | — | CANNOT USE |
| OVERALL | 6M | 10 | 9 | 66.67 | -3.2973 | USE |
| QE | 6M | 3 | 3 | — | — | CANNOT USE |
| CUTTING_LATE | 9M | 2 | 1 | — | — | CANNOT USE |
| HIKING_LATE | 9M | 5 | 5 | — | — | CANNOT USE |
| OVERALL | 9M | 10 | 9 | 66.67 | -6.3274 | USE |
| QE | 9M | 3 | 3 | — | — | CANNOT USE |

## Method

- Episode = first Friday crossing recalibrated gate with 5-calendar-day cooldown.
- fed_cycle = legacy 7-state label from `fed_cycle_at_date()` (FRED DFF + WALCL).
- Bear hit = % episodes where SPX forward return < 0 at horizon.
- Total D episodes: 46; total E episodes: 10.

## Artifacts

- `D5_fed_cycle_reslice_2026-07-21.csv` — slice summary
- `D5_fed_cycle_per_fire_2026-07-21.csv` — per-episode rows with fed_cycle
- `D5_fed_cycle_reslice_2026-07-21.json` — machine-readable payload
