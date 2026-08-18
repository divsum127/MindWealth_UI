# Integration guide for Ahil: wiring the regime feed into the backtest engine

**Date:** 2026-07-29
**Trigger:** Macro regime system fix-to-spec plan, work item 3, action 6 (coordination
dependency — flagged in the plan as "not ours to close alone"). This document is the technical
handoff; Ahil's side (actually importing this into his signal/backtest code) is still pending.

## TL;DR for Ahil

The "bridge" from the original thread is built and live-tested. It is a **data contract, not yet
a live integration** — nothing in your signal/backtest code reads it today. Two ways to consume
it, pick whichever fits your codebase better:

1. **HTTP** — call `GET /api/v1/macro/regime/history` from wherever you already pull other data.
2. **Direct Python import** — if your backtest runs in this repo/venv, import
   `regime_feed_as_records()` (or `get_regime_feed()` for a DataFrame) directly, no HTTP round
   trip.

## Option 1 — HTTP

```python
import requests
import pandas as pd

API_KEY = "..."  # from .env, X-API-Key header
BASE = "http://51.20.53.218:8506/api/v1"

def load_regime_history(start: str, end: str) -> pd.DataFrame:
    r = requests.get(
        f"{BASE}/macro/regime/history",
        params={"start": start, "end": end},
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()["rows"]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")

regime = load_regime_history("2010-01-01", "2026-07-29")
# regime["gross_mult"], regime["fed_cycle_v2"], etc. — see field notes in
# docs/mindwealth-api-docs/services/macro/endpoints/get-regime-history.md
```

## Option 2 — direct import (same repo/venv only)

```python
from src.macro_intelligence.output.regime_feed_export import get_regime_feed

regime = get_regime_feed(start="2010-01-01", end="2026-07-29")
```

Both return the same columns. Use whichever matches how your backtest engine already sources
other data (HTTP vs in-process).

## Applying it to a backtest — mandatory execution-lag step

The feed exports the **raw point-in-time regime state** (no lookahead), not a pre-lagged trading
signal. Before joining to next-day returns, shift by at least 1 day:

```python
returns = returns.join(regime[["gross_mult"]].shift(1), how="left")
returns["gross_mult"] = returns["gross_mult"].ffill()  # carry forward over non-trading days
returns["strategy_return"] = returns["raw_return"] * returns["gross_mult"]
```

## Mandatory: label `regime_source` in every result you produce

Per the original thread (and enforced by the API tagging every row already):

> "Flag in your results which regime source you actually used, stand-in or Divyanshu's real
> output, so it's not presented to Pete as more integrated than it is."

Use one of these four values, matching whatever you actually ran:

| Label | Meaning |
|---|---|
| `stand-in` | Your own simplified proxy (VIX pctile + SPX 200dma + HY OAS), no dependency on this feed |
| `D1_bucket` | `testing/macro_th_exp/D1_regime_bucket_daily_*.csv` combo-bucket feed |
| `regime_daily_v2` | This feed (`macro_regime_log_v2` via `regime_feed_export.py` / `GET /macro/regime/history`), **currently unsigned** multiplier table |
| `live_v2` | Same source, but only once both pending decisions below are signed off |

## Two things still pending before this can be called `live_v2`

Both are Rohit decisions, not engineering blockers on your side — you can and should proceed
with `regime_daily_v2` labeling now rather than wait:

1. **Source-of-truth sign-off** — is `macro_regime_log_v2` *the* production regime, superseding
   the legacy `runic_output.json` block? `docs/plans/regime_source_of_truth_decision_2026-07-29.md`
2. **Multiplier table sign-off** — `m_fed`/`m_curve`/`m_val`/`m_geo`/`m_liq`/`gross_mult` are v1
   illustrative economic priors from the Michele demo, not calibrated against real returns.
   `docs/plans/multiplier_signoff_request_2026-07-29.md`

If you'd rather use your own multiplier weights on top of the raw dimension *states*
(`fed_cycle_v2`, `curve_regime_v2`, `val_regime`, `geo_overlay_v2`, `liquidity_v2`) instead of the
provided `m_*`/`gross_mult` columns, that sidesteps caveat 2 entirely — the states themselves are
just a read of `macro_regime_log_v2`, only the multiplier weights are unsigned.

## Known data limitations to be aware of

- **HY OAS leg (feeds into the separate ceiling-chain series, not this regime feed directly)**
  is proxy-tier before 2023-07-13 (BAA10Y+VIX-calibrated, not real ICE BofA OAS) — see
  `docs/ssi_validation/hy_oas_recalibration_2026-07-29.md`. If your stand-in already uses raw HY
  OAS directly, the same proxy-era caveat applies to whichever source you pull it from.
- **`macro_regime_log_v2` is refreshed by a manual/on-demand backfill script, not a live nightly
  cron** — for a historical backtest this doesn't matter, but don't assume the *latest* row is
  as fresh as today's date without checking `evaluation_date` on the last row.
- Full VIX × SPX-trend × HY multiplier history (the other half of the live ceiling formula,
  independent of the 5-dimension regime) is now also backfilled and available via
  `src/portfolio_nav/four_book_engine.py::load_full_ceiling_chain_series()` if your backtest
  wants to combine both legs (`regime_max × VIX × trend × HY × SSI`) rather than the regime leg
  alone — see `docs/ssi_validation/ceiling_chain_backfill_2026-07-29.md`.

## Ask

Ahil: pick Option 1 or 2 above, wire it into your regime-gated leverage backtest, and label
`regime_source: regime_daily_v2` (or `stand-in` if you keep running the simplified version in
parallel for comparison) in every result before sharing with Pete. Ping Divyanshu if the schema
doesn't cover something you need (e.g. a different forward-fill convention, trading-day vs
calendar-day index) — `schema_version` will bump if the contract changes.
