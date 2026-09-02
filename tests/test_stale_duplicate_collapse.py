"""The fetcher must serve the freshest row when a signal has several vintages.

chatbot/data/entry.csv held 14 rows for MCY.NZ OSCILLATOR DELTA 2026-06-22, all
stamped with the same refreshed price but each carrying the R:R, timeliness and
stop ladder frozen on its own write date. Exact-duplicate dedupe could not see
them, and the fetcher served the first, which was the oldest.
"""

import pandas as pd

from chatbot.smart_data_fetcher import SmartDataFetcher
from src.utils.quality_refresh import QUALITY_AS_OF_COLUMN

SYMBOL_COL = "Symbol, Signal, Signal Date/Price[$]"
TODAY_COL = "Today Trading Date/Price[$], Today Price vs Signal"
INTERVAL_COL = "Interval, Confirmation Status"


def _vintage_row(rr_dynamic, timeliness, quality_as_of=None):
    row = {
        "Function": "OSCILLATOR DELTA",
        SYMBOL_COL: "MCY.NZ, Long, 2026-06-22 (Price: 6.89)",
        INTERVAL_COL: "Daily, is Confirmed on 2026-06-22",
        "Signal Open Price": 6.94,
        TODAY_COL: "2026-08-26 (Price: 7.0200), 1.89% above",
        "R:R Dynamic": rr_dynamic,
        "Timeliness Score": timeliness,
    }
    if quality_as_of is not None:
        row[QUALITY_AS_OF_COLUMN] = quality_as_of
    return row


def test_oldest_vintage_is_dropped_in_favour_of_the_newest():
    df = pd.DataFrame(
        [
            _vintage_row(1.90, 100.0, "2026-06-22"),
            _vintage_row(1.09, 40.0, "2026-06-25"),
            _vintage_row(0.95, 0.0, "2026-08-26"),
        ]
    )
    out = SmartDataFetcher.collapse_stale_identity_duplicates(df)
    assert len(out) == 1
    assert out.iloc[0]["R:R Dynamic"] == 0.95
    assert out.iloc[0]["Timeliness Score"] == 0.0


def test_without_a_vintage_stamp_the_last_written_row_wins():
    """Legacy rows carry no stamp; the writer appends the refreshed row last."""
    df = pd.DataFrame([_vintage_row(1.90, 100.0), _vintage_row(0.95, 0.0)])
    out = SmartDataFetcher.collapse_stale_identity_duplicates(df)
    assert len(out) == 1
    assert out.iloc[0]["R:R Dynamic"] == 0.95


def test_different_signals_on_one_ticker_are_both_kept():
    other = _vintage_row(2.2, 80.0, "2026-08-26")
    other[SYMBOL_COL] = "MCY.NZ, Long, 2026-07-14 (Price: 6.92)"
    other["Function"] = "TRENDPULSE"
    df = pd.DataFrame([_vintage_row(0.95, 0.0, "2026-08-26"), other])
    out = SmartDataFetcher.collapse_stale_identity_duplicates(df)
    assert len(out) == 2


def test_same_ticker_and_function_on_different_dates_are_both_kept():
    later = _vintage_row(1.1, 60.0, "2026-08-26")
    later[SYMBOL_COL] = "MCY.NZ, Long, 2026-08-03 (Price: 6.95)"
    df = pd.DataFrame([_vintage_row(0.95, 0.0, "2026-08-26"), later])
    out = SmartDataFetcher.collapse_stale_identity_duplicates(df)
    assert len(out) == 2


def test_row_order_is_preserved_for_survivors():
    a = _vintage_row(0.95, 0.0, "2026-08-26")
    b = _vintage_row(1.1, 60.0, "2026-08-26")
    b[SYMBOL_COL] = "AIA.NZ, Long, 2026-08-03 (Price: 8.10)"
    df = pd.DataFrame([a, b])
    out = SmartDataFetcher.collapse_stale_identity_duplicates(df)
    assert list(out[SYMBOL_COL]) == [a[SYMBOL_COL], b[SYMBOL_COL]]


def test_empty_and_columnless_frames_pass_through():
    assert SmartDataFetcher.collapse_stale_identity_duplicates(pd.DataFrame()).empty
    other = pd.DataFrame([{"unrelated": 1}])
    assert len(SmartDataFetcher.collapse_stale_identity_duplicates(other)) == 1


def test_served_rows_are_recomputed_not_just_picked():
    """Even the newest stored row is a day behind; serving must recompute."""
    stop_col = (
        "Stop Loss (Recent Extrema/Horizontal/F-Stack 1/F-Stack 2/"
        "F-Track 1/F-Track 2/EMA 200) [$]"
    )
    row = {
        "Function": "OSCILLATOR DELTA",
        SYMBOL_COL: "MCY.NZ, Long, 2026-06-22 (Price: 6.89)",
        INTERVAL_COL: "Daily, is Confirmed on 2026-06-22",
        "Signal Open Price": 6.94,
        TODAY_COL: "2026-08-25 (Price: 6.9500), 0.87% above",
        "Trading Days between Signal and Today Date": "65 days",
        "Backtested Returns(Win Trades) [%] (Max/Min/Avg)": "9.68%/0.31%/2.64%",
        stop_col: (
            "No Recent Minima/5.13/No F-Stack Support/No F-Stack Support/"
            "6.7672/6.5259/6.56"
        ),
        "Cancellation Level/Date": "Already confirmed",
        "R:R Static": 1.48,
        "R:R Dynamic": 1.90,
        "Timeliness Score": 100.0,
    }
    out = SmartDataFetcher._refresh_quality_for_served_rows(pd.DataFrame([row]))
    assert out.loc[0, "R:R Dynamic"] < 1.0
    assert out.loc[0, "Timeliness Score"] == 0


def test_broad_sweeps_are_not_recomputed_row_by_row():
    from chatbot.smart_data_fetcher import QUALITY_REFRESH_ROW_LIMIT

    big = pd.DataFrame([_vintage_row(1.90, 100.0)] * (QUALITY_REFRESH_ROW_LIMIT + 1))
    out = SmartDataFetcher._refresh_quality_for_served_rows(big)
    assert out.loc[0, "R:R Dynamic"] == 1.90


def test_write_time_and_serve_time_agree():
    """The nightly writer and the fetcher must not disagree about a row.

    Two layers recompute: the price job when it writes, and the fetcher when it
    serves. If they ever diverged, the stored file and the answer would tell the
    user two different things about the same signal.
    """
    from src.utils.quality_refresh import refresh_quality_columns

    stop_col = (
        "Stop Loss (Recent Extrema/Horizontal/F-Stack 1/F-Stack 2/"
        "F-Track 1/F-Track 2/EMA 200) [$]"
    )
    row = _vintage_row(1.90, 100.0, "2026-06-22")
    row.update(
        {
            "Trading Days between Signal and Today Date": "65 days",
            "Backtested Returns(Win Trades) [%] (Max/Min/Avg)": "9.68%/0.31%/2.64%",
            stop_col: (
                "No Recent Minima/5.13/No F-Stack Support/No F-Stack Support/"
                "6.7672/6.5259/6.56"
            ),
            "Cancellation Level/Date": "Already confirmed",
        }
    )
    frame = pd.DataFrame([row])
    written = refresh_quality_columns(frame)
    served = SmartDataFetcher._refresh_quality_for_served_rows(frame)
    for column in ("R:R Dynamic", "Timeliness Score", "nearest_support_stop", QUALITY_AS_OF_COLUMN):
        assert str(written.loc[0, column]) == str(served.loc[0, column]), column
