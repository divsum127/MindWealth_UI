"""Regression tests for investor-facing Portfolio audit findings."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from api.services import portfolio_service


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
