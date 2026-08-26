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
    # The all-or-nothing fallback below used to be `parsed.isna().all()`, which is only true when
    # every file in the frame shares the odd layout. In the combined history it never was: the
    # yearly files are ISO and the 2006-2016 bulk file is "M/D/YYYY 12:00:00 AM", so the bulk rows
    # coerced to NaT and were dropped without a word -- the analysis sample silently started 2017
    # instead of 2006-06-13, taking the GFC and 1052-week window with it (found 2026-08-20 while
    # answering Rohit's CFTC points). Parse the leftovers instead of testing whether *all* failed.
    missing = parsed.isna() & values.notna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            values.loc[missing], errors="coerce", format="mixed"
        )
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


def _component_frames(df: pd.DataFrame) -> tuple[str | None, str | None, pd.Series]:
    """(market column, date column, normalised market names) for the component-line parsers."""
    market_col = _find_col(df, ["Market_and_Exchange_Names", "Market and Exchange Names"])
    date_col = _find_col(
        df, ["Report_Date_as_YYYY-MM-DD", "Report_Date", "As of Date in Form YYYY-MM-DD"]
    )
    if market_col is None:
        return None, date_col, pd.Series(dtype=str)
    return market_col, date_col, df[market_col].astype(str).str.strip()


def _emini_equivalent_series(
    df: pd.DataFrame,
    *,
    asset_manager: bool = False,
    open_interest: bool = False,
) -> pd.Series:
    """S&P 500 positioning restated in E-mini contract equivalents, continuous 2006-06-13 on.

    CFTC changed what the "S&P 500 Consolidated" line means on 2023-05-02. Verified against the
    raw files, to the contract:

        2023-04-25  Consolidated OI 453,159   = E-mini 2,265,794 / 5      (+ big, then zero)
        2023-05-02  Consolidated OI 2,304,633 = E-mini 2,276,183 + micro 284,500 / 10

    So the line switched from big-contract ($250) equivalents to E-mini ($50) equivalents, and
    started including micro. Everything before 2023-05-02 is therefore 5x smaller than everything
    after it -- the pre and post ranges do not overlap in a single one of 834 weeks, and any
    156-week window spanning the date ranks one unit against the other. That artifact is what
    pinned the FM percentile near zero through 2023-24 (found by Rohit, 24 Aug 2026).

    Rather than splice a scale factor onto the Consolidated line -- which would still carry the
    micro-inclusion change and would break again at the next redefinition -- the series is summed
    from the component contract lines at their notional weights (see ``cftc.contract_weights``).
    That reproduces post-2023 Consolidated exactly (the big contract is retired, so the sum is
    E-mini + micro/10) and extends cleanly back to the first TFF report on 2006-06-13, with no
    stitch and no pre-2010 special case.
    """
    cfg = load_config().get("cftc", {})
    weights: dict[str, float] = cfg.get("contract_weights") or {}
    if not weights:
        return pd.Series(dtype=float)

    market_col, date_col, names = _component_frames(df)
    if market_col is None or date_col is None or names.empty:
        return pd.Series(dtype=float)

    if open_interest:
        value_cols = [_find_col(df, ["Open_Interest_All", "Open Interest (All)"])]
    elif asset_manager:
        value_cols = [
            _find_col(df, ["Asset_Mgr_Positions_Long_All", "Asset Mgr Positions-Long-All"]),
            _find_col(df, ["Asset_Mgr_Positions_Short_All", "Asset Mgr Positions-Short-All"]),
        ]
    else:
        value_cols = [
            _find_col(df, ["Lev_Money_Positions_Long_All", "Lev Money Positions-Long-All"]),
            _find_col(df, ["Lev Money Positions-Short-All", "Lev_Money_Positions_Short_All"]),
        ]
    if any(col is None for col in value_cols):
        return pd.Series(dtype=float)

    dates = _parse_report_dates(df[date_col])
    lowered = names.str.lower()
    total: pd.Series | None = None
    for label, weight in weights.items():
        mask = lowered == str(label).strip().lower()
        if not mask.any():
            continue
        sub = df.loc[mask]
        value = pd.to_numeric(sub[value_cols[0]], errors="coerce")
        if len(value_cols) == 2:
            value = value - pd.to_numeric(sub[value_cols[1]], errors="coerce")
        leg = pd.Series(value.values, index=pd.DatetimeIndex(dates.loc[mask])).dropna()
        # One row per market per report date; ``last`` guards against re-published corrections.
        leg = leg.groupby(level=0).last() * float(weight)
        total = leg if total is None else total.add(leg, fill_value=0.0)

    if total is None or total.empty:
        return pd.Series(dtype=float)
    return total.sort_index()


def detect_unit_break(
    data: pd.DataFrame | pd.Series,
    *,
    ratio: float | None = None,
    agreement: float = 0.15,
) -> list[dict[str, Any]]:
    """Weeks that look like a contract/aggregation change rather than like positioning.

    Rohit's standing test after the 2023-05-02 seam. The tell is not that one number moved a
    lot -- leveraged funds really do swing -- it is that *every* field scales by the *same*
    factor in the same week, which no market variable does. So pass the fields together
    (open interest, FM net, RM net) and the check requires them to agree:

        2023-05-02 raw Consolidated: OI x5.09, FM x4.81, RM x5.09  -> flagged
        2022-03-22 genuine short build: OI x1.01, FM x1.6, RM x1.0 -> not flagged

    ``ratio`` is the minimum common scale factor (default ``cftc.unit_break_ratio``);
    ``agreement`` is how far the per-field factors may spread before the week is treated as
    ordinary positioning. A single Series is checked on its own, with no agreement test, which
    is weaker -- prefer the frame form.
    """
    cfg = load_config().get("cftc", {})
    ratio = float(ratio if ratio is not None else cfg.get("unit_break_ratio", 2.5))
    frame = data.to_frame("value") if isinstance(data, pd.Series) else data
    frame = frame.dropna(how="all").sort_index()
    if len(frame) < 2:
        return []

    prior = frame.shift(1)
    # Ratios only mean anything away from zero: a field crossing zero produces an arbitrary
    # factor, so fields whose prior level is negligible sit the vote out.
    floor = frame.abs().median() * 0.05
    breaks: list[dict[str, Any]] = []
    for i in range(1, len(frame)):
        factors: dict[str, float] = {}
        for col in frame.columns:
            before, after = prior[col].iloc[i], frame[col].iloc[i]
            if pd.isna(before) or pd.isna(after) or abs(before) <= float(floor[col]):
                continue
            factors[str(col)] = abs(float(after)) / abs(float(before))
        if len(factors) < max(2, len(frame.columns)):
            continue
        values = list(factors.values())
        if min(values) < ratio:
            continue
        if (max(values) - min(values)) / min(values) > agreement:
            continue  # fields disagree -> positioning, not a redefinition
        breaks.append(
            {
                "date": str(frame.index[i].date()),
                "common_factor": round(sum(values) / len(values), 2),
                "factors": {k: round(v, 2) for k, v in factors.items()},
            }
        )
    return breaks


CFTC_LEGACY_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"
LEGACY_FIRST_YEAR = 2003
TFF_FIRST_DATE = "2006-06-13"


def _legacy_zip_path(year: int) -> Path:
    return CFTC_LOCAL_CACHE_DIR / f"deacot{year}.zip"


def _fetch_legacy_zips(start_year: int, end_year: int) -> list[Path]:
    """Legacy Commitments-of-Traders annual zips, downloaded once and cached beside the TFF ones."""
    CFTC_LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for year in range(start_year, end_year + 1):
        path = _legacy_zip_path(year)
        if not path.is_file():
            url = CFTC_LEGACY_URL.format(year=year)
            try:
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                path.write_bytes(resp.content)
                logger.info("CFTC legacy COT %s downloaded (%d bytes)", year, len(resp.content))
            except Exception as exc:
                logger.warning("CFTC legacy COT %s unavailable: %s", year, exc)
                continue
        paths.append(path)
    return paths


def fetch_cftc_legacy_noncommercial_net(
    start_year: int = LEGACY_FIRST_YEAR,
    end_year: int = 2010,
) -> pd.Series:
    """S&P 500 non-commercial net (long minus short) from the legacy COT report.

    **This is not Fast Money.** TFF Leveraged Money begins 2006-06-13; before that the only
    available split is the legacy commercial / non-commercial one, which is a different trader
    definition -- non-commercial lumps managed money together with other speculators and is not
    a like-for-like substitute. It is built here so the pre-2006 years Rohit asked for exist as a
    clearly-labelled proxy (``series_tier='legacy_noncommercial'``), and so the definitional gap
    can be measured on the overlap rather than argued about (``compare_legacy_to_tff``).
    """
    paths = _fetch_legacy_zips(start_year, end_year)
    frames = _read_zip_frames(paths)
    if not frames:
        return pd.Series(dtype=float)
    df = pd.concat(frames, ignore_index=True)
    market_col = _find_col(df, ["Market and Exchange Names", "Market_and_Exchange_Names"])
    date_col = _find_col(
        df, ["As of Date in Form YYYY-MM-DD", "Report_Date_as_YYYY-MM-DD", "As_of_Date_In_Form_YYMMDD"]
    )
    long_col = _find_col(df, ["Noncommercial Positions-Long (All)", "NonComm_Positions_Long_All"])
    short_col = _find_col(df, ["Noncommercial Positions-Short (All)", "NonComm_Positions_Short_All"])
    if not all([market_col, date_col, long_col, short_col]):
        logger.warning("CFTC legacy COT: expected columns missing, got %s", list(df.columns)[:8])
        return pd.Series(dtype=float)

    cfg = load_config().get("cftc", {})
    exclude = cfg.get("market_exclude", "E-MINI|MICRO|DIVIDEND|ADJUSTED INT RATE")
    names = df[market_col].astype(str).str.strip()
    mask = names.str.contains("S&P 500", case=False, na=False)
    mask &= ~names.str.contains(exclude, case=False, na=False, regex=True)
    sub = df.loc[mask].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    sub[date_col] = _parse_report_dates(sub[date_col])
    sub = sub.dropna(subset=[date_col])
    net = pd.to_numeric(sub[long_col], errors="coerce") - pd.to_numeric(sub[short_col], errors="coerce")
    out = pd.Series(net.values, index=pd.DatetimeIndex(sub[date_col]), dtype=float).dropna()
    return out.sort_index().groupby(level=0).last()


def compare_legacy_to_tff(
    legacy: pd.Series | None = None,
    tff: pd.Series | None = None,
    *,
    overlap_end: str = "2010-12-31",
) -> dict[str, Any]:
    """Quantify the definitional gap on the overlap before anyone leans on the pre-2006 years.

    Reports level correlation, weekly-change correlation and rank agreement between the legacy
    non-commercial net and TFF leveraged-money net over the window where both exist.
    """
    legacy = fetch_cftc_legacy_noncommercial_net() if legacy is None else legacy
    tff = fetch_cftc_fast_money_net(2006) if tff is None else tff
    if legacy.empty or tff.empty:
        return {"overlap_weeks": 0, "note": "one of the series is empty"}
    idx = legacy.index.intersection(tff.index)
    idx = idx[idx <= pd.Timestamp(overlap_end)]
    if len(idx) < 20:
        return {"overlap_weeks": int(len(idx)), "note": "overlap too short to judge"}
    a, b = legacy.loc[idx], tff.loc[idx]
    da, db = a.diff().dropna(), b.diff().dropna()
    common = da.index.intersection(db.index)
    return {
        "overlap_start": str(idx.min().date()),
        "overlap_end": str(idx.max().date()),
        "overlap_weeks": int(len(idx)),
        "level_corr": round(float(a.corr(b)), 4),
        "level_rank_corr": round(float(a.corr(b, method="spearman")), 4),
        "change_corr": round(float(da.loc[common].corr(db.loc[common])), 4),
        "legacy_mean": round(float(a.mean()), 1),
        "tff_mean": round(float(b.mean()), 1),
        "legacy_std": round(float(a.std()), 1),
        "tff_std": round(float(b.std()), 1),
    }


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


def _positioning_series(df: pd.DataFrame, *, asset_manager: bool = False) -> pd.Series:
    """FM/RM net on the configured unit basis, falling back to the Consolidated line."""
    basis = str(load_config().get("cftc", {}).get("unit_basis", "emini_equivalent")).lower()
    if basis == "emini_equivalent":
        restated = _emini_equivalent_series(df, asset_manager=asset_manager)
        if not restated.empty:
            return restated
        logger.warning(
            "CFTC unit_basis=emini_equivalent produced no rows (contract lines missing?); "
            "falling back to the Consolidated line, which carries the 2023-05-02 unit seam."
        )
    return _stitch_legacy_consolidated_net(df, asset_manager=asset_manager)


def fetch_cftc_open_interest(start_year: int = 2006) -> pd.Series:
    """S&P 500 open interest on the same unit basis as the FM/RM series."""
    df = _download_frames(start_year)
    if df.empty:
        return pd.Series(dtype=float)
    return _emini_equivalent_series(df, open_interest=True)


def fetch_cftc_fast_money_net(start_year: int = 2006) -> pd.Series:
    try:
        df = _download_frames(start_year)
        if df.empty:
            return pd.Series(dtype=float)
        s = _positioning_series(df, asset_manager=False)
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
        s = _positioning_series(df, asset_manager=True)
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
