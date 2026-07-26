"""API adapter for Ahil nav_engine — implements ``get_nav_history`` for portfolio_nav.service."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.config_paths import BASE_DIR
from src.portfolio_nav import four_book_engine
from src.portfolio_nav import portfolio_sharpe_analysis as psa
from src.portfolio_nav.ahil_nav_engine_core import (
    build_model_approved_trades,
    compute_stats,
    monthly_from_daily,
    run_nav_engine,
)
from src.portfolio_nav.stats import build_daily_nav_points, build_nav_points
from src.portfolio_nav.types import AttributionRow, MonthlyReturn, NavHistoryBundle, NavPoint
from src.portfolio_nav.attribution import attribution_for_book
from src.portfolio_nav.workbook_provider import _load_nav_config

_FOUR_BOOK_IDS = ("base", "ssi", "cv", "enhanced")

logger = logging.getLogger(__name__)


_POLICY_PATH = BASE_DIR / "config" / "portfolio_policy.yaml"


def _load_policy_config() -> dict[str, Any]:
    if not _POLICY_PATH.is_file():
        return {}
    with _POLICY_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _resolve_rebalance_mode() -> tuple[str, str]:
    """(mode, source) — mirrors api/services/policy_service.py:get_rebalance_mode() precedence.

    Kept self-contained (no api.services import) — src/ stays independent of api/, matching
    every other module in this package.
    """
    env_val = os.getenv("PORTFOLIO_REBALANCE_MODE", "").strip().lower()
    if env_val in ("hold_original", "legacy_rebalance"):
        return env_val, "env"
    cfg = _load_policy_config().get("rebalance_mode", {})
    return str(cfg.get("value") or "hold_original"), cfg.get("status", "interim")


def _resolve_n_slots() -> int:
    env_val = os.getenv("PORTFOLIO_N_SLOTS")
    if env_val:
        try:
            return int(float(env_val))
        except ValueError:
            pass
    cfg = _load_policy_config().get("n_slots", {})
    return int(cfg.get("value") or 60)


def _month_label_to_yyyy_mm(mmm_yy: str) -> str:
    from datetime import datetime

    try:
        dt = datetime.strptime(mmm_yy.strip(), "%b-%y")
        return f"{dt.year:04d}-{dt.month:02d}"
    except ValueError:
        return mmm_yy


def _monthly_to_bundle_points(monthly: pd.DataFrame) -> list[NavPoint]:
    labels = monthly["Month"].astype(str).tolist()
    closes = monthly["Closing_NAV"].astype(float).tolist()
    return [
        NavPoint(
            date=str(row["date"]),
            value=float(row["value"]),
            drawdown_pct=float(row["drawdown_pct"]),
            high_water_mark=float(row["high_water_mark"]),
        )
        for row in build_nav_points(labels, closes)
    ]


def _daily_df_to_bundle_points(daily: pd.DataFrame) -> list[NavPoint]:
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in daily.index]
    closes = daily["NAV"].astype(float).tolist()
    return [
        NavPoint(
            date=str(row["date"]),
            value=float(row["value"]),
            drawdown_pct=float(row["drawdown_pct"]),
            high_water_mark=float(row["high_water_mark"]),
        )
        for row in build_daily_nav_points(dates, closes)
    ]


@lru_cache(maxsize=1)
def _compute_engine_series_cached(
    forward_testing_mtime: float,
    use_cache_flag: str,
    rebalance_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Cache Version B/A monthly + daily frames. Keyed on forward_testing dir mtime + rebalance_mode."""
    del use_cache_flag
    cfg = _load_nav_config()
    start_nav = float(cfg.get("research_notional_usd") or 10_000_000)
    root = os.getenv("PORTFOLIO_FORWARD_TESTING_ROOT")
    n_slots = _resolve_n_slots()

    trades_b = build_model_approved_trades(forward_testing_root=root, version="b")
    trades_a = build_model_approved_trades(forward_testing_root=root, version="a")
    price_map, _ = psa.fetch_daily_prices_for_trades(
        trades_b,
        use_cache=os.getenv("PORTFOLIO_NAV_PRICE_CACHE", "1") != "0",
    )

    daily_b = run_nav_engine(
        trades_b, price_map, start_nav=start_nav, rebalance_mode=rebalance_mode, n_target=n_slots,
    )
    daily_a = run_nav_engine(
        trades_a, price_map, start_nav=start_nav, rebalance_mode=rebalance_mode, n_target=n_slots,
    )
    monthly_b = monthly_from_daily(daily_b, start_nav=start_nav)
    monthly_a = monthly_from_daily(daily_a, start_nav=start_nav)
    stats_b = compute_stats(monthly_b, start_nav=start_nav)

    methodology = (
        "Axiom 2 (hold original weight to exit; no rebalance-to-1/N on entry; freed cash "
        "idle until next admitted signal takes the slot)"
        if rebalance_mode == "hold_original"
        else "legacy: rebalance to 1/N on entry, pro-rata redistribution on exit"
    )
    meta = {
        "trade_count_b": len(trades_b),
        "trade_count_a": len(trades_a),
        "asset_count_b": int(trades_b["Symbol"].nunique()),
        "avg_active_n": float(daily_b["N_active"].mean()),
        "max_active_n": int(daily_b["N_active"].max()),
        "engine_cagr_pct": round(float(stats_b["cagr"]) * 100, 2),
        "engine_sharpe": round(float(stats_b["sharpe"]), 3) if stats_b.get("sharpe") == stats_b.get("sharpe") else None,
        "methodology": f"Ahil nav_engine: position-level MTM, {methodology}, dual-gated BT>=70 & FWD combos",
        "rebalance_mode": rebalance_mode,
        "daily_point_count_b": int(len(daily_b)),
        "daily_point_count_a": int(len(daily_a)),
    }
    return monthly_b, monthly_a, daily_b, daily_a, meta


@lru_cache(maxsize=1)
def _compute_four_book_cached(
    forward_testing_mtime: float,
    use_cache_flag: str,
    rebalance_mode: str,
    n_slots: int,
) -> dict[str, Any]:
    """Cache the four-book split (Phase 5 / A1) off the SAME Model Approved trade ledger as
    the B/A monthly engine — see src/portfolio_nav/four_book_engine.py for the rules."""
    del use_cache_flag
    cfg = _load_nav_config()
    start_nav = float(cfg.get("research_notional_usd") or 10_000_000)
    root = os.getenv("PORTFOLIO_FORWARD_TESTING_ROOT")
    trades_b = build_model_approved_trades(forward_testing_root=root, version="b")
    price_map, _ = psa.fetch_daily_prices_for_trades(
        trades_b,
        use_cache=os.getenv("PORTFOLIO_NAV_PRICE_CACHE", "1") != "0",
    )
    result = four_book_engine.run_four_book_engine(
        trades_b, price_map, start_nav=start_nav, n_target=n_slots,
    )
    result["start_nav"] = start_nav
    return result


def _four_book_attribution(
    book: str,
    decomposition: dict[str, Any],
    cv_data_status: dict[str, Any],
) -> list[AttributionRow]:
    """Real (not proxy) attribution rows from four_book_engine's decomposition (Phase 5)."""
    base_pct = decomposition.get("base_cum_return_pct")
    rows = [
        AttributionRow(
            id="base", label="BASE",
            return_pct=base_pct if base_pct is not None else 0.0,
            description="Equal-weight base book (Axiom 2 hold-original), full history",
        ),
    ]
    if book in ("ssi", "cv", "enhanced"):
        ssi_pct = decomposition.get("ssi_cum_return_pct")
        ssi_effect = decomposition.get("ssi_effect_pp")
        rows.append(AttributionRow(
            id="ssi", label="BASE + SSI",
            return_pct=ssi_pct if ssi_pct is not None else (base_pct or 0.0),
            description=f"SSI ceiling overlay effect {ssi_effect:+.2f}pp (full history)" if ssi_effect is not None else "SSI ceiling overlay",
        ))
    if book in ("cv", "enhanced"):
        cv_pct = decomposition.get("cv_cum_return_pct")
        cv_effect = decomposition.get("conviction_effect_pp")
        status_note = cv_data_status.get("note") or ""
        rows.append(AttributionRow(
            id="cv", label="BASE + CONVICTION",
            return_pct=cv_pct if cv_pct is not None else (base_pct or 0.0),
            description=(
                f"Conviction overlay effect {cv_effect:+.2f}pp — {status_note}"
                if cv_effect is not None else status_note or "Conviction overlay unavailable"
            ),
        ))
    if book == "enhanced":
        enhanced_pct = decomposition.get("enhanced_cum_return_pct")
        interaction = decomposition.get("interaction_pp")
        rows.append(AttributionRow(
            id="enhanced", label="ENHANCED",
            return_pct=enhanced_pct if enhanced_pct is not None else (base_pct or 0.0),
            description=(
                f"SSI + Conviction combined, interaction {interaction:+.2f}pp"
                if interaction is not None else "Production settings (SSI + Conviction)"
            ),
        ))
    return rows


def _forward_testing_mtime(root: Path | None = None) -> float:
    base = root or Path(
        os.getenv(
            "PORTFOLIO_FORWARD_TESTING_ROOT",
            str(psa._FORWARD_TESTING_ROOT),  # noqa: SLF001
        )
    )
    if not base.is_dir():
        return 0.0
    mtimes = [p.stat().st_mtime for p in base.glob("*/*/*.csv")]
    return max(mtimes) if mtimes else 0.0


def get_nav_history(
    book: str,
    *,
    forward_testing_root: Path | None = None,
    starting_nav: float = 10_000_000,
    n_slots: int = 60,
) -> NavHistoryBundle:
    """Run Ahil nav_engine and return API-ready NAV history.

    ``book`` selects attribution strip; MTM/closed series are engine-computed for all books
    until SSI/conviction overlay replay ships per-book series.
    """
    del n_slots  # engine uses floating N (concurrent positions), not fixed slot cap
    if forward_testing_root is not None:
        psa.set_forward_testing_root(forward_testing_root)

    mtime = _forward_testing_mtime(forward_testing_root)
    rebalance_mode, rebalance_mode_source = _resolve_rebalance_mode()
    monthly_b, monthly_a, daily_b, daily_a, meta = _compute_engine_series_cached(
        mtime,
        os.getenv("PORTFOLIO_NAV_PRICE_CACHE", "1"),
        rebalance_mode,
    )
    n_slots_active = _resolve_n_slots()

    # Phase 5 (A1): base/ssi/cv/enhanced each get their OWN daily/monthly series and REAL
    # (not proxy) attribution when four_book_engine has data for that book. Falls back to the
    # B/A engine's series + proxy attribution only if the four-book split itself fails.
    book_daily = daily_b
    book_monthly = monthly_b
    attribution_rows: list[AttributionRow] = attribution_for_book(book)
    data_status: dict[str, Any] | None = None
    four_book_note = ""
    if book in _FOUR_BOOK_IDS:
        try:
            four_book = _compute_four_book_cached(
                mtime, os.getenv("PORTFOLIO_NAV_PRICE_CACHE", "1"), rebalance_mode, n_slots_active,
            )
            book_series = four_book.get(book)
            if book_series is not None and not book_series.empty:
                book_daily = book_series
                book_monthly = monthly_from_daily(book_series, start_nav=four_book["start_nav"])
                attribution_rows = _four_book_attribution(
                    book, four_book["decomposition"], four_book.get("cv_data_status") or {},
                )
                four_book_note = " Four-book split (Phase 5/A1) — real per-book series, not proxy."
            elif book in ("cv", "enhanced"):
                data_status = four_book.get("cv_data_status") or {"status": "unavailable"}
                four_book_note = f" book={book}: {data_status.get('note') or data_status.get('reason') or 'no conviction data yet'}"
        except Exception as exc:
            logger.warning("four_book_engine failed for book=%s (%s); falling back to B/A series", book, exc)

    mtm_points = _monthly_to_bundle_points(book_monthly)
    closed_points = _monthly_to_bundle_points(monthly_a)
    mtm_daily_points = _daily_df_to_bundle_points(book_daily)
    closed_daily_points = _daily_df_to_bundle_points(daily_a)

    monthly_returns = [
        MonthlyReturn(
            month=_month_label_to_yyyy_mm(row["Month"]),
            return_pct=round(float(row["Monthly_Return"]) * 100.0, 2),
        )
        for _, row in book_monthly.iterrows()
        if pd.notna(row.get("Monthly_Return"))
    ]

    month_ends = [pd.Timestamp(_month_label_to_yyyy_mm(m) + "-01") + pd.offsets.MonthEnd(0)
                  for m in book_monthly["Month"]]
    bench_levels = psa.fetch_benchmark_monthly(month_ends)
    if bench_levels and len(bench_levels) == len(book_monthly):
        bench_labels = book_monthly["Month"].astype(str).tolist()
        bench_points = [
            NavPoint(
                date=str(row["date"]),
                value=float(row["value"]),
                drawdown_pct=float(row["drawdown_pct"]),
                high_water_mark=float(row["high_water_mark"]),
            )
            for row in build_nav_points(bench_labels, bench_levels)
        ]
    else:
        bench_points = []

    stats = compute_stats(book_monthly, start_nav=starting_nav)
    note = (
        f"Live nav_engine ({meta.get('methodology')})."
        f"{four_book_note or ' book={} attribution is proxy until per-book overlay replay.'.format(book)}"
        f" Daily series: {len(mtm_daily_points)} trading days."
    )

    return NavHistoryBundle(
        book=book,
        source="nav_engine",
        inception_nav=starting_nav,
        mtm=mtm_points,
        closed=closed_points,
        mtm_daily=mtm_daily_points,
        closed_daily=closed_daily_points,
        benchmark=bench_points,
        monthly_returns=monthly_returns,
        attribution=attribution_rows,
        position_limit=int(_load_nav_config().get("position_limit_n") or 60),
        nav_history_note=note,
        metadata={
            **meta,
            "research_notional_usd": starting_nav,
            "rebalance_mode_source": rebalance_mode_source,
            "n_slots": n_slots_active,
            "data_status": data_status,
            "stats_ann_vol_pct": round(float(stats["ann_vol"]) * 100, 2) if stats.get("ann_vol") == stats.get("ann_vol") else None,
            "stats_best_month_pct": round(float(stats["best_month"]) * 100, 2),
            "stats_worst_month_pct": round(float(stats["worst_month"]) * 100, 2),
        },
    )
