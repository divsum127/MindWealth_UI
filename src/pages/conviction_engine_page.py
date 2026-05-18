"""Streamlit page for Conviction Engine signal overlays."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..conviction_engine.data_coverage import summarize_pe_history_distribution
from ..conviction_engine.engine import apply_to_signal_file, generate_daily_report, update_overrides
from ..conviction_engine.formatting import display_columns, summarize_overlay
from ..conviction_engine.fundamentals_enriched import PE_HISTORY_TARGET_YEARS
from ..conviction_engine.signals import discover_signal_sources
from ..conviction_engine.store import list_records, load_record, overlay_path


@st.cache_data(show_spinner=False)
def _load_overlay(source_path: str) -> pd.DataFrame:
    return apply_to_signal_file(source_path, save_output=False)


def _metric_cards(summary: dict[str, int]) -> None:
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Signals", summary["total_signals"])
    col2.metric("Applicable", summary["applicable"])
    col3.metric("Cancel Buy", summary["cancel_buy"])
    col4.metric("Max (raw ≥8)", summary["max_conviction"], help="Equity BUY with conviction_raw ≥8 or verdict MAX CONVICTION. Uses raw score because FS caps often block the verdict.")
    col5.metric("Tactical+ (≥5)", summary.get("tactical_plus", 0), help="Equity BUY with conviction_raw ≥5 (strong fundamental tier).")
    col6.metric("Yield traps", summary["yield_traps"], help="yield_trap_warning true, or rationale mentions yield trap; includes rationale fallback for CSV-reloaded rows.")
    st.caption(
        "Max conviction counts **fundamental** tier (raw score). Verdict alone undercounts because apply_fs_cap can cap below +8 even when raw is high."
    )


def _conviction_chart(df: pd.DataFrame) -> None:
    if df.empty or "conviction_score" not in df.columns:
        st.info("No conviction score data available for charting.")
        return

    score_df = df[pd.to_numeric(df["conviction_score"], errors="coerce").notna()].copy()
    if score_df.empty:
        st.info("No numeric conviction scores available.")
        return

    score_df["conviction_score"] = pd.to_numeric(score_df["conviction_score"], errors="coerce")
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=score_df["conviction_score"],
            nbinsx=20,
            name="Conviction Score",
        )
    )
    fig.update_layout(
        title="Conviction Score Distribution",
        xaxis_title="Conviction Score",
        yaxis_title="Signal Count",
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)


def _pe_history_years_chart() -> None:
    summary = summarize_pe_history_distribution(list_records())
    dist = summary.get("years_distribution") or []
    if not dist or not summary.get("total_equity_records"):
        st.info("No equity conviction records with P/E history metadata yet. Run a full fundamentals refresh.")
        return

    labels = [str(row["bucket"]) for row in dist]
    counts = [int(row["count"]) for row in dist]
    fig = go.Figure(data=[go.Bar(x=labels, y=counts, name="Tickers")])
    fig.update_layout(
        title=f"P/E history span (years) — target {PE_HISTORY_TARGET_YEARS}Y",
        xaxis_title="Years of valid trailing P/E series",
        yaxis_title="Equity tickers",
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"{summary.get('insufficient_20y_count', 0)} of {summary.get('total_equity_records', 0)} equities "
        f"({summary.get('insufficient_20y_pct', 0)}%) have < {PE_HISTORY_TARGET_YEARS} years. "
        f"{summary.get('without_pe_series', 0)} have no P/E series."
    )
    with st.expander("Per-ticker P/E history years", expanded=False):
        rows = summary.get("tickers") or []
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _verdict_chart(df: pd.DataFrame) -> None:
    if df.empty or "verdict" not in df.columns:
        return
    counts = df["verdict"].fillna("Unknown").astype(str).value_counts()
    fig = go.Figure(data=[go.Bar(x=counts.index.tolist(), y=counts.values.tolist())])
    fig.update_layout(title="Verdict Counts", xaxis_title="Verdict", yaxis_title="Count", height=420)
    st.plotly_chart(fig, use_container_width=True)


def _ticker_detail(df: pd.DataFrame) -> None:
    ticker_values: list[str] = []
    if "ticker" in df.columns:
        ticker_values.extend(df["ticker"].dropna().astype(str).unique().tolist())
    ticker_values.extend([str(record.get("ticker")) for record in list_records() if record.get("ticker")])
    ticker_values = sorted(set(ticker_values))

    if not ticker_values:
        st.info("No ticker records or overlaid signals available yet.")
        return

    ticker = st.selectbox("Select ticker", ticker_values, key="conviction_ticker_select")
    signal_rows = df[df.get("ticker", pd.Series(dtype=str)).astype(str) == ticker] if "ticker" in df.columns else pd.DataFrame()
    record = load_record(ticker)

    if record:
        coverage = record.get("data_coverage") or {}
        low_conf = bool(coverage.get("low_data_confidence"))
        if low_conf:
            st.warning(
                "Low data confidence: sparse fundamentals, fetch issues, or missing valuation inputs. "
                "Scores may rely on neutral-zero BQ dimensions; see Missing fields below."
            )
        cols = st.columns(8)
        cols[0].metric("BQ Raw", record.get("bq_raw", "N/A"))
        cols[1].metric("Valuation Tax", record.get("valuation_tax", "N/A"))
        cols[2].metric("Conviction", record.get("conviction_score", "N/A"))
        cols[3].metric("FS Class", record.get("fs_class", "N/A"))
        cols[4].metric("Yield Trap", str(record.get("yield_trap_warning", False)))
        cols[5].metric("Business Type", record.get("business_type", "N/A"))
        ratio = coverage.get("coverage_ratio")
        cols[6].metric(
            "Data coverage",
            f"{ratio:.0%}" if isinstance(ratio, (int, float)) else "N/A",
            help="Share of critical fundamental fields present on the record.",
        )
        cols[7].metric("Low confidence", "Yes" if low_conf else "No")
        pe_hist = record.get("pe_history_meta") or coverage.get("pe_history") or {}
        years = pe_hist.get("years_available")
        if years is not None:
            insufficient = pe_hist.get("insufficient_20y", True)
            st.caption(
                f"P/E history: **{years}** years "
                f"({'<' if insufficient else '≥'} {PE_HISTORY_TARGET_YEARS}Y target)"
                + (" — percentile uses shorter history" if insufficient else "")
            )
    else:
        st.warning("No stored conviction record exists for this ticker yet.")

    if not signal_rows.empty:
        st.markdown("#### Overlaid Signals")
        st.dataframe(signal_rows[display_columns(signal_rows)], use_container_width=True, hide_index=True)

    if record:
        coverage = record.get("data_coverage") or {}
        missing = record.get("missing_fields") or coverage.get("fields_missing") or []
        fetch_errors = coverage.get("fetch_errors") or record.get("fetch_errors") or []
        with st.expander("Missing fields / fetch errors", expanded=bool(coverage.get("low_data_confidence"))):
            if fetch_errors:
                st.markdown("**Fetch errors**")
                for err in fetch_errors:
                    st.write(f"- {err}")
            if missing:
                st.markdown("**Missing fields**")
                st.code(", ".join(str(m) for m in missing))
            else:
                st.caption("No missing critical fields reported.")
            statements = coverage.get("statements") or {}
            if statements:
                st.markdown("**Quarterly statements (non-empty at last full fetch)**")
                st.write(
                    f"Income: {statements.get('income', False)} | "
                    f"Balance: {statements.get('balance', False)} | "
                    f"Cashflow: {statements.get('cashflow', False)}"
                )
            valuation = coverage.get("valuation_inputs") or {}
            if valuation:
                st.markdown("**Valuation tax inputs**")
                st.json(valuation)
            bq_dims = coverage.get("bq_auto_dimensions") or {}
            if bq_dims:
                with st.expander("BQ dimension inputs", expanded=False):
                    st.json(bq_dims)

    with st.expander("Stored JSON Record", expanded=False):
        if record:
            st.json(record)
        else:
            st.write("No record found.")


def _manual_overrides() -> None:
    st.caption("Use JSON overrides for fields such as bq_raw, business_type, fd_direction, or bq_components.")
    ticker = st.text_input("Ticker", key="conviction_override_ticker").strip().upper()
    raw_updates = st.text_area(
        "Override JSON",
        value='{"fd_direction": "stable"}',
        height=140,
        key="conviction_override_json",
    )
    if st.button("Apply Overrides", key="conviction_apply_overrides"):
        if not ticker:
            st.error("Enter a ticker first.")
            return
        try:
            updates = json.loads(raw_updates)
            if not isinstance(updates, dict):
                raise ValueError("Override JSON must be an object")
            record = update_overrides(ticker, updates)
            st.success(f"Updated overrides for {record.get('ticker')}.")
            st.cache_data.clear()
        except Exception as exc:
            st.error(f"Could not apply overrides: {exc}")


def create_conviction_engine_page() -> None:
    st.title("Conviction Engine")
    st.caption("Fundamental conviction overlay for existing quant signals in trade_store.")

    sources = discover_signal_sources()
    if not sources:
        st.warning("No supported signal CSVs were found in trade_store.")
        return

    source_label = st.selectbox("Signal source", list(sources.keys()), key="conviction_source")
    source_path = sources[source_label]
    st.caption(f"Source: {source_path}")

    with st.spinner("Applying conviction overlay..."):
        overlay_df = _load_overlay(str(source_path))

    summary = summarize_overlay(overlay_df)
    _metric_cards(summary)

    tab_overlay, tab_charts, tab_detail, tab_report, tab_overrides = st.tabs(
        ["Signal Overlay", "Charts", "Ticker Detail", "Daily Report", "Manual Overrides"]
    )

    with tab_overlay:
        if overlay_df.empty:
            st.info("No rows available in selected source.")
        else:
            search = st.text_input("Search ticker", key="conviction_signal_search").strip().upper()
            display_df = overlay_df
            if search and "ticker" in display_df.columns:
                display_df = display_df[display_df["ticker"].astype(str).str.upper().str.contains(search, na=False)]
            st.dataframe(display_df[display_columns(display_df)], use_container_width=True, hide_index=True)
            csv = display_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download overlaid CSV",
                data=csv,
                file_name=overlay_path(source_path).name,
                mime="text/csv",
            )

    with tab_charts:
        col1, col2 = st.columns(2)
        with col1:
            _conviction_chart(overlay_df)
        with col2:
            _verdict_chart(overlay_df)
        st.markdown("#### P/E history coverage (universe)")
        _pe_history_years_chart()

    with tab_detail:
        _ticker_detail(overlay_df)

    with tab_report:
        records = list_records()
        alert_map = {}
        for record in records:
            flags = []
            if record.get("yield_trap_warning"):
                flags.append("yield_trap")
            if record.get("fs_class") in {"weak", "moderate_low"}:
                flags.append(f"fs_{record.get('fs_class')}")
            if (record.get("conviction_score") or 0) < 2:
                flags.append("low_conviction")
            if flags and record.get("ticker"):
                alert_map[str(record["ticker"])] = flags
        st.text(generate_daily_report(alert_map, records))

    with tab_overrides:
        _manual_overrides()
