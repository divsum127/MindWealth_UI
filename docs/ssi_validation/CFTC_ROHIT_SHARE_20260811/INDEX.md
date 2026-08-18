# CFTC SQUEEZE / LIQUIDITY EXIT — Share Package for Rohit

**Package date:** 2026-08-11  
**COT data through:** 2026-08-04 (Tuesday position date)  
**Spec:** Rohit Aug 4, 2026 email (episode collapse, extended FM axis, mean−median gap, PAR/excess, robustness)

---

## Quick links (after push to `chatbot-dev`)

| Item | View | Download |
|------|------|----------|
| **Start here — sign-off report** | [REPORT.md](REPORT.md) | [raw](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/REPORT.md) |
| **This index** | [INDEX.md](INDEX.md) | [GitHub](https://github.com/divsum127/MindWealth_UI/blob/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/INDEX.md) |
| SQUEEZE grid (12w metrics) | [csv/squeeze_grid_12w.csv](csv/squeeze_grid_12w.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/squeeze_grid_12w.csv) |
| SQUEEZE grid (all horizons) | [csv/squeeze_grid_all_horizons.csv](csv/squeeze_grid_all_horizons.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/squeeze_grid_all_horizons.csv) |
| LIQUIDITY EXIT grid (4w metrics) | [csv/liquidity_exit_grid_4w.csv](csv/liquidity_exit_grid_4w.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/liquidity_exit_grid_4w.csv) |
| LIQUIDITY EXIT grid (all horizons) | [csv/liquidity_exit_grid_all_horizons.csv](csv/liquidity_exit_grid_all_horizons.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/liquidity_exit_grid_all_horizons.csv) |
| Dated episodes (top cells) | [csv/episode_dates_top_cells.csv](csv/episode_dates_top_cells.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/episode_dates_top_cells.csv) |
| 12-offset subsample robustness | [csv/robustness_subsample.csv](csv/robustness_subsample.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/robustness_subsample.csv) |
| FM pctile regression | [csv/fm_pctile_regression.csv](csv/fm_pctile_regression.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/fm_pctile_regression.csv) |
| FM fixed distribution | [csv/fm_net_distribution.csv](csv/fm_net_distribution.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/fm_net_distribution.csv) |
| PAR row (unconditional) | [csv/par_row.csv](csv/par_row.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/par_row.csv) |
| Sample diagnostics | [csv/sample_diagnostics.csv](csv/sample_diagnostics.csv) | [raw CSV](https://raw.githubusercontent.com/divsum127/MindWealth_UI/chatbot-dev/docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/sample_diagnostics.csv) |

## Executive summary

1. **Ranking metric:** mean − median gap at 12w (SQUEEZE) / 4w (LIQUIDITY EXIT), read with dated episodes — **not Sharpe**.
2. **Top SQUEEZE cell:** `FM_roll_pct<10 AND RM_roll_pct>55` — n_ep=21, 12w gap ≈ +0.41%, excess_hit 65%.
3. **PDF default FM<30/RM>50:** negative gap (−0.57%) — tracks market, not tail.
4. **Extreme FM<5:** n_ep=6 only — high mean (~5.8%) but tiny sample.
5. **LIQUIDITY EXIT RM<30/FM>60:** n_ep=40, 4w hit 32.5% — stress context flag, not a clean short.
6. **Sample start:** raw TFF from 2006-06-13; first **full 156-week** rolling window **2009-06-02** → GFC Sep 2008–May 2009 excluded from rolling-percentile grids.
7. **Display wiring:** held pending sign-off (flags only, no composite sizing).

## Package contents

### Reports

- `REPORT.md` — full sign-off report (heatmaps, top cells, recommendations)
- `TAIL_EPISODES.md` — dated episode lists (FM>70/75 discontinuity explained)
- `ROBUSTNESS.md` — 12-offset subsample stability tables
- `FM_DISTRIBUTION.md` — FM net fixed distribution + proposed absolute cuts
- `data/README.md` — column definitions for CSV files

### CSV data (`csv/`)

- `squeeze_grid_12w.csv` — SQUEEZE grid (12w metrics)
- `squeeze_grid_all_horizons.csv` — SQUEEZE grid (all horizons)
- `liquidity_exit_grid_4w.csv` — LIQUIDITY EXIT grid (4w metrics)
- `liquidity_exit_grid_all_horizons.csv` — LIQUIDITY EXIT grid (all horizons)
- `episode_dates_top_cells.csv` — Dated episodes (top cells)
- `robustness_subsample.csv` — 12-offset subsample robustness
- `fm_pctile_regression.csv` — FM pctile regression
- `fm_net_distribution.csv` — FM fixed distribution
- `par_row.csv` — PAR row (unconditional)
- `sample_diagnostics.csv` — Sample diagnostics

### Supporting files

- `data/fm_net_distribution_histogram.png` — FM net fixed distribution
- `data/sample_diagnostics.json` — sample start / window diagnostics
- `data/benchmark.json` — PAR benchmark returns per horizon

## Methodology (short)

| Item | Value |
|------|-------|
| Percentile window | 156 weeks rolling |
| Episode collapse | Consecutive qualifying weeks → one episode (first fire) |
| Benchmark | Mean SPX forward return across all weeks in sample |
| Excess | Episode return minus benchmark; excess_hit = beat market |
| SQUEEZE | FM pctile < X AND RM pctile > Y |
| LIQUIDITY EXIT | RM pctile < X AND FM pctile > Y |

## Source artifacts

- `macro_intelligence/analysis/ssi_validation/03_squeeze_grid_v2_20260811.json`
- `macro_intelligence/analysis/ssi_validation/04_liquidity_exit_grid_v2_20260811.json`

## Regenerate

```bash
.venv/bin/python scripts/run_cftc_rohit_rerun.py
.venv/bin/python scripts/compile_cftc_pattern_threshold_report.py
.venv/bin/python scripts/export_cftc_rohit_share_package.py
```

