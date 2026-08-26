"""Export the S&P 500 CFTC TFF series restated into one unit (E-mini equivalents).

Replaces the June export that Rohit reviewed on 24 Aug 2026. That file carried CFTC's
2023-05-02 redefinition of the "S&P 500 Consolidated" line -- big-contract equivalents before,
E-mini equivalents (micro included) after -- so every field scaled ~5x in one week and no
156-week percentile spanning the date was rankable.

Writes two files:

* ``cftc_tff_sp500_fm_rm_2006_2026.csv``            -- restated, continuous, 2006-06-13 onward
* ``cftc_tff_sp500_fm_rm_legacy_consolidated.csv``  -- the published Consolidated line as-is,
  kept so the seam stays reproducible and the pre/post split can be run against it

Rolling percentiles are published only once the 156-week window is genuinely full, so the
first ranked week is the true analysis start rather than the 20-observation date.

Usage:  python scripts/export_cftc_restated_series.py [--out-dir macro_intelligence/output]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data import cftc_pull as C  # noqa: E402
from src.macro_intelligence.engine.percentiles import percentile_rank  # noqa: E402


def _full_window_pctile(series: pd.Series, weeks: int) -> pd.Series:
    """Rank each week against the trailing ``weeks``-week window, blank until the window fills."""
    out: list[float | None] = []
    for i, ts in enumerate(series.index):
        window = series.iloc[: i + 1]
        window = window[window.index >= ts - pd.DateOffset(weeks=weeks)]
        out.append(percentile_rank(float(series.iloc[i]), window) if len(window) >= weeks else None)
    return pd.Series(out, index=series.index, dtype=float)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = C._download_frames(2006)
    if raw.empty:
        raise SystemExit("no CFTC TFF data in the local cache -- run scripts/download_cftc_tff_zip.py")
    weeks = int(load_config().get("cftc", {}).get("pctile_window_weeks", 156))

    restated = pd.DataFrame(
        {
            "Open_Interest": C._emini_equivalent_series(raw, open_interest=True),
            "FM_Net": C._emini_equivalent_series(raw, asset_manager=False),
            "RM_Net": C._emini_equivalent_series(raw, asset_manager=True),
        }
    ).dropna(how="all")
    restated["FM_WeeklyChange"] = restated["FM_Net"].diff()
    restated["RM_WeeklyChange"] = restated["RM_Net"].diff()
    restated["FM_Pctile_3yr_Rolling"] = _full_window_pctile(restated["FM_Net"], weeks).round(2)
    restated["RM_Pctile_3yr_Rolling"] = _full_window_pctile(restated["RM_Net"], weeks).round(2)
    restated["Unit"] = "emini_equivalent"
    restated.index.name = "Date"

    legacy = pd.DataFrame(
        {
            "FM_Net": C._stitch_legacy_consolidated_net(raw, asset_manager=False),
            "RM_Net": C._stitch_legacy_consolidated_net(raw, asset_manager=True),
        }
    ).dropna(how="all")
    legacy["Unit"] = "published_consolidated_line"
    legacy.index.name = "Date"
    return restated, legacy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(_ROOT / "macro_intelligence" / "output"))
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    restated, legacy = build()
    restated_path = out_dir / "cftc_tff_sp500_fm_rm_2006_2026.csv"
    legacy_path = out_dir / "cftc_tff_sp500_fm_rm_legacy_consolidated.csv"
    restated.round(1).to_csv(restated_path)
    legacy.round(1).to_csv(legacy_path)

    ranked = restated["FM_Pctile_3yr_Rolling"].dropna()
    breaks = C.detect_unit_break(restated[["Open_Interest", "FM_Net", "RM_Net"]])
    legacy_breaks = C.detect_unit_break(legacy[["FM_Net", "RM_Net"]])
    print(f"restated : {restated_path}  {len(restated)} weeks  "
          f"{restated.index.min().date()} -> {restated.index.max().date()}")
    print(f"           first ranked week (full {int(load_config().get('cftc', {}).get('pctile_window_weeks', 156))}w window): "
          f"{ranked.index.min().date()}  ranked weeks: {len(ranked)}")
    print(f"           unit breaks: {breaks or 'none'}")
    print(f"legacy   : {legacy_path}  {len(legacy)} weeks  unit breaks: {legacy_breaks}")


if __name__ == "__main__":
    main()
