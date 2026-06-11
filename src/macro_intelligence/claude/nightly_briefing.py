"""Claude nightly macro intelligence briefing — detailed 5-paragraph format."""

from __future__ import annotations

import json
import os
from typing import Any

from src.macro_intelligence.claude._client import call_claude
from src.macro_intelligence.claude.geo_news import fetch_macro_headlines
from src.macro_intelligence.config import load_config

SYSTEM = """You are a senior macro strategist writing the Runic Agent nightly briefing.
Your audience are portfolio managers who rely on this as their primary morning note.
Write with the precision and authority of a BTIG or Goldman Sachs macro morning note.
No hedging language. No disclaimers. Cite specific numbers.
Do NOT use subjective adjectives (e.g. commanding, dismal, spectacular). State hit rates as neutral facts.
Use numeric horizon labels: 3m, 6m, 12m, 5d — never spell out "three-month".
Combo G is a timing warning only — not a return predictor; note testable from 2007 only (VIX3M data).
For Combo E, cite only the confirmed_legs provided — do not imply CFTC is active unless listed.

Mandatory structure — five paragraphs, in this order:

PARAGRAPH 1 — DOMINANT SIGNAL
Name the dominant combo (letter + full name), its current duration and bucket (SHORT/MEDIUM/LONG), the single most important variable driving it with its exact current level and percentile, and in one sentence why this combo outweighs every competing signal this week.

PARAGRAPH 2 — ALL ACTIVE AND WATCH COMBOS
Cover EVERY active and watch combo individually, one sentence each minimum. For each: state its status (ACTIVE/PARTIAL/WATCH/CONFIRMED/CANCELLED), duration (include episode start date if provided), the direction of its signal (bullish or bearish for SPX), its validated-horizon historical hit rate (primary_label from payload), and what the specific variable levels are saying right now. Combo G: timing warning only, no return hit rate. Do not skip any combo from the list provided.

PARAGRAPH 3 — WHY THE DOMINANT SIGNAL WINS
Give three numbered reasons (1) (2) (3) why the dominant signal outweighs the competing signals. Each reason must cite a specific variable level, regime dimension, or historical precedent. Include the regime context (Fed cycle, yield curve, valuation, liquidity).

PARAGRAPH 4 — HISTORICAL ANALOGS
Provide 2–3 historical analogs with exact dates, the macro conditions at that date that matched the current setup, and the realized SPX forward return at 3 months, 6 months, and 12 months. State which analog is closest and why.

PARAGRAPH 5 — SYSTEM POSTURE AND ACTION
State the system posture (e.g. TACTICAL FEARFUL / TACTICAL EASY MONEY). Give explicit numbered conditions that would change the posture. Be specific — name the variable, the threshold, and the time requirement.

Total length: 380–450 words. Use plain paragraphs. No bullet points. No markdown headers."""


def generate_nightly_briefing(payload: dict[str, Any], use_claude: bool = True) -> str:
    if not use_claude or not os.environ.get("ANTHROPIC_API_KEY"):
        return _template_briefing(payload)

    cfg = load_config()
    max_tokens = cfg.get("claude", {}).get("narrative_max_tokens", 1200)
    briefing_cfg = cfg.get("briefing", {})
    combo_labels = briefing_cfg.get("combo_labels", {})

    dominant = payload.get("dominant_signal") or "—"
    dom_label = combo_labels.get(str(dominant), "")

    macro_headlines = fetch_macro_headlines(
        payload.get("date", ""),
        combo_label=dom_label,
        max_results=6,
    )

    active_combos = payload.get("active_combos", [])
    watch_combos = payload.get("watch_combos", [])
    vars_block = payload.get("variables_dashboard") or []

    combo_descriptions = []
    for c in active_combos:
        letter = c.get("combo", "?")
        label = combo_labels.get(letter, letter)
        combo_descriptions.append({
            "combo": f"{letter} — {label}",
            "status": c.get("status"),
            "duration_weeks": c.get("duration_weeks"),
            "duration_bucket": c.get("duration_bucket"),
            "episode_start": c.get("episode_start"),
            "confirmed_legs": c.get("confirmed_legs"),
            "primary_hit_rate": (
                f"{c['hit_rate_primary'] * 100:.0f}% {c.get('primary_label', '')}"
                if c.get("hit_rate_primary") is not None
                else "n/a"
            ),
            "primary_avg_return": (
                f"{c['avg_return_primary']:+.1f}% {c.get('primary_label', '')}"
                if c.get("avg_return_primary") is not None
                else "n/a"
            ),
        })
    for w in watch_combos:
        label = combo_labels.get(str(w), str(w))
        combo_descriptions.append({
            "combo": f"{w} — {label}",
            "status": "WATCH",
            "duration_weeks": None,
            "hit_rate_3m": "n/a",
            "avg_return_3m": "n/a",
        })

    var_summary = []
    for v in vars_block:
        var_summary.append({
            "variable": v.get("variable"),
            "current": v.get("current"),
            "tier": v.get("tier"),
            "pctile_3yr": v.get("pctile_3yr"),
            "direction": v.get("direction"),
        })

    user = (
        f"Date: {payload.get('date')}.\n"
        f"Dominant signal: Combo {dominant} ({dom_label}). "
        f"Dominant reason: {payload.get('dominant_reason')}. "
        f"System posture: {payload.get('brave_fearful')}.\n"
        f"Dominant combo — 3m hit rate: {payload.get('spx_3m_hit_rate')}, "
        f"3m avg SPX return: {payload.get('spx_3m_forward_avg')}%.\n\n"
        f"ALL ACTIVE AND WATCH COMBOS:\n{json.dumps(combo_descriptions, indent=2)}\n\n"
        f"REGIME (5 dimensions): {json.dumps(payload.get('regime', {}))}\n\n"
        f"12-VARIABLE DASHBOARD:\n{json.dumps(var_summary, indent=2)}\n\n"
        f"HISTORICAL ANALOGS (date + realized SPX returns):\n"
        f"{json.dumps(payload.get('analog_details', payload.get('analog_dates', [])), indent=2)}\n\n"
        f"COMBO C CANCEL STATE: {json.dumps(payload.get('combo_c_cancel', {}))}\n"
        f"PENDING CPI RELEASE THIS WEEK: {payload.get('pending_cpi_release', False)}\n"
        f"SSI LAYER2 STATUS: {payload.get('ssi_layer2_status')}\n\n"
        f"CURRENT MACRO NEWS (Tavily, use where relevant):\n"
        f"{macro_headlines or 'No headlines available.'}\n\n"
        "Write the nightly briefing now."
    )

    try:
        return call_claude(SYSTEM, user, max_tokens=max_tokens)
    except Exception:
        return _template_briefing(payload)


def _template_briefing(payload: dict[str, Any]) -> str:
    """Fallback when Claude is unavailable."""
    cfg = load_config().get("briefing", {})
    combo_labels = cfg.get("combo_labels", {})
    dom = payload.get("dominant_signal", "N/A")
    dom_label = combo_labels.get(str(dom), "")
    reason = payload.get("dominant_reason", "")
    brave = (payload.get("brave_fearful") or "NEUTRAL").replace("_", " ")

    active_combos = payload.get("active_combos", [])
    watch_combos = payload.get("watch_combos", [])

    combo_lines = []
    for c in active_combos:
        letter = c.get("combo", "?")
        label = combo_labels.get(letter, letter)
        hr = c.get("hit_rate_3m")
        wk = c.get("duration_weeks")
        hr_txt = f"{hr * 100:.0f}% 3m hit rate" if hr is not None else "—"
        wk_txt = f"week {wk}" if wk else ""
        combo_lines.append(
            f"Combo {letter} ({label}) is {c.get('status', 'ACTIVE')} {wk_txt} — {hr_txt}."
        )
    for w in watch_combos:
        label = combo_labels.get(str(w), str(w))
        combo_lines.append(f"Combo {w} ({label}) is on WATCH.")

    details = payload.get("analog_details") or []
    analog_parts = []
    for d in details[:2]:
        if not d.get("date"):
            continue
        ret = d.get("spx_3m_pct")
        analog_parts.append(
            f"{d['date']} (SPX 3m {ret:+.1f}%)" if ret is not None else str(d["date"])
        )
    analog_txt = "; ".join(analog_parts) if analog_parts else "historical analogs pending"

    hr = payload.get("spx_3m_hit_rate")
    hr_txt = f"{hr * 100:.0f}% 3m hit rate" if hr is not None else "hit rate pending"

    parts = [
        f"The dominant macro signal is Combo {dom} ({dom_label}), which outweighs competing "
        f"signals because {reason} Historical database shows {hr_txt}.",
    ]
    if combo_lines:
        parts.append(" ".join(combo_lines))
    parts.append(
        f"Closest historical analogs: {analog_txt}. "
        f"The system posture is {brave}. "
        "Hold existing positions and do not add broad equity exposure until the dominant signal clears."
    )
    return " ".join(parts)
