"""Streamlit page for Runic Macro Intelligence Agent."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config_paths import MACRO_INTEL_CONFIG, MACRO_INTEL_JSON_PATH, SSI_ANALYSIS_DIR, SSI_POSITIONING_JSON
from src.macro_intelligence.engine.vix_bypass import VIX_BYPASS_BANNER
from src.macro_intelligence.config import load_config


@st.cache_data(show_spinner=False)
def _load_output() -> dict | None:
    path = MACRO_INTEL_JSON_PATH
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def _load_positioning() -> dict | None:
    if not SSI_POSITIONING_JSON.exists():
        return None
    return json.loads(SSI_POSITIONING_JSON.read_text(encoding="utf-8"))


def create_runic_page() -> None:
    st.title("Macro Intelligence — Runic + SSI")
    st.caption(f"Runic: `{MACRO_INTEL_JSON_PATH}` | SSI: `{SSI_POSITIONING_JSON}`")

    data = _load_output()
    if not data:
        st.warning(f"No output at `{MACRO_INTEL_JSON_PATH}`. Run `python scripts/run_macro_nightly.py --no-claude`.")
        return

    if data.get("vix_bypass"):
        st.error(VIX_BYPASS_BANNER)

    col1, col2, col3 = st.columns(3)
    col1.metric("Date", data.get("date", "—"))
    col2.metric("Dominant", data.get("dominant_signal", "—"))
    col3.metric("SSI mult.", f"{data.get('ssi_multiplier', 1.0):.2f}×")

    pos = _load_positioning()
    if pos:
        st.subheader("SSI (Sentiment SuperIndex)")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("SSI level", f"{pos.get('ssi_level', 0):.3f}")
        p2.metric("5y pctile", pos.get("ssi_percentile_5y", "—"))
        p3.metric("Layer 2", pos.get("layer2_status", "—"))
        p4.metric("L2 votes", pos.get("layer2_confirmed_count", "—"))
        sig = pos.get("signals", {})
        if sig:
            st.caption(
                f"Long threshold {sig.get('long', {}).get('entry_threshold')} | "
                f"Short threshold {sig.get('short', {}).get('entry_threshold')}"
            )
    else:
        st.info(f"No SSI file at `{SSI_POSITIONING_JSON}`. Run `python scripts/run_ssi_daily.py`.")

    sweep_files = sorted(SSI_ANALYSIS_DIR.glob("ssi_threshold_sweep_*.csv"), reverse=True) if SSI_ANALYSIS_DIR.exists() else []
    if sweep_files:
        with st.expander("Latest SSI threshold sweep"):
            st.dataframe(pd.read_csv(sweep_files[0]), use_container_width=True, hide_index=True)

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
        st.info("Watch combos")
        st.dataframe(pd.DataFrame(watch), use_container_width=True, hide_index=True)

    st.subheader("Live Variable Dashboard")
    dash = data.get("variables_dashboard", [])
    if dash:
        st.dataframe(pd.DataFrame(dash), use_container_width=True, hide_index=True)

    analog_details = data.get("analog_details") or []
    if analog_details:
        st.subheader("Historical analogs (dominant combo)")
        st.dataframe(pd.DataFrame(analog_details), use_container_width=True, hide_index=True)
    elif data.get("analog_dates"):
        st.caption(f"Analog dates: {', '.join(data['analog_dates'])}")

    hr = data.get("spx_3m_hit_rate")
    if hr is not None:
        st.caption(
            f"3m SPX stats for Combo {data.get('dominant_signal')}: "
            f"hit rate {hr * 100:.0f}%, avg return {data.get('spx_3m_forward_avg')}%"
        )

    st.subheader("Macro Intelligence Briefing")
    st.write(data.get("narrative", ""))
    st.caption(data.get("dominant_reason", ""))
    date = data.get("date", "")
    html_path = Path(f"macro_intelligence/output/runic_briefing_{date}.html")
    if html_path.exists():
        st.download_button(
            "Download BTIG-style briefing (HTML)",
            html_path.read_text(encoding="utf-8"),
            file_name=html_path.name,
            mime="text/html",
        )
    if data.get("ppi_cooling") is not None:
        st.caption(f"PPI cooling (context only): {data.get('ppi_cooling')}")
    if data.get("combo_c_cancel"):
        st.caption(f"Combo C cancel progress: week {data['combo_c_cancel'].get('wti_potential_week', 0)} of 4")

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
