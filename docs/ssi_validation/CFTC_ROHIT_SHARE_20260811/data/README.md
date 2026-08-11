# CSV column reference

## squeeze_grid_12w.csv / liquidity_exit_grid_4w.csv
One row per grid cell at the primary ranking horizon.
- `n_weeks` — qualifying weeks (before episode collapse)
- `n_episodes` — collapsed distinct episodes
- `{horizon}_mean`, `{horizon}_median`, `{horizon}_mean_median_gap` — SPX forward return stats
- `{horizon}_hit_pct` — positive return share
- `{horizon}_mean_excess`, `{horizon}_hit_excess_pct` — vs unconditional market benchmark

## episode_dates_top_cells.csv
Every episode date for top-ranked cells with SPX return and excess at 12w.

## robustness_subsample.csv
12-offset non-overlapping subsample stability (Rohit primary robustness test).

## fm_net_distribution.csv
Fixed (non-rolling) percentiles of FM net contracts over full sample.
