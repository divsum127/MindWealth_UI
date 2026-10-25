"""CE-03 / CE-04: specials classifier (two-of-three gate) and the held dividend-cut penalty."""

from __future__ import annotations

import pandas as pd

from src.conviction_engine.capital_allocation import detect_dividend_cut
from src.conviction_engine.dividend_series import (
    TYPE_REGULAR,
    TYPE_REVIEW,
    TYPE_SPECIAL,
    classify_dividend_events,
    declared_annual_dividends,
)


def _quarterly(amounts, start="2023-03-15"):
    index = pd.date_range(start, periods=len(amounts), freq="3MS") + pd.Timedelta(days=14)
    return pd.Series(amounts, index=index)


def test_regular_payer_has_no_specials():
    events = classify_dividend_events(_quarterly([0.25] * 12))
    assert {e["type_code"] for e in events} == {TYPE_REGULAR}


def test_outlier_without_text_queues_for_review():
    series = _quarterly([0.25] * 6 + [1.50] + [0.25] * 5)
    events = classify_dividend_events(series)
    flagged = [e for e in events if e["type_code"] != TYPE_REGULAR]
    assert len(flagged) == 1
    assert flagged[0]["type_code"] == TYPE_REVIEW
    assert flagged[0]["legs"] == {"retrieved": False, "type_word": False, "outlier": True}


def test_two_of_three_classifies_special():
    series = _quarterly([0.25] * 6 + [1.50] + [0.25] * 5)
    stamp = series.index[6]
    events = classify_dividend_events(series, {stamp: "Board declares a special dividend of $1.50"})
    assert events[6]["type_code"] == TYPE_SPECIAL
    # Text retrieved, explicit word, normal amount: still two of three.
    events = classify_dividend_events(_quarterly([0.25] * 8), {_quarterly([0.25] * 8).index[5]: "supplementary dividend"})
    assert events[5]["type_code"] == TYPE_SPECIAL


def test_retrieved_text_without_type_word_or_outlier_is_regular():
    series = _quarterly([0.25] * 8)
    events = classify_dividend_events(series, {series.index[5]: "Quarterly dividend of 25 cents"})
    assert events[5]["type_code"] == TYPE_REGULAR


def test_too_little_history_casts_no_outlier_vote():
    events = classify_dividend_events(_quarterly([0.25, 3.0, 0.25]))
    assert all(e["legs"]["outlier"] is False for e in events)


def test_specials_are_excluded_from_the_annual_sum():
    # A special is paid on top of the regular quarterly, not instead of it.
    regular = _quarterly([0.25] * 12)
    stamp = regular.index[8] + pd.Timedelta(days=20)
    series = pd.concat([regular, pd.Series([1.50], index=[stamp])]).sort_index()
    declared = declared_annual_dividends(series, announcements={stamp: "special dividend"})
    assert declared["current"] == 1.0
    assert declared["prior"] == 1.0
    assert [e["type_code"] for e in declared["excluded_specials"]] == [TYPE_SPECIAL]


def test_semi_annual_drift_does_not_add_a_third_payment():
    # SPK.NZ shape: 12.5c Mar 2025, 12.5c Sep 2025, 8c Mar 2026 (one day past anniversary).
    series = pd.Series(
        [12.5, 12.5, 12.5, 12.5, 8.0],
        index=pd.to_datetime(["2024-03-14", "2024-09-12", "2025-03-13", "2025-09-11", "2026-03-14"]),
    )
    declared = declared_annual_dividends(series)
    assert declared["current"] == 20.5
    assert declared["prior"] == 25.0


def test_cut_touching_a_review_payment_is_held():
    flag = detect_dividend_cut(
        {
            "annual_div_declared_current": 1.0,
            "annual_div_declared_prior": 2.5,
            "dividend_review_pending": [{"date": "2025-09-15", "amount": 1.5, "type_code": TYPE_REVIEW}],
        }
    )
    assert flag["triggered"] is False
    assert flag["penalty"] == 0.0
    assert flag["held_for_review"] is True
    assert flag["held_penalty"] < 0.0


def test_clean_cut_still_scores():
    flag = detect_dividend_cut({"annual_div_declared_current": 1.0, "annual_div_declared_prior": 2.5})
    assert flag["triggered"] is True
    assert "held_for_review" not in flag


def test_monthly_to_quarterly_switch_is_not_a_special():
    # PPL.TO shape: twelve monthly payments, then quarterly at the same annual rate.
    monthly = pd.Series([0.23] * 12, index=pd.date_range("2022-01-15", periods=12, freq="MS") + pd.Timedelta(days=14))
    quarterly = pd.Series([0.69] * 6, index=pd.date_range("2023-03-15", periods=6, freq="3MS") + pd.Timedelta(days=14))
    events = classify_dividend_events(pd.concat([monthly, quarterly]))
    assert {e["type_code"] for e in events} == {TYPE_REGULAR}


def test_missing_payments_are_a_data_gap_and_hold_the_cut():
    # TD shape: quarterly, then yfinance drops two payments (one 273-day gap), then quarterly again.
    dates = pd.to_datetime(
        ["2024-01-09", "2024-04-08", "2024-07-10", "2024-10-10", "2025-01-10", "2025-04-10",
         "2025-07-10", "2026-04-09", "2026-07-10", "2026-10-09"]
    )
    series = pd.Series([0.75] * len(dates), index=dates)
    declared = declared_annual_dividends(series)
    assert [g["date"] for g in declared["data_gaps"]] == ["2026-04-09"]
    flag = detect_dividend_cut(
        {
            "annual_div_declared_current": declared["current"],
            "annual_div_declared_prior": declared["prior"],
            "dividend_data_gaps": declared["data_gaps"],
        }
    )
    assert flag["triggered"] is False
    assert flag["penalty"] == 0.0  # 25% decline scores 0 anyway; larger ones are held (see above)


def test_frequency_change_is_not_a_data_gap():
    monthly = pd.Series([0.23] * 12, index=pd.date_range("2022-01-15", periods=12, freq="MS") + pd.Timedelta(days=14))
    quarterly = pd.Series([0.69] * 6, index=pd.date_range("2023-03-15", periods=6, freq="3MS") + pd.Timedelta(days=14))
    from src.conviction_engine.dividend_series import find_data_gaps

    assert find_data_gaps(pd.concat([monthly, quarterly])) == []
