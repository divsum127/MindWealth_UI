"""Signal Quality Composite bubble chart (Y) vs lifecycle / timeliness (X)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st


def render_quality_bubble_chart(
    rows: list[dict[str, Any]],
    *,
    title: str = "Signal Quality Composite vs Lifecycle",
    height: int = 520,
    x_axis_mode: str = "auto",
) -> None:
    """Render bubble chart when at least one row has composite_score.

    x_axis_mode: 'auto' | 'window_remaining' | 'timeliness'
    Outstanding Signals should pass x_axis_mode='window_remaining' per Supplementary §1.
    """
    if not rows:
        st.info("No quality-composite data available for bubble chart.")
        return

    df = pd.DataFrame(rows)
    if "composite_score" not in df.columns:
        st.info("composite_score not present — run a nightly pipeline with MasterSpec fields.")
        return

    df = df[df["composite_score"].notna()].copy()
    if df.empty:
        st.info("No signals with a computed composite score.")
        return

    if x_axis_mode == "window_remaining" and "window_remaining_pct" in df.columns and df["window_remaining_pct"].notna().any():
        df["lifecycle_x"] = df["window_remaining_pct"]
        x_label = "Window Remaining % (time in avg-hold window)"
    elif (x_axis_mode in ("auto", "timeliness")) and "timeliness_score" in df.columns and df["timeliness_score"].notna().any():
        df["lifecycle_x"] = df["timeliness_score"]
        x_label = "Timeliness Score (100 = new, 0 = aged out)"
    elif "days_elapsed" in df.columns:
        df["lifecycle_x"] = df["days_elapsed"]
        x_label = "Days Elapsed Since Signal"
    else:
        st.info("No lifecycle axis (timeliness_score or days_elapsed) available.")
        return

    df["label"] = (
        df.get("symbol", "").astype(str)
        + " | "
        + df.get("function", "").astype(str)
        + " "
        + df.get("interval", "").astype(str)
    )
    if "tier" in df.columns:
        color_col = "tier"
    elif "asset_class" in df.columns:
        color_col = "asset_class"
    else:
        color_col = None

    size_col = "signal_alpha_per_trade" if "signal_alpha_per_trade" in df.columns else None
    if size_col and df[size_col].notna().any():
        df["_size"] = df[size_col].abs().clip(lower=0.1)
    else:
        df["_size"] = 12

    fig = px.scatter(
        df,
        x="lifecycle_x",
        y="composite_score",
        size="_size",
        color=color_col,
        hover_name="label",
        hover_data={
            "er": True,
            "er_annualized": True,
            "signal_alpha_per_trade": True,
            "signal_alpha_annualized": True,
            "reward_remaining_pct": True,
            "window_remaining_pct": True,
            "intrinsic_lag_days": True,
            "rr_dynamic": True,
            "tier": True,
            "lifecycle_x": False,
            "_size": False,
        },
        title=title,
        labels={
            "lifecycle_x": x_label,
            "composite_score": "Signal Quality Composite (v4)",
        },
        height=height,
    )
    fig.update_layout(
        yaxis=dict(title="Signal Quality Composite Score"),
        legend_title_text=color_col.replace("_", " ").title() if color_col else "",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Y-axis: v4 composite — C1 E[R]_ann + C2 signal_alpha_ann + C3 Sharpe + C4 CAGR_diff. "
        "X-axis: signal lifecycle (window remaining % for Outstanding; timeliness for New). "
        "Bubble size ∝ |signal_alpha| when available."
    )
