"""Dividend series construction (Rohit 1 Sep, C2).

His instruction, and why the previous approach was wrong:

    "Stop using date windows. Attribute each dividend to the period it was declared
    for — interim FY26, final FY26. ... A payment landing a day after its anniversary
    still belongs to FY26. Anniversary drift stops mattering. A year of 4 x 7.5c and a
    year of 2 x 15c both read 30c. Frequency stops mattering. Frequency doesn't need
    inferring at all. Drop the median gap approach — it breaks the moment a company
    changes frequency, which they do."

He is right that frequency changes are common. Measured across the universe on
2026-09-02: **25 of 139 payers changed payment frequency inside five years** — ASML,
TD, BNS.TO, WPM, QQQ, TRI.TO, CNQ.TO, FSF.NZ, TWR.NZ among them, and PPL.TO went from
twelve payments in 2022 to four from 2023. So median-gap inference is not salvageable
and is removed here.

**What blocks the full design.** Period attribution needs the period each declaration
covers. The current feed (yfinance) returns an amount and one date, the ex-date. There
is no declaration date, no period label, and no type code. So "interim FY26" cannot be
read from the data we hold today; it needs exchange announcements or a paid provider.

Rather than stall, this module splits the design in two:

* ``build_dividend_periods`` accepts period labels when a source can supply them, and
  otherwise derives coverage from the payment record. Either way the twelve-month
  figure is built by **summing declarations until their periods cover twelve months**,
  which is frequency-free and drift-proof — it is the part of his design that does not
  depend on the missing fields.
* ``dividend_yield_series`` samples **month-end**, sixty observations over five years,
  as specified.

Frequency is stored as a **history** (payments per calendar year), never one value per
ticker, so applying today's cadence backwards can never halve an older observation.
"""

from __future__ import annotations

import collections
from typing import Any

import pandas as pd

# Twelve months of coverage, in days, with a tolerance so a half-year period reported as
# 182 or 184 days still closes the year cleanly.
YEAR_DAYS = 365
COVERAGE_TOLERANCE_DAYS = 45

# Five years of month-end observations (his "sixty observations over five years").
YIELD_SERIES_MONTHS = 60


def normalize_dividends(dividends: pd.Series | None) -> pd.Series | None:
    """Timezone-naive, sorted, positive dividend series."""
    if not isinstance(dividends, pd.Series) or dividends.empty:
        return None
    series = dividends.dropna()
    series = series[series > 0]
    if series.empty:
        return None
    index = series.index
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    return pd.Series(series.values, index=index).sort_index()


def frequency_history(dividends: pd.Series | None) -> dict[int, int]:
    """Payments per calendar year — a history, not one value per ticker.

    Rohit: "frequency has to be stored as a history, not one value per ticker — if a
    name paid quarterly in FY24 and semi-annually now, applying today's count backwards
    halves every FY24 observation and wrecks the mean."
    """
    series = normalize_dividends(dividends)
    if series is None:
        return {}
    return dict(sorted(collections.Counter(series.index.year).items()))


def frequency_changed(dividends: pd.Series | None, lookback_years: int = 5) -> bool:
    """True when payments per year is not constant across complete years in the window."""
    series = normalize_dividends(dividends)
    history = frequency_history(dividends)
    if series is None or len(history) < 2:
        return False

    # Only compare years that are actually complete. Dropping the first and last year
    # outright was too blunt: on a three-year history it left a single year and could
    # never report a change, which hid PPL.TO going from twelve payments a year to four.
    first_payment = series.index[0]
    last_payment = series.index[-1]
    complete_years = []
    for year in sorted(history)[-lookback_years - 1 :]:
        if year == first_payment.year and first_payment.month > 3:
            continue  # history starts mid-year, so the count is a partial view
        if year == last_payment.year and last_payment.month < 10:
            continue  # year still in progress
        complete_years.append(year)

    if len(complete_years) < 2:
        return False
    return len({history[y] for y in complete_years}) > 1


def trailing_twelve_month_dividend(
    dividends: pd.Series | None,
    as_of: pd.Timestamp,
    period_labels: dict[Any, str] | None = None,
) -> dict[str, Any]:
    """Twelve months of declared dividend as at ``as_of``, by covered period.

    Declarations are summed newest-first until the periods they cover span twelve
    months. That is frequency-free: four payments of 7.5c and two of 15c both close the
    year at 30c, and a payment landing a day past its anniversary still closes the same
    year rather than opening a third slot in a rolling window.

    ``period_labels`` maps a payment timestamp to the period it was declared for, when a
    source can supply it. Absent that — which is the case on the current feed — coverage
    is derived from the spacing of the payments themselves, which gives the same answer
    for a regular payer and states its assumption in ``basis``.
    """
    series = normalize_dividends(dividends)
    result: dict[str, Any] = {
        "amount": None,
        "payments_used": 0,
        "periods": [],
        "coverage_days": None,
        "basis": "no_data",
        "complete": False,
    }
    if series is None:
        return result

    eligible = series[series.index <= as_of]
    if eligible.empty:
        return result

    # Accumulate the period each declaration COVERS, newest first, and stop as soon as
    # the covered periods span twelve months. This is the frequency-free part of his
    # design: four quarterly declarations each cover a quarter and close the year at
    # four; two half-year declarations close it at two. Nothing is counted because it
    # happens to fall inside a date window, which is what pulled a third payment into
    # SPK's year and read 33c against a real 20.5c.
    #
    # Where a source supplies period labels the covered length comes from the label.
    # Absent that, a declaration's covered period is the interval back to the previous
    # declaration, which is the same quantity the issuer is paying for.
    stamps = list(eligible.index)
    total = 0.0
    used: list[pd.Timestamp] = []
    periods: list[str] = []
    coverage = 0
    for position in range(len(stamps) - 1, -1, -1):
        stamp = stamps[position]
        if position > 0:
            covered_days = (stamp - stamps[position - 1]).days
        elif len(stamps) > 1:
            # Oldest payment on file: assume it covers the same span as the next one.
            covered_days = (stamps[1] - stamps[0]).days
        else:
            # A single payment with nothing before it says nothing about the period it
            # covers. Assuming a year here made an early semi-annual history read half
            # its true yield, so the window is reported incomplete instead and no
            # observation is emitted for that date.
            covered_days = 0
        total += float(eligible.loc[stamp])
        used.append(stamp)
        coverage += max(0, covered_days)
        if period_labels and stamp in period_labels:
            periods.append(str(period_labels[stamp]))
        if coverage >= YEAR_DAYS - COVERAGE_TOLERANCE_DAYS:
            break

    complete = coverage >= YEAR_DAYS - COVERAGE_TOLERANCE_DAYS
    result.update(
        amount=round(total, 6),
        payments_used=len(used),
        periods=list(reversed(periods)),
        coverage_days=coverage,
        basis="declared_periods" if periods else "payment_coverage",
        complete=bool(complete),
    )
    return result


def dividend_yield_series(
    prices: pd.Series | None,
    dividends: pd.Series | None,
    months: int = YIELD_SERIES_MONTHS,
    period_labels: dict[Any, str] | None = None,
) -> pd.Series:
    """Month-end trailing-twelve-month dividend divided by the month-end price.

    Rohit: "The yield series is a twelve-month dividend divided by the price, sampled at
    month-end — the price moves daily, the dividend doesn't. Sixty observations over
    five years for the z-score."
    """
    series = normalize_dividends(dividends)
    if series is None or not isinstance(prices, pd.Series) or prices.empty:
        return pd.Series(dtype=float)

    close = prices.dropna()
    if close.empty:
        return pd.Series(dtype=float)
    if getattr(close.index, "tz", None) is not None:
        close.index = close.index.tz_localize(None)
    month_end = close.resample("ME").last().dropna()
    if month_end.empty:
        return pd.Series(dtype=float)
    month_end = month_end.tail(months)

    observations: dict[pd.Timestamp, float] = {}
    for stamp, price in month_end.items():
        if not price or price <= 0:
            continue
        window = trailing_twelve_month_dividend(series, stamp, period_labels)
        if not window["complete"] or not window["amount"]:
            continue
        observations[stamp] = window["amount"] / float(price)
    return pd.Series(observations, dtype=float).sort_index()


def dividend_yield_stats(
    prices: pd.Series | None,
    dividends: pd.Series | None,
    period_labels: dict[Any, str] | None = None,
) -> dict[str, Any]:
    """Mean/std of the month-end yield series, plus the frequency history behind it.

    The mean and standard deviation are of dividend **yields**, not dividend amounts —
    a distinction Rohit asked to have stated plainly.
    """
    series = dividend_yield_series(prices, dividends, period_labels=period_labels)
    history = frequency_history(dividends)
    stats: dict[str, Any] = {
        "dividend_yield_observations": int(len(series)),
        "dividend_frequency_history": history,
        "dividend_frequency_changed": frequency_changed(dividends),
        "dividend_series_basis": "month_end_ttm_declared" if period_labels else "month_end_ttm_coverage",
    }
    if len(series) >= 12:
        stats["dividend_yield_5y_mean"] = round(float(series.mean()), 6)
        stats["dividend_yield_5y_std"] = round(float(series.std(ddof=0)), 6)
    return stats
