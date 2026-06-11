"""Tavily headlines for geo_overlay classification and nightly narrative context."""

from __future__ import annotations

import os


def _tavily_search(query: str, max_results: int) -> str:
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        return ""
    try:
        from tavily import TavilyClient
    except ImportError:
        return ""
    try:
        client = TavilyClient(api_key=key)
        resp = client.search(query=query, max_results=max_results, search_depth="basic")
        results = resp.get("results", [])
        lines = [f"- {r.get('title', '')}: {r.get('content', '')[:200]}" for r in results[:max_results]]
        return "\n".join(lines)
    except Exception:
        return ""


def fetch_geo_headlines(as_of: str, max_results: int = 5) -> str:
    """Geo-focused headlines for regime classifier (geo_overlay)."""
    query = f"geopolitical macro markets Fed inflation oil Middle East {as_of}"
    return _tavily_search(query, max_results)


def fetch_macro_headlines(as_of: str, combo_label: str = "", max_results: int = 6) -> str:
    """Broad macro headlines for nightly narrative context.

    Queries Fed policy, SPX market, and the dominant combo theme so the
    Claude narrative is grounded in current news rather than stale training data.
    """
    theme = combo_label.lower().replace("/", " ").replace("-", " ")
    query = (
        f"S&P 500 Federal Reserve inflation {theme} macro outlook {as_of}"
    )
    return _tavily_search(query, max_results)
