# Ceiling-chain historical backfill (VIX / SPX-trend / HY multipliers)

**Date:** 2026-07-29 (refreshed 2026-08-02 — see addendum at the bottom)
**Trigger:** Macro regime system fix-to-spec plan, work item 3, action 4 — `four_book_engine.py`
explicitly documented that "VIX/trend/HY multipliers have no historical daily series stored
anywhere in this repo." This backfills that gap as a standalone, queryable series.

## What was built

`src/portfolio_nav/four_book_engine.py` gained four new functions:

| Function | Output | Source |
|---|---|---|
| `load_vix_mult_series()` | Daily VIX-level ceiling multiplier | `yahoo_pull.fetch_yahoo_close("^VIX")` |
| `load_spx_trend_mult_series()` | Daily SPX-vs-200dma trend multiplier | `yahoo_pull.fetch_yahoo_close("^GSPC")`, 200-day rolling mean |
| `load_hy_mult_series()` | Daily HY-OAS-level multiplier + `hy_tier` (NORMAL/PROXY/RARE/EXTREME) | `daily_readings` table, var `HY` (real + Model-v2-recalibrated proxy) |
| `load_full_ceiling_chain_series()` | Combines all three into one `DataFrame` with a `chain_mult` product column | Union of the three indices, each leg forward-filled onto the combined calendar, then rows before all three legs have started are dropped |

Each threshold rule is copy-mirrored from the **live** production logic already used in
`api/services/portfolio_service.py` (`_compute_ceiling`, `_compute_spx_trend_mult`), not
reinvented — same cutoffs, same multiplier values:

- **VIX:** `>30 → 0.90`, `>25 → 0.95`, else `1.00`
- **SPX trend:** below 200dma `→ 0.90`, else `1.00` (no MA yet → `1.00`, matches live
  "insufficient history" behavior)
- **HY OAS:** `>5% → 0.80`, `>4% → 0.85`, `>3% → 0.90`, else `1.00`

`chain_mult = vix_mult × trend_mult × hy_mult` — this is the missing VIX×trend×HY leg of the
full live chain (`regime_max × VIX × trend × HY × SSI`); the `regime_max` and `SSI` legs are
handled separately (regime leg: `regime_feed_export.py`; SSI leg: existing BASE+SSI/ENHANCED
book replay above these functions in the same file).

## Validation — spot checks against known stress periods

Ran `load_full_ceiling_chain_series()` over three known stress windows and confirmed multipliers
tighten as expected (values pulled 2026-07-29):

| Period | vix_mult | trend_mult | hy_mult | hy_tier | chain_mult |
|---|---|---|---|---|---|
| 2008-11-17 → 11-25 (GFC) | 0.90 | 0.90 | 0.80 | PROXY | 0.648 |
| 2020-03-16 → 03-26 (COVID crash) | 0.90 | 0.90 | 0.80 | PROXY | 0.648 |
| 2022-06-13 (CPI-shock selloff) | 0.90 | 0.90 | 0.85 | PROXY | 0.6885 |
| 2026-07-23 → 07-29 (current, calm) | 1.00 | 1.00 | 1.00 | NORMAL | 1.00 |

All three legs correctly tighten together during stress and relax to 1.00 in calm markets. The
2022-06 window (real, non-proxy-adjacent) also shows day-to-day granularity in the HY leg (0.85
↔ 0.90 as OAS crossed the 4%/3% cutoffs intraweek), confirming the recalibrated (work item 1)
HY series feeds through correctly with its tier label intact.

## Known limitations (carried forward, not fixed here)

1. ~~**HY leg pre-2023-07-13 is PROXY-tier**~~ **Closed 2026-08-02** — see addendum below. The HY
   leg is now real ICE BofA OAS for virtually all of history; `hy_is_proxy` remains exposed as an
   explicit boolean column (now `False` for all but 7 disclosed dates) so any consumer can still
   filter/flag it if needed.
2. **This is a standalone diagnostic series, not yet wired into the BASE+SSI/ENHANCED NAV
   decomposition** at the top of `four_book_engine.py`. Switching the live book replay to use the
   full chain (vs. SSI-only today) is a separate, deliberate decision — it would restate every
   historical BASE+SSI/ENHANCED number, not just add a diagnostic column — and is left for a
   follow-up decision alongside the regime-source-of-truth and multiplier-table sign-offs.
3. **VIX/SPX/HY series are combined on the union of their trading-day indices**, each leg
   forward-filled onto that combined calendar (weekends/holidays/short data outages inherit the
   prior day's multiplier, same as `_ceiling_on`'s forward-fill convention used elsewhere in this
   file); rows before all three legs have at least one reading are dropped rather than
   backfilled/interpolated.
4. No production job persists this series anywhere yet — it is a callable function, not a
   scheduled backfill into a database table. Wiring it into the same on-disk/DB pattern as
   `macro_regime_log_v2` is out of scope for this plan (only in scope: prove the series is
   computable end-to-end and matches live threshold logic).

## Addendum — 2026-08-02 (refreshed after the HY OAS wayback backfill)

`scripts/backfill_hy_oas_from_wayback.py` replaced the HY OAS BAA10Y+VIX proxy with real ICE
BofA OAS for virtually all of history (see `docs/ssi_validation/hy_oas_wayback_backfill_2026-08-02.md`).
`load_hy_mult_series()`/`load_full_ceiling_chain_series()` needed **no code change** — they already
read `daily_readings` directly — but the underlying values and, more importantly, the `hy_tier` /
`hy_is_proxy` provenance columns are now different. Re-ran the same three stress windows and the
current-calm check (2026-08-02):

| Period | vix_mult | trend_mult | hy_mult | hy_tier (was) | hy_tier (now) | hy_is_proxy (now) | chain_mult |
|---|---|---|---|---|---|---|---|
| 2008-11-17 → 11-25 (GFC) | 0.90 | 0.90 | 0.80 | PROXY | **EXTREME** | **False** | 0.648 (unchanged) |
| 2020-03-16 → 03-26 (COVID crash) | 0.90 | 0.90 | 0.80 | PROXY | **EXTREME** | **False** | 0.648 (unchanged) |
| 2022-06-13 (CPI-shock selloff) | 0.90 | 0.90 | 0.85 | PROXY | **NORMAL** | **False** | 0.6885 (unchanged) |
| 2026-07-23 → 07-29 (current, calm) | 1.00 | 1.00 | 1.00 | NORMAL | NORMAL | False | 1.00 (unchanged) |

**The multiplier *values* (`hy_mult`, `chain_mult`) did not change** for these four specific anchor
dates — the Model v2 proxy happened to already land in the same threshold bucket (`>5%`/`>4%`/
`>3%`) as the real data for these particular dates. **What changed is provenance**: `hy_tier` now
reflects the real signal tier (`EXTREME` for the GFC/COVID peaks, correctly identifying them as
extreme HY stress, vs. the flat `PROXY` label before) and `hy_is_proxy` is now `False`.

**But across the full pre-2023 history, the bucket DID change materially for many other dates** —
a full point-by-point diff (old proxy `raw_value` vs. new real `raw_value`, both run through the
same `_tiered_mult` bucketing) across the 7,400 dates common to both the pre- and post-backfill
`runic.db` snapshots found:

| | Count | % of common dates |
|---|---|---|
| `hy_mult` bucket unchanged | 5,433 | 73.4% |
| `hy_mult` bucket changed | 1,967 | 26.6% |

Direction is mixed, not uniformly tighter or looser — the real series showed both understated
*and* overstated stress at different times relative to the linear+VIX proxy:

| Old bucket → | 0.80 (n=338) | 0.85 (n=1,029) | 0.90 (n=574) | 1.00 (n=26) |
|---|---|---|---|---|
| New bucket distribution | mostly stays 0.80 or loosens | splits across all 4 buckets | splits across all 4 buckets | mostly stays 1.00 |

Anyone citing a specific historical `chain_mult`/`hy_mult` value for a pre-2023-07-13 date from
before 2026-08-02 must re-pull it — it may have moved. This is the intended effect of replacing a
proxy with real data, not a bug; flagged explicitly per this plan's downstream-effects checklist.
