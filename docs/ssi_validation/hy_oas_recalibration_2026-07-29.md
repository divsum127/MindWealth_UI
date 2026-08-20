# HY OAS Proxy Recalibration — Model v2 (VIX-amplified)

**Date:** 2026-07-29
**Status:** APPLIED to runic.db
**Related:** `docs/ssi_validation/data_gap_report_2026-06-06.md`, `docs/MACRO_INTELLIGENCE_MASTER.md` §HY Credit Spreads OAS

## Still a proxy — what this does NOT fix

Real ICE BofA HY OAS (`BAMLH0A0HYM2`) full history remains **paid-only**. FRED's own free API/CSV was relicensed to a rolling 3-year window starting **April 2026** — confirmed live on 2026-07-29 (`fredgraph.csv?id=BAMLH0A0HYM2&cosd=1996-01-01` returns data starting 2023-07-31 regardless of the requested start date). Rows before the real-data cutoff stay tagged `signal_tier='PROXY'` (6627 rows) — no consumer that already checks this tag needs to change.

## What changed — Model v2

The 2026-06 backfill used a single flat linear regression (`HY = 2.0528*BAA10Y - 0.1833`, R²=0.40, n=153) that is well-documented to understate 2008/2020/2022 blowouts, because linear regression fit only on calm-market co-movement cannot capture how much more convexly HY spreads widen vs investment-grade (BAA10Y) spreads in real credit stress.

**Model v2** adds a VIX-driven stress multiplier on top of a (re-fit) calm linear baseline:

```
calm_baseline(BAA10Y) = 1.9462 * BAA10Y + -0.0329   (fit on n=761 real ICE OAS rows)
stress_multiplier(VIX) = 1                              for VIX <= 25
                       = (VIX / 25) ** 0.4381                for VIX > 25
predicted_HY = calm_baseline(BAA10Y) * stress_multiplier(VIX)
```

`VIX_STRESS_THRESHOLD = 25` reuses the existing `CONFIG.yaml` VIX "rare" `abs_level` convention rather than inventing a new constant.

## Calibration anchors (public, independently documented — not the licensed ICE series)

| Date | Event | Known real HY OAS | Source basis |
|------|-------|--------------------|--------------|
| 2008-11-20 | GFC peak | 2100bps | GFC peak; sources range 2,020-2,150bps, using 2,100bps consensus |
| 2020-03-23 | COVID peak | 1087bps | COVID peak; tightly agreed (1,087bps) across independent sources |
| 2022-07-01 | 2022 rate-shock peak, ~600bps (also cited for Oct 2022) | 600bps | 2022 rate-shock peak, ~600bps (also cited for Oct 2022) |

Cross-checked against 4+ independent sources (FRED series notes, QuantSandbox, RecessionPulse, CFA Institute Enterprising Investor, Convex, contemporaneous financial press) on 2026-07-29. These are widely-cited summary statistics, not a redistribution of ICE's licensed daily series — the same category of public fact as "the S&P 500 fell 34% in March 2020".

## Anchor fit — old vs new model

| Date | BAA10Y | VIX | Known real | Old model (v1) | Old error | New model (v2) | New error |
|------|--------|-----|------------|-----------------|-----------|-----------------|-----------|
| 2008-11-20 | 5.92 | 80.9 | 2100bps | 1197bps | -43.0% | 1921bps | -8.5% |
| 2020-03-23 | 4.31 | 61.6 | 1087bps | 866bps | -20.3% | 1240bps | +14.1% |
| 2022-07-01 | 2.42 | 26.7 | 600bps | 478bps | -20.3% | 481bps | -19.8% |

**R² on the calm real-OAS overlap sample:** old model = 0.3593, new model = 0.3731 (new model does not sacrifice calm-period fit quality to gain tail accuracy).

## Honest limitation — 2022 is not well fixed

2022's credit stress was HY-specific/technical (rate-shock driven), without a proportional investment-grade (BAA10Y) move, and VIX was only moderately elevated (~27) that day. A BAA10Y+VIX proxy structurally cannot see this kind of stress well. This is a genuine, known limitation of the recalibration, not a bug — do not present the 2022 result as fixed.

## Sanity check — other historical vol spikes (NOT used for calibration)

| Date | Event | BAA10Y | VIX | Old model | New model |
|------|-------|--------|-----|-----------|-----------|
| 2015-08-24 | China deval flash crash | 3.14 | 40.7 | 626bps | 753bps |
| 2018-02-05 | Feb 2018 Volmageddon | 1.63 | 37.3 | 316bps | 374bps |
| 2018-12-24 | Dec 2018 selloff | 2.35 | 36.1 | 464bps | 533bps |
| 2011-08-08 | 2011 US downgrade / Euro crisis | 2.88 | 48.0 | 573bps | 742bps |

## Percentile recompute

HY uses a rolling-3-year percentile window (`CONFIG.yaml: pctile_window: rolling_3y`). Because real-tier rows (n=770, 2023-06-09 onward) still have a 3-year lookback window that includes pre-2023-07-13 PROXY history for most of their existence so far (real history only exceeds 3 years starting mid-2026), **every** HY date's `pctile_rank_3yr` / `unconditional_pctile` was recomputed against the updated series, not just PROXY-era dates. `raw_value` for real-tier rows was never modified — only their percentile columns, which depend on now-recalibrated proxy history in their lookback window.

## Regenerate

```bash
.venv/bin/python scripts/recalibrate_hy_oas_proxy.py --apply
```
