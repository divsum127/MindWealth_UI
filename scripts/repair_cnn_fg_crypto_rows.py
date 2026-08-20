"""Remove CRYPTO Fear & Greed values from the CNN F&G cache, refetching CNN where it has data.

Why
---
``src/sentiment_superindex/data/cnn_fear_greed.py`` documents the Alternative.me crypto index as a
disclosed proxy for one residual window only (2011-01 -> 2012-05-24). The live cache disagrees:
audited 2026-08-20, ``macro_intelligence/data/ssi/cnn_fear_greed.csv`` carried **974** rows tagged
``crypto_proxy`` spanning 2018-02-03 -> 2026-07-15, and **24 of them fell on real SPX trading
days** -- including 2026-03-12 and 2026-07-15, where the page showed a crypto sentiment number as
the CNN stock-market print. CNN's own API has no value for those two dates (verified live), so
there is nothing to substitute: the honest state is no observation, which lets the SSI daily carry
(cap 3d, weight-penalised) use the last real CNN print instead.

What it does
------------
1. Refetches CNN's own history and fills any ``crypto_proxy`` date CNN actually covers.
2. Drops every remaining ``crypto_proxy`` row -- none of them fall in the documented residual
   window, so each one is a crypto number standing in for a stock-market index.
3. Prints a before/after audit: rows removed, rows recovered from CNN, and the trading-day count,
   so the effect on SSI history is visible rather than silent.

Run
---
    .venv/bin/python scripts/repair_cnn_fg_crypto_rows.py            # audit only
    .venv/bin/python scripts/repair_cnn_fg_crypto_rows.py --apply    # write the cache
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config_paths import SSI_DATA_DIR  # noqa: E402
from src.sentiment_superindex.data.cnn_fear_greed import CNN_CACHE, fetch_cnn_history  # noqa: E402

CRYPTO_SOURCE = "crypto_proxy"
SPX_CACHE = SSI_DATA_DIR / "yahoo" / "gspc.csv"


def _trading_days() -> set[pd.Timestamp]:
    """SPX session dates from the Yahoo cache -- the dates a CNN print is expected."""
    spx = pd.read_csv(SPX_CACHE)
    date_col = next(c for c in spx.columns if "date" in c.lower())
    dates = pd.to_datetime(spx[date_col], utc=True, errors="coerce").dt.tz_localize(None)
    return set(dates.dropna().dt.normalize())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the repaired cache")
    args = parser.parse_args()

    cache = pd.read_csv(CNN_CACHE)
    cache["date"] = pd.to_datetime(cache["date"]).dt.normalize()
    crypto = cache[cache["source"] == CRYPTO_SOURCE]
    sessions = _trading_days()
    on_sessions = crypto[crypto["date"].isin(sessions)]

    print(f"cache rows            : {len(cache)}")
    print(f"crypto_proxy rows     : {len(crypto)}  ({crypto['date'].min().date()} -> {crypto['date'].max().date()})")
    print(f"  of which SPX sessions: {len(on_sessions)}")
    for _, row in on_sessions.tail(10).iterrows():
        print(f"    {row['date'].date()}  score {row['score']:.2f}")

    cnn = fetch_cnn_history()
    cnn.index = pd.DatetimeIndex(cnn.index).normalize()
    cnn = cnn[~cnn.index.duplicated(keep="last")]
    recoverable = crypto[crypto["date"].isin(set(cnn.index))]
    print(f"recoverable from CNN  : {len(recoverable)}")

    repaired = cache.copy()
    recovered_dates = set(recoverable["date"])
    is_recovered = repaired["date"].isin(recovered_dates) & (repaired["source"] == CRYPTO_SOURCE)
    repaired.loc[is_recovered, "score"] = repaired.loc[is_recovered, "date"].map(cnn)
    repaired.loc[is_recovered, "source"] = "real_cnn_api"

    still_crypto = repaired["source"] == CRYPTO_SOURCE
    print(f"dropped (no CNN value): {int(still_crypto.sum())}")
    repaired = repaired[~still_crypto].sort_values("date").reset_index(drop=True)
    print(f"cache rows after      : {len(repaired)}")

    if not args.apply:
        print("\naudit only -- rerun with --apply to write")
        return 0

    repaired["date"] = repaired["date"].dt.strftime("%Y-%m-%d")
    repaired.to_csv(CNN_CACHE, index=False)
    print(f"\nwritten {CNN_CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
