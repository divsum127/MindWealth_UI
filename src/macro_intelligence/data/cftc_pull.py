"""CFTC TFF report parsing — Fast Money (combos) + Asset Manager (context/SSI)."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.retry_cache import pull_with_cache
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.percentiles import percentile_rank

CFTC_TFF_YEAR_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
CFTC_TFF_BULK_URL = "https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip"
CFTC_TFF_BULK_TXT = "F_TFF_2006_2016.txt"
CFTC_LOCAL_CACHE_DIR = Path(__file__).resolve().parents[3] / "macro_intelligence" / "data_cache" / "cftc"
_TFF_RAW_CACHE: pd.DataFrame | None = None

# How old a cached ZIP can be before we force a re-download regardless of the day.
# CFTC publishes every Friday — so anything older than 8 days means we missed a release.
_CFTC_STALE_DAYS = 8


def refresh_cftc_zip_if_stale(year: int | None = None) -> bool:
    """Auto-refresh the current-year CFTC TFF ZIP without any manual intervention.

    Download strategy (two independent triggers — either one fires a download):

    1. **Friday trigger**: Today is Friday (CFTC release day) AND the local file is
       more than 12 hours old — i.e. the file predates today's 3:30pm ET publication.

    2. **Staleness trigger**: The local file (or absence of one) is older than
       ``_CFTC_STALE_DAYS`` days (8 days) — we missed at least one Friday release.

    Additionally, a lightweight HEAD request checks ``Content-Length`` — if the
    remote file is strictly larger than the local one we always download, regardless
    of day (catches mid-week corrections or re-publications by CFTC).

    After a successful download the module-level ``_TFF_RAW_CACHE`` is cleared so
    the next ``fetch_cftc_fast_money_net()`` call reads the fresh data.

    Returns True when a fresh file was downloaded, False otherwise.
    """
    global _TFF_RAW_CACHE

    year = year or datetime.now().year
    local_path = CFTC_LOCAL_CACHE_DIR / f"fut_fin_txt_{year}.zip"
    url = CFTC_TFF_YEAR_URL.format(year=year)

    now = datetime.now()
    is_friday = now.weekday() == 4

    # --- staleness check ---
    local_size = 0
    local_age_days = float("inf")
    if local_path.exists():
        stat = local_path.stat()
        local_size = stat.st_size
        local_age_days = (now.timestamp() - stat.st_mtime) / 86400

    file_is_old = local_age_days > _CFTC_STALE_DAYS
    # On Fridays re-download if the local file is older than 12 hours
    # (meaning it was not downloaded today after the 3:30pm release)
    friday_needs_refresh = is_friday and local_age_days > 0.5

    # --- remote size check via HEAD (fast, no body) ---
    remote_size = 0
    try:
        head = requests.head(url, timeout=15)
        remote_size = int(head.headers.get("Content-Length", 0))
    except Exception:
        pass  # network error — fall through to day-based logic

    remote_is_larger = remote_size > 0 and remote_size > local_size

    if not (file_is_old or friday_needs_refresh or remote_is_larger):
        return False  # local file is fresh enough

    # --- download ---
    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            return False
        CFTC_LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(resp.content)
        _TFF_RAW_CACHE = None  # force re-parse on next fetch
        return True
    except Exception:
        return False


def _local_zip_paths(start_year: int) -> list[Path]:
    """Prefer zips saved by scripts/download_cftc_tff_zip.py before hitting CFTC."""
    cache = CFTC_LOCAL_CACHE_DIR
    if not cache.is_dir():
        return []
    paths: list[Path] = []
    bulk = cache / "fin_fut_txt_2006_2016.zip"
    if start_year <= 2016 and bulk.is_file():
        paths.append(bulk)
    current_year = datetime.now().year
    for year in range(max(2017, start_year), current_year + 1):
        annual = cache / f"fut_fin_txt_{year}.zip"
        if annual.is_file():
            paths.append(annual)
    return paths


def _read_zip_frames(paths: list[Path]) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for path in paths:
        try:
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".txt"):
                        with zf.open(name) as f:
                            frames.append(pd.read_csv(f, low_memory=False))
                        break
        except Exception:
            continue
    return frames


@dataclass
class CftcSnapshot:
    date: pd.Timestamp
    fm_net: float
    rm_net: float | None
    fm_pctile: float | None
    rm_pctile: float | None
    status: str


def _download_frames(start_year: int) -> pd.DataFrame:
    """TFF futures-only files (fut_fin_txt_*.zip), not legacy deacot."""
    global _TFF_RAW_CACHE
    if _TFF_RAW_CACHE is not None and not _TFF_RAW_CACHE.empty:
        return _TFF_RAW_CACHE
    local = _local_zip_paths(start_year)
    if local:
        frames = _read_zip_frames(local)
        if frames:
            _TFF_RAW_CACHE = pd.concat(frames, ignore_index=True)
            return _TFF_RAW_CACHE
    frames: list[pd.DataFrame] = []
    if start_year <= 2016:
        try:
            resp = requests.get(CFTC_TFF_BULK_URL, timeout=120)
            if resp.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    with zf.open(CFTC_TFF_BULK_TXT) as f:
                        frames.append(pd.read_csv(f, low_memory=False))
        except Exception:
            pass
    current_year = datetime.now().year
    for year in range(max(2017, start_year), current_year + 1):
        url = CFTC_TFF_YEAR_URL.format(year=year)
        try:
            resp = requests.get(url, timeout=90)
            if resp.status_code != 200:
                continue
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".txt"):
                        with zf.open(name) as f:
                            frames.append(pd.read_csv(f, low_memory=False))
                        break
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    _TFF_RAW_CACHE = pd.concat(frames, ignore_index=True)
    return _TFF_RAW_CACHE


def _market_mask(series: pd.Series, cfg: dict[str, Any]) -> pd.Series:
    """Prefer S&P 500 Consolidated (index); never sum e-mini + micro + dividend contracts."""
    primary = cfg.get("market_primary", "S&P 500 Consolidated")
    m = series.astype(str)
    consolidated = m.str.contains(primary, case=False, na=False)
    if consolidated.any():
        return consolidated
    exclude = cfg.get("market_exclude", "E-MINI|MICRO|DIVIDEND|ADJUSTED INT RATE")
    broad = m.str.contains(cfg.get("market_filter", "S&P 500"), case=False, na=False)
    return broad & ~m.str.contains(exclude, case=False, na=False, regex=True)


def parse_cftc_pair(
    df: pd.DataFrame,
    *,
    market_filter: str = "S&P 500",
    classification_regex: str,
) -> pd.Series:
    cfg = load_config().get("cftc", {})
    if market_filter:
        cfg = {**cfg, "market_filter": market_filter}
    market_col = _find_col(df, ["Market_and_Exchange_Names", "Market and Exchange Names"])
    cat_col = _find_col(
        df,
        [
            "Traders_Classification",
            "Trader Classification",
            "Traders Classification",
            "Traders-Classification",
        ],
    )
    if market_col is None:
        return pd.Series(dtype=float)

    mask = _market_mask(df[market_col], cfg)
    if cat_col:
        mask &= df[cat_col].astype(str).str.contains(classification_regex, case=False, na=False)

    sub = df.loc[mask].copy()
    date_col = _find_col(sub, ["Report_Date_as_YYYY-MM-DD", "Report_Date", "As of Date in Form YYYY-MM-DD"])
    if "Asset" in classification_regex:
        long_names = ["Asset_Mgr_Positions_Long_All", "Asset Mgr Positions-Long-All", "Asset_Mgr_Positions_Long_All"]
        short_names = ["Asset_Mgr_Positions_Short_All", "Asset Mgr Positions-Short-All", "Asset_Mgr_Positions_Short_All"]
    else:
        long_names = ["Lev_Money_Positions_Long_All", "Lev Money Positions-Long-All"]
        short_names = ["Lev_Money_Positions_Short_All", "Lev Money Positions-Short-All"]
    long_col = _find_col(sub, long_names)
    short_col = _find_col(sub, short_names)
    if long_col is None or short_col is None:
        long_col = long_col or _find_col(
            sub, ["Lev_Money_Positions_Long_All", "Lev Money Positions-Long-All"]
        )
        short_col = short_col or _find_col(
            sub, ["Lev_Money_Positions_Short_All", "Lev Money Positions-Short-All"]
        )

    if date_col is None or long_col is None or short_col is None:
        return pd.Series(dtype=float)

    sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
    sub["net"] = pd.to_numeric(sub[long_col], errors="coerce") - pd.to_numeric(sub[short_col], errors="coerce")
    # One consolidated row per date expected; use last if duplicates
    out = sub.groupby(date_col)["net"].last().sort_index()
    out.index = pd.to_datetime(out.index)
    return out.dropna()


def parse_cftc_dataframe(df: pd.DataFrame) -> pd.Series:
    """FM net series for backward compatibility."""
    cfg = load_config().get("cftc", {})
    return parse_cftc_pair(
        df,
        market_filter=cfg.get("market_filter", "S&P 500"),
        classification_regex=cfg.get("fm_classification", "Lev Money|Leveraged Funds"),
    )


def parse_cftc_rm_dataframe(df: pd.DataFrame) -> pd.Series:
    cfg = load_config().get("cftc", {})
    return parse_cftc_pair(
        df,
        market_filter=cfg.get("market_filter", "S&P 500"),
        classification_regex=cfg.get("rm_classification", "Asset Mgr|Asset Manager"),
    )


def _rolling_pctile(series: pd.Series, as_of: pd.Timestamp, weeks: int = 156) -> float | None:
    hist = series.loc[:as_of].dropna()
    if hist.empty:
        return None
    cutoff = as_of - pd.DateOffset(weeks=weeks)
    window = hist[hist.index >= cutoff]
    if len(window) < 10:
        window = hist
    return percentile_rank(float(hist.iloc[-1]), window)


def fetch_cftc_fast_money_net(start_year: int = 2006) -> pd.Series:
    try:
        df = _download_frames(start_year)
        if df.empty:
            return pd.Series(dtype=float)
        s = parse_cftc_dataframe(df)
        from src.macro_intelligence.data.retry_cache import log_pull

        log_pull("cftc_fm", "OK", {"rows": len(s)})
        return s
    except Exception as exc:
        from src.macro_intelligence.data.retry_cache import log_pull

        log_pull("cftc_fm", "ERROR", error=str(exc))
        return pd.Series(dtype=float)


def fetch_cftc_asset_manager_net(start_year: int = 2006) -> pd.Series:
    try:
        df = _download_frames(start_year)
        if df.empty:
            return pd.Series(dtype=float)
        s = parse_cftc_rm_dataframe(df)
        from src.macro_intelligence.data.retry_cache import log_pull

        log_pull("cftc_rm", "OK", {"rows": len(s)})
        return s
    except Exception as exc:
        from src.macro_intelligence.data.retry_cache import log_pull

        log_pull("cftc_rm", "ERROR", error=str(exc))
        return pd.Series(dtype=float)


def persist_cftc_snapshot(as_of: str) -> CftcSnapshot | None:
    fm = fetch_cftc_fast_money_net()
    rm = fetch_cftc_asset_manager_net()
    if fm.empty:
        return None
    ts = pd.Timestamp(as_of)
    fm_hist = fm.loc[:ts].dropna()
    if fm_hist.empty:
        return None
    fm_net = float(fm_hist.iloc[-1])
    rm_hist = rm.loc[:ts].dropna() if not rm.empty else pd.Series(dtype=float)
    rm_net = float(rm_hist.iloc[-1]) if not rm_hist.empty else None
    weeks = load_config().get("cftc", {}).get("pctile_window_weeks", 156)
    fm_pct = _rolling_pctile(fm, ts, weeks)
    rm_pct = _rolling_pctile(rm, ts, weeks) if rm_net is not None else None
    status = load_config().get("cftc", {}).get("pending_status", "PENDING_CFTC_CONFIRM")
    if datetime.now().weekday() == 4:
        status = "CONFIRMED"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cftc_positioning (date, fm_net, rm_net, fm_pctile, rm_pctile, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
              fm_net=excluded.fm_net, rm_net=excluded.rm_net,
              fm_pctile=excluded.fm_pctile, rm_pctile=excluded.rm_pctile, status=excluded.status
            """,
            (as_of, fm_net, rm_net, fm_pct, rm_pct, status),
        )
    return CftcSnapshot(ts, fm_net, rm_net, fm_pct, rm_pct, status)


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for cand in candidates:
        for col in df.columns:
            if col.strip() == cand or cand.lower() in col.lower():
                return col
    return None
