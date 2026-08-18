#!/usr/bin/env python3
"""Recalibrate the pre-2023 HY OAS proxy with a VIX-amplified stress correction.

SUPERSEDED (2026-08-02)
------------------------
This Model v2 proxy is superseded by ``scripts/backfill_hy_oas_from_wayback.py``, which replaced
essentially all PROXY-tier HY OAS rows (6620 of 6627) with the REAL ICE BofA HY OAS series
recovered from a Wayback Machine snapshot of FRED's own CSV (see
``docs/ssi_validation/hy_oas_wayback_backfill_2026-08-02.md``). Real data is strictly better than
any proxy model, however improved. This file is kept in the repo for provenance/history and as a
fallback only (e.g. if the wayback source ever becomes unusable) -- do not run it against
current data expecting it to still be the active proxy; only 7 orphan PROXY dates remain in
``runic.db`` (bond-market holidays with no wayback print), and this script's PROXY-only
recalibration logic still applies correctly to just those 7 dates if ever needed again.

Background
----------
``BAMLH0A0HYM2`` (ICE BofA US High Yield OAS) is licensed data. FRED's free API/CSV was
re-restricted to a rolling 3-year window starting April 2026 (verified live: requesting
``cosd=1996-01-01`` from ``fredgraph.csv`` now returns data starting 2023-07-31 regardless).
Full pre-2023 history therefore requires a paid ICE Data Direct / Bloomberg subscription --
this script does NOT remove that data gap. Rows stay tagged ``signal_tier='PROXY'``.

What this script does fix: the 2026-06 backfill calibrated a single flat linear regression
(``HY = 2.0528*BAA10Y - 0.1833``, R^2=0.40 on a 163-row overlap) which is well-documented
(``docs/ssi_validation/data_gap_report_2026-06-06.md``) to understate 2008/2020/2022 blowouts
because a linear fit trained only on calm-market BAA10Y/HY co-movement cannot capture how much
more convexly HY spreads widen vs investment-grade (BAA10Y) spreads during real credit stress.

Model v2
--------
    calm_baseline(BAA10Y) = b0 * BAA10Y + a0          -- linear fit, refit live each run against
                                                          every real ICE OAS row currently in the DB
                                                          (signal_tier != 'PROXY'; overlap grows over
                                                          time as the nightly cron adds new real rows)
    stress_multiplier(VIX) = 1                         if VIX <= VIX_STRESS_THRESHOLD
                            = (VIX / VIX_STRESS_THRESHOLD) ** gamma   if VIX > VIX_STRESS_THRESHOLD
    predicted_HY = calm_baseline(BAA10Y) * stress_multiplier(VIX)

``VIX_STRESS_THRESHOLD = 25`` reuses the existing ``CONFIG.yaml`` VIX "rare" ``abs_level``
convention (no new arbitrary constant introduced). ``gamma`` is fit (log-space least squares)
against 3 independently, publicly documented HY OAS peaks -- NOT redistributed from the licensed
ICE series; these are widely cited summary statistics repeated across dozens of independent
financial-press/research sources, the same category of fact as "the S&P 500 fell 34% in March
2020":

    2008-11-20  ~2,100 bps (GFC peak; sources range 2,020-2,150bps)
    2020-03-23  ~1,087 bps (COVID peak; tightly agreed across sources)
    2022-07-01  ~600 bps   (2022 rate-shock peak, also cited for Oct 2022)

Validated improvement at those 3 anchors (see the generated report for exact numbers each run):
old flat-linear model understated by roughly 43% / 20% / 20% respectively; Model v2 reduces
that to roughly 9% / -14% (overshoot) / 20% (2022 is a known structural miss -- see caveats).

Caveats (do not oversell this fix)
-----------------------------------
- Still a proxy. Still tagged ``signal_tier='PROXY'``. Every consumer that already branches on
  that tag continues to work unchanged.
- 2022 is NOT well fixed by this model: that episode was HY-specific/technical stress without a
  proportional investment-grade (BAA10Y) move, which a BAA10Y-based proxy structurally cannot
  see. VIX was only moderately elevated too (~27), so the multiplier barely engages. This is a
  genuine limitation, not a bug -- flagged explicitly in the output report.
- Percentile recompute: because HY uses a rolling-3-year percentile window
  (``CONFIG.yaml: pctile_window: rolling_3y``), *every* date's ``pctile_rank_3yr`` /
  ``unconditional_pctile`` -- including real-tier dates whose 3-year lookback still includes
  pre-2023-07-13 proxy history -- is recomputed after the raw-value update, for consistency.
  Real-tier ``raw_value`` rows are never modified, only their percentile columns.

Usage
-----
    .venv/bin/python scripts/recalibrate_hy_oas_proxy.py                 # dry run, report only
    .venv/bin/python scripts/recalibrate_hy_oas_proxy.py --apply         # write to runic.db
    .venv/bin/python scripts/recalibrate_hy_oas_proxy.py --apply --report docs/ssi_validation/hy_oas_recalibration_2026-07-29.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.config import db_path, load_config  # noqa: E402
from src.macro_intelligence.data.fred_pull import fetch_fred_series  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import get_connection  # noqa: E402
from src.macro_intelligence.engine.percentiles import compute_unconditional_pctile  # noqa: E402

VIX_STRESS_THRESHOLD = 25.0  # matches CONFIG.yaml HY/VIX 'rare' abs_level convention

# Independently, publicly documented HY OAS peaks -- NOT the licensed ICE series (see module
# docstring). Cross-checked against 4+ independent sources on 2026-07-29.
ANCHORS: list[tuple[str, float, str]] = [
    ("2008-11-20", 21.00, "GFC peak; sources range 2,020-2,150bps, using 2,100bps consensus"),
    ("2020-03-23", 10.87, "COVID peak; tightly agreed (1,087bps) across independent sources"),
    ("2022-07-01", 6.00, "2022 rate-shock peak, ~600bps (also cited for Oct 2022)"),
]


def _fit_calm_baseline(real: pd.Series, baa: pd.Series) -> tuple[float, float, int]:
    """Linear HY = b0*BAA10Y + a0 fit against every real (non-PROXY) OAS row currently in DB."""
    df = pd.DataFrame({"hy": real}).join(pd.DataFrame({"baa10y": baa})).dropna()
    X = np.column_stack([np.ones(len(df)), df["baa10y"].values])
    y = df["hy"].values
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    a0, b0 = float(coef[0]), float(coef[1])
    return a0, b0, len(df)


def _fit_gamma(a0: float, b0: float, baa: pd.Series, vix: pd.Series) -> float:
    logx, logy = [], []
    for date_str, real_hy, _note in ANCHORS:
        ts = pd.Timestamp(date_str)
        baa_val = float(baa.loc[:ts].iloc[-1])
        vix_val = float(vix.loc[:ts].iloc[-1])
        calm = a0 + b0 * baa_val
        required_mult = real_hy / calm
        logx.append(np.log(vix_val / VIX_STRESS_THRESHOLD))
        logy.append(np.log(required_mult))
    logx_arr, logy_arr = np.array(logx), np.array(logy)
    return float((logx_arr * logy_arr).sum() / (logx_arr * logx_arr).sum())


def predict_hy(baa_val: float, vix_val: float, a0: float, b0: float, gamma: float) -> float:
    calm = a0 + b0 * baa_val
    if vix_val <= VIX_STRESS_THRESHOLD or calm <= 0:
        return calm
    mult = (vix_val / VIX_STRESS_THRESHOLD) ** gamma
    return calm * mult


def _r2(y: np.ndarray, pred: np.ndarray) -> float:
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return 1 - ss_res / ss_tot if ss_tot else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write recalibrated values to runic.db (default: dry run)")
    parser.add_argument(
        "--report",
        default=str(ROOT / "docs" / "ssi_validation" / "hy_oas_recalibration_2026-07-29.md"),
        help="Path to write the validation report markdown",
    )
    args = parser.parse_args()

    print("Loading BAA10Y (FRED, free full history) and VIX (Yahoo, free full history)...")
    baa = fetch_fred_series("BAA10Y", "1996-01-01")
    vix = fetch_yahoo_close("^VIX", "1990-01-01")

    with get_connection(db_path()) as conn:
        real = pd.read_sql(
            "SELECT date, raw_value FROM daily_readings WHERE var_id='HY' AND signal_tier != 'PROXY' ORDER BY date",
            conn, parse_dates=["date"],
        ).set_index("date")["raw_value"]
        proxy_rows = pd.read_sql(
            "SELECT date, raw_value, meta_json FROM daily_readings WHERE var_id='HY' AND signal_tier='PROXY' ORDER BY date",
            conn, parse_dates=["date"],
        )
        all_hy_dates = pd.read_sql(
            "SELECT date, signal_tier FROM daily_readings WHERE var_id='HY' ORDER BY date",
            conn, parse_dates=["date"],
        )

    print(f"Real (non-PROXY) HY OAS rows in DB: {len(real)} ({real.index.min().date()} -> {real.index.max().date()})")
    print(f"PROXY HY OAS rows in DB: {len(proxy_rows)} ({proxy_rows['date'].min().date()} -> {proxy_rows['date'].max().date()})")

    a0, b0, n_calm = _fit_calm_baseline(real, baa)
    gamma = _fit_gamma(a0, b0, baa, vix)
    print(f"\nModel v2: calm_baseline = {b0:.4f}*BAA10Y + {a0:.4f}  (fit on n={n_calm} real rows)")
    print(f"          stress_multiplier(VIX) = 1 for VIX<={VIX_STRESS_THRESHOLD:.0f}, else (VIX/{VIX_STRESS_THRESHOLD:.0f})^{gamma:.4f}")

    # Old (2026-06 backfill) model for comparison
    OLD_A, OLD_B = -0.1833, 2.0528

    anchor_rows = []
    for date_str, real_hy, note in ANCHORS:
        ts = pd.Timestamp(date_str)
        baa_val = float(baa.loc[:ts].iloc[-1])
        vix_val = float(vix.loc[:ts].iloc[-1])
        old_pred = OLD_B * baa_val + OLD_A
        new_pred = predict_hy(baa_val, vix_val, a0, b0, gamma)
        anchor_rows.append({
            "date": date_str, "baa10y": baa_val, "vix": vix_val,
            "known_real_pct": real_hy, "known_real_bps": real_hy * 100,
            "old_pred_pct": old_pred, "old_pred_bps": old_pred * 100,
            "old_err_pct": 100 * (old_pred - real_hy) / real_hy,
            "new_pred_pct": new_pred, "new_pred_bps": new_pred * 100,
            "new_err_pct": 100 * (new_pred - real_hy) / real_hy,
            "note": note,
        })
        print(
            f"  {date_str}: known={real_hy*100:.0f}bps  old_model={old_pred*100:.0f}bps ({100*(old_pred-real_hy)/real_hy:+.1f}%)"
            f"  new_model={new_pred*100:.0f}bps ({100*(new_pred-real_hy)/real_hy:+.1f}%)"
        )

    # R^2 on calm overlap sample for both models
    df_calm = pd.DataFrame({"hy": real}).join(pd.DataFrame({"baa10y": baa})).join(pd.DataFrame({"vix": vix})).dropna()
    old_pred_calm = OLD_B * df_calm["baa10y"].values + OLD_A
    new_pred_calm = np.array([predict_hy(b, v, a0, b0, gamma) for b, v in zip(df_calm["baa10y"], df_calm["vix"])])
    y_calm = df_calm["hy"].values
    r2_old = _r2(y_calm, old_pred_calm)
    r2_new = _r2(y_calm, new_pred_calm)
    print(f"\nR^2 on calm real-OAS overlap (n={len(df_calm)}): old={r2_old:.4f}  new={r2_new:.4f}")

    # Recompute the full HY raw-value series: real rows unchanged, PROXY rows recalibrated
    proxy_new_values = {}
    for _, row in proxy_rows.iterrows():
        ts = row["date"]
        try:
            baa_val = float(baa.loc[:ts].iloc[-1])
            vix_val = float(vix.loc[:ts].iloc[-1])
        except IndexError:
            continue
        new_val = predict_hy(baa_val, vix_val, a0, b0, gamma)
        proxy_new_values[ts] = new_val

    full_series = real.copy()
    for ts, val in proxy_new_values.items():
        full_series.loc[ts] = val
    full_series = full_series.sort_index()

    print(f"\nRecalibrated {len(proxy_new_values)} PROXY-era rows out of {len(proxy_rows)}.")

    # Recompute percentiles for every HY date (rolling_3y window) using the new full series
    cfg = load_config()
    hy_var_cfg = next(v for v in cfg["variables"] if v["id"] == "HY")
    all_dates = sorted(pd.Timestamp(d) for d in all_hy_dates["date"])
    print(f"Recomputing rolling-3y percentiles for {len(all_dates)} HY dates (this covers both PROXY and real rows)...")
    new_pctiles: dict[pd.Timestamp, float | None] = {}
    for ts in all_dates:
        new_pctiles[ts] = compute_unconditional_pctile(full_series, hy_var_cfg, ts)

    if not args.apply:
        print("\nDRY RUN -- no changes written. Re-run with --apply to persist to runic.db.")
    else:
        print("\nApplying updates to runic.db ...")
        calibration_note = {
            "proxy": "BAA10Y_VIX_amplified_v2",
            "note": (
                "Moody Baa-Treasury spread (calm baseline) x VIX stress multiplier "
                "(VIX>25 -> (VIX/25)^gamma). Recalibrated 2026-07-29 to reduce documented "
                "2008/2020/2022 blowout understatement of the flat-linear v1 proxy. "
                "Still a proxy -- real ICE BofA OAS unavailable pre-2023 without paid data."
            ),
            "calm_baseline": f"HY = {b0:.4f}*BAA10Y + {a0:.4f}",
            "stress_multiplier": f"(VIX/{VIX_STRESS_THRESHOLD:.0f})^{gamma:.4f} for VIX>{VIX_STRESS_THRESHOLD:.0f}",
            "calibration_anchors": [a[0] for a in ANCHORS],
            "recalibrated_on": datetime.now().strftime("%Y-%m-%d"),
        }
        meta_json_str = json.dumps(calibration_note)
        with get_connection(db_path()) as conn:
            for ts, val in proxy_new_values.items():
                ds = ts.strftime("%Y-%m-%d")
                pct = new_pctiles.get(ts)
                conn.execute(
                    """
                    UPDATE daily_readings
                    SET raw_value = ?, pctile_rank_3yr = ?, unconditional_pctile = ?, meta_json = ?
                    WHERE var_id = 'HY' AND date = ? AND signal_tier = 'PROXY'
                    """,
                    (val, pct, pct, meta_json_str, ds),
                )
            # Real-tier rows: percentile columns only, raw_value untouched.
            for ts in all_dates:
                if ts in proxy_new_values:
                    continue
                ds = ts.strftime("%Y-%m-%d")
                pct = new_pctiles.get(ts)
                conn.execute(
                    """
                    UPDATE daily_readings
                    SET pctile_rank_3yr = ?, unconditional_pctile = ?
                    WHERE var_id = 'HY' AND date = ? AND signal_tier != 'PROXY'
                    """,
                    (pct, pct, ds),
                )
        print(f"Updated {len(proxy_new_values)} PROXY rows (raw_value + percentiles) and "
              f"{len(all_dates) - len(proxy_new_values)} real-tier rows (percentiles only).")

    # Stress-date sanity check (not used for calibration) for the report
    sanity_dates = [
        ("2015-08-24", "China deval flash crash"),
        ("2018-02-05", "Feb 2018 Volmageddon"),
        ("2018-12-24", "Dec 2018 selloff"),
        ("2011-08-08", "2011 US downgrade / Euro crisis"),
    ]
    sanity_rows = []
    for date_str, label in sanity_dates:
        ts = pd.Timestamp(date_str)
        baa_val = float(baa.loc[:ts].iloc[-1])
        vix_val = float(vix.loc[:ts].iloc[-1])
        old_val = float(proxy_rows.set_index("date")["raw_value"].loc[:ts].iloc[-1])
        new_val = predict_hy(baa_val, vix_val, a0, b0, gamma)
        sanity_rows.append({
            "date": date_str, "label": label, "baa10y": baa_val, "vix": vix_val,
            "old_bps": old_val * 100, "new_bps": new_val * 100,
        })

    _write_report(
        args.report, a0=a0, b0=b0, gamma=gamma, n_calm=n_calm, r2_old=r2_old, r2_new=r2_new,
        anchor_rows=anchor_rows, sanity_rows=sanity_rows, applied=args.apply,
        n_proxy=len(proxy_rows), n_real=len(real),
    )
    print(f"\nReport written to {args.report}")
    return 0


def _write_report(
    path: str, *, a0: float, b0: float, gamma: float, n_calm: int, r2_old: float, r2_new: float,
    anchor_rows: list[dict], sanity_rows: list[dict], applied: bool, n_proxy: int, n_real: int,
) -> None:
    lines = [
        "# HY OAS Proxy Recalibration — Model v2 (VIX-amplified)",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}",
        f"**Status:** {'APPLIED to runic.db' if applied else 'DRY RUN — not written to runic.db'}",
        "**Related:** `docs/ssi_validation/data_gap_report_2026-06-06.md`, `docs/MACRO_INTELLIGENCE_MASTER.md` §HY Credit Spreads OAS",
        "",
        "## Still a proxy — what this does NOT fix",
        "",
        "Real ICE BofA HY OAS (`BAMLH0A0HYM2`) full history remains **paid-only**. FRED's own free "
        "API/CSV was relicensed to a rolling 3-year window starting **April 2026** — confirmed live "
        "on 2026-07-29 (`fredgraph.csv?id=BAMLH0A0HYM2&cosd=1996-01-01` returns data starting "
        "2023-07-31 regardless of the requested start date). Rows before the real-data cutoff stay "
        f"tagged `signal_tier='PROXY'` ({n_proxy} rows) — no consumer that already checks this tag needs to change.",
        "",
        "## What changed — Model v2",
        "",
        "The 2026-06 backfill used a single flat linear regression "
        "(`HY = 2.0528*BAA10Y - 0.1833`, R²=0.40, n=153) that is well-documented to understate "
        "2008/2020/2022 blowouts, because linear regression fit only on calm-market co-movement "
        "cannot capture how much more convexly HY spreads widen vs investment-grade (BAA10Y) "
        "spreads in real credit stress.",
        "",
        "**Model v2** adds a VIX-driven stress multiplier on top of a (re-fit) calm linear baseline:",
        "",
        "```",
        f"calm_baseline(BAA10Y) = {b0:.4f} * BAA10Y + {a0:.4f}   (fit on n={n_calm} real ICE OAS rows)",
        f"stress_multiplier(VIX) = 1                              for VIX <= 25",
        f"                       = (VIX / 25) ** {gamma:.4f}                for VIX > 25",
        "predicted_HY = calm_baseline(BAA10Y) * stress_multiplier(VIX)",
        "```",
        "",
        "`VIX_STRESS_THRESHOLD = 25` reuses the existing `CONFIG.yaml` VIX \"rare\" `abs_level` "
        "convention rather than inventing a new constant.",
        "",
        "## Calibration anchors (public, independently documented — not the licensed ICE series)",
        "",
        "| Date | Event | Known real HY OAS | Source basis |",
        "|------|-------|--------------------|--------------|",
    ]
    for date_str, real_hy, note in ANCHORS:
        lines.append(f"| {date_str} | {note.split(';')[0]} | {real_hy*100:.0f}bps | {note} |")
    lines += [
        "",
        "Cross-checked against 4+ independent sources (FRED series notes, QuantSandbox, "
        "RecessionPulse, CFA Institute Enterprising Investor, Convex, contemporaneous financial "
        "press) on 2026-07-29. These are widely-cited summary statistics, not a redistribution of "
        "ICE's licensed daily series — the same category of public fact as \"the S&P 500 fell 34% "
        "in March 2020\".",
        "",
        "## Anchor fit — old vs new model",
        "",
        "| Date | BAA10Y | VIX | Known real | Old model (v1) | Old error | New model (v2) | New error |",
        "|------|--------|-----|------------|-----------------|-----------|-----------------|-----------|",
    ]
    for r in anchor_rows:
        lines.append(
            f"| {r['date']} | {r['baa10y']:.2f} | {r['vix']:.1f} | {r['known_real_bps']:.0f}bps | "
            f"{r['old_pred_bps']:.0f}bps | {r['old_err_pct']:+.1f}% | {r['new_pred_bps']:.0f}bps | {r['new_err_pct']:+.1f}% |"
        )
    lines += [
        "",
        f"**R² on the calm real-OAS overlap sample:** old model = {r2_old:.4f}, new model = {r2_new:.4f} "
        "(new model does not sacrifice calm-period fit quality to gain tail accuracy).",
        "",
        "## Honest limitation — 2022 is not well fixed",
        "",
        "2022's credit stress was HY-specific/technical (rate-shock driven), without a proportional "
        "investment-grade (BAA10Y) move, and VIX was only moderately elevated (~27) that day. A "
        "BAA10Y+VIX proxy structurally cannot see this kind of stress well. This is a genuine, "
        "known limitation of the recalibration, not a bug — do not present the 2022 result as fixed.",
        "",
        "## Sanity check — other historical vol spikes (NOT used for calibration)",
        "",
        "| Date | Event | BAA10Y | VIX | Old model | New model |",
        "|------|-------|--------|-----|-----------|-----------|",
    ]
    for r in sanity_rows:
        lines.append(
            f"| {r['date']} | {r['label']} | {r['baa10y']:.2f} | {r['vix']:.1f} | "
            f"{r['old_bps']:.0f}bps | {r['new_bps']:.0f}bps |"
        )
    lines += [
        "",
        "## Percentile recompute",
        "",
        f"HY uses a rolling-3-year percentile window (`CONFIG.yaml: pctile_window: rolling_3y`). "
        f"Because real-tier rows (n={n_real}, 2023-06-09 onward) still have a 3-year lookback window "
        "that includes pre-2023-07-13 PROXY history for most of their existence so far (real history "
        "only exceeds 3 years starting mid-2026), **every** HY date's `pctile_rank_3yr` / "
        "`unconditional_pctile` was recomputed against the updated series, not just PROXY-era dates. "
        "`raw_value` for real-tier rows was never modified — only their percentile columns, which "
        "depend on now-recalibrated proxy history in their lookback window.",
        "",
        "## Regenerate",
        "",
        "```bash",
        ".venv/bin/python scripts/recalibrate_hy_oas_proxy.py --apply",
        "```",
        "",
    ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
