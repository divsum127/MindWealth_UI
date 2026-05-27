"""Streamlit page for Runic Macro Intelligence Agent."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config_paths import MACRO_INTEL_CONFIG, MACRO_INTEL_JSON_PATH
from src.macro_intelligence.config import load_config


@st.cache_data(show_spinner=False)
def _load_output() -> dict | None:
    path = MACRO_INTEL_JSON_PATH
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def create_runic_page() -> None:
    st.title("Macro Intelligence — Runic Agent v2.2")
    st.caption("Reads runic_output.json only (not SSI positioning.json)")

    data = _load_output()
    if not data:
        st.warning(f"No output at `{MACRO_INTEL_JSON_PATH}`. Run `python scripts/run_macro_nightly.py --no-claude`.")
        return

    if data.get("vix_bypass"):
        st.error("VIX REGIME MULTIPLIER BYPASSED — Combo B (or confirmed F) active. Full size in effect.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Date", data.get("date", "—"))
    col2.metric("Dominant", data.get("dominant_signal", "—"))
    col3.metric("SSI mult.", f"{data.get('ssi_multiplier', 1.0):.2f}×")

    st.subheader("Current Regime")
    regime = data.get("regime", {})
    rcols = st.columns(5)
    for i, key in enumerate(["fed_cycle", "curve_regime", "geo_overlay", "val_regime", "liquidity"]):
        rcols[i].metric(key.replace("_", " ").title(), regime.get(key, "—"))

    st.subheader("Combo Status")
    combos = data.get("active_combos", [])
    watch = data.get("watch_combos", [])
    if combos:
        st.dataframe(pd.DataFrame(combos), use_container_width=True, hide_index=True)
    if watch:
        st.info(f"Watch combos: {', '.join(watch)}")

    st.subheader("Live Variable Dashboard")
    dash = data.get("variables_dashboard", [])
    if dash:
        st.dataframe(pd.DataFrame(dash), use_container_width=True, hide_index=True)

    st.subheader("Macro Intelligence Briefing")
    st.write(data.get("narrative", ""))
    st.caption(data.get("dominant_reason", ""))

    with st.expander("Raw JSON"):
        st.json(data)

    with st.expander("Percentile history windows"):
        cfg = load_config()
        rows = []
        for v in cfg.get("variables", []):
            rows.append(
                {
                    "Variable": v["id"],
                    "Window": v.get("pctile_window", "rolling_3y"),
                    "Start": v.get("pctile_start", "—"),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(f"Config: `{MACRO_INTEL_CONFIG}`")
