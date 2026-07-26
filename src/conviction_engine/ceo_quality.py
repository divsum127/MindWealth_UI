"""CEO quality dimension — objective TSR vs SPY + new-CEO transition penalty."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .scoring import _float_or_none


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")[:10]).date()
    except ValueError:
        return None


def compute_price_return(ticker: str, start: date, end: date | None = None) -> float | None:
    """Total return (price-only) from start to end using yfinance history."""
    try:
        import yfinance as yf
    except ImportError:
        return None

    end = end or date.today()
    if start >= end:
        return None

    try:
        hist = yf.Ticker(ticker).history(
            start=start.isoformat(),
            end=(end.replace(day=min(end.day, 28)) if end else end).isoformat(),
            auto_adjust=True,
        )
        if hist is None or hist.empty:
            hist = yf.Ticker(ticker).history(period="max", auto_adjust=True)
        if hist is None or hist.empty:
            return None
        closes = hist["Close"].dropna()
        if closes.empty:
            return None
        start_px = float(closes.iloc[0])
        end_px = float(closes.iloc[-1])
        if start_px <= 0:
            return None
        return (end_px / start_px) - 1.0
    except Exception:
        return None


def compute_tsr_vs_spy(ticker: str, ceo_start_date: date) -> float | None:
    """Ticker TSR minus SPY TTR since CEO start."""
    stock = compute_price_return(ticker, ceo_start_date)
    spy = compute_price_return("SPY", ceo_start_date)
    if stock is None or spy is None:
        return None
    return stock - spy


def tsr_score_from_vs_spy(tsr_vs_spy: float) -> int:
    if tsr_vs_spy > 0.30:
        return 9
    if tsr_vs_spy > 0.10:
        return 7
    if tsr_vs_spy > -0.10:
        return 5
    if tsr_vs_spy > -0.25:
        return 3
    return 1


def score_0_10_to_bq(score_10: float) -> float:
    if score_10 >= 8:
        return 2.0
    if score_10 >= 6:
        return 1.0
    if score_10 >= 3:
        return 0.0
    return -1.0


def compute_ceo_quality_score(
    record: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    """
    Programmatic CEO quality from TSR vs SPY when tenure >= 12 months.

    New CEO (<12 months): neutral base (5/10) then mechanical -1 penalty (floor -1).
    """
    overrides = overrides or {}
    detail: dict[str, Any] = {}

    if overrides.get("ceo_quality_score") is not None:
        from .scoring import score_manual

        return score_manual("ceo_quality_score", overrides), detail

    if isinstance(overrides.get("ceo_quality_detail"), dict):
        from .agent_dims import analyst_score_to_bq

        agent = overrides["ceo_quality_detail"]
        score_10 = _float_or_none(agent.get("score_0_10"))
        if score_10 is not None:
            bq = analyst_score_to_bq(score_10)
            if overrides.get("new_ceo_transition"):
                bq = max(bq - 1.0, -1.0)
            return bq, {"source": "agent", **agent}

    ceo_start = _parse_date(
        overrides.get("ceo_start_date")
        or record.get("ceo_start_date")
        or (record.get("manual_overrides") or {}).get("ceo_start_date")
    )
    today = date.today()
    tenure_months = None
    if ceo_start:
        tenure_months = (today.year - ceo_start.year) * 12 + (today.month - ceo_start.month)
        detail["ceo_start_date"] = ceo_start.isoformat()
        detail["ceo_tenure_months"] = tenure_months

    ticker = str(record.get("ticker") or overrides.get("ticker") or "").upper()
    if tenure_months is not None and tenure_months < 12:
        detail["tsr_score"] = 5
        detail["rationale"] = "CEO tenure <12 months — neutral base with transition penalty"
        return max(score_0_10_to_bq(5) - 1.0, -1.0), detail

    if ceo_start and ticker:
        tsr_vs = compute_tsr_vs_spy(ticker, ceo_start)
        if tsr_vs is not None:
            tsr_score = tsr_score_from_vs_spy(tsr_vs)
            detail.update({"tsr_vs_spy": round(tsr_vs, 4), "tsr_score": tsr_score})
            return score_0_10_to_bq(float(tsr_score)), detail

    return 0.0, detail
