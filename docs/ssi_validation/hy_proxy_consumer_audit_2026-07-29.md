# HY OAS Proxy — Consumer Audit

**Date:** 2026-07-29
**Trigger:** Macro regime system fix-to-spec plan, work item 1, action 2 — "Audit every consumer
that reads the HY variable ... and confirm each one either checks `signal_tier == 'PROXY'` or is
documented as accepting the proxy." Open item carried over from the 2026-06-06 data gap report.

**Companion doc:** `docs/ssi_validation/hy_oas_recalibration_2026-07-29.md` (Model v2 calibration
that this audit's fixes build on top of).

## Summary table

| Consumer | Reads PROXY-tagged `HY`? | Tier-aware today? | Status after this audit |
|---|---|---|---|
| `combo_detector.evaluate_combo_b_legs` (Combo B) | Yes, via `daily_readings.HY` | No explicit tier check, but uses numeric `raw_value`/percentile directly | **Improved as a side effect** — now benefits from the Model v2 recalibration + full percentile recompute (see hy-calibration). No code change needed; documented. |
| `combo_detector._is_rare_or_extreme` (Combo A HY leg) | Yes, via `signal_tier` | Checks tier, but PROXY-era rows are blanket-tagged `'PROXY'` (never `RARE`/`EXTREME`) | **Closed 2026-08-02** (see addendum below) — the wayback backfill gave 1,786 of 6,933 pre-2023-07-13 dates real `RARE`/`EXTREME` tiers (was 0 before), so this check now works correctly for virtually all of history. No code change needed; fixed as a byproduct of real data replacing the proxy. |
| `combo_detector._hy_4wk_change_bps` (Combo G HY leg) | **No** — bypasses `daily_readings` entirely, calls FRED live | N/A | **Documented gap, not fixed.** Since the Apr-2026 FRED 3yr licensing cap, this silently returns `None` (via a bare `except Exception`) for any `as_of` older than FRED's live rolling window, so Combo G's HY leg cannot fire outside that window. Not caused by the June proxy backfill — a consequence of the FRED relicensing. Docstring added in code. |
| `portfolio_service._compute_ceiling` (deployment ceiling HY multiplier) | Reads `hy_var.get("current")` from `runic_output.json`'s `variables_dashboard` | **Was not tier-aware at all** | **Fixed.** Now reads `hy_var.get("tier")`, exposes `hy_tier` / `hy_is_proxy` in the response, and appends a `[PROXY: ...]` marker to `hy_note` when applicable. No behavior change today (this function only ever runs for *today's* date, which has been in the real-data era since 2023-06-09) — this closes the gap for when `ceiling-chain-backfill` (later plan item) starts calling it, or an equivalent, for historical dates. |
| `four_book_engine.py` (four-book ceiling replay) | **No** — confirmed zero references to `HY` or any credit-spread variable anywhere in this file | N/A | No action needed today. Its own docstring already states the ceiling replay is SSI-only and does not include the full `regime_max × VIX × trend × HY × SSI` chain. This is exactly the gap `ceiling-chain-backfill` is scoped to close later. |
| SSI Layer-2 "HYG/LQD" vote (`src/sentiment_superindex/engine/layer2.py`) | **No** — confirmed this uses `hyg_lqd_ratio()` (`src/sentiment_superindex/data/yahoo_inputs.py`), a Yahoo Finance **HYG/LQD ETF price ratio**, entirely independent of `daily_readings.var_id='HY'` / FRED `BAMLH0A0HYM2` | N/A — not the same variable | **Not affected by the HY OAS proxy issue at all.** This is a different, always-free, always-real market-price signal. Its own (much smaller, non-blocking) data-depth limit is HYG's 2007 inception / LQD's 2002 inception — a distinct, pre-existing constraint, not part of this audit's scope. |

## Detail — fixes applied

### `api/services/portfolio_service.py::_compute_ceiling`

Added:
```python
hy_tier: str | None = hy_var.get("tier")
hy_is_proxy: bool = hy_tier == "PROXY"
```
and surfaced `hy_tier` / `hy_is_proxy` in the returned dict, plus a `[PROXY: ...]` suffix on
`hy_note` when `hy_is_proxy` is true. `variables_dashboard` already carried a `"tier"` field
(`src/macro_intelligence/jobs/nightly_run.py::_variables_dashboard`) that this function was
simply not reading before.

### `src/macro_intelligence/engine/combo_detector.py`

Added explanatory docstrings to `_is_rare_or_extreme` and `_hy_4wk_change_bps` documenting the
two PROXY-era blind spots found above. No behavior change — both are pre-existing, and changing
either would retroactively alter historical Combo A / Combo G fire counts used in past backtests,
which is a bigger call than this audit pass is scoped to make.

## Detail — no action needed

- Combo B (`evaluate_combo_b_legs`) reads `daily_readings.HY` numerically (raw_value + percentile,
  not tier), so it automatically benefited from the Model v2 recalibration and full percentile
  recompute done in the same session (see `hy_oas_recalibration_2026-07-29.md`). No further change
  needed here.
- `four_book_engine.py` has no HY exposure today — tracked separately under `ceiling-chain-backfill`.
- SSI Layer-2 hyg_lqd vote is a different, independently-sourced, always-real signal — out of
  scope for the HY OAS proxy issue.

## Open follow-ups (not closed by this audit, tracked separately)

1. `ceiling-chain-backfill` (separate plan item): when the HY leg of the four-book ceiling replay
   is built, it must inherit the `hy_tier`/`hy_is_proxy` pattern added to `_compute_ceiling` here,
   and any pre-2023 dates in that backfill are bounded by the same proxy-accuracy limits described
   in `hy_oas_recalibration_2026-07-29.md`.
2. ~~Combo A / Combo G's PROXY-era blind spots are documented, not fixed.~~ **Combo A's blind spot
   is now closed as a byproduct of the 2026-08-02 wayback backfill — see addendum below.** Combo
   G's remains open (different root cause, see addendum).

## Addendum — 2026-08-02 (HY OAS wayback backfill closes the Combo A blind spot)

`scripts/backfill_hy_oas_from_wayback.py` replaced 6,620 of 6,627 `PROXY`-tagged HY rows with
real ICE OAS and real `NORMAL`/`RARE`/`EXTREME` tiers (see
`docs/ssi_validation/hy_oas_wayback_backfill_2026-08-02.md`). This retroactively closes item 2
above for **Combo A** but not for **Combo G** — the two blind spots had different root causes:

| | Root cause | Fixed by the wayback backfill? |
|---|---|---|
| Combo A `_is_rare_or_extreme` (`combo_detector.py`) | Read `daily_readings.signal_tier`, which was blanket `'PROXY'` (never `RARE`/`EXTREME`) pre-2023-07-13 | **Yes, automatically.** The function's logic never changed — it already checked the real tier column; that column now holds real tiers instead of a blanket `PROXY` string. |
| Combo G `_hy_4wk_change_bps` (`combo_detector.py`) | Bypasses `daily_readings` entirely, calls `fetch_fred_series("BAMLH0A0HYM2", ...)` (live FRED) directly | **No.** This function never reads `daily_readings.HY` at all, so backfilling that table has zero effect on it. Still capped by FRED's live rolling-3yr window. Docstring updated in code to clarify this distinction; no functional change made (would require rerouting the function to read `daily_readings.HY`, a separate decision, not made here to avoid silently changing Combo G's historical fire behavior). |

**Before/after magnitude for Combo A's HY leg** (measured directly against `runic.db`,
2026-08-02): of the 6,933 HY dates on/before 2023-07-13, **0 were `RARE`/`EXTREME` before** this
backfill (blanket `PROXY`) — **1,786 (25.8%) are `RARE`/`EXTREME` after**. This is an upper bound
on how many additional days Combo A's HY leg can now contribute a rare/extreme vote (actually
firing still requires ≥2 of the 4 Combo A legs to agree and a non-`CONTESTED` direction vote —
this number is *not* itself a change in Combo A fire *count*, it is the size of the underlying
tier-availability change that feeds into that count). Anyone citing historical Combo A fire
counts for dates before 2023-07-13 from before 2026-08-02 must re-run them — see
`retroactive-recompute` in the free-source backfill plan for the full regression re-check.
