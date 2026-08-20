"""Shared CFTC grid report formatting (episode distribution spec, Aug 2026)."""

from __future__ import annotations

from typing import Any

# Worked examples from Rohit reporting spec — tail vs market-beta cells.
WORKED_EXAMPLE_A = [22.0, 18.0, 14.0, 3.0, 2.0, 1.0, -1.0, -2.0, -4.0]
WORKED_EXAMPLE_B = [6.0, 5.0, 4.0, 3.0, 3.0, 2.0, 1.0, -1.0, -2.0]


def horizon_metrics(row: dict[str, Any], horizon: str) -> dict[str, Any]:
    m = (row.get("metrics") or {}).get(horizon) or {}
    if m.get("mean") is None and m.get("avg") is not None:
        m = dict(m)
        m["mean"] = m.get("avg")
    if m.get("hit_excess_pct") is None and m.get("excess_hit_pct") is not None:
        m = dict(m)
        m["hit_excess_pct"] = m.get("excess_hit_pct")
    return m


def cell_rank_gap(row: dict[str, Any], horizon: str = "12w") -> float | None:
    m = horizon_metrics(row, horizon)
    gap = m.get("mean_median_gap")
    return float(gap) if gap is not None else None


def rank_cells_by_gap(
    rows: list[dict[str, Any]],
    horizon: str = "12w",
    *,
    min_episodes: int = 3,
    positive_gap: bool | None = None,
    squeeze_only: bool = False,
    long_side: bool = True,
) -> list[dict[str, Any]]:
    """Rank cells on mean−median gap (tail marker), not Sharpe."""
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        if squeeze_only and row.get("pattern") not in (None, "SQUEEZE"):
            continue
        m = horizon_metrics(row, horizon)
        if not m or m.get("n", 0) < min_episodes:
            continue
        gap = m.get("mean_median_gap")
        if gap is None:
            continue
        if positive_gap is True and gap <= 0:
            continue
        if positive_gap is False and gap >= 0:
            continue
        scored.append((float(gap), row))
    scored.sort(key=lambda x: -x[0] if long_side else x[0])
    return [row for _, row in scored]


def format_cell_line(row: dict[str, Any], horizon: str = "12w") -> str:
    m = horizon_metrics(row, horizon)
    if not m or not m.get("n"):
        return "—"
    return (
        f"n_ep={row.get('n_episodes', 0)} (wk={row.get('n_weeks', 0)}) | "
        f"mean={m.get('mean')}% med={m.get('median')}% gap={m.get('mean_median_gap')}% | "
        f"hit={m.get('hit_pct')}% excess_hit={m.get('hit_excess_pct')}% | "
        f"mean_excess={m.get('mean_excess')}% med_excess={m.get('median_excess')}% | "
        f"best={m.get('best')}% worst={m.get('worst')}%"
    )


def format_par_horizon(par: dict[str, Any], horizon: str, benchmark: dict[str, float | None] | None = None) -> str:
    m = horizon_metrics(par, horizon)
    if not m or not m.get("n"):
        return f"- **{horizon}**: no data"
    bench = (benchmark or {}).get(horizon)
    bench_s = f"{bench}%" if bench is not None else "—"
    return (
        f"- **{horizon}** (bench {bench_s}): n_wk={par.get('n_weeks', 0)} | "
        f"mean={m.get('mean')}% med={m.get('median')}% | "
        f"mean_excess={m.get('mean_excess')}% med_excess={m.get('median_excess')}% | "
        f"hit={m.get('hit_pct')}% excess_hit={m.get('hit_excess_pct')}%"
    )


def format_par_section(
    par: dict[str, Any],
    *,
    benchmark: dict[str, float | None] | None = None,
    horizons: list[str] | None = None,
    title: str = "PAR (unconditional — every week in sample, no episode collapse)",
) -> list[str]:
    """Standard par block for top of CFTC grids."""
    horizons = horizons or ["4w", "8w", "12w"]
    lines = [
        f"## {title}",
        "",
        "Excess = SPX forward return minus mean SPX return across **all** weeks at that horizon.",
        "excess_hit = share of observations that **beat the market** (excess > 0), not merely positive SPX.",
        "",
    ]
    for h in horizons:
        lines.append(format_par_horizon(par, h, benchmark))
    lines.append("")
    return lines


def format_heatmap_cell(row: dict[str, Any] | None, horizon: str = "12w") -> str:
    """Compact heatmap cell: avg / excess_hit."""
    if not row:
        return "—"
    m = horizon_metrics(row, horizon)
    if not m or not m.get("n"):
        n_ep = row.get("n_episodes", row.get("n", 0))
        return f"n_ep={n_ep}"
    avg = m.get("mean") or m.get("avg")
    excess_hit = m.get("hit_excess_pct")
    if excess_hit is not None:
        return f"{avg}% / ex_hit {excess_hit}% (n_ep={row.get('n_episodes', 0)})"
    return f"{avg}% (n_ep={row.get('n_episodes', 0)})"


def format_episode_instances(
    row: dict[str, Any],
    horizon: str = "12w",
    *,
    top_n: int = 9,
    sort_key: str | None = None,
) -> str:
    """Dated list of top episode returns for a cell."""
    key = sort_key or f"ret_{horizon}"
    episodes = row.get("episodes") or row.get("all_episodes") or []
    ranked = [ep for ep in episodes if ep.get(key) is not None]
    if not ranked:
        return "—"
    ranked = sorted(ranked, key=lambda ep: ep[key], reverse=True)[:top_n]
    parts = [f"{ep.get('date')} {ep[key]:+.4f}%" for ep in ranked]
    return "; ".join(parts)


def cell_distribution_row(
    row: dict[str, Any],
    horizon: str = "12w",
    *,
    fm_key: str = "fm_pct_max",
    rm_key: str = "rm_pct_min",
    include_instances: bool = False,
) -> dict[str, Any]:
    m = horizon_metrics(row, horizon)
    out = {
        "condition": row.get("condition", ""),
        "fm": row.get(fm_key) or row.get("fm_max"),
        "rm": row.get(rm_key) or row.get("rm_min"),
        "n_weeks": row.get("n_weeks", row.get("n", 0)),
        "n_episodes": row.get("n_episodes", 0),
        "mean": m.get("mean"),
        "median": m.get("median"),
        "mean_median_gap": m.get("mean_median_gap"),
        "hit_pct": m.get("hit_pct"),
        "mean_excess": m.get("mean_excess"),
        "median_excess": m.get("median_excess"),
        "hit_excess_pct": m.get("hit_excess_pct"),
        "best": m.get("best"),
        "worst": m.get("worst"),
    }
    if include_instances:
        out["top_instances"] = format_episode_instances(row, horizon)
    return out


def distribution_table_header(*, include_instances: bool = False, include_excess: bool = True) -> str:
    cols = (
        "| FM < | RM > | n_wk | n_ep | mean % | median % | gap % | hit % | "
        "mean_ex % | med_ex % | ex_hit % | best % | worst %"
    )
    if include_instances:
        cols += " | top instances (date ret)"
    return cols + " |"


def distribution_table_sep(*, include_instances: bool = False, include_excess: bool = True) -> str:
    base = (
        "|------|------|------|------|--------|----------|-------|-------|"
        "|----------|----------|----------|--------|---------"
    )
    if include_instances:
        base += "|-------------------"
    return base + "|"


def distribution_table_line(
    row: dict[str, Any],
    horizon: str = "12w",
    *,
    fm_key: str = "fm_pct_max",
    rm_key: str = "rm_pct_min",
    include_instances: bool = False,
) -> str:
    d = cell_distribution_row(row, horizon, fm_key=fm_key, rm_key=rm_key, include_instances=include_instances)
    fm = d.get("fm", "—")
    rm = d.get("rm", "—")
    line = (
        f"| {fm} | {rm} | {d['n_weeks']} | {d['n_episodes']} | "
        f"{d['mean']} | {d['median']} | {d['mean_median_gap']} | "
        f"{d['hit_pct']} | {d['mean_excess']} | {d['median_excess']} | {d['hit_excess_pct']} | "
        f"{d['best']} | {d['worst']}"
    )
    if include_instances:
        line += f" | {d.get('top_instances', '—')}"
    return line + " |"


def worked_examples_section() -> str:
    from src.sentiment_superindex.analysis.cftc_episode_metrics import summarize_episode_horizon

    a = summarize_episode_horizon(WORKED_EXAMPLE_A, benchmark=None, long_side=True)
    b = summarize_episode_horizon(WORKED_EXAMPLE_B, benchmark=None, long_side=True)
    lines = [
        "## Worked examples — why mean−median gap, not Sharpe or hit rate alone",
        "",
        "**Example A (tail-driven squeeze is real):** "
        "+22%, +18%, +14%, +3%, +2%, +1%, −1%, −2%, −4%",
        "",
        f"- mean **{a['mean']}%**, median **{a['median']}%**, gap **{a['mean_median_gap']}%**, "
        f"hit **{a['hit_pct']}%**, worst **{a['worst']}%**",
        "",
        "**Example B (nothing there — market beta):** "
        "+6%, +5%, +4%, +3%, +3%, +2%, +1%, −1%, −2%",
        "",
        f"- mean **{b['mean']}%**, median **{b['median']}%**, gap **{b['mean_median_gap']}%**, "
        f"hit **{b['hit_pct']}%**, worst **{b['worst']}%**",
        "",
        "B has higher hit rate and better worst case. Only the gap and dated top instances reveal A's tail edge.",
        "",
    ]
    return "\n".join(lines)
