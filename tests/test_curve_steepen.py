"""Curve steepening from post-inversion trough."""

from __future__ import annotations

import pandas as pd

from src.macro_intelligence.data.fred_pull import curve_features, steepen_bps_post_inversion_trough
from src.macro_intelligence.engine.regime_v2_shadow import curve_regime_f2


def test_post_trough_steepen_positive_after_recovery():
    # Simulate inversion trough -1.0% then recovery to +0.38%
    idx = pd.date_range("2024-01-01", periods=80, freq="W-FRI")
    vals = [-0.5, -0.8, -1.0, -0.6, -0.2, 0.1, 0.2, 0.3, 0.38]
    vals = vals + [0.38] * (len(idx) - len(vals))
    spread_bps = pd.Series([v * 100 for v in vals], index=idx)
    steepen = steepen_bps_post_inversion_trough(spread_bps)
    assert float(steepen.iloc[-1]) >= 15


def test_curve_regime_steepening_when_post_trough_rise():
    spread = 38.0
    steepen = 120.0
    assert curve_regime_f2(spread, steepen, inverted_weeks=0) == "STEEPENING"


def test_curve_features_includes_post_trough_column():
    idx = pd.date_range("2020-01-01", periods=100, freq="D")
    t10y2y = pd.Series(0.5, index=idx)
    t10y2y.iloc[-30:] = 0.38
    t10y2y.iloc[-60:-30] = -0.2
    df = curve_features(t10y2y)
    assert "steepen_4wk_bps" in df.columns
    assert "steepen_4wk_simple_bps" in df.columns
