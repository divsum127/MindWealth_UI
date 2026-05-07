"""
AI Chatbot Page for Trading Analysis
"""

import streamlit as st
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo
import pandas as pd

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from chatbot import ChatbotEngine, SessionManager
from chatbot.signal_type_selector import SIGNAL_TYPE_DESCRIPTIONS, DEFAULT_SIGNAL_TYPES
from chatbot.config import MAX_CHATS_DISPLAY, ENGINE_LOG_LINES_CAP, FLAGGED_PAIRS_DIR
from chatbot.flagged_export import save_flagged_pair
from chatbot.agents.intent_classifier import INTENT_LABELS

logger = logging.getLogger(__name__)

_EASTERN_TZ = ZoneInfo("America/New_York")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_message_time_est(timestamp_iso: Optional[str]) -> str:
    """Format a stored ISO-8601 instant for display in US Eastern (EST or EDT)."""
    try:
        if not timestamp_iso:
            return ""
        else:
            s = timestamp_iso.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_EASTERN_TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z")
    except (ValueError, TypeError, OSError):
        return ""


def get_signal_type_label(signal_type: str, uppercase: bool = False) -> str:
    """Return a user-facing label for a signal type key."""
    title = SIGNAL_TYPE_DESCRIPTIONS.get(signal_type, (signal_type.replace("_", " ").title(), ""))[0]
    return title.upper() if uppercase else title


def extract_user_prompt(content: str, metadata: Optional[dict] = None) -> str:
    """Return the original user prompt without appended data payloads or conversation context.
    
    This ensures both current and historical messages show only the clean user question,
    not the internal conversation context that's appended for the AI.
    """
    # Use display_prompt from metadata only if it does NOT contain conversation context
    # (older sessions may have stored full context in display_prompt)
    display = (metadata or {}).get("display_prompt") or ""
    if display and "CONVERSATION CONTEXT (for reference)" not in display:
        return display.strip()
    
    cleaned = content or ""
    
    # Handle follow-up queries with conversation context (from content or bad display_prompt)
    if 'CONVERSATION CONTEXT (for reference):' in cleaned:
        # Extract only the CURRENT QUESTION part for UI display
        if 'CURRENT QUESTION:' in cleaned:
            cleaned = cleaned.split('CURRENT QUESTION:', 1)[1].strip()
        else:
            # Fallback: remove everything before the actual question
            cleaned = cleaned.split('CONVERSATION CONTEXT (for reference):', 1)[1].strip()
    
    # Handle standard formats
    if 'FOLLOW-UP QUESTION:' in cleaned:
        cleaned = cleaned.split('FOLLOW-UP QUESTION:', 1)[1].strip()
    
    # Remove "User Query:" prefix
    if cleaned.startswith('User Query:'):
        cleaned = cleaned.replace('User Query:', '', 1).strip()
    
    # Remove any signal data context sections (everything from first === onwards)
    if '===' in cleaned:
        cleaned = cleaned.split('===', 1)[0].strip()
    
    # Remove NOTE: sections
    if 'NOTE:' in cleaned:
        note_pos = cleaned.find('NOTE:')
        # Find the line break before NOTE:
        last_newline = cleaned.rfind('\n', 0, note_pos)
        if last_newline != -1:
            cleaned = cleaned[:last_newline].strip()
        else:
            cleaned = cleaned.split('NOTE:', 1)[0].strip()
    
    # Remove trailing/leading whitespace and empty lines
    cleaned = cleaned.strip()
    
    return cleaned


def apply_table_styling():
    """Apply custom CSS styling for larger table fonts."""
    st.markdown("""
    <style>
    /* Enhanced CSS for larger table fonts with comprehensive targeting */
    
    /* Primary dataframe container targeting */
    .stDataFrame {
        font-size: 16px !important;
    }
    
    [data-testid="stDataFrame"] {
        font-size: 16px !important;
    }
    
    /* Target AG Grid components (Streamlit's dataframe implementation) */
    .ag-root-wrapper {
        font-size: 16px !important;
    }
    
    .ag-header {
        font-size: 17px !important;
        font-weight: 600 !important;
    }
    
    .ag-header-cell-text {
        font-size: 17px !important;
        font-weight: 600 !important;
    }
    
    .ag-cell {
        font-size: 16px !important;
        padding: 10px 12px !important;
        line-height: 1.4 !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    
    .ag-cell-value {
        font-size: 16px !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    
    /* Target table elements within dataframes */
    .stDataFrame table,
    [data-testid="stDataFrame"] table {
        font-size: 16px !important;
    }
    
    .stDataFrame th,
    [data-testid="stDataFrame"] th {
        font-size: 17px !important;
        font-weight: 600 !important;
        padding: 12px 14px !important;
    }
    
    .stDataFrame td,
    [data-testid="stDataFrame"] td {
        font-size: 16px !important;
        padding: 10px 14px !important;
        line-height: 1.4 !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    
    /* Target all text elements within dataframe containers */
    .stDataFrame *,
    [data-testid="stDataFrame"] * {
        font-size: 16px !important;
    }
    
    /* Additional comprehensive targeting */
    .element-container div[data-testid="stDataFrame"] * {
        font-size: 16px !important;
    }
    
    /* Streamlit specific dataframe elements */
    .streamlit-expanderHeader {
        font-size: 16px !important;
    }
    
    /* Style for dataframe in expander */
    .streamlit-expander .stDataFrame {
        font-size: 16px !important;
    }
    
    /* Override any inherited smaller font sizes */
    .stApp .stDataFrame {
        font-size: 16px !important;
    }
    
    /* Enable text wrapping in dataframe cells */
    .stDataFrame,
    [data-testid="stDataFrame"] {
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    
    /* Ensure AG Grid cells can expand vertically */
    .ag-row {
        min-height: auto !important;
    }
    
    .ag-cell-wrapper {
        height: auto !important;
        min-height: 30px;
    }
    </style>
    """, unsafe_allow_html=True)


def render_route_badge(metadata: dict):
    """Render intent badge, route label, and web sources from response metadata."""
    intent = metadata.get("intent")
    route = metadata.get("route")
    web_sources = metadata.get("web_sources", [])
    confidence = metadata.get("intent_confidence", 0.0)

    if not intent:
        return

    label = INTENT_LABELS.get(intent, intent)

    # Route colour mapping
    route_colours = {
        "INTERNAL":       "#1f77b4",
        "WEB_RAG":        "#d62728",
        "HYBRID":         "#9467bd",
        "CONVERSATIONAL": "#7f7f7f",
    }
    colour = route_colours.get(route, "#1f77b4")
    route_label = {
        "INTERNAL":       "📊 Internal",
        "WEB_RAG":        "🌍 Web RAG",
        "HYBRID":         "🔗 Hybrid",
        "CONVERSATIONAL": "💬 History",
    }.get(route, route or "")

    badge_html = (
        f'<span style="'
        f'background:{colour};color:#fff;padding:2px 8px;border-radius:4px;'
        f'font-size:0.78em;font-weight:600;margin-right:6px;">'
        f'{label}</span>'
        f'<span style="'
        f'background:#444;color:#eee;padding:2px 8px;border-radius:4px;'
        f'font-size:0.78em;margin-right:6px;">'
        f'{route_label}</span>'
        f'<span style="color:#888;font-size:0.75em;">conf {confidence:.0%}</span>'
    )
    st.markdown(badge_html, unsafe_allow_html=True)

    reasoning = metadata.get("llm_router_reasoning")
    if reasoning:
        with st.expander("Why this route? (LLM router)", expanded=False):
            st.markdown(reasoning)

    if web_sources:
        with st.expander(f"🌐 Web Sources ({len(web_sources)})", expanded=False):
            for i, url in enumerate(web_sources, 1):
                st.markdown(f"[Source {i}]({url})", unsafe_allow_html=False)


class _ChatbotLogCaptureHandler(logging.Handler):
    """Buffers formatted log lines for the ``chatbot`` logger subtree during one engine call."""

    def __init__(self, lines: list) -> None:
        super().__init__(logging.INFO)
        self._lines = lines

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._lines.append(self.format(record))
        except Exception:
            self.handleError(record)


# ── Investor-friendly translation for the engine flow_trace ─────────────────
# The chatbot engine emits technical stage names ("Router", "Hybrid
# Orchestrator", "Synthesis"…) that are useful for debugging but read as
# engineering jargon to financial investors and analysts. The map below
# converts each stage into a plain-English label + analyst-style description
# without changing the underlying engine flow_trace (which is still saved to
# session JSON for support / audit purposes).
_FRIENDLY_FLOW_STEPS: dict = {
    "Router": (
        "🔍",
        "Understanding your question",
        "Reading your request to identify what insights you need",
    ),
    "Conversation Mode": (
        "💬",
        "Continuing the conversation",
        "Answering from our earlier discussion — no new data needed",
    ),
    "Web Search": (
        "🌐",
        "Researching the markets",
        "Searching the web for the latest news, prices and market context",
    ),
    "Web Search Fallback": (
        "🔁",
        "Switching to internal data",
        "Live web research wasn't available — using your signal data instead",
    ),
    "Hybrid Orchestrator": (
        "⚡",
        "Gathering insights",
        "Pulling the latest market updates and your signal data at the same time",
    ),
    "Hybrid (Sequential)": (
        "⏳",
        "Gathering insights",
        "Combining market research with your signal data",
    ),
    "Synthesis": (
        "🧩",
        "Connecting the dots",
        "Bringing market context together with your signal data",
    ),
    "Internal Search": (
        "📊",
        "Reviewing your signal data",
        "Pulling the relevant trading signals and analytics",
    ),
    "Context Handling": (
        "📚",
        "Reviewing earlier discussion",
        "Loading prior conversation so this answer stays consistent",
    ),
    "Internal Data Query": (
        "📈",
        "Pulling signal data",
        "Selected the relevant signals, columns and date range",
    ),
    "Response Generation": (
        "✍️",
        "Preparing your insights",
        "Drafting your final analysis-ready response",
    ),
}

# Internal route codes → investor-facing strategy descriptions
_FRIENDLY_ROUTE_DESCRIPTIONS: dict = {
    "HYBRID":         "Combining live market research with your signal data",
    "WEB_RAG":        "Looking up live market information online",
    "INTERNAL":       "Using your internal trading signal data",
    "CONVERSATIONAL": "Continuing our conversation",
}


def _humanize_flow_step(stage: str, detail: str) -> tuple:
    """Translate an engine flow step into (icon, friendly_stage, friendly_detail).

    The engine's ``flow_trace`` uses technical names such as ``"Router"``,
    ``"Hybrid Orchestrator"`` or ``"Synthesis"``. Financial investors and
    analysts shouldn't have to read pipeline jargon, so we map every known
    stage to a plain-English label + description here. Unknown stages fall
    back to a lightly cleaned-up version of the original text.
    """
    stage = (stage or "").strip()
    detail = (detail or "").strip()

    if stage == "Route Selected":
        # Detail looks like: "HYBRID (intent=SIGNAL_LOOKUP, conf=0.88)"
        route_code = detail.split(" ", 1)[0] if detail else ""
        intent_label = ""
        if "intent=" in detail:
            try:
                intent_code = detail.split("intent=", 1)[1].split(",", 1)[0].strip(") ")
                intent_label = INTENT_LABELS.get(intent_code, intent_code.replace("_", " ").title())
            except Exception:
                intent_label = ""

        strategy = _FRIENDLY_ROUTE_DESCRIPTIONS.get(route_code, "Selecting the best approach")
        if intent_label:
            friendly_detail = f"{strategy} (your question looks like: {intent_label})"
        else:
            friendly_detail = strategy
        return ("🎯", "Approach chosen", friendly_detail)

    if stage == "Parallel Branches Complete":
        # Detail like: "web=ok, internal=ok"
        web_ok = "web=ok" in detail.lower()
        internal_ok = "internal=ok" in detail.lower()
        web_mark = "✓" if web_ok else "—"
        internal_mark = "✓" if internal_ok else "—"
        friendly_detail = (
            f"Market research {web_mark}  |  Signal data {internal_mark}"
        )
        return ("✅", "Insights gathered", friendly_detail)

    if stage in _FRIENDLY_FLOW_STEPS:
        icon, friendly_stage, friendly_detail = _FRIENDLY_FLOW_STEPS[stage]
        return (icon, friendly_stage, friendly_detail)

    # Unknown stage — keep the original text but add a neutral icon
    return ("•", stage or "Step", detail)


def run_smart_followup_with_progress(
    chatbot: Any,
    *,
    status_title: str = "Analyzing your query…",
    status_caption: str = "Live progress — updates as I work through your question:",
    **followup_kwargs: Any,
) -> tuple:
    """
    Run ``smart_followup_query`` with live Streamlit updates.

    ``st.spinner`` does not flush intermediate UI; ``st.status`` does, so users
    see router / web / internal steps instead of a frozen loading line.

    Attaches a temporary handler to the ``chatbot`` logger and stores capped
    lines in ``metadata["engine_log_lines"]`` on success.
    """
    log_lines: list = []
    log_handler = _ChatbotLogCaptureHandler(log_lines)
    log_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    )
    root_chatbot = logging.getLogger("chatbot")
    root_chatbot.addHandler(log_handler)

    result_tuple: Any = None
    try:
        if hasattr(st, "status"):
            with st.status(status_title, expanded=True) as status:
                st.caption(status_caption)

                def _live(stage: str, detail: str) -> None:
                    icon, friendly_stage, friendly_detail = _humanize_flow_step(stage, detail)
                    st.markdown(f"{icon} **{friendly_stage}** — {friendly_detail}")

                try:
                    result_tuple = chatbot.smart_followup_query(
                        **followup_kwargs,
                        on_flow_step=_live,
                    )
                    status.update(label="Done", state="complete")
                except Exception:
                    status.update(label="Error", state="error")
                    raise
        else:
            with st.spinner("🤔 Analyzing your query with conversation context..."):
                result_tuple = chatbot.smart_followup_query(**followup_kwargs)
    finally:
        root_chatbot.removeHandler(log_handler)

    response, metadata = result_tuple
    if isinstance(metadata, dict):
        metadata["engine_log_lines"] = log_lines[-ENGINE_LOG_LINES_CAP:]
    return response, metadata


def render_flow_trace(metadata: Optional[dict]) -> None:
    """Render investor-friendly "how I answered this" steps for a response.

    The engine emits a technical ``flow_trace`` (Router → Hybrid Orchestrator
    → Synthesis → Response Generation …). For an audience of financial
    investors and analysts we translate each step into plain-English labels
    via :func:`_humanize_flow_step` before rendering.
    """
    if not metadata:
        return

    flow_steps = metadata.get("flow_trace") or []
    if not flow_steps:
        return

    humanized = [
        (
            *_humanize_flow_step(step.get("stage", ""), step.get("detail", "")),
            step.get("timestamp"),
        )
        for step in flow_steps
    ]

    # One-line summary so the journey is visible at a glance
    summary = "  →  ".join(f"{icon} {stage}" for icon, stage, _detail, _ts in humanized)
    st.markdown(f"🧭 **How I answered this:** {summary}")

    with st.expander("🪄 Behind the scenes — how this answer was built", expanded=False):
        st.caption(
            "A plain-English walk-through of the steps taken to research "
            "and prepare your answer."
        )
        for idx, (icon, friendly_stage, friendly_detail, ts) in enumerate(humanized, 1):
            ts_html = (
                f'<span style="color:#888;font-size:0.78em;">  ·  {ts}</span>'
                if ts else ""
            )
            st.markdown(
                f"{idx}. {icon} **{friendly_stage}** — {friendly_detail}{ts_html}",
                unsafe_allow_html=True,
            )


def display_styled_dataframe(df, height=400, key_suffix=""):
    """Display dataframe with enhanced styling and larger fonts."""
    # Exclude Signal Open Price - backend deduplication only, never display
    if not df.empty and 'Signal Open Price' in df.columns:
        df = df.drop(columns=['Signal Open Price'])
    # Reorder columns: Symbol/Signal first, Exit Signal second, Function third
    from ..utils.helpers import reorder_dataframe_columns, find_column_by_keywords
    df = reorder_dataframe_columns(df)
    
    # Find Symbol and Exit Signal columns for pinning
    symbol_col = find_column_by_keywords(df.columns, ['Symbol, Signal', 'Symbol'])
    if not symbol_col:
        for col in df.columns:
            if 'Symbol' in col and 'Signal' in col and 'Exit' not in col:
                symbol_col = col
                break
    exit_col = find_column_by_keywords(df.columns, ['Exit Signal Date', 'Exit Signal', 'Exit'])
    
    # Apply additional styling through column configuration with pinning and autosize
    column_config = {}
    for col in df.columns:
        column_config[col] = st.column_config.TextColumn(
            col,
            help=None
            # No width parameter = autosize
        )
    
    # Display with enhanced parameters
    st.dataframe(
        df,
        width='stretch',
        hide_index=True,
        height=min(height, (len(df) + 1) * 40),  # Slightly larger row height for better readability
        column_config=column_config,
        key=f"styled_df_{key_suffix}_{hash(str(df.shape))}"  # Unique key
    )


def show_input_limit_notice(metadata: Optional[dict]) -> None:
    """Show when request content had to be reduced before calling Claude."""
    if not metadata:
        return

    notices = []
    history_trimmed = metadata.get("history_trimmed_count", 0)
    if history_trimmed:
        notices.append(f"trimmed {history_trimmed} older message(s)")
    if metadata.get("input_truncated"):
        notices.append("truncated the latest request to stay within Claude input budget")

    if notices:
        st.caption(f"Input safeguard applied: {', '.join(notices)}.")


def _coerce_to_dataframe(data: Any) -> Optional[pd.DataFrame]:
    """Best-effort conversion of legacy signal tables to pandas DataFrame."""
    if data is None:
        return None

    if isinstance(data, pd.DataFrame):
        return data

    try:
        if isinstance(data, list):
            # Empty list -> empty DataFrame
            if not data:
                return pd.DataFrame()
            return pd.DataFrame(data)

        if isinstance(data, dict):
            # Dict of iterables (column mapping) or a single record
            if any(isinstance(v, (list, tuple, set)) for v in data.values()):
                return pd.DataFrame(data)
            return pd.DataFrame([data])
    except Exception:
        return None

    return None


def render_chat_history_sidebar():
    """Render the chat history sidebar for managing sessions."""
    st.sidebar.title("💬 Chat History")
    
    # New Chat button at the top
    if st.sidebar.button("➕ New Chat", use_container_width=True, type="primary"):
        # Create new session
        new_session_id = SessionManager.create_new_session()
        st.session_state.current_session_id = new_session_id
        st.session_state.chatbot_engine = None  # Will be recreated with new session
        st.session_state.chat_history = []
        st.session_state.last_settings = None
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Search box
    search_query = st.sidebar.text_input("🔍 Search chats", placeholder="Type to search...")
    
    # Get sessions
    if search_query:
        sessions = SessionManager.search_sessions(search_query)
    else:
        sessions = SessionManager.list_all_sessions(sort_by='last_updated')
    
    # Limit displayed sessions to MAX_CHATS_DISPLAY (unless searching)
    total_sessions = len(sessions)
    if not search_query and total_sessions > MAX_CHATS_DISPLAY:
        sessions = sessions[:MAX_CHATS_DISPLAY]
        showing_limited = True
    else:
        showing_limited = False
    
    # Display sessions (compact, no chat number/time, use preview as title)
    if not sessions:
        st.sidebar.info("No chat history yet. Start a new conversation!")
    else:
        for session in sessions:
            session_id = session['session_id']
            # Use one-line summary preview, fallback to title.
            preview = session.get('preview', '').strip()
            display_title = preview if preview else session.get('title', 'New Chat')
            # Keep a concise one-liner but preserve meaning.
            if len(display_title) > 90:
                display_title = display_title[:87].rstrip() + '...'
            is_current = st.session_state.get('current_session_id') == session_id
            # Compact row: title + rename + delete
            # Use two columns: title (wide) and icons (narrow, side-by-side)
            cols = st.sidebar.columns([8, 2], gap="small")
            with cols[0]:
                if st.button(f"{'🟢 ' if is_current else ''}{display_title}", key=f"load_{session_id}", use_container_width=True, disabled=is_current):
                    st.session_state.current_session_id = session_id
                    st.session_state.chatbot_engine = None
                    st.session_state.chat_history = []
                    st.session_state.last_settings = None
                    st.rerun()
            with cols[1]:
                icon_cols = st.columns([1, 1], gap="small")
                with icon_cols[0]:
                    if st.button("✏️", key=f"rename_{session_id}", help="Rename"):
                        st.session_state[f'renaming_{session_id}'] = True
                        st.rerun()
                with icon_cols[1]:
                    if st.button("🗑️", key=f"delete_{session_id}", help="Delete"):
                        if not is_current or len(sessions) > 1:
                            SessionManager.delete_session(session_id)
                            if is_current:
                                remaining = [s for s in sessions if s['session_id'] != session_id]
                                if remaining:
                                    st.session_state.current_session_id = remaining[0]['session_id']
                                    st.session_state.chatbot_engine = None
                                    st.session_state.chat_history = []
                                    st.session_state.last_settings = None
                            st.rerun()
            # Inline rename input (compact)
            if st.session_state.get(f'renaming_{session_id}', False):
                new_title = st.text_input("Rename chat:", value=display_title, key=f"rename_input_{session_id}")
                col_save, col_cancel = st.columns([1,1], gap="small")
                with col_save:
                    if st.button("✅", key=f"save_rename_{session_id}"):
                        SessionManager.update_session_title(session_id, new_title)
                        st.session_state[f'renaming_{session_id}'] = False
                        st.rerun()
                with col_cancel:
                    if st.button("❌", key=f"cancel_rename_{session_id}"):
                        st.session_state[f'renaming_{session_id}'] = False
                        st.rerun()


def render_chatbot_page():
    """Render the AI Chatbot page."""
    
    # Info button at the top
    if st.button("ℹ️ Info About Page", key="info_chatbot", help="Click to learn about this page"):
        st.session_state['show_info_chatbot'] = not st.session_state.get('show_info_chatbot', False)
    
    if st.session_state.get('show_info_chatbot', False):
        with st.expander("📖 AI Trading Assistant Information", expanded=True):
            st.markdown("""
            ### What is this page?
            The AI Trading Assistant is an intelligent chatbot powered by advanced AI that helps you analyze trading signal data, answer questions about signal data, and provide strategic insights.
            
            ### Why is it used?
            - **Interactive Analysis**: Ask questions about your trading signal data in natural language
            - **Smart Insights**: Get AI-powered analysis of signals, strategies, and performance
            - **Quick Answers**: Find information faster than manually searching through signals
            - **Signal Data Exploration**: Explore complex trading signal data through conversational interface
            
            ### How to use?
            1. **Select Signal Types**: Choose which signal data sources to include (Entry, Exit, Breadth, etc.)
            2. **Ask Questions**: Type your question in the chat input box
            3. **Review Responses**: Read the AI's analysis and view any tables or signal data provided
            4. **Follow-up**: Ask follow-up questions for deeper insights
            5. **Manage Chats**: Use sidebar to create new chats, rename, or delete old ones
            6. **View History**: Access your previous conversations from the sidebar
            
            ### Key Features:
            - Natural language querying of trading signal data
            - Multi-source signal data integration
            - Conversation history management
            - Interactive tables and visualizations
            - Context-aware responses
            - Quick action buttons for common queries
            """)
    
    st.title("🤖 AI Trading Analysis Chatbot")
    
    # Display data fetch datetime at top of page
    from ..utils.helpers import display_data_fetch_info
    display_data_fetch_info(location="header")
    st.markdown("Ask questions about your trading signal data and get AI-powered insights!")
    
    # Apply custom styling for larger table fonts
    apply_table_styling()
    
    # Initialize current session if not exists
    if 'current_session_id' not in st.session_state:
        # Check if there are existing sessions
        existing_sessions = SessionManager.list_all_sessions()
        if existing_sessions:
            # Use the most recent session
            st.session_state.current_session_id = existing_sessions[0]['session_id']
        else:
            # Create a new session
            st.session_state.current_session_id = SessionManager.create_new_session()
    
    # Initialize chatbot engine with current session
    if 'chatbot_engine' not in st.session_state or st.session_state.chatbot_engine is None:
        try:
            st.session_state.chatbot_engine = ChatbotEngine(
                session_id=st.session_state.current_session_id
            )
            # Load chat history from the session
            history_manager = st.session_state.chatbot_engine.history_manager
            st.session_state.chat_history = []
            
            # Convert history to chat format - clean user messages for display
            for msg in history_manager.get_full_history():
                if msg['role'] in ['user', 'assistant']:
                    metadata = msg.get('metadata', {}) or {}
                    content = msg['content']
                    if msg['role'] == 'user':
                        content = extract_user_prompt(content, metadata)
                    
                    st.session_state.chat_history.append({
                        'role': msg['role'],
                        'content': content,
                        'metadata': metadata,
                        'timestamp': msg.get('timestamp'),
                    })
            
            st.session_state.last_settings = None
        except Exception as e:
            st.error(f"❌ Failed to initialize chatbot: {e}")
            st.error("Please check:")
            st.error("1. OpenAI API key is set in .streamlit/secrets.toml")
            st.error("2. API key is valid and active")
            st.error("3. openai library is properly installed (version 1.12.0+)")
            import traceback
            st.code(traceback.format_exc())
            st.stop()
    
    chatbot = st.session_state.chatbot_engine
    
    # Get available tickers
    available_tickers = chatbot.get_available_tickers()

    # Handle pending analysis prompt (from Analyze button)
    if 'pending_analysis_prompt' in st.session_state and st.session_state.pending_analysis_prompt:
        analysis_prompt = st.session_state.pending_analysis_prompt
        analysis_asset = st.session_state.pending_analysis_asset
        analysis_from_date = st.session_state.pending_analysis_from_date
        analysis_to_date = st.session_state.pending_analysis_to_date
        
        # Clear the pending prompt
        del st.session_state.pending_analysis_prompt
        del st.session_state.pending_analysis_asset
        del st.session_state.pending_analysis_from_date
        del st.session_state.pending_analysis_to_date
        
        # Get AI signal type selection for the analysis
        selected_signal_types, ai_reason = chatbot.signal_type_selector.select_signal_types(
            user_query=analysis_prompt
        )
        
        # Update session state
        st.session_state.last_signal_types = selected_signal_types
        st.session_state.last_signal_reason = ai_reason
        
        # Add user message to chat history
        user_ts = utc_now_iso()
        st.session_state.chat_history.append({
            'role': 'user',
            'content': analysis_prompt,
            'metadata': {'display_prompt': analysis_prompt},
            'timestamp': user_ts,
        })
        
        # Display user message immediately (clean version only)
        with st.chat_message("user"):
            # Use extract_user_prompt to show only the clean question
            clean_prompt = extract_user_prompt(analysis_prompt, {'display_prompt': analysis_prompt})
            ts = format_message_time_est(user_ts)
            if ts:
                st.caption(ts)
            st.markdown(clean_prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            selection_text = ", ".join(get_signal_type_label(sig) for sig in selected_signal_types)
            st.markdown(f"**AI Signal Type Selection:** {selection_text}")
            if ai_reason:
                st.caption(f"💡 {ai_reason}")
            try:
                response, metadata = run_smart_followup_with_progress(
                    chatbot,
                    status_title="Running deep dive analysis…",
                    user_message=analysis_prompt,
                    selected_signal_types=selected_signal_types,
                    assets=[analysis_asset],  # Use the selected asset
                    from_date=analysis_from_date.strftime('%Y-%m-%d'),
                    to_date=analysis_to_date.strftime('%Y-%m-%d'),
                    functions=None,  # Auto-extract functions
                    auto_extract_tickers=False,  # We're providing the asset
                    signal_type_reasoning=ai_reason,
                )

                resp_ts = utc_now_iso()
                rts = format_message_time_est(resp_ts)
                if rts:
                    st.caption(rts)
                # Display response
                st.markdown(response)
                show_input_limit_notice(metadata)
                if metadata.get("intent"):
                    render_route_badge(metadata)
                render_flow_trace(metadata)

                # Display Smart Query Details with signals
                if metadata.get('input_type') in ['smart_query', 'smart_followup'] or metadata.get('selected_signal_types'):
                    with st.expander("📊 Smart Query Details", expanded=False):
                        # Show signal types and reasoning
                        signal_types_meta = metadata.get('selected_signal_types', selected_signal_types)
                        if signal_types_meta:
                            st.markdown(f"**AI Signal Types:** {', '.join(get_signal_type_label(sig) for sig in signal_types_meta)}")
                            if ai_reason:
                                st.caption(f"💡 {ai_reason}")

                        # Display full signal tables if available
                        full_signal_tables = metadata.get('full_signal_tables', {})
                        if full_signal_tables:
                            st.markdown("---")
                            st.subheader("📊 Complete Signal Data Used in Analysis")

                            for signal_type, signal_df in full_signal_tables.items():
                                if not signal_df.empty:
                                    st.markdown(f"**{get_signal_type_label(signal_type, uppercase=True)} Signals** ({len(signal_df)} records)")
                                    display_styled_dataframe(
                                        signal_df,
                                        height=min(400, (len(signal_df) + 1) * 40),
                                        key_suffix=f"analysis_{signal_type}"
                                    )

                # Add to history
                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': response,
                    'metadata': metadata,
                    'timestamp': resp_ts,
                })

            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
        
        # Rerun to update chat display
        st.rerun()
    
    # Handle pending signal insights prompt (from Signal Insights button)
    if 'pending_insights_prompt' in st.session_state and st.session_state.pending_insights_prompt:
        insights_prompt = st.session_state.pending_insights_prompt
        insights_from_date = st.session_state.pending_insights_from_date
        insights_to_date = st.session_state.pending_insights_to_date
        
        # Clear the pending prompt
        del st.session_state.pending_insights_prompt
        del st.session_state.pending_insights_from_date
        del st.session_state.pending_insights_to_date
        
        # For signal insights, we only want entry signals
        selected_signal_types = ["entry"]  # Only entry signals
        ai_reason = "Signal Insights focuses on high-quality entry signals across all assets"
        
        # Update session state
        st.session_state.last_signal_types = selected_signal_types
        st.session_state.last_signal_reason = ai_reason
        
        # Add user message to chat history
        user_ts = utc_now_iso()
        st.session_state.chat_history.append({
            'role': 'user',
            'content': insights_prompt,
            'metadata': {'display_prompt': insights_prompt},
            'timestamp': user_ts,
        })
        
        # Display user message immediately (clean version only)
        with st.chat_message("user"):
            # Use extract_user_prompt to show only the clean question
            clean_prompt = extract_user_prompt(insights_prompt, {'display_prompt': insights_prompt})
            ts = format_message_time_est(user_ts)
            if ts:
                st.caption(ts)
            st.markdown(clean_prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            selection_text = ", ".join(get_signal_type_label(sig) for sig in selected_signal_types)
            st.markdown(f"**AI Signal Type Selection:** {selection_text}")
            st.caption(f"💡 {ai_reason}")
            try:
                response, metadata = run_smart_followup_with_progress(
                    chatbot,
                    status_title="Finding high-quality entry signals…",
                    user_message=insights_prompt,
                    selected_signal_types=selected_signal_types,
                    assets=None,  # Analyze all assets
                    from_date=insights_from_date.strftime('%Y-%m-%d'),
                    to_date=insights_to_date.strftime('%Y-%m-%d'),
                    functions=None,  # Auto-extract functions
                    auto_extract_tickers=True,  # Auto-extract from all assets
                    signal_type_reasoning=ai_reason,
                )

                resp_ts = utc_now_iso()
                rts = format_message_time_est(resp_ts)
                if rts:
                    st.caption(rts)
                # Display response
                st.markdown(response)
                show_input_limit_notice(metadata)
                if metadata.get("intent"):
                    render_route_badge(metadata)
                render_flow_trace(metadata)

                # Display Smart Query Details with signals
                with st.expander("📊 Smart Query Details", expanded=False):
                    # Show signal types and reasoning
                    st.markdown(f"**AI Signal Types:** {get_signal_type_label(selected_signal_types[0])}")
                    if ai_reason:
                        st.caption(f"💡 {ai_reason}")

                    # Display full signal tables if available
                    full_signal_tables = metadata.get('full_signal_tables', {})
                    if full_signal_tables:
                        st.markdown("---")
                        st.subheader("📊 Complete Signal Data Used in Analysis")

                        for signal_type, signal_df in full_signal_tables.items():
                            if not signal_df.empty:
                                st.markdown(f"**{get_signal_type_label(signal_type, uppercase=True)} Signals** ({len(signal_df)} records)")
                                display_styled_dataframe(
                                    signal_df,
                                    height=min(400, (len(signal_df) + 1) * 40),
                                    key_suffix=f"insights_{signal_type}"
                                )

                # Add to history
                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': response,
                    'metadata': metadata,
                    'timestamp': resp_ts,
                })

            except Exception as e:
                st.error(f"❌ Error during signal insights analysis: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
        
        # Rerun to update chat display
        st.rerun()
    
    # Handle pending breadth analysis prompt (from Breadth Analysis button)
    if 'pending_breadth_prompt' in st.session_state and st.session_state.pending_breadth_prompt:
        breadth_prompt = st.session_state.pending_breadth_prompt
        breadth_from_date = st.session_state.pending_breadth_from_date
        breadth_to_date = st.session_state.pending_breadth_to_date
        
        # Clear the pending prompt
        del st.session_state.pending_breadth_prompt
        del st.session_state.pending_breadth_from_date
        del st.session_state.pending_breadth_to_date
        
        # For breadth analysis, we only want breadth signals
        selected_signal_types = ["breadth"]  # Only breadth signals
        ai_reason = "Breadth Analysis focuses on market breadth signal data and percentile analysis"
        
        # Update session state
        st.session_state.last_signal_types = selected_signal_types
        st.session_state.last_signal_reason = ai_reason
        
        # Add user message to chat history
        user_ts = utc_now_iso()
        st.session_state.chat_history.append({
            'role': 'user',
            'content': breadth_prompt,
            'metadata': {'display_prompt': breadth_prompt},
            'timestamp': user_ts,
        })
        
        # Display user message immediately (clean version only)
        with st.chat_message("user"):
            # Use extract_user_prompt to show only the clean question
            clean_prompt = extract_user_prompt(breadth_prompt, {'display_prompt': breadth_prompt})
            ts = format_message_time_est(user_ts)
            if ts:
                st.caption(ts)
            st.markdown(clean_prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            selection_text = ", ".join(get_signal_type_label(sig) for sig in selected_signal_types)
            st.markdown(f"**AI Signal Type Selection:** {selection_text}")
            st.caption(f"💡 {ai_reason}")
            try:
                response, metadata = run_smart_followup_with_progress(
                    chatbot,
                    status_title="Analyzing breadth signal data…",
                    user_message=breadth_prompt,
                    selected_signal_types=selected_signal_types,
                    assets=None,  # Breadth is market-wide, no specific assets
                    from_date=breadth_from_date.strftime('%Y-%m-%d'),
                    to_date=breadth_to_date.strftime('%Y-%m-%d'),
                    functions=None,  # Auto-extract functions
                    auto_extract_tickers=False,  # Breadth doesn't use tickers
                    signal_type_reasoning=ai_reason,
                )

                resp_ts = utc_now_iso()
                rts = format_message_time_est(resp_ts)
                if rts:
                    st.caption(rts)
                # Display response
                st.markdown(response)
                show_input_limit_notice(metadata)
                if metadata.get("intent"):
                    render_route_badge(metadata)
                render_flow_trace(metadata)

                # Display full signal tables if available
                full_signal_tables = metadata.get('full_signal_tables', {})
                if full_signal_tables:
                    st.markdown("### 📊 Complete Breadth Signal Data Used in Analysis")

                    for signal_type, signal_df in full_signal_tables.items():
                        if not signal_df.empty:
                            st.markdown(f"#### {get_signal_type_label(signal_type, uppercase=True)} Signals ({len(signal_df)} records)")
                            display_styled_dataframe(
                                signal_df,
                                height=min(400, (len(signal_df) + 1) * 40),
                                key_suffix=f"breadth_{signal_type}"
                            )

                # Add to history
                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': response,
                    'metadata': metadata,
                    'timestamp': resp_ts,
                })

            except Exception as e:
                st.error(f"❌ Error during breadth analysis: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
        
        # Rerun to update chat display
        st.rerun()
    
    # Initialize signal type session defaults
    if 'last_signal_types' not in st.session_state:
        st.session_state.last_signal_types = DEFAULT_SIGNAL_TYPES.copy()
    if 'last_signal_reason' not in st.session_state:
        st.session_state.last_signal_reason = "Default selection: entry, exit, target."
    
    # Auto-extraction is always enabled (no manual selection)
    use_auto_extract_tickers = True
    selected_tickers = None

    # Set default dates (last 15 days)
    default_from_date = datetime.now() - timedelta(days=15)
    default_to_date = datetime.now()

    # Keep date inputs near top so Deep Dive controls can use them.
    st.sidebar.subheader("Select Date Range")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        from_date = st.date_input(
            "From Date",
            value=default_from_date,
            help="Start date for signal data (default: 15 days ago)"
        )

    with col2:
        to_date = st.date_input(
            "To Date",
            value=default_to_date,
            help="End date for signal data (default: today)"
        )

    # Asset selection for Analyze feature (kept high in sidebar, just below page selector)
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Deep Dive Analysis")
    
    # Get available assets
    if available_tickers:
        selected_asset = st.sidebar.selectbox(
            "Select Asset",
            options=[""] + sorted(available_tickers),
            help="Choose an asset for deep dive analysis",
            key="analyze_asset_selector"
        )
        
        # Analyze button
        analyze_button = st.sidebar.button(
            "📊 Analyze Asset",
            use_container_width=True,
            type="primary",
            disabled=not selected_asset,
            help="Run deep dive analysis on selected asset"
        )
        
        if analyze_button and selected_asset:
            # Save current chat session before creating new one
            if 'chatbot_engine' in st.session_state and st.session_state.chatbot_engine is not None:
                try:
                    # Ensure current session history is saved
                    st.session_state.chatbot_engine.history_manager.save_history()
                except Exception as e:
                    logger.warning(f"Could not save current session: {e}")
            
            # Create a new chat session for the analysis
            new_session_id = SessionManager.create_new_session()
            st.session_state.current_session_id = new_session_id
            st.session_state.chatbot_engine = None  # Will be recreated with new session
            st.session_state.chat_history = []
            st.session_state.last_settings = None
            
            # Format the analysis prompt
            analysis_prompt = f"""Please run a deep dive on {selected_asset} covering all signals recorded over the past few weeks. Use the specified entry and / or exit-date range as the filter.

Retrieve and list all signals for this period, showing each function, timeframe, and direction (long/short).

Identify contradictions, such as:

Short signals that have already hit targets or registered exits while higher-interval (e.g., monthly-candle) functions are still showing active longs.

Overlaps between exit dates on short-term signals and open longer-term entries.

Assess alignment between short-term and medium-term outlooks based strictly on the verified signals in the Streamlit reports.

Determine stance — whether the current setup indicates a Buy, Hold, or Sell — using only the pre-computed signal data and the historically observed holding periods for each function.

Important:

Do not fabricate or infer new signals. Use only signals verifiable from the existing Streamlit reports.

Date Range: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"""
            
            # Store the prompt to send after rerun
            st.session_state.pending_analysis_prompt = analysis_prompt
            st.session_state.pending_analysis_asset = selected_asset
            st.session_state.pending_analysis_from_date = from_date
            st.session_state.pending_analysis_to_date = to_date
            st.rerun()
    else:
        st.sidebar.info("No assets available. Please ensure signal data files are present.")
    
    # Signal Insights button (works across all assets, entry signals only)
    # This button is always visible, regardless of asset availability
    st.sidebar.markdown("---")
    signal_insights_button = st.sidebar.button(
        "💡 Signal Insights",
        use_container_width=True,
        type="secondary",
        help="Find high-quality entry signals across all assets (Sharpe >1.5, Win Rate >80%, Forward Testing >65%)"
    )
    
    if signal_insights_button:
        # Save current chat session before creating new one
        if 'chatbot_engine' in st.session_state and st.session_state.chatbot_engine is not None:
            try:
                # Ensure current session history is saved
                st.session_state.chatbot_engine.history_manager.save_history()
            except Exception as e:
                logger.warning(f"Could not save current session: {e}")
        
        # Create a new chat session for the signal insights
        new_session_id = SessionManager.create_new_session()
        st.session_state.current_session_id = new_session_id
        st.session_state.chatbot_engine = None  # Will be recreated with new session
        st.session_state.chat_history = []
        st.session_state.last_settings = None
        
        # Format the signal insights prompt
        signal_insights_prompt = f"""Please analyze all ENTRY signals across all assets and functions for the date range {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}.

Focus on identifying high-quality signals that meet the following criteria:

1. **High Sharpe Ratio**: Strategy Sharpe Ratio > 1.5
2. **High Win Rate (Full History)**: Win Rate > 80% based on full historical testing
3. **Latest Performance Win Rate**: Win Rate > 85% for past 4 years
4. **Forward Testing Win Rate**: Win Rate > 65% from forward testing signal data

For each qualifying signal, provide:
- Asset symbol
- Function name
- Timeframe/Interval
- Signal direction (Long/Short)
- Signal date
- Strategy Sharpe Ratio
- Win Rate (full history, latest performance, and forward testing if available)
- Any other relevant performance metrics

Organize the results by:
1. Highest Sharpe Ratio signals first
2. Then by highest Win Rate
3. Highlight any signals with high Forward Testing Win Rate (>65%)

Important:
- Only analyze ENTRY signals (signals that are still open, no exit yet)
- Use only signals verifiable from the existing Streamlit reports
- Do not fabricate or infer new signals
- Focus on signals that meet ALL or MOST of the quality criteria above

Date Range: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"""
        
        # Store the prompt to send after rerun
        st.session_state.pending_insights_prompt = signal_insights_prompt
        st.session_state.pending_insights_from_date = from_date
        st.session_state.pending_insights_to_date = to_date
        st.rerun()
    
    # Breadth Analysis button (analyzes breadth reports and identifies percentile days)
    st.sidebar.markdown("---")
    breadth_analysis_button = st.sidebar.button(
        "📊 Breadth Analysis",
        use_container_width=True,
        type="secondary",
        help="Analyze breadth reports and identify top/bottom 10% days (days with breadth values in bottom 10 percentile)"
    )
    
    if breadth_analysis_button:
        # Save current chat session before creating new one
        if 'chatbot_engine' in st.session_state and st.session_state.chatbot_engine is not None:
            try:
                # Ensure current session history is saved
                st.session_state.chatbot_engine.history_manager.save_history()
            except Exception as e:
                logger.warning(f"Could not save current session: {e}")
        
        # Create a new chat session for the breadth analysis
        new_session_id = SessionManager.create_new_session()
        st.session_state.current_session_id = new_session_id
        st.session_state.chatbot_engine = None  # Will be recreated with new session
        st.session_state.chat_history = []
        st.session_state.last_settings = None
        
        # Format the breadth analysis prompt
        breadth_analysis_prompt = f"""Please analyze breadth report signal data for the date range {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}.

Focus on the following analysis:

1. **Breadth Ratios Analysis**:
   - Identify days when breadth values are in the **bottom 10 percentile** (bottom 10% days)
   - Identify days when breadth values are in the **top 10 percentile** (top 10% days)
   - Calculate and show the breadth ratios for these extreme days

2. **Breadth Signal Type Analysis**:
   - Analyze breadth signal types and their patterns
   - Identify any SBI (Signal Breadth Indicator) type signals if present
   - Show how breadth values correlate with market conditions

3. **Percentile Analysis**:
   - For each day in the date range, determine if the breadth value falls below the 10th percentile
   - List all days where breadth value is under 10 percentile
   - Provide context on what these low breadth days indicate (e.g., oversold conditions, potential reversal signals)

4. **Summary**:
   - Total number of days analyzed
   - Number of days in bottom 10 percentile
   - Number of days in top 10 percentile
   - Average breadth value for the period
   - Trends and patterns observed

For each identified day (especially bottom 10 percentile days), provide:
- Date
- Breadth value
- Percentile rank
- Function/indicator name
- Any relevant signal type or SBI information
- Context about what this breadth level means

Important:
- Use only breadth signal data verifiable from the existing Streamlit reports
- Focus on breadth signal type and SBI type if available
- Calculate percentiles based on historical breadth signal data
- Do not fabricate or infer signal data

Date Range: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"""
        
        # Store the prompt to send after rerun
        st.session_state.pending_breadth_prompt = breadth_analysis_prompt
        st.session_state.pending_breadth_from_date = from_date
        st.session_state.pending_breadth_to_date = to_date
        st.rerun()
    
    # Signal Type selection is AI-driven
    st.sidebar.subheader("Signal Types (auto-selected)")
    st.sidebar.caption("The assistant reads your question and chooses the relevant signal categories.")
    
    signal_selection_placeholder = st.sidebar.empty()
    
    def render_signal_selection(selected, reasoning):
        with signal_selection_placeholder.container():
            selection_text = ", ".join(get_signal_type_label(sig) for sig in selected) if selected else "None"
            st.markdown(f"**AI Selection:** {selection_text}")
            if reasoning:
                st.caption(f"💡 {reasoning}")
    
    last_signal_types = st.session_state.get("last_signal_types", DEFAULT_SIGNAL_TYPES)
    last_signal_reason = st.session_state.get("last_signal_reason", "")
    
    # Handle None case for last_signal_types
    if last_signal_types is None:
        last_signal_types = DEFAULT_SIGNAL_TYPES
    
    render_signal_selection(last_signal_types, last_signal_reason)
    
    with st.sidebar.expander("Available Signal Types", expanded=False):
        for key, (title, description) in SIGNAL_TYPE_DESCRIPTIONS.items():
            st.markdown(f"**{title}**")
            st.markdown(description)

    # --- SIDEBAR QUERY CONFIGURATION ---
    st.sidebar.markdown("---")
    st.sidebar.header("📊 Query Configuration")

    # Web Search toggle
    st.sidebar.subheader("🌐 Web Search")
    web_search_enabled = st.sidebar.toggle(
        "Enable Web Search (Tavily)",
        value=st.session_state.get("web_search_enabled", True),
        help=(
            "When enabled, the chatbot can search the web for live market news, "
            "earnings, and macro data. Requires TAVILY_API_KEY in your .env or secrets.toml."
        ),
    )
    st.session_state["web_search_enabled"] = web_search_enabled
    if web_search_enabled:
        st.sidebar.caption("🟢 Web search active — news/macro queries will use Tavily.")
    else:
        st.sidebar.caption("🔴 Web search disabled — all queries use internal data only.")

    # Propagate toggle to engine config at runtime
    import chatbot.config as _cfg
    _cfg.ENABLE_WEB_SEARCH = web_search_enabled

    llm_router_enabled = st.sidebar.toggle(
        "LLM router (web vs internal)",
        value=st.session_state.get("llm_router_enabled", True),
        help=(
            "Uses gpt-4o-mini to decide if each question needs internal signal data, "
            "web search (Tavily), both, or chat-only. Turn off to use keyword-based routing only."
        ),
    )
    st.session_state["llm_router_enabled"] = llm_router_enabled
    _cfg.LLM_ROUTER_ENABLED = llm_router_enabled

    # Reset cached router so toggles take effect
    chatbot._master_router = None

    # Render Chat History after Query Configuration
    st.sidebar.markdown("---")
    render_chat_history_sidebar()
    
    # Auto-extract functions is always enabled (no manual selection)
    use_auto_extract = True
    selected_functions = None
    selected_signal_types = list(last_signal_types)
    
    # Smart batch processing is always enabled
    import chatbot.config as config
    config.ENABLE_BATCH_PROCESSING = True
    
    # Check if settings have changed - if yes, clear history
    current_settings = {
        'tickers': tuple(sorted(selected_tickers)) if selected_tickers else None,
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'functions': tuple(sorted(selected_functions)) if selected_functions else None
    }
    
    # Clear everything button in sidebar
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Clear Current Chat"):
        chatbot.clear_history()
        # Update title to "New Chat"
        chatbot.history_manager.update_session_title("New Chat")
        st.session_state.chat_history = []
        st.session_state.last_settings = current_settings
        st.session_state.last_signal_types = DEFAULT_SIGNAL_TYPES.copy()
        st.session_state.last_signal_reason = "Default selection: entry, exit, target."
        st.rerun()
    
    if st.session_state.last_settings is not None:
        if current_settings != st.session_state.last_settings:
            logger_msg = "Settings changed - clearing backend history (chat visible)"
            st.sidebar.warning("⚠️ Settings changed - Starting fresh context (previous chat still visible)")
            # Clear backend history but keep chat visible for reference
            chatbot.clear_history()
            # Don't clear st.session_state.chat_history - keep it visible
            st.session_state.last_settings = current_settings
    else:
        st.session_state.last_settings = current_settings

    # --- CHAT HISTORY UI ---
    # Display chat messages
    chat_container = st.container()
    with chat_container:
        for idx, message in enumerate(st.session_state.chat_history):
            if message['role'] == 'user':
                with st.chat_message("user"):
                    # Extract clean user prompt for display
                    clean_content = extract_user_prompt(message['content'], message.get('metadata'))
                    ts = format_message_time_est(message.get('timestamp'))
                    if ts:
                        st.caption(ts)
                    st.markdown(clean_content)
            else:
                with st.chat_message("assistant"):
                    ts = format_message_time_est(message.get('timestamp'))
                    if ts:
                        st.caption(ts)
                    st.markdown(message['content'])
                    show_input_limit_notice(message.get('metadata'))

                    # Show metadata
                    msg_metadata = message.get('metadata', {})

                    # Intent + route badge (shown for all routed responses)
                    if msg_metadata.get("intent"):
                        render_route_badge(msg_metadata)
                    # Flow trace below the answer so it stays on-screen after long replies
                    render_flow_trace(msg_metadata)

                    # Check if it's a smart query or smart followup
                    if msg_metadata.get('input_type') in ['smart_query', 'smart_followup', 'web_rag', 'conversational']:
                        with st.expander("📊 Smart Query Details", expanded=False):
                            signal_types_meta = msg_metadata.get('selected_signal_types', [])
                            signal_reason_meta = msg_metadata.get('signal_type_reasoning', '')
                            if signal_types_meta:
                                st.markdown(f"**AI Signal Types:** {', '.join(get_signal_type_label(sig) for sig in signal_types_meta)}")
                                if signal_reason_meta:
                                    st.caption(f"💡 {signal_reason_meta}")
                            # Show column selection per signal type
                            st.subheader("🎯 Column Selection by Signal Type")
                            columns_by_type = msg_metadata.get('columns_by_signal_type', {})
                            reasoning_by_type = msg_metadata.get('reasoning_by_signal_type', {})
                            for signal_type in msg_metadata.get('selected_signal_types', []):
                                if signal_type in columns_by_type:
                                    cols = columns_by_type[signal_type]
                                    reasoning = reasoning_by_type.get(signal_type, '')
                                    st.markdown(f"**{get_signal_type_label(signal_type, uppercase=True)}** ({len(cols)} columns)")
                                    st.caption(f"💡 {reasoning}")
                                    with st.expander(f"View {signal_type} columns"):
                                        for col in cols:
                                            st.text(f"  • {col}")
                            
                            # Show signal data statistics
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Rows Fetched", msg_metadata.get('rows_fetched', 0))
                            with col2:
                                st.metric("Signal Types", len(msg_metadata.get('signal_types_with_data', [])))
                            with col3:
                                total_tokens = msg_metadata.get('tokens_used', {}).get('total', 0)
                                st.metric("Tokens Used", f"{total_tokens:,}")

                            # Display full signal tables if available
                            full_signal_tables = msg_metadata.get('full_signal_tables', {})
                            if full_signal_tables:
                                st.markdown("---")
                                st.subheader("📊 Complete Signal Data Used in Analysis")

                                # Display each signal type in separate sections
                                for signal_type, signal_df in full_signal_tables.items():
                                    if not signal_df.empty:
                                        st.markdown(f"**{get_signal_type_label(signal_type, uppercase=True)} Signals** ({len(signal_df)} records)")

                                        # Display the complete table with all columns and enhanced styling
                                        display_styled_dataframe(
                                            signal_df,
                                            height=min(350, (len(signal_df) + 1) * 40),  # Adaptive height for history
                                            key_suffix=f"smart_{signal_type}"
                                        )

                                        # Show summary info
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            st.metric("Records", len(signal_df))
                                        with col2:
                                            try:
                                                # Try to extract symbols from various columns
                                                symbols_found = set()
                                                for col in signal_df.columns:
                                                    if any(keyword in col.lower() for keyword in ['symbol', 'asset']):
                                                        symbols = signal_df[col].astype(str).str.extract(r'([A-Z]{2,5})').dropna()
                                                        symbols_found.update(symbols.iloc[:, 0].tolist() if not symbols.empty else [])
                                                unique_symbols = len(symbols_found) if symbols_found else "N/A"
                                            except:
                                                unique_symbols = "N/A"
                                            st.metric("Unique Symbols", unique_symbols)
                                        with col3:
                                            st.metric("Total Columns", len(signal_df.columns))
                    
                    # Show batch processing metadata for old query() method
                    elif msg_metadata.get('batch_processing_used'):
                        batch_mode = msg_metadata.get('batch_mode', 'unknown')
                        batch_count = msg_metadata.get('batch_count', 0)
                        tokens_used = msg_metadata.get('tokens_used', {})
                        finish_reason = msg_metadata.get('finish_reason', '')
                        
                        with st.expander("📊 Processing Details", expanded=False):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                if batch_mode == 'single':
                                    st.metric("Batch Mode", "Single 🎯", help="All signal data processed in one optimized batch")
                                else:
                                    if 'synthesis' in finish_reason:
                                        st.metric("Batch Mode", f"Multi + Synthesis ✨", help=f"{batch_count} batches with AI synthesis for unified response")
                                    else:
                                        st.metric("Batch Mode", f"Multi ({batch_count}) 🔄", help="Signal data split across multiple batches for optimal processing")
                            
                            with col2:
                                total_tokens = tokens_used.get('total', 0)
                                st.metric("Total Tokens", f"{total_tokens:,}", help="Total tokens used (prompt + completion)")
                            
                            with col3:
                                tickers_processed = len(msg_metadata.get('tickers', []))
                                st.metric("Tickers Processed", tickers_processed, help="Number of tickers analyzed")
                            
                            # Additional info
                            if 'synthesis' in finish_reason:
                                st.caption(f"✨ Multi-batch results synthesized into single response | Total: {tokens_used.get('prompt', 0):,} prompt + {tokens_used.get('completion', 0):,} completion tokens")
                            else:
                                st.caption(f"💡 Prompt: {tokens_used.get('prompt', 0):,} tokens | Completion: {tokens_used.get('completion', 0):,} tokens")

                    prev_is_user = (
                        idx > 0
                        and st.session_state.chat_history[idx - 1].get("role") == "user"
                    )
                    if prev_is_user:
                        um = st.session_state.chat_history[idx - 1]
                        am = message
                        sid = (
                            st.session_state.get("current_session_id")
                            or getattr(chatbot.history_manager, "session_id", "")
                            or ""
                        )
                        with st.expander("Flag this exchange for debugging", expanded=False):
                            st.caption(
                                "Engine log lines are only captured for queries run in this session. "
                                "Older messages still include flow_trace and metadata from the saved session."
                            )
                            st.caption(
                                f"Files are written under **`{FLAGGED_PAIRS_DIR.resolve()}`** on this machine "
                                "(e.g. EC2 disk—open that folder in Remote Desktop or copy via SCP)."
                            )
                            flag_notes = st.text_area(
                                "Notes (issue description)",
                                key=f"flag_notes_{sid}_{idx}",
                                height=100,
                                placeholder="Describe the issue…",
                            )
                            flag_full_tables = st.checkbox(
                                "Include full signal tables in JSON",
                                value=False,
                                key=f"flag_full_tables_{sid}_{idx}",
                            )
                            if st.button("Save JSON", key=f"flag_save_{sid}_{idx}"):
                                try:
                                    out_path = save_flagged_pair(
                                        session_id=sid,
                                        notes=flag_notes,
                                        user_message=um,
                                        assistant_message=am,
                                        include_full_tables=flag_full_tables,
                                        max_rows_sample=50,
                                    )
                                    st.success(f"Saved: `{out_path.resolve()}`")
                                except Exception as exc:
                                    st.error(f"Could not save: {exc}")
    
    # Chat input
    st.markdown("### 💬 Ask a Question")
    
    user_input = st.chat_input("Ask a question about your trading signal data...")
    
    if user_input:
        # Don't call determine_signal_types here - let smart_followup_query do it internally
        # This avoids duplicate extraction calls
        # Use default signal types as placeholder - will be determined by AI in smart_query
        selected_signal_types = DEFAULT_SIGNAL_TYPES.copy()
        ai_reason = None
        # Don't render signal selection here - will be shown after query completes
        # Keep last signal types as default until we get AI response
        st.session_state.last_signal_types = DEFAULT_SIGNAL_TYPES.copy()
        st.session_state.last_signal_reason = "Analyzing..."
        
        # Add user message to history (store clean user input for UI display)
        user_ts = utc_now_iso()
        st.session_state.chat_history.append({
            'role': 'user',
            'content': user_input,
            'metadata': {'display_prompt': user_input},
            'timestamp': user_ts,
        })
        
        # Display user message immediately (clean version only)
        with st.chat_message("user"):
            # Use extract_user_prompt to show only the clean question
            clean_prompt = extract_user_prompt(user_input, {'display_prompt': user_input})
            ts = format_message_time_est(user_ts)
            if ts:
                st.caption(ts)
            st.markdown(clean_prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            try:
                # Live pipeline steps (st.spinner does not refresh until the call returns)
                response, metadata = run_smart_followup_with_progress(
                    chatbot,
                    status_title="Analyzing your query with conversation context…",
                    user_message=user_input,
                    selected_signal_types=[],  # Let AI determine signal types
                    assets=selected_tickers if not use_auto_extract_tickers else None,
                    from_date=from_date.strftime('%Y-%m-%d'),
                    to_date=to_date.strftime('%Y-%m-%d'),
                    functions=selected_functions if not use_auto_extract else None,
                    auto_extract_tickers=use_auto_extract_tickers,
                    signal_type_reasoning=None,  # Will be determined by AI
                )

                # Get AI-determined signal types from metadata
                ai_selected_signal_types = metadata.get('selected_signal_types', [])
                ai_reason = metadata.get('signal_type_reasoning', '')

                # Update session state with AI-determined signal types
                if ai_selected_signal_types:
                    st.session_state.last_signal_types = ai_selected_signal_types
                    st.session_state.last_signal_reason = ai_reason

                resp_ts = utc_now_iso()
                rts = format_message_time_est(resp_ts)
                if rts:
                    st.caption(rts)

                # Display AI signal type selection at the top
                if ai_selected_signal_types:
                    selection_text = ", ".join(get_signal_type_label(sig) for sig in ai_selected_signal_types)
                    st.markdown(f"**AI Signal Type Selection:** {selection_text}")
                    if ai_reason:
                        st.caption(f"💡 {ai_reason}")

                # Intent + route badge
                if metadata.get("intent"):
                    render_route_badge(metadata)

                # Display response first; flow trace below so it is visible after long answers
                st.markdown(response)
                show_input_limit_notice(metadata)
                render_flow_trace(metadata)

                # Display Smart Query Details with signals
                with st.expander("📊 Smart Query Details", expanded=False):
                    # Show signal types and reasoning
                    st.markdown(f"**AI Signal Types:** {', '.join(get_signal_type_label(sig) for sig in selected_signal_types)}")
                    if ai_reason:
                        st.caption(f"💡 {ai_reason}")

                    # Display full signal tables if available
                    full_signal_tables = metadata.get('full_signal_tables', {})
                    if full_signal_tables:
                        st.markdown("---")
                        st.subheader("📊 Complete Signal Data Used in Analysis")

                        for signal_type, signal_df in full_signal_tables.items():
                            if not signal_df.empty:
                                st.markdown(f"**{get_signal_type_label(signal_type, uppercase=True)} Signals** ({len(signal_df)} records)")
                                display_styled_dataframe(
                                    signal_df,
                                    height=min(400, (len(signal_df) + 1) * 40),
                                    key_suffix=f"smart_{signal_type}"
                                )

                # Show smart query metadata
                input_type = metadata.get('input_type', '')

                if input_type in ['smart_query', 'smart_followup']:
                    selection_list = metadata.get('selected_signal_types', [])
                    selection_reason = metadata.get('signal_type_reasoning', '')
                    if selection_list:
                        st.markdown(f"**AI Signal Types:** {', '.join(get_signal_type_label(sig) for sig in selection_list)}")
                        if selection_reason:
                            st.caption(f"💡 {selection_reason}")
                    # Show column selection per signal type
                    st.subheader("🎯 Column Selection by Signal Type")

                    columns_by_type = metadata.get('columns_by_signal_type', {})
                    reasoning_by_type = metadata.get('reasoning_by_signal_type', {})

                    for signal_type in metadata.get('selected_signal_types', []):
                        if signal_type in columns_by_type:
                            cols = columns_by_type[signal_type]
                            reasoning = reasoning_by_type.get(signal_type, '')

                            # Simple display - same for all queries
                            st.markdown(f"**{get_signal_type_label(signal_type, uppercase=True)}** ({len(cols)} columns)")
                            st.caption(f"💡 {reasoning}")

                            with st.expander(f"View {signal_type} columns"):
                                for col in cols:
                                    st.text(f"  • {col}")

                    # Show signal data statistics - same format for all queries
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Rows Fetched", metadata.get('rows_fetched', 0))
                    with col2:
                        signal_types_count = len(metadata.get('signal_types_with_data', metadata.get('selected_signal_types', [])))
                        st.metric("Signal Types", signal_types_count)
                    with col3:
                        total_tokens = metadata.get('tokens_used', {}).get('total', 0)
                        st.metric("Tokens Used", f"{total_tokens:,}")

                # Add to history
                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': response,
                    'metadata': metadata,
                    'timestamp': resp_ts,
                })

                # Rerun to update chat display
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
    
    # Footer
    st.markdown("---")


if __name__ == "__main__":
    render_chatbot_page()

