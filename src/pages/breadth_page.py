"""
Breadth analysis page for signal breadth indicators
"""

import streamlit as st
import pandas as pd
import os

from ..components.cards import create_breadth_summary_cards, create_breadth_cards
from ..utils.data_loader import load_data_from_file
from ..parsers.advanced_parsers import _breadth_is_sbi_schema, _breadth_parse_number
from constant import BREADTH_SIGNAL_STORE_CSV_PATH_US
from ..utils.file_discovery import extract_date_from_filename

_COMBINED_CHART_FUNCTIONS = (
    'Combined (TrendPulse + DeltaDrift + BandMatrix)',
    'All Function Combined',
)

_LONG_PCT_COL = 'Today Long Signal Percentile From Top (Last 6 Month)'
_SHORT_PCT_COL = 'Today Short Signal Percentile From Top (Last 6 Month)'


def _has_valid_sbi_percentile(val) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip()
    return s not in ('', 'nan', 'N/A', 'Not Applicable')


def _filter_sbi_chart_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep Combined rows with at least one populated SBI percentile."""
    if df.empty:
        return df
    has_long = df[_LONG_PCT_COL].apply(_has_valid_sbi_percentile) if _LONG_PCT_COL in df.columns else False
    has_short = df[_SHORT_PCT_COL].apply(_has_valid_sbi_percentile) if _SHORT_PCT_COL in df.columns else False
    if isinstance(has_long, bool) and isinstance(has_short, bool):
        return df.iloc[0:0]
    return df[has_long | has_short].copy()


def _breadth_entry_csv_path(data_file):
    """Companion file: YYYY-MM-DD_breadth_entry.csv next to YYYY-MM-DD_breadth.csv, or breadth_entry.csv next to breadth.csv."""
    dirname = os.path.dirname(data_file)
    basename = os.path.basename(data_file)
    if basename == "breadth.csv":
        return os.path.join(dirname, "breadth_entry.csv")
    if basename.endswith("_breadth.csv"):
        return os.path.join(dirname, basename.replace("_breadth.csv", "_breadth_entry.csv"))
    return None


def create_breadth_page(data_file, page_title):
    """Create a specialized page for breadth signal data"""
    # Info button at the top
    if st.button("ℹ️ Info About Page", key=f"info_breadth_{page_title}", help="Click to learn about this page"):
        st.session_state[f'show_info_breadth_{page_title}'] = not st.session_state.get(f'show_info_breadth_{page_title}', False)
    
    if st.session_state.get(f'show_info_breadth_{page_title}', False):
        with st.expander("📖 Market Breadth Information", expanded=True):
            st.markdown("""
            ### What is this page?
            The Signal Breadth Indicator (SBI) page shows **trade-arrival** metrics on the **S&P 500** universe:
            how many new long/short signals arrived today, and where today's counts rank versus the last 6 months
            (top-percentile from the busiest day).

            ### Why is it used?
            - **Signal activity**: See whether today is a quiet or extreme day for new signals
            - **Market-wide view**: The **Combined** row aggregates TrendPulse, DeltaDrift, and Band Matrix
            - **Strategy breakdown**: Compare TRENDPULSE, DELTADRIFT, and BAND MATRIX individually
            - **Historical context**: Chart tracks Combined-row long/short percentiles over time

            ### How to use?
            1. **Review Summary**: Combined-row new signal counts and today percentiles
            2. **Analyze Strategies**: Per-function cards with thresholds and percentiles
            3. **View Chart**: SBI trade-arrival percentile history (Combined row)
            4. **Compare Functions**: Contrast activity across strategies
            5. **Track Trends**: Monitor percentile changes over dates in the chart

            ### Key metrics (trade-arrival SBI)
            - **Total New Long/Short Signal**: Count of new signals today
            - **Today Long/Short Percentile From Top**: Rank vs last 6 months (**lower = busier**, e.g. 10 ≈ top 10% activity; **higher = quieter**; 100 with 0 signals = no new signals)
            - **Last 6 Month Top 10 Percentile**: Historical threshold for extreme days
            - Legacy reports may still show Bullish Asset/Signal % when present
            """)
    
    st.title(f"📊 {page_title}")
    
    # Display data fetch datetime at top of page (from JSON file)
    from ..utils.helpers import display_data_fetch_info
    display_data_fetch_info(location="header")
    
    st.markdown("---")
    
    # Load data from the specific file
    df = load_data_from_file(f'{data_file}', page_title)
    
    if df.empty:
        st.warning(f"No signal data available for {page_title}")
        return
    
    # Breadth summary cards
    st.markdown("### 🎯 Market Breadth Summary")
    create_breadth_summary_cards(df)
    
    st.markdown("---")
    
    # Breadth analysis cards
    st.markdown("### 📈 Strategy Breadth Analysis")
    create_breadth_cards(df)
    
    # Historical SBI chart from consolidated breadth store
    st.markdown("---")
    st.markdown("### 📊 SBI Trade-Arrival Chart")
    try:
        sbi_df = pd.read_csv(BREADTH_SIGNAL_STORE_CSV_PATH_US, index_col=False)
        data_rows = sbi_df[sbi_df['Function'].isin(_COMBINED_CHART_FUNCTIONS)].copy()

        if not data_rows.empty and 'Date' in data_rows.columns:
            data_rows['Date'] = pd.to_datetime(data_rows['Date'], errors='coerce')
            data_rows = data_rows.dropna(subset=['Date'])
            data_rows = data_rows.sort_values('Date')
            data_rows = data_rows.drop_duplicates(subset=['Date'], keep='last')

        use_sbi_chart = _breadth_is_sbi_schema(data_rows) if not data_rows.empty else False
        if use_sbi_chart:
            data_rows = _filter_sbi_chart_rows(data_rows)

        if not data_rows.empty:
            x = data_rows['Date'].dt.strftime('%Y-%m-%d').tolist() if 'Date' in data_rows.columns else list(range(1, len(data_rows) + 1))
            xaxis_title = 'Date'

            import plotly.graph_objects as go
            fig = go.Figure()

            if use_sbi_chart:
                y_long = [
                    _breadth_parse_number(v)
                    for v in data_rows[_LONG_PCT_COL].tolist()
                ]
                y_short = [
                    _breadth_parse_number(v)
                    for v in data_rows[_SHORT_PCT_COL].tolist()
                ]
                fig.add_trace(go.Scatter(
                    x=x, y=y_long, mode='lines+markers',
                    name='Long percentile from top',
                    line=dict(color='#1f77b4', width=3),
                ))
                fig.add_trace(go.Scatter(
                    x=x, y=y_short, mode='lines+markers',
                    name='Short percentile from top',
                    line=dict(color='#ff7f0e', width=3),
                ))
                chart_title = 'SBI trade-arrival percentiles (Combined row; lower = busier)'
                yaxis_title = 'Percentile from top (%)'
            else:
                y1 = [_breadth_parse_number(v) for v in data_rows['Bullish Asset vs Total Asset (%)'].tolist()]
                y2 = [_breadth_parse_number(v) for v in data_rows['Bullish Signal vs Total Signal (%)'].tolist()]
                fig.add_trace(go.Scatter(
                    x=x, y=y1, mode='lines', name='Bullish Asset vs Total Asset (%)',
                    line=dict(color='#1f77b4', width=3),
                ))
                fig.add_trace(go.Scatter(
                    x=x, y=y2, mode='lines', name='Bullish Signal vs Total Signal (%)',
                    line=dict(color='#ff7f0e', width=3),
                ))
                chart_title = 'Legacy bullish breadth (Combined row)'
                yaxis_title = 'Percentage (%)'

            fig.update_layout(
                title=chart_title,
                xaxis_title=xaxis_title,
                yaxis_title=yaxis_title,
                legend=dict(
                    orientation='h',
                    yanchor='bottom', y=1.05,
                    xanchor='right', x=1,
                    bgcolor='rgba(255,255,255,0.95)',
                    bordercolor='#333', borderwidth=1,
                    font=dict(size=13, color='#111'),
                ),
                margin=dict(t=110, b=70, r=20, l=65),
                plot_bgcolor='white',
                paper_bgcolor='#fafafa',
                xaxis=dict(
                    showgrid=True, gridcolor='#e9e9e9', gridwidth=1,
                    title=dict(text=xaxis_title, font=dict(size=16, color='#111')),
                    tickfont=dict(size=13, color='#111'),
                    showline=True, linewidth=1.5, linecolor='#333', mirror=True,
                ),
                yaxis=dict(
                    showgrid=True, gridcolor='#e9e9e9', gridwidth=1,
                    title=dict(text=yaxis_title, font=dict(size=16, color='#111')),
                    tickfont=dict(size=13, color='#111'),
                    showline=True, linewidth=1.5, linecolor='#333', mirror=True,
                ),
            )
            st.plotly_chart(fig, use_container_width=True)
            if use_sbi_chart and len(data_rows) >= 1:
                min_d = data_rows['Date'].min().strftime('%Y-%m-%d')
                max_d = data_rows['Date'].max().strftime('%Y-%m-%d')
                st.caption(
                    f"Showing {len(data_rows)} Combined observations with SBI percentiles ({min_d} – {max_d}). "
                    "Lower values indicate busier signal days."
                )
        elif use_sbi_chart:
            st.info(
                "Not enough Combined-row SBI percentile history to chart yet. "
                "Re-run data sync after more daily breadth reports are ingested."
            )
        else:
            st.info(
                "No Combined-row observations found in breadth history "
                f"({', '.join(_COMBINED_CHART_FUNCTIONS)})."
            )
    except Exception as e:
        st.warning(f"Unable to render SBI graph: {e}")

    st.markdown("---")

    # Active BreadthIndicator stance (YYYY-MM-DD_breadth_entry.csv, written by SBI email job)
    entry_path = _breadth_entry_csv_path(data_file)
    if entry_path and os.path.isfile(entry_path):
        entry_date_hint = extract_date_from_filename(os.path.basename(entry_path)) or ""
        st.markdown("### 📌 Active BreadthIndicator Stance")
        if entry_date_hint:
            st.caption(
                f"From `{os.path.basename(entry_path)}` (Combined SBI percentile rule). "
                f"Entry file date: {entry_date_hint}."
            )
        try:
            entry_df = pd.read_csv(entry_path, index_col=False)
            if not entry_df.empty:
                st.dataframe(
                    entry_df,
                    use_container_width=True,
                    height=min(400, max(120, 48 + 35 * len(entry_df))),
                    column_config={
                        col: st.column_config.TextColumn(col, help=f"Breadth entry column: {col}")
                        for col in entry_df.columns
                    },
                )
            else:
                st.caption("Breadth entry file is empty.")
        except Exception as e:
            st.warning(f"Unable to load breadth entry file ({entry_path}): {e}")
        st.markdown("---")

    # Data table - Original CSV format
    st.markdown("### 📋 Detailed Signal Data Table (Original CSV Format)")
    
    # Create a dataframe with original CSV data
    csv_data = []
    for _, row in df.iterrows():
        csv_data.append(row['Raw_Data'])
    
    if csv_data:
        original_df = pd.DataFrame(csv_data)
        # Exclude Signal Open Price - backend deduplication only, never display
        if 'Signal Open Price' in original_df.columns:
            original_df = original_df.drop(columns=['Signal Open Price'])
        
        # Display with better formatting and autosize for ALL columns
        st.dataframe(
            original_df,
            use_container_width=True,
            height=400,
            column_config={
                col: st.column_config.TextColumn(
                    col,
                    help=f"Original CSV column: {col}"
                    # No width parameter = autosize
                ) for col in original_df.columns
            }
        )
