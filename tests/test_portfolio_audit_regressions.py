"""Regression tests for investor-facing Portfolio audit findings."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from api.services import portfolio_pipeline_service, portfolio_service


def _cancel_buy_vt_row() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": "MAR",
                "Status": "Open",
                "Function": "TRENDPULSE",
                "Interval": "Daily",
                "Signal": "Long",
                "Entry Date": "2026-09-23",
                "Entry Price": 300.0,
                "Today price": 300.0,
                "Realised/Unrealised Profit": "0.0%",
                "Backtested Win Rate [%]": 70.0,
                "asset_type": "EQUITY",
            }
        ]
    )


def _cancel_buy_overlay() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "MAR",
                "bq_raw": 6.0,
                "conviction_score": 1.0,
                "verdict": "CANCEL BUY",
                "sizing_pct": 0.0,
                "business_type": "compounder",
                "yield_trap_warning": False,
            }
        ]
    )


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        ("CANCEL", "CANCEL"),
        ("cancel buy", "CANCEL BUY"),
        ("CANCEL_BUY", "CANCEL BUY"),
        ("yield-trap", "YIELD TRAP"),
        ("TACTICAL", None),
        ("NOT_APPLICABLE", None),
    ],
)
def test_MW_019_normalizes_only_blocking_conviction_verdicts(
    verdict: str,
    expected: str | None,
) -> None:
    assert portfolio_service._conviction_hard_gate_reason(verdict) == expected


@pytest.mark.parametrize("sizing_version", ["legacy", "d1_slots"])
def test_MW_019_cancel_buy_is_a_final_zero_allocation_gate(sizing_version: str) -> None:
    """A cancellation verdict must win over positive BQ and every sizing engine."""

    long_book = _cancel_buy_vt_row()
    overlay = _cancel_buy_overlay()

    def load_vt(side: str) -> pd.DataFrame:
        return long_book if side == "long" else pd.DataFrame()

    def load_overlay(side: str) -> pd.DataFrame:
        return overlay if side == "long" else pd.DataFrame()

    with (
        patch.object(portfolio_service, "_load_vt", side_effect=load_vt),
        patch.object(portfolio_service, "_load_conviction_overlay", side_effect=load_overlay),
        patch.object(portfolio_service, "_load_runic_safe", return_value={}),
        patch.object(portfolio_service, "_load_ssi_safe", return_value={"ssi_multiplier": 1.0}),
        patch.object(portfolio_service, "_compute_spx_trend_mult", return_value=(1.0, {})),
        patch.object(portfolio_service, "_refresh_ticker_names_cache", return_value={"MAR": "Marriott"}),
        patch.object(portfolio_service, "_cross_function_conflict_tickers", return_value=set()),
        patch.object(portfolio_service, "get_portfolio_notional", return_value=100_000_000),
        patch.object(portfolio_service.sizing_engine, "sizing_engine_version", return_value=sizing_version),
    ):
        payload = portfolio_service.get_portfolio_sizer("normal")

    assert len(payload["pnl_rows"]) == 1
    row = payload["pnl_rows"][0]
    assert row["ticker"] == "MAR"
    assert row["verdict"] == "CANCEL BUY"
    assert row["blocked"] is True
    assert row["status"] == "Blocked"
    assert row["size_tier"] == "BLOCKED"
    assert row["conviction_multiplier"] == 0.0
    assert row["allocation_usd"] == 0
    assert row["allocation_pct"] == 0.0
    assert row["blocked_reason"] == "CANCEL BUY"
    assert payload["summary"]["open_position_count"] == 0


def test_MW_020_conviction_summary_declares_rows_and_unique_equity_tickers() -> None:
    """Risk counts must distinguish legitimate signal legs from deduplicated names."""

    payload = {
        "as_of": "2026-09-26T12:00:00+00:00",
        "pnl_rows": [
            {"ticker": "AAPL", "size_tier": "MAX 100%", "blocked": False},
            {"ticker": "AAPL", "size_tier": "MAX 80%", "blocked": False},
            {"ticker": "MSFT", "size_tier": "TACTICAL 55%", "blocked": False},
            {"ticker": "NVO", "size_tier": "REDUCED 20%", "blocked": False},
            {
                "ticker": "SPK.NZ",
                "size_tier": "BLOCKED",
                "blocked": True,
                "verdict": "YIELD TRAP",
                "blocked_reason": "YIELD TRAP",
                "flags": ["YIELD TRAP"],
            },
            {
                "ticker": "QQQ",
                "size_tier": "N/A 100%",
                "blocked": False,
                "not_applicable": True,
            },
            {
                "ticker": "MAR",
                "size_tier": "BLOCKED",
                "blocked": True,
                "verdict": "CANCEL BUY",
                "blocked_reason": "CANCEL BUY",
            },
        ],
    }

    summary = portfolio_service.build_conviction_summary(payload)

    assert summary["count_unit"] == "signal_positions"
    assert summary["as_of"] == payload["as_of"]
    assert summary["population_count"] == 5
    assert summary["population_count"] == sum(
        summary[key]
        for key in ("max_count", "tactical_count", "reduced_count", "yield_trap_count")
    )
    assert summary["unique_ticker_count"] == 4
    assert summary["max_count"] == 2
    assert summary["max_unique_ticker_count"] == 1
    assert summary["tactical_unique_ticker_count"] == 1
    assert summary["reduced_unique_ticker_count"] == 1
    assert summary["yield_trap_count"] == 1
    assert summary["yield_trap_unique_ticker_count"] == 1
    assert summary["excluded_not_applicable_count"] == 1
    assert summary["excluded_blocked_count"] == 1
    assert summary["tier_conflict_ticker_count"] == 0
    assert summary["max_names"] == ["AAPL"]
    assert summary["yield_trap_names"] == ["SPK.NZ"]


@pytest.mark.parametrize(
    ("weights", "expected_pct", "expected_status", "requires_rebalance"),
    [
        ((8.8, 8.8), 17.6, "within_cap", False),
        ((10.0, 10.0), 20.0, "within_cap", False),
        ((12.0, 12.0), 24.0, "breach", True),
    ],
)
def test_MW_021_correlation_and_exposure_triggers_are_independent(
    weights: tuple[float, float],
    expected_pct: float,
    expected_status: str,
    requires_rebalance: bool,
) -> None:
    """High correlation must not imply that the displayed exposure cap was breached."""

    labels = ["semiconductors", "us_tech"]
    matrix = [[1.0, 0.88], [0.88, 1.0]]
    sizer = {
        "as_of": "2026-09-26T12:00:00+00:00",
        "pnl_rows": [],
        "clusters": [
            {"id": labels[0], "deployed_pct": weights[0]},
            {"id": labels[1], "deployed_pct": weights[1]},
        ],
    }

    with (
        patch.object(
            portfolio_service,
            "_load_correlation_matrix",
            return_value=(labels, matrix, {"source": "fixture", "as_of": "2026-09-26"}),
        ),
        patch.object(portfolio_service, "get_portfolio_sizer", return_value=sizer),
        patch.object(portfolio_service, "get_portfolio_notional", return_value=100_000_000),
    ):
        breach = portfolio_service.get_portfolio_risk()["breaches"][0]

    assert breach["level"] == "action"
    assert breach["rho"] == 0.88
    assert breach["correlation_threshold"] == 0.85
    assert breach["correlation_threshold_breached"] is True
    assert breach["combined_weight_pct"] == expected_pct
    assert breach["exposure_status"] == expected_status
    assert breach["exposure_threshold_breached"] is requires_rebalance
    assert breach["requires_rebalance"] is requires_rebalance
    assert "correlation_action" in breach["trigger_reasons"]
    assert ("pair_cap_breach" in breach["trigger_reasons"]) is requires_rebalance
    assert (breach["recommendation"] is not None) is requires_rebalance
    if requires_rebalance:
        assert "Exposure breach: 24.0% > 20.0%" in breach["explanation"]
    else:
        assert f"Exposure within cap: {expected_pct:.1f}% <= 20.0%" in breach["explanation"]

    chip = portfolio_pipeline_service._risk_chips_from_breaches([breach])[0]
    assert chip["title"] == (
        "Correlation action + exposure cap breach"
        if requires_rebalance
        else "Correlation action · exposure within cap"
    )
    assert chip["body"] == (
        f"{breach['explanation']} {breach['recommendation']}"
        if requires_rebalance
        else breach["explanation"]
    )
