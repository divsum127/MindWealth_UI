# Decision needed (Rohit): production regime source of truth

**Date:** 2026-07-29
**Status:** AWAITING ROHIT SIGN-OFF — not yet approved. This document is the decision request,
not a record of approval.
**Trigger:** Macro regime system fix-to-spec plan, work item 3, action 1 — bridge between
Divyanshu's regime output and Ahil's backtest engine requires picking one production regime
source first.

## The decision

Today there are **three different "regime" outputs** in the repo with no single one designated as
canonical:

| Source | What it is | Depth | Backfilled? | Used by |
|---|---|---|---|---|
| `runic_output.json` legacy `regime` block | Original 2-3 field regime (fed_cycle, val_regime, geo_overlay) | Today only (nightly snapshot) | No | `GET /macro/regime` (today only), `portfolio_service._compute_ceiling` |
| `macro_regime_log_v2` (SQLite table) | **Real 5-dimension** shadow regime: `fed_cycle_v2`, `curve_regime_v2`, `val_regime`, `geo_overlay_v2`, `liquidity_v2` | 1,901 Friday rows, 1990-01-05 → present, Friday-cadence with forward-fill | Yes — this is the only one with real historical depth | Test 5 (`testing/5_regime_uplift/`), Ahil's Sharpe-uplift study |
| `book_snapshot_store.regime_bucket_daily` | Combo-bucket regime classification | Accumulates only from whenever the daily job first started running | **No** — explicitly never backfilled | `GET /portfolio/regime-history` |

**Recommendation: designate `macro_regime_log_v2` as the production regime source of truth**,
superseding the legacy `regime` block in `runic_output.json` for anything regime-conditional
(including Ahil's regime-gated leverage work). This is the only one of the three with genuine
multi-decade historical depth, which is a hard requirement for a backtest.

## Why this needs Rohit's sign-off, not just an engineering default

Changing "which table is the regime system" changes what "the regime system" means in
production — it affects anything downstream that currently reads the legacy block (today only
`GET /macro/regime` and the live ceiling calc), and it's the field Ahil's backtest engine will be
wired to permanently once the bridge is built. This is a product decision, not something to
default silently.

## What approving this unlocks (already scoped, not yet built pending this decision)

1. `regime-feed-module` — promote the existing one-off `regime_daily.csv` export
   (`testing/5_regime_uplift/run_regime_sharpe_uplift.py`) into a maintained, versioned module.
2. `regime-history-endpoint` — a real `GET /macro/regime/history` API backed by
   `macro_regime_log_v2`, for Ahil's engine to consume directly instead of a manual CSV handoff.
3. `ceiling-chain-backfill` — the four-book ceiling replay's regime leg would source from this
   table once backfilled.

Both are being built now regardless (so they're ready the moment sign-off lands), tagged as
`regime_source: regime_daily_v2` in their output — see `regime-feed-module` and
`regime-history-endpoint` work below. Nothing consumes them as "the" production regime yet; that
switch-over is what actually needs Rohit's approval.

## What happens if this is NOT approved / a different source is preferred

- If the legacy `runic_output.json` regime block is preferred instead: it has zero historical
  depth today (today-only snapshot) — someone would need to scope a separate backfill effort
  before it could support a backtest at all.
- If `book_snapshot_store.regime_bucket_daily` is preferred: same issue — explicitly never
  backfilled, accumulates only from job-start.
- Either alternative pushes the "real historical depth" requirement onto new backfill work that
  `macro_regime_log_v2` already has today.

## Ask

Rohit: confirm `macro_regime_log_v2` (5-dimension shadow regime table) as the production regime
source of truth for regime-conditional leverage / backtest work, superseding the legacy
`runic_output.json` regime block. Reply with go / no-go / alternate preference.
