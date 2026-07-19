# D6 — Regime Analytics Re-slice (post-collapse)

**Date:** 2026-07-17
**Task:** Re-run regime-conditional tables with D6 analytics collapse.

## Fed cycle — storage vs analytics

- Fridays in sample: **1901**
- PIVOTING in storage: **27**
- PIVOTING absent from analytics buckets: **True** (merged into EASING)

### Storage counts

| State | n |
|-------|---|
| EASING | 727 |
| EASY | 384 |
| PIVOTING | 27 |
| TIGHTENING | 763 |

### Analytics counts (PIVOTING → EASING)

| State | n |
|-------|---|
| EASING | 754 |
| EASY | 384 |
| TIGHTENING | 763 |

## Liquidity — 9-state storage vs 4-state analytics

- Storage states: **9**
- Analytics states: **4**

## FM band slices (analytics labels)

See `D6_fm_regime_slices_analytics_2026-07-17.csv`.

## Named combos by fed_cycle_v2 analytics @ 3M

See `D6_combo_fed_cycle_analytics_2026-07-17.csv`.

## Liquidity combo fires — 9-state vs 4-state @ 3M

See `D6_liquidity_9state_combo_fires_2026-07-17.csv` and `D6_liquidity_4state_analytics_combo_fires_2026-07-17.csv`.
