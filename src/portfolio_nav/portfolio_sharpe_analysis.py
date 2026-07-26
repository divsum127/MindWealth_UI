"""Trade loading + price fetch for Ahil NAV engine (MindWealth forward_testing inputs)."""

from __future__ import annotations

import os
import pickle
from datetime import timedelta
from pathlib import Path

import pandas as pd

from src.config_paths import BASE_DIR, MINDWEALTH_ROOT
from src.portfolio_nav.combos import HIGH_WIN_RATE_COMBOS, normalize_combo_key

_OPEN_TRADE_MAX_AGE_DAYS = 14
_PRICE_CACHE_DIR = BASE_DIR / "src" / "portfolio_nav" / "cache"
_PRICE_CACHE_FILE = _PRICE_CACHE_DIR / "prices.pkl"

_FORWARD_TESTING_ROOT = Path(
    os.getenv(
        "PORTFOLIO_FORWARD_TESTING_ROOT",
        str(MINDWEALTH_ROOT / "trade_store" / "US" / "forward_testing"),
    )
)
_STAKE_CSV = Path(
    os.getenv("PORTFOLIO_STAKE_CSV", str(MINDWEALTH_ROOT / "data" / "stake.csv"))
)


def set_forward_testing_root(path: Path | str) -> None:
    global _FORWARD_TESTING_ROOT
    _FORWARD_TESTING_ROOT = Path(path)


def load_all_strategy_trades(root: Path | str | None = None) -> pd.DataFrame:
    """Load all forward-testing CSV rows under ``<STRATEGY>/<SYMBOL>/<Interval>.csv``."""
    base = Path(root) if root else _FORWARD_TESTING_ROOT
    if not base.is_dir():
        raise FileNotFoundError(f"forward_testing root not found: {base}")

    frames: list[pd.DataFrame] = []
    for path in sorted(base.glob("*/*/*.csv")):
        try:
            frames.append(_load_trades_from_file(path))
        except Exception:
            continue
    if not frames:
        raise FileNotFoundError(f"No trade CSVs under {base}")
    out = pd.concat(frames, ignore_index=True)
    return out


def _load_trades_from_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return df
    mtime = pd.Timestamp(path.stat().st_mtime, unit="s").normalize()
    exit_col = pd.to_datetime(df.get("Exit Date"), errors="coerce")
    max_exit = exit_col.max()
    is_open = False
    if pd.notna(max_exit):
        is_open = (exit_col == max_exit) & ((mtime - max_exit).days <= _OPEN_TRADE_MAX_AGE_DAYS)
    df = df.copy()
    df["is_open"] = is_open.fillna(False).astype(bool)
    df["Entry Date"] = pd.to_datetime(df["Entry Date"], errors="coerce")
    df["Exit Date"] = pd.to_datetime(df["Exit Date"], errors="coerce")
    return df


def load_stake_symbols(stake_path: Path | str | None = None) -> set[str]:
    path = Path(stake_path) if stake_path else _STAKE_CSV
    df = pd.read_csv(path)
    col = "symbol" if "symbol" in df.columns else df.columns[0]
    return {str(s).strip().upper() for s in df[col].dropna()}


def filter_trades_by_symbols(df: pd.DataFrame, symbols: set[str]) -> pd.DataFrame:
    sym = df["Symbol"].astype(str).str.upper()
    return df[sym.isin(symbols)].copy()


def filter_trades_by_win_rate_combos(df: pd.DataFrame) -> pd.DataFrame:
    keys = df.apply(
        lambda r: normalize_combo_key(r.get("Function"), r.get("Interval"), r.get("Signal")),
        axis=1,
    )
    return df[keys.isin(HIGH_WIN_RATE_COMBOS)].copy()


def split_versions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Version A (closed only) and Version B (all incl. synthetic open exits)."""
    work = df.copy()
    work["Exit Date"] = pd.to_datetime(work["Exit Date"], errors="coerce")
    work["Entry Date"] = pd.to_datetime(work["Entry Date"], errors="coerce")
    closed = work[~work["is_open"].astype(bool)].copy()
    full_b = work.copy()
    return closed, full_b


def fetch_daily_prices_for_trades(
    trades_df: pd.DataFrame,
    *,
    use_cache: bool = True,
) -> tuple[dict[str, pd.Series], pd.Series | None]:
    """Fetch daily close prices for trade symbols (+ ^IRX stub). Returns symbol -> close series."""
    symbols = sorted({str(s).upper() for s in trades_df["Symbol"].dropna().unique()})
    cache_key = tuple(symbols)
    if use_cache and _PRICE_CACHE_FILE.is_file():
        try:
            with _PRICE_CACHE_FILE.open("rb") as fh:
                cached = pickle.load(fh)
            if cached.get("symbols") == cache_key:
                return cached["price_map"], cached.get("irx")
        except Exception:
            pass

    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError("yfinance required for nav_engine price fetch") from exc

    start = trades_df["Entry Date"].min() - timedelta(days=5)
    end = trades_df["Exit Date"].max() + timedelta(days=5)
    price_map: dict[str, pd.Series] = {}
    for sym in symbols:
        try:
            data = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
            if data is None or data.empty:
                continue
            close = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            price_map[sym] = close.dropna()
        except Exception:
            continue

    irx = None
    _PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with _PRICE_CACHE_FILE.open("wb") as fh:
            pickle.dump({"symbols": cache_key, "price_map": price_map, "irx": irx}, fh)
    except Exception:
        pass
    return price_map, irx


def fetch_benchmark_monthly(
    month_end_dates: list[pd.Timestamp],
) -> list[float]:
    """S&P 500 (^GSPC) month-end levels aligned to portfolio month ends."""
    if not month_end_dates:
        return []
    try:
        import yfinance as yf
    except ImportError:
        return []

    start = min(month_end_dates) - timedelta(days=40)
    end = max(month_end_dates) + timedelta(days=5)
    data = yf.download("^GSPC", start=start, end=end, progress=False, auto_adjust=True)
    if data is None or data.empty:
        return []
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.sort_index()
    levels: list[float] = []
    for dt in month_end_dates:
        subset = close[close.index <= dt]
        levels.append(float(subset.iloc[-1]) if len(subset) else float("nan"))
    return levels
