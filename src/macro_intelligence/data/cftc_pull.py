"""CFTC TFF report parsing — Fast Money (combos) + Asset Manager (context/SSI)."""

from __future__ import annotations

import logging

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

logger = logging.getLogger("macro.cftc")

CFTC_TFF_YEAR_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
CFTC_TFF_BULK_URL = "https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip"
CFTC_TFF_BULK_TXT = "F_TFF_2006_2016.txt"
CFTC_LOCAL_CACHE_DIR = Path(__file__).resolve().parents[3] / "macro_intelligence" / "data_cache" / "cftc"
# Keyed by start_year: a single global meant the first caller's window was served to
# every later caller for the life of the process (the API server is long-lived).
_TFF_RAW_CACHE: dict[int, pd.DataFrame] = {}

# How old a cached ZIP can be before we force a re-download regardless of the day.
# CFTC publishes every Friday — so anything older than 8 days means we missed a release.
_CFTC_STALE_DAYS = 8

# Minimum observations before a rolling percentile is publishable. A full 156-week window holds
# ~156 weekly prints; 100 allows for the genuine ramp-up at the very start of the TFF series
# (June 2006) while still rejecting the "only the current year was loaded" failure.
MIN_PCTILE_WINDOW_OBS = 100


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
        _TFF_RAW_CACHE.clear()  # force re-parse on next fetch
        return True
    except Exception:
        return False


def force_refresh_cftc_zip(year: int | None = None) -> bool:
    """Download current-year CFTC TFF ZIP unconditionally (nightly lag recovery)."""

    year = year or datetime.now().year
    local_path = CFTC_LOCAL_CACHE_DIR / f"fut_fin_txt_{year}.zip"
    url = CFTC_TFF_YEAR_URL.format(year=year)
    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            return False
        CFTC_LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(resp.content)
        _TFF_RAW_CACHE.clear()
        return True
    except Exception:
        return False


def _expected_zip_specs(start_year: int) -> list[tuple[Path, str]]:
    """Every (local path, source URL) the requested window needs, oldest first.

    Made explicit because "which files should exist" and "which files do exist" were
    previously the same question -- see ``_download_frames``.
    """
    cache = CFTC_LOCAL_CACHE_DIR
    specs: list[tuple[Path, str]] = []
    if start_year <= 2016:
        specs.append((cache / "fin_fut_txt_2006_2016.zip", CFTC_TFF_BULK_URL))
    current_year = datetime.now().year
    for year in range(max(2017, start_year), current_year + 1):
        specs.append((cache / f"fut_fin_txt_{year}.zip", CFTC_TFF_YEAR_URL.format(year=year)))
    return specs


def _local_zip_paths(start_year: int) -> list[Path]:
    """Zips already on disk for the requested window (saved by download_cftc_tff_zip.py)."""
    if not CFTC_LOCAL_CACHE_DIR.is_dir():
        return []
    return [path for path, _ in _expected_zip_specs(start_year) if path.is_file()]


def _fetch_missing_zips(start_year: int) -> list[Path]:
    """Download only the window's missing zips into the local cache. Returns what was added.

    This is what stops a *partial* cache being mistaken for a complete one. On prod the cache
    held only ``fut_fin_txt_2026.zip``, so the 156-week percentile window was computed over the
    ~31 weekly prints of the current year: identical ``fm_net`` of -333,099 ranked 87.1st on
    prod (27/31) against 52.9th on dev (82/155). Nothing flagged it, because a short window is
    indistinguishable from a normal one once the frames are concatenated.
    """
    added: list[Path] = []
    for path, url in _expected_zip_specs(start_year):
        if path.is_file():
            continue
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code != 200:
                logger.warning("CFTC zip unavailable (HTTP %s): %s", resp.status_code, url)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(resp.content)
            added.append(path)
            logger.info("CFTC zip backfilled: %s (%d bytes)", path.name, len(resp.content))
        except Exception as exc:
            logger.warning("CFTC zip download failed for %s: %s", url, exc)
    return added


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
    """TFF futures-only files (fut_fin_txt_*.zip), not legacy deacot.

    Completeness matters more than presence here: the percentile window is only as deep as the
    files that were loaded, so a cache holding one year silently produces a one-year rank. Any
    zip the window needs but does not have is fetched and persisted, rather than the whole
    network path being skipped because *some* local file was found.
    """
    cached = _TFF_RAW_CACHE.get(start_year)
    if cached is not None and not cached.empty:
        return cached

    expected = _expected_zip_specs(start_year)
    _fetch_missing_zips(start_year)
    local = _local_zip_paths(start_year)
    if len(local) < len(expected):
        missing = [path.name for path, _ in expected if not path.is_file()]
        logger.warning(
            "CFTC history incomplete for start_year=%s: %d of %d zips present, missing %s. "
            "Rolling percentiles will be computed over a shortened window.",
            start_year,
            len(local),
            len(expected),
            missing,
        )

    frames = _read_zip_frames(local)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    _TFF_RAW_CACHE[start_year] = combined
    return combined


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

    sub[date_col] = _parse_report_dates(sub[date_col])
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


def _parse_report_dates(values: pd.Series) -> pd.Series:
    """Parse the TFF ``Report_Date_as_YYYY-MM-DD`` column.

    The column is ISO by contract, but parsing it without an explicit format made pandas fall
    back to per-element ``dateutil`` and emit a UserWarning for every call. Those warnings were
    the only thing in ssi_daily.log -- hundreds of lines of noise that hid the real pull
    failures. The explicit format is also an order of magnitude faster on a full history.
    """
    parsed = pd.to_datetime(values, format="%Y-%m-%d", errors="coerce")
    if parsed.isna().all() and len(values):
        # Older bulk files have been seen with other layouts; fall back rather than lose them.
        parsed = pd.to_datetime(values, errors="coerce", format="mixed")
    return parsed


def _exact_market_net(
    df: pd.DataFrame,
    market_label: str,
    *,
    asset_manager: bool = False,
) -> pd.Series:
    """Parse FM or RM net for one exact TFF market line (no consolidated preference)."""
    market_col = _find_col(df, ["Market_and_Exchange_Names", "Market and Exchange Names"])
    if market_col is None:
        return pd.Series(dtype=float)
    needle = market_label.strip().lower()
    sub = df.loc[df[market_col].astype(str).str.strip().str.lower() == needle].copy()
    if sub.empty:
        sub = df.loc[df[market_col].astype(str).str.contains(market_label, case=False, na=False)].copy()
        exclude = load_config().get("cftc", {}).get("market_exclude", "E-MINI|MICRO|DIVIDEND|ADJUSTED INT RATE")
        sub = sub.loc[~sub[market_col].astype(str).str.contains(exclude, case=False, na=False, regex=True)]
        sub = sub.loc[sub[market_col].astype(str).str.contains(market_label, case=False, na=False)]
    if sub.empty:
        return pd.Series(dtype=float)
    if asset_manager:
        long_names = ["Asset_Mgr_Positions_Long_All", "Asset Mgr Positions-Long-All"]
        short_names = ["Asset_Mgr_Positions_Short_All", "Asset Mgr Positions-Short-All"]
    else:
        long_names = ["Lev_Money_Positions_Long_All", "Lev Money Positions-Long-All"]
        short_names = ["Lev_Money_Positions_Short_All", "Lev Money Positions-Short-All"]
    date_col = _find_col(sub, ["Report_Date_as_YYYY-MM-DD", "Report_Date", "As of Date in Form YYYY-MM-DD"])
    long_col = _find_col(sub, long_names)
    short_col = _find_col(sub, short_names)
    if date_col is None or long_col is None or short_col is None:
        return pd.Series(dtype=float)
    sub[date_col] = _parse_report_dates(sub[date_col])
    sub["net"] = pd.to_numeric(sub[long_col], errors="coerce") - pd.to_numeric(sub[short_col], errors="coerce")
    out = sub.groupby(date_col)["net"].last().sort_index()
    out.index = pd.to_datetime(out.index)
    return out.dropna()


def _stitch_legacy_consolidated_net(df: pd.DataFrame, *, asset_manager: bool = False) -> pd.Series:
    """Production Consolidated line + pre-2010 S&P 500 STOCK INDEX backfill for GFC-era tests."""
    cfg = load_config().get("cftc", {})
    primary = cfg.get("market_primary", "S&P 500 Consolidated")
    legacy = cfg.get("legacy_market_backfill", "S&P 500 STOCK INDEX")
    if not cfg.get("legacy_market_backfill_enabled", True):
        if asset_manager:
            return parse_cftc_rm_dataframe(df)
        return parse_cftc_dataframe(df)
    consolidated = _exact_market_net(df, primary, asset_manager=asset_manager)
    if consolidated.empty:
        if asset_manager:
            return parse_cftc_rm_dataframe(df)
        return parse_cftc_dataframe(df)
    legacy_series = _exact_market_net(df, legacy, asset_manager=asset_manager)
    if legacy_series.empty:
        return consolidated
    cutoff = consolidated.index.min()
    pre = legacy_series.loc[legacy_series.index < cutoff]
    if pre.empty:
        return consolidated
    return pd.concat([pre, consolidated]).sort_index().groupby(level=0).last()


def _rolling_pctile(series: pd.Series, as_of: pd.Timestamp, weeks: int = 156) -> float | None:
    """3-year rolling percentile **rank** of the latest value (dashboard ``fm_pctile`` / ``rm_pctile``).

    Uses ``percentile_rank`` (fraction of window readings <= current), not min–max
    range position. Low FM rank = most net short in the window; high = least net short.
    """
    hist = series.loc[:as_of].dropna()
    if hist.empty:
        return None
    cutoff = as_of - pd.DateOffset(weeks=weeks)
    window = hist[hist.index >= cutoff]
    if len(window) < 10:
        window = hist
    # A rank is only meaningful against the window it claims to use. Before this guard a
    # partial zip cache produced a ~31-week window that was published as a "3yr pct" -- the
    # same fm_net ranked 87.1st on prod and 52.9th on dev. Refusing to rank is the correct
    # answer to "we do not have three years of history", the same way combo hit rates refuse
    # to publish below their minimum episode count.
    if len(window) < MIN_PCTILE_WINDOW_OBS:
        logger.warning(
            "CFTC percentile suppressed: window has %d observations, need %d for a %d-week "
            "rank (history likely incomplete -- check %s)",
            len(window),
            MIN_PCTILE_WINDOW_OBS,
            weeks,
            CFTC_LOCAL_CACHE_DIR,
        )
        return None
    return percentile_rank(float(hist.iloc[-1]), window)


def describe_cftc_pctile_window(
    series: pd.Series,
    as_of: str | pd.Timestamp,
    *,
    weeks: int | None = None,
) -> dict[str, Any]:
    """Diagnostic: min/max and sign mix for the CFTC rolling percentile window."""
    ts = pd.Timestamp(as_of)
    weeks = weeks if weeks is not None else load_config().get("cftc", {}).get("pctile_window_weeks", 156)
    hist = series.loc[:ts].dropna()
    if hist.empty:
        return {"as_of": str(ts.date()), "weeks": weeks, "n": 0}
    cutoff = ts - pd.DateOffset(weeks=weeks)
    window = hist[hist.index >= cutoff]
    if len(window) < 10:
        window = hist
    current = float(hist.iloc[-1])
    n = len(window)
    n_neg = int((window < 0).sum())
    n_pos = int((window > 0).sum())
    n_zero = int((window == 0).sum())
    roll_min = float(window.min())
    roll_max = float(window.max())
    minmax_pct = (
        (current - roll_min) / (roll_max - roll_min) * 100 if roll_max != roll_min else 50.0
    )
    rank_pct = percentile_rank(current, window)
    return {
        "as_of": str(ts.date()),
        "weeks": weeks,
        "n": n,
        "current": current,
        "min": roll_min,
        "max": roll_max,
        "sign_negative": n_neg,
        "sign_zero": n_zero,
        "sign_positive": n_pos,
        "sign_negative_pct": round(100.0 * n_neg / n, 1),
        "sign_positive_pct": round(100.0 * n_pos / n, 1),
        "minmax_range_pct": round(minmax_pct, 2) if minmax_pct is not None else None,
        "percentile_rank": round(rank_pct, 2) if rank_pct is not None else None,
    }


def fetch_cftc_fast_money_net(start_year: int = 2006) -> pd.Series:
    try:
        df = _download_frames(start_year)
        if df.empty:
            return pd.Series(dtype=float)
        s = _stitch_legacy_consolidated_net(df, asset_manager=False)
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
        s = _stitch_legacy_consolidated_net(df, asset_manager=True)
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
    from src.macro_intelligence.data.source_freshness import check_cftc_freshness

    freshness = check_cftc_freshness(as_of, fm)
    pending_status = load_config().get("cftc", {}).get("pending_status", "PENDING_CFTC_CONFIRM")
    status = pending_status if freshness.stale else "CONFIRMED"
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
