# Decision needed (Rohit): sign-off on regime-dimension multiplier table

**Date:** 2026-07-29
**Status:** AWAITING ROHIT SIGN-OFF — not yet approved. This document is the decision request,
not a record of approval.
**Trigger:** Macro regime system fix-to-spec plan, work item 3, action 5 — regime-conditional
leverage should not go live on unsigned economic-prior multipliers.

## The decision

`testing/5_regime_uplift/multiplier_spec.md` defines a per-dimension multiplier table (the
weights that turn a `macro_regime_log_v2` regime state into a gross-exposure haircut). It is
explicitly labeled in its own header:

> "Status: Illustrative for Michele demo. Not production-signed. Replace with Rohit-approved
> table when available."

This table has now been promoted, unchanged, into a production-adjacent module —
`src/macro_intelligence/output/regime_feed_export.py` — so it can back the new
`GET /macro/regime/history` API that Ahil's backtest engine will consume. The module tags every
row with `multiplier_version="v1_illustrative_unsigned"` precisely so nothing downstream can
mistake it for an approved table, but **the table itself has not changed** — it is the same v1
economic-prior guesses from the Michele demo, not re-derived or re-validated.

## The table awaiting sign-off

| Dimension | States → multiplier | Rationale (as documented) |
|---|---|---|
| `fed_cycle_v2` | TIGHTENING 0.82 / PIVOTING 0.92 / EASING 1.00 / EASY 1.00 | Fed hiking = headwind; cuts = supportive |
| `curve_regime_v2` | INVERTED 0.78 / FLAT 0.90 / NORMAL 1.00 / STEEPENING 0.95 | Inversion = recession signal |
| `val_regime` | EXTREME_CAPE 0.85 / ELEVATED_CAPE 0.92 / NORMAL 1.00 / CHEAP_CAPE 1.00 | Valuation headwind at extremes |
| `geo_overlay_v2` | CRISIS 0.70 / ELEVATED_RISK 0.85 / NEUTRAL 1.00 | COVID/Ukraine-style shocks |
| `liquidity_v2` (level bucket) | TIGHT_ 0.80 / NEUTRAL_ 0.95 / EASY_ 1.00 | NFCI-style financial stress |
| Unknown/missing (any dimension) | 0.95 (mild haircut) | Default, not a modeled prior |

Combined: `gross_mult = clip(m_fed × m_curve × m_val × m_geo × m_liq, 0.40, 1.00)`, applied with
a 1-day lag to gross exposure.

## Why this needs Rohit's sign-off, not an engineering default

These are **economic priors chosen for a demo**, not multipliers fit or validated against actual
portfolio return data. Nobody has checked whether, e.g., a 0.78× haircut on curve inversion vs.
a 0.70× or 0.85× alternative produces materially different backtest Sharpe/drawdown outcomes.
Before Ahil's regime-gated leverage results are shown to Pete as a real strategy input (vs. an
exploratory stand-in), the multiplier table itself needs to be either (a) approved as-is with
Rohit's explicit sign-off that "illustrative economic priors" is an acceptable v1 production
choice, or (b) replaced with a table derived from an actual calibration exercise (e.g. grid
search / historical regime-return decile analysis) before going live.

## What is already in place regardless of this decision

- `regime_feed_export.py` exports `m_fed`, `m_curve`, `m_val`, `m_geo`, `m_liq`, and `gross_mult`
  per day, all tagged `multiplier_version="v1_illustrative_unsigned"`.
- `GET /macro/regime/history` (`api/routers/macro.py`) surfaces this same tag in every response,
  so any consumer (including Ahil's engine) can see at a glance that the multiplier values are
  unsigned, independent of whichever regime *states* end up being used.
- No production code path (portfolio ceiling calc, live trading decisions) reads this multiplier
  table today — it is only consumed by the Test 5 Sharpe-uplift study and the new history API,
  both explicitly exploratory/backtest-only until this sign-off lands.

## What happens if this is NOT approved / a different table is preferred

- Ahil's regime-gated leverage backtest can still run using the current `v1_illustrative_unsigned`
  table — that is the intended use during this pending-decision period — but every result must
  be labeled with that multiplier version (already enforced by the export module) and should not
  be presented to Pete as a production-validated multiplier scheme.
- If Rohit requests a re-derivation, that is new analysis work (e.g. historical regime-bucket
  return statistics from `macro_regime_log_v2` joined to SPX/portfolio returns) — not scoped or
  started here, since it depends on which methodology Rohit prefers (economic-prior table vs.
  data-driven calibration vs. hybrid).

## Ask

Rohit: review the multiplier table above (unchanged from `testing/5_regime_uplift/multiplier_spec.md`)
and either (a) sign off on it as the v1 production table, or (b) request a data-driven
re-calibration before any regime-conditional leverage goes live beyond backtest/exploratory use.
Reply with approve / reject / request-recalibration.
