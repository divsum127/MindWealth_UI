# Test 5 — Regime Sharpe Uplift vs Equal-Weight Benchmark

**Lead:** Ahil  
**Goal:** Demonstrate whether the Runic **5 regime dimensions** improve risk-adjusted returns on a simple multi-asset benchmark.

## Benchmark

| Asset | Role | Inception (Yahoo) |
|-------|------|-------------------|
| SPY | US equities | 1993+ |
| TLT | Rates / duration | 2002+ |
| GLD | Gold | 2004+ |
| HYG | Credit / HY | **2007-04-11** |

**Excluded:** EUR=X (unstable correlation to regime states).

**Common sample:** 2007-04-11 → latest ETF date (limited by HYG).

## Two strategies

1. **Baseline** — 100% gross exposure, equal-weight (25% each), **monthly rebalance**.
2. **Regime overlay** — same basket, gross exposure scaled by **5-dimension regime multiplier** (lagged 1 day, no lookahead).

Cash when scaled down earns **0%** (conservative; no idle yield).

## Five regime dimensions (v2 shadow labels)

From `macro_regime_log_v2.regime_json` (Friday backfill, forward-filled to daily):

| Dimension | JSON field | States used |
|-----------|------------|-------------|
| Fed cycle | `fed_cycle_v2` | TIGHTENING, PIVOTING, EASING, EASY |
| Curve | `curve_regime_v2` | INVERTED, FLAT, NORMAL, STEEPENING |
| Valuation | `val_regime` | EXTREME_CAPE, ELEVATED_CAPE, NORMAL, CHEAP_CAPE |
| Geo | `geo_overlay_v2` | CRISIS, ELEVATED_RISK, NEUTRAL |
| Liquidity | `liquidity_v2` | Level bucket: TIGHT_*, NEUTRAL_*, EASY_* |

Multiplier table: see `regime_dimension_multipliers_v1_unsigned.md` (v1 economic priors — illustrative until Rohit sign-off).

**Combined multiplier:** `clip(Π dimension_mult, 0.40, 1.00)`.

## Metrics

- Annualized Sharpe (daily returns, rf=0)
- CAGR, annualized vol, max drawdown
- Hit rate of overlay beating baseline on rolling 12m Sharpe (diagnostic)

## Outputs (`output_files/`)

| File | Contents |
|------|----------|
| `etf_daily_prices.csv` | SPY, TLT, GLD, HYG closes |
| `regime_daily.csv` | 5 dimensions + combined mult per day |
| `portfolio_daily_returns.csv` | baseline vs overlay daily returns + equity |
| `summary_metrics.json` | Sharpe, CAGR, vol, max DD |
| `REPORT.md` | Michele-ready narrative |

## Regenerate

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
.venv/bin/python testing/5_regime_uplift/run_regime_sharpe_uplift.py
```

## Related (Test 3)

`combo_classification_history.csv` — dominant-combo **adverse_regime** flag (separate from 5-dimension mult). Optional sensitivity in script appendix.
