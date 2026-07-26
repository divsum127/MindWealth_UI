#!/usr/bin/env python
"""Daily portfolio book-state snapshot — run once per trading day (market close).

"Set up books from today": conviction overlay history only goes back to 2026-05-15, and no
eviction/slot-occupancy or regime-bucket history exists anywhere in production. Rather than
fabricate a backfill, this job starts capturing exact per-position state (sleeve, conviction
tier + multiplier, SSI ceiling scalar, regime bucket, true weight, size) from today forward, so
D1 slot audits, the four-book NAV replay, and Ahil's regime-bucket series are exact and
reproducible going forward without ever re-deriving history after the fact.

Usage: python scripts/run_portfolio_book_snapshot_daily.py [--date YYYY-MM-DD] [--scenario normal]

Cron: installed by scripts/install_aws_cron.sh alongside the SSI/macro jobs, after market
close on trading days.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_portfolio_book_snapshot_daily")


def _regime_bucket_label(ceiling: dict[str, Any]) -> str:
    """Coarse regime-bucket classification from the live deployment-ceiling chain.

    Combines VIX regime + SPX trend + HY credit state into one label — this is what Ahil's
    A1 four-book re-run reports SSI/Conviction effects against (per regime bucket, Axiom 6).
    """
    vix_regime = str(ceiling.get("vix_regime") or "NORMAL")
    above_ma = bool((ceiling.get("spx_trend_meta") or {}).get("above_ma200", True))
    hy_bps = ceiling.get("hy_bps")
    hy_stress = hy_bps is not None and hy_bps > 400
    if vix_regime == "STRESS" or hy_stress:
        return "STRESS"
    if not above_ma:
        return "BEAR_TREND"
    if vix_regime == "LOW_VOL":
        return "LOW_VOL"
    return "NORMAL"


def run_snapshot(snapshot_date: str, scenario: str = "normal") -> dict[str, Any]:
    from api.services import portfolio_service as portfolio_svc
    from src.portfolio_nav import book_snapshot_store as store

    sizer = portfolio_svc.get_portfolio_sizer(scenario=scenario)
    ceiling = sizer.get("ceiling") or {}
    regime_bucket = _regime_bucket_label(ceiling)

    rows: list[dict[str, Any]] = []
    for cluster in sizer.get("clusters", []):
        for pos in cluster.get("positions", []):
            if pos.get("blocked"):
                continue
            rows.append({
                "ticker": pos.get("ticker"),
                "function": pos.get("function"),
                "interval": pos.get("interval"),
                "direction": pos.get("direction"),
                "sleeve_id": cluster.get("id"),
                "sleeve_label": cluster.get("label"),
                "conviction_tier": str(pos.get("size_tier") or "").split()[0] or None,
                "conviction_multiplier": pos.get("conviction_multiplier"),
                "ssi_ceiling_scalar": ceiling.get("ssi_multiplier"),
                "regime_bucket": regime_bucket,
                "true_weight_pct": pos.get("allocation_pct"),
                "size_usd": pos.get("allocation_usd"),
                # slot_index / eviction_margin populate once the D1 slot + eviction engines are wired in.
                "slot_index": None,
                "eviction_margin": None,
            })

    written = store.write_position_snapshots(snapshot_date, rows, scenario=scenario)
    store.write_regime_bucket(
        snapshot_date,
        scenario=scenario,
        regime_bucket=regime_bucket,
        vix_regime=ceiling.get("vix_regime"),
        val_regime=ceiling.get("val_regime"),
        final_ceiling_pct=ceiling.get("final_ceiling_pct"),
        formula_text=ceiling.get("formula_text"),
    )
    logger.info(
        "Snapshot %s (%s): %d positions, regime_bucket=%s, ceiling=%s%%",
        snapshot_date, scenario, written, regime_bucket, ceiling.get("final_ceiling_pct"),
    )

    # Phase 3 (A1/A2/A3): 1C admission/eviction pass — persisted into eviction_log so
    # D4's exit_type=eviction has ground truth going forward (no history before today).
    eviction_summary: dict[str, Any] = {}
    try:
        from api.services import portfolio_pipeline_service as pipeline_svc

        eviction_summary = pipeline_svc.run_eviction_check("model", snapshot_date=snapshot_date)
        logger.info(
            "Eviction check %s: %d evicted, %d admitted, %d waiting (mode=%s, M=%s)",
            snapshot_date,
            eviction_summary.get("evicted_count"),
            eviction_summary.get("admitted_count"),
            eviction_summary.get("waiting_count"),
            eviction_summary.get("mode"),
            eviction_summary.get("margin_m"),
        )
    except Exception:
        logger.exception("Eviction check failed for %s (non-fatal — snapshot already written)", snapshot_date)

    return {
        "date": snapshot_date,
        "scenario": scenario,
        "positions": written,
        "regime_bucket": regime_bucket,
        "eviction": eviction_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None, help="Snapshot date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--scenario", default="normal", choices=["normal", "stress", "lowvol"])
    args = parser.parse_args()

    snapshot_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        run_snapshot(snapshot_date, scenario=args.scenario)
    except Exception:
        logger.exception("Portfolio book snapshot failed for %s", snapshot_date)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
