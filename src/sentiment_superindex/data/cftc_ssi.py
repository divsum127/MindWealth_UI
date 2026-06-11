"""SSI Layer 3 CFTC FM/RM and gross-net divergence."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.macro_intelligence.data.cftc_pull import (
    fetch_cftc_asset_manager_net,
    fetch_cftc_fast_money_net,
    persist_cftc_snapshot,
)
from src.macro_intelligence.engine.percentiles import percentile_rank


def cftc_layer3_snapshot(as_of: str) -> dict[str, Any]:
    snap = persist_cftc_snapshot(as_of)
    if not snap:
        return {}
    fm = fetch_cftc_fast_money_net()
    rm = fetch_cftc_asset_manager_net()
    ts = pd.Timestamp(as_of)
    gross = None
    if not fm.empty and not rm.empty:
        gross = float(fm.loc[:ts].iloc[-1]) + float(rm.loc[:ts].iloc[-1])
    return {
        "fm_net": snap.fm_net,
        "rm_net": snap.rm_net,
        "fm_pctile": snap.fm_pctile,
        "rm_pctile": snap.rm_pctile,
        "status": snap.status,
        "gross_net_divergence": gross,
    }
