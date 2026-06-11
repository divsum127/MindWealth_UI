"""BLS CPI/PPI with retry schedule and FRED fallback."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.fred_pull import fetch_fred_series
from src.macro_intelligence.data.retry_cache import pull_with_cache
from src.macro_intelligence.db.connection import get_connection

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def _bls_api_key() -> str:
    return os.environ.get("BLS_API_KEY", "")


def fetch_bls_cpi_mom_history(
    series_id: str | None = None,
    *,
    start_year: int = 1990,
    end_year: int | None = None,
) -> pd.DataFrame:
    """Monthly CPI MoM % from BLS API (20-year chunks). Columns: period (YYYY-MM), mom_pct."""
    key = _bls_api_key()
    if not key:
        return pd.DataFrame(columns=["period", "mom_pct"])
    cfg = load_config().get("cpi", {})
    series_id = series_id or cfg.get("bls_series_id", "CUSR0000SA0")
    end_year = end_year or datetime.now().year
    chunks: list[pd.DataFrame] = []
    chunk_start = start_year
    while chunk_start <= end_year:
        chunk_end = min(chunk_start + 19, end_year)
        payload = {
            "seriesid": [series_id],
            "startyear": str(chunk_start),
            "endyear": str(chunk_end),
            "registrationkey": key,
        }
        try:
            resp = requests.post(BLS_API_URL, json=payload, timeout=60)
            if resp.status_code != 200:
                chunk_start = chunk_end + 1
                continue
            data = resp.json()
            if data.get("status") != "REQUEST_SUCCEEDED":
                chunk_start = chunk_end + 1
                continue
            series = data.get("Results", {}).get("series", [])
            if not series:
                chunk_start = chunk_end + 1
                continue
            points = []
            for p in series[0].get("data", []):
                if not str(p.get("period", "")).startswith("M"):
                    continue
                raw_val = str(p.get("value", "")).strip()
                if not raw_val or raw_val in ("-", "NaN"):
                    continue
                try:
                    val = float(raw_val)
                except ValueError:
                    continue
                points.append((f"{p['year']}-{str(p['period']).replace('M', '')}", val))
            if points:
                df = pd.DataFrame(points, columns=["period_ym", "index_level"])
                df["period"] = pd.to_datetime(df["period_ym"] + "-01", errors="coerce")
                df = df.dropna(subset=["period"]).sort_values("period")
                df["mom_pct"] = df["index_level"].pct_change() * 100.0
                chunks.append(df[["period", "mom_pct"]].dropna())
        except Exception:
            pass
        chunk_start = chunk_end + 1
    if not chunks:
        return pd.DataFrame(columns=["period", "mom_pct"])
    out = pd.concat(chunks, ignore_index=True).drop_duplicates(subset=["period"]).sort_values("period")
    return out


def bls_mom_for_reference_month(mom_df: pd.DataFrame, reference_month: str) -> float | None:
    """Lookup MoM % for YYYY-MM reference month."""
    if mom_df.empty:
        return None
    ts = pd.Timestamp(f"{reference_month[:7]}-01")
    row = mom_df.loc[mom_df["period"] == ts]
    if row.empty:
        return None
    val = row.iloc[-1]["mom_pct"]
    return float(val) if pd.notna(val) else None


def reference_month_for_release(release_date: str) -> str:
    """CPI is released mid-month for the prior calendar month (YYYY-MM)."""
    ts = pd.Timestamp(release_date)
    ref = ts - pd.DateOffset(months=1)
    return ref.strftime("%Y-%m")


def fetch_bls_latest_mom_pct(series_id: str, years: int = 3) -> float | None:
    """Fetch latest month-over-month % change from BLS API."""
    key = _bls_api_key()
    if not key:
        return None
    end_year = datetime.now().year
    start_year = end_year - years
    payload = {
        "seriesid": [series_id],
        "startyear": str(start_year),
        "endyear": str(end_year),
        "registrationkey": key,
    }
    resp = requests.post(BLS_API_URL, json=payload, timeout=30)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("status") != "REQUEST_SUCCEEDED":
        return None
    series = data.get("Results", {}).get("series", [])
    if not series:
        return None
    points = series[0].get("data", [])
    if len(points) < 2:
        return None
    latest = float(points[0]["value"])
    prior = float(points[1]["value"])
    if prior == 0:
        return None
    return (latest / prior - 1.0) * 100.0


def fetch_cpi_from_fred() -> tuple[str, float] | None:
    s = fetch_fred_series("CPIAUCSL", "2000-01-01")
    if s is None or len(s) < 2:
        return None
    s = s.dropna().sort_index()
    mom = (s.iloc[-1] / s.iloc[-2] - 1.0) * 100.0
    return s.index[-1].strftime("%Y-%m-%d"), float(mom)


def load_cpi_surprise_series() -> pd.Series:
    """Series of CPI surprise (actual - consensus) by release date."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT release_date, surprise_pp FROM pending_releases WHERE release_type='CPI' ORDER BY release_date"
        ).fetchall()
    if rows:
        idx = [pd.Timestamp(r["release_date"]) for r in rows]
        vals = [float(r["surprise_pp"]) for r in rows]
        return pd.Series(vals, index=idx).sort_index()
    return pd.Series(dtype=float)


def ingest_cpi_release(date: str, actual: float, consensus: float, source: str = "manual") -> float:
    surprise = actual - consensus
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pending_releases (release_type, release_date, actual, consensus, surprise_pp, source, applied)
            VALUES ('CPI', ?, ?, ?, ?, ?, 0)
            ON CONFLICT(release_type, release_date) DO UPDATE SET
              actual=excluded.actual, consensus=excluded.consensus,
              surprise_pp=excluded.surprise_pp, source=excluded.source
            """,
            (date, actual, consensus, surprise, source),
        )
    return surprise


def fetch_ppi_cooling_flag(as_of: str | None = None) -> bool:
    cfg = load_config().get("ppi_cooling", {})
    if not cfg.get("enabled", True):
        return False
    series_id = cfg.get("bls_series_id", "WPSFD49207")
    mom = pull_with_cache(f"ppi_{series_id}", lambda: fetch_bls_latest_mom_pct(series_id))
    if mom is None:
        return False
    return mom <= cfg.get("cooling_mom_max_pct", 0.0)


def cpi_not_hot_for_week(release_date: str | None) -> bool:
    """True if CPI leg passes for cancel (not hot or no release)."""
    if not release_date:
        return True
    with get_connection() as conn:
        row = conn.execute(
            "SELECT actual, consensus FROM pending_releases WHERE release_type='CPI' AND release_date=?",
            (release_date,),
        ).fetchone()
    if not row:
        return True
    actual, consensus = row["actual"], row["consensus"]
    if actual is None or consensus is None:
        return True
    return float(actual) <= float(consensus)


def try_fetch_cpi_consensus() -> float | None:
    """Consensus MoM % from Trading Economics (primary), optional Investing.com, or DB cache."""
    try:
        from src.macro_intelligence.data.investing_cpi_consensus import latest_cpi_consensus_row

        row = latest_cpi_consensus_row()
        if row and row.consensus is not None:
            return float(row.consensus)
    except Exception:
        pass
    with get_connection() as conn:
        db_row = conn.execute(
            """
            SELECT consensus FROM pending_releases
            WHERE release_type='CPI' AND consensus IS NOT NULL
            ORDER BY release_date DESC LIMIT 1
            """
        ).fetchone()
    if db_row and db_row["consensus"] is not None:
        return float(db_row["consensus"])
    return None


def try_bls_cpi_pull() -> dict[str, Any] | None:
    cfg = load_config().get("cpi", {})
    series = cfg.get("bls_series_id", "CUSR0000SA0")

    def _fetch():
        mom = fetch_bls_latest_mom_pct(series)
        if mom is None:
            raise RuntimeError("BLS CPI unavailable")
        consensus = try_fetch_cpi_consensus()
        as_of = datetime.now().strftime("%Y-%m-%d")
        if consensus is not None:
            ingest_cpi_release(as_of, mom, consensus, source="BLS+investing_consensus")
        return {"mom_pct": mom, "consensus": consensus, "source": "BLS", "as_of": as_of}

    return pull_with_cache("cpi_bls", _fetch)


def try_fred_cpi_fallback_if_stale(days: int = 2) -> bool:
    """Use FRED when BLS unavailable for N calendar days."""
    cfg = load_config().get("cpi", {})
    min_days = cfg.get("fred_fallback_after_calendar_days", days)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT pulled_at FROM data_pull_log WHERE source_id='cpi_bls' AND status='OK' ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
    if row:
        pulled = row["pulled_at"].strip().replace("Z", "+00:00")
        last = datetime.fromisoformat(pulled)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        else:
            last = last.astimezone(timezone.utc)
        if datetime.now(timezone.utc) - last < timedelta(days=min_days):
            return False
    fred = fetch_cpi_from_fred()
    if not fred:
        return False
    date, mom = fred
    ingest_cpi_release(date, mom, mom, source="FRED_PROXY")
    return True
