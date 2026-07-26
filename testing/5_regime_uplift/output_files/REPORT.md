# Test 5 — Regime Sharpe Uplift Report

Generated: 2026-07-14 06:38 UTC

## Michele headline

| Strategy | Sharpe | CAGR | Vol | Max DD |
|----------|--------|------|-----|--------|
| Baseline EW (100% gross) | 0.885 | 7.72% | 8.84% | -22.63% |
| 5-dimension regime overlay | 0.938 | 6.39% | 6.85% | -17.59% |
| **Sharpe uplift** | **+0.053** | | | |

Regime overlay **improves** Sharpe on this sample.

## Setup

- Basket: **SPY, TLT, GLD, HYG** equal-weight, monthly rebalance
- Sample: **2007-04-12** → **2026-07-13** (4843 trading days)
- Overlay: product of 5 dimension multipliers (see `multiplier_spec.md`), lagged 1d, cash at 0%
- EUR=X excluded per spec

## Regime multiplier distribution

- Mean gross mult: **0.805**
- Min / max: **0.532** / **1.0**
- Days at full exposure (mult=1.0): **0.2%**
- Days below 0.80: **47.0%**

## Caveats

1. Multipliers are **v1 economic priors** — not empirically optimised (overfit risk).
2. Regime labels are **weekly v2 shadow** forward-filled to daily.
3. Gross scaling only — does not tilt toward TLT in INVERTED (asset-specific tilts = future work).
4. `regime_backtest.py` (Part D) tested combo hit rates, **not** this portfolio Sharpe test.
