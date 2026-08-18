# HY OAS Wayback Machine Backfill — Real History Replaces the BAA10Y Proxy

**Date:** 2026-08-02
**Status:** APPLIED to runic.db
**Supersedes:** `scripts/recalibrate_hy_oas_proxy.py` (Model v2 BAA10Y+VIX proxy, 2026-07-29) — kept in the repo for provenance/history and as a fallback only.
**Related:** `docs/ssi_validation/data_gap_report_2026-06-06.md`, `docs/MACRO_INTELLIGENCE_MASTER.md` §HY Credit Spreads OAS, `docs/ssi_validation/hy_proxy_consumer_audit_2026-07-29.md`

## Source

Internet Archive (Wayback Machine) snapshot captured **2025-11-04** of FRED's own public CSV endpoint for `BAMLH0A0HYM2` (ICE BofA US High Yield OAS):

```
http://web.archive.org/web/20251104204105/https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2
```

This is days before FRED's April-2026 3-year licensing cutoff took effect (a later 2026-07-16 snapshot of the same URL already shows the capped 3-year window, confirming this November-2025 capture is the last free full-history snapshot available). It contains the **real** ICE BofA HY OAS series, 1996-12-31 -> 2025-11-03 (7530 rows). Combined with the real data already collected live since 2023-06-09 (`src/macro_intelligence/data/pull_all.py`), coverage is now continuous real data from 1996-12-31 to today — this closes the gap completely, it does not merely improve a proxy.

## Anchor cross-checks (sanity, not calibration — this is real data)

| Date | Wayback value | Known public figure | Note |
|------|----------------|----------------------|------|
| 2008-12-15 | 21.82% | 21.82% | GFC peak; matches the ~21-22% widely-cited consensus |
| 2020-03-23 | 10.87% | 10.87% | COVID peak; matches the commonly cited 1,087bps almost exactly |
| 2022-06-13 | 4.87% | 4.87% | 2022 rate-shock stress; Model v2 proxy estimated 4.37% for this date |

## What changed in `daily_readings`

| Category | Count | Effect |
|----------|-------|--------|
| `PROXY` -> real (wayback covers the date) | 6620 | `raw_value` replaced with real ICE OAS; `signal_tier`/`direction` recomputed via `evaluate_variable_tier`; `pctile_rank_3yr`/`unconditional_pctile` recomputed |
| `PROXY` orphans (wayback has no value) | 7 | **Unchanged** — still `signal_tier='PROXY'` with the old BAA10Y-derived estimate; only percentile columns recomputed |
| New rows inserted (wayback has a value, no prior row existed) | 327 | Inserted as real, tier computed via `evaluate_variable_tier` |
| Already-real rows (2023-06-09 onward, live-collected) | 773 | `raw_value`/`signal_tier`/`direction` **untouched**; only percentile columns recomputed (rolling-3y window now includes real, not proxy, pre-2023 history) |

New tier distribution among backfilled + newly-inserted dates: `{'NORMAL': 5162, 'RARE': 874, 'EXTREME': 911}`.

## Disclosed residual gap — 7 orphan PROXY dates

These dates have `signal_tier='PROXY'` in the DB but the wayback CSV has no printed value for them (bond-market-only holidays, e.g. Good Friday, that the BAA10Y/Federal Reserve H.15 calendar used for the original 2026-06 proxy backfill did not observe as holidays, so a proxy value was computed and stored where the real ICE series has none). No free real source was found to cover this narrow residual — left on the old BAA10Y-derived estimate, not silently dropped:

| Date | Old proxy raw_value |
|------|----------------------|
| 2001-09-13 | 6.8007 |
| 2007-04-06 | 3.2950 |
| 2010-04-02 | 4.7158 |
| 2012-04-06 | 6.0586 |
| 2013-08-30 | 4.9493 |
| 2015-01-16 | 5.0661 |
| 2015-04-03 | 4.9882 |

## Downstream effects — handle explicitly, do not present as a free lunch

- **Retroactive reclassification:** 6620 rows flip from `PROXY` to real `NORMAL`/`RARE`/`EXTREME` tiers across 1997-2023. This changes historical HY-driven combo fire counts (Combo A, G — `combos: [A, B, F, G]` in `CONFIG.yaml`) and any report built on them. See the addendum in `docs/ssi_validation/hy_proxy_consumer_audit_2026-07-29.md`.
- `api/services/portfolio_service.py`'s `hy_is_proxy` flag will now be `False` for virtually all history (previously `True` for 1997-2023-07-13) — its docstring/behavior is unchanged, it will simply reflect the new (mostly non-proxy) reality correctly.
- `src/portfolio_nav/four_book_engine.py::load_hy_mult_series()` reads `daily_readings` directly — no code change needed, but the stress-window numbers in `docs/ssi_validation/ceiling_chain_backfill_2026-07-29.md` (2008/2020/2022 `hy_mult`) should be regenerated since the underlying HY values moved from proxy to real.
- `scripts/recalibrate_hy_oas_proxy.py` (Model v2) is now superseded — its header carries an explicit superseded notice; the file is kept for provenance and as a fallback only.

## Regenerate

```bash
.venv/bin/python scripts/backfill_hy_oas_from_wayback.py --apply
```
