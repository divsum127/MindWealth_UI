"""Streamlit page for Conviction Engine signal overlays."""

from __future__ import annotations

# import json  # Manual Overrides tab (disabled)
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..conviction_engine.data_coverage import summarize_pe_history_distribution
from ..conviction_engine.daily_run import run_daily_conviction_pipeline
# from ..conviction_engine.engine import generate_daily_report, update_overrides  # Daily Report / Manual Overrides tabs (disabled)
from ..conviction_engine.scoring import market_yield_threshold
from ..conviction_engine.formatting import display_columns, summarize_overlay
from ..conviction_engine.fundamentals_enriched import PE_HISTORY_TARGET_YEARS
from ..conviction_engine.signals import PRIMARY_DAILY_REPORT
from ..conviction_engine.store import (
    daily_new_signal_overlay_path,
    list_daily_snapshot_dates,
    list_records,
    load_daily_new_signal_overlay,
    load_record,
)


@st.cache_data(show_spinner=False)
def _load_archived_overlay(report_date: str) -> pd.DataFrame:
    return load_daily_new_signal_overlay(report_date)


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


def _ticker_detail(df: pd.DataFrame, archive_date: str | None = None) -> None:
    ticker_values: list[str] = []
    if "ticker" in df.columns:
        ticker_values = sorted(df["ticker"].dropna().astype(str).unique().tolist())

    if not ticker_values:
        st.info("No ticker records or overlaid signals available yet.")
        return

    ticker = st.selectbox("Select ticker", ticker_values, key="conviction_ticker_select")
    signal_rows = df[df.get("ticker", pd.Series(dtype=str)).astype(str) == ticker] if "ticker" in df.columns else pd.DataFrame()
    record = load_record(ticker)
    if archive_date:
        st.caption(
            f"Overlay snapshot: **{archive_date}** (New Signals). "
            "Ticker JSON below is the latest conviction_store record and may differ from that day."
        )

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
        with st.expander("Yield trap diagnostics", expanded=False):
            cy = record.get("dividend_yield_current")
            z = record.get("dividend_yield_zscore")
            mean = record.get("dividend_yield_5y_mean")
            std = record.get("dividend_yield_5y_std")
            thresh = market_yield_threshold(ticker)
            st.write(
                {
                    "dividend_yield_current": cy,
                    "dividend_yield_zscore": z,
                    "dividend_yield_5y_mean": mean,
                    "dividend_yield_5y_std": std,
                    "market_threshold": thresh,
                    "z_above_1_5": (z is not None and float(z) > 1.5),
                    "yield_above_market": (cy is not None and float(cy) > thresh),
                    "yield_trap_warning": record.get("yield_trap_warning"),
                }
            )
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


# def _manual_overrides() -> None:
#     st.caption("Use JSON overrides for fields such as bq_raw, business_type, fd_direction, or bq_components.")
#     ticker = st.text_input("Ticker", key="conviction_override_ticker").strip().upper()
#     raw_updates = st.text_area(
#         "Override JSON",
#         value='{"fd_direction": "stable"}',
#         height=140,
#         key="conviction_override_json",
#     )
#     if st.button("Apply Overrides", key="conviction_apply_overrides"):
#         if not ticker:
#             st.error("Enter a ticker first.")
#             return
#         try:
#             updates = json.loads(raw_updates)
#             if not isinstance(updates, dict):
#                 raise ValueError("Override JSON must be an object")
#             record = update_overrides(ticker, updates)
#             st.success(f"Updated overrides for {record.get('ticker')}.")
#             st.cache_data.clear()
#         except Exception as exc:
#             st.error(f"Could not apply overrides: {exc}")


def create_conviction_engine_page() -> None:
    st.title("Conviction Engine")

    snapshot_dates = list_daily_snapshot_dates()
    if not snapshot_dates:
        st.warning("No conviction data for New Signals yet. Run the daily trade update first.")
        return

    col_date, col_rebuild = st.columns([4, 1])
    with col_date:
        selected_date = st.selectbox(
            "Report date",
            list(reversed(snapshot_dates)),
            key="conviction_report_date",
        )
    with col_rebuild:
        st.write("")
        st.write("")
        if st.button("Rebuild", key="conviction_rebuild_date", help="Refresh conviction for this date's New Signals."):
            with st.spinner(f"Rebuilding {selected_date}..."):
                result = run_daily_conviction_pipeline(
                    report_date=selected_date,
                    overlay_reports=[PRIMARY_DAILY_REPORT],
                    fundamentals_mode="daily",
                )
            st.cache_data.clear()
            if result.get("status") == "error":
                st.error(result.get("error", "Rebuild failed"))
            else:
                st.success("Done")
                st.rerun()

    archive_path = daily_new_signal_overlay_path(selected_date)
    overlay_df = _load_archived_overlay(selected_date)

    if overlay_df.empty:
        st.info(f"No conviction overlay for {selected_date}. Use Rebuild after New Signals are available.")
        return

    summary = summarize_overlay(overlay_df)
    _metric_cards(summary)

    tab_overlay, tab_charts, tab_detail = st.tabs(["Signal Overlay", "Charts", "Ticker Detail"])
    # tab_report, tab_overrides = Daily Report, Manual Overrides (disabled — see commented blocks below)

    download_name = archive_path.name if archive_path else f"{selected_date}_new_signal_conviction.csv"

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
                file_name=download_name,
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
        _ticker_detail(overlay_df, archive_date=selected_date)

    # with tab_report:
    #     records = list_records()
    #     alert_map = {}
    #     for record in records:
    #         flags = []
    #         if record.get("yield_trap_warning"):
    #             flags.append("yield_trap")
    #         if record.get("fs_class") in {"weak", "moderate_low"}:
    #             flags.append(f"fs_{record.get('fs_class')}")
    #         if (record.get("conviction_score") or 0) < 2:
    #             flags.append("low_conviction")
    #         if flags and record.get("ticker"):
    #             alert_map[str(record["ticker"])] = flags
    #     st.text(generate_daily_report(alert_map, records))

    # with tab_overrides:
    #     _manual_overrides()
