"""BTIG-style nightly briefing PDF/HTML from runic payload."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from src.macro_intelligence.config import load_config
from src.macro_intelligence.engine.combo_metadata import format_hit_rate_display, posture_display

logger = logging.getLogger(__name__)

_COMBO_ORDER = "ABCDEFG"


def _all_time_combo_stats() -> dict[str, dict]:
    """Return all-time hit rate at each combo's validated primary horizon."""
    from src.macro_intelligence.engine.combo_metadata import combo_hit_rate_stats, format_hit_rate_display

    stats: dict[str, dict] = {}
    for letter in "ABCDEFG":
        s = combo_hit_rate_stats(letter)
        hr_txt, avg_txt = format_hit_rate_display(s)
        stats[letter] = {
            "hit_rate_display": hr_txt,
            "avg_return_display": avg_txt,
            "hit_rate_primary": s.get("hit_rate_primary"),
            "avg_return_primary": s.get("avg_return_primary"),
            "primary_label": s.get("primary_label"),
            "show_hit_rate": s.get("show_hit_rate", True),
        }
    return stats

# ── Colour palette ────────────────────────────────────────────────────────────
_NAVY       = "#0A1628"   # header, rec-box background
_NAVY_LIGHT = "#1B2E4B"   # table header row
_WHITE      = "#FFFFFF"
_GREEN_BG   = "#1A5C38"   # ACTIVE combo row
_GREEN_TEXT = "#FFFFFF"
_AMBER_BG   = "#7D5200"   # WATCH combo row / EXTREME var row
_AMBER_TEXT = "#FFFFFF"
_HIGH_BG    = "#FFF3CD"   # HIGH var row (yellow-ish)
_HIGH_TEXT  = "#3D2800"
_INACTIVE_BG= "#F2F2F2"
_BODY_TEXT  = "#1A1A1A"
_SUBTLE     = "#6B7280"
_BORDER     = "#D1D5DB"


def _combo_links() -> dict[str, str]:
    cfg = load_config()
    links: dict[str, set[str]] = {}
    for var in cfg.get("variables", []):
        vid = var.get("id", "")
        for c in var.get("combos", []):
            links.setdefault(str(c), set()).add(vid)
    return {k: ",".join(sorted(v)) for k, v in links.items()}


def _fmt_pct(val: float | None, *, decimals: int = 1) -> str:
    if val is None:
        return "—"
    if abs(val) <= 1.5:
        return f"{val * 100:.{decimals}f}%"
    return f"{val:.{decimals}f}%"


def _fmt_num(val: Any, *, decimals: int = 2) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)


def build_system_recommendation(payload: dict[str, Any]) -> str:
    if payload.get("system_recommendation"):
        return str(payload["system_recommendation"])
    dom = payload.get("dominant_signal")
    brave = payload.get("brave_fearful", "NEUTRAL")
    cancel = payload.get("combo_c_cancel", {})
    pending_cpi = payload.get("pending_cpi_release")
    parts: list[str] = [brave.replace("_", " ")]
    if dom == "C":
        parts.append(
            "Hold existing longs; do NOT add broad equity exposure until Combo C cancel completes "
            "(WTI 4wk below +5% for 4 consecutive Fridays AND CPI not hot)."
        )
    elif dom == "F":
        parts.append(
            "Combo F recovery window active; hold/add tactically per conviction. "
            "Respect Combo C if also active."
        )
    else:
        parts.append("Monitor regime, Friday CFTC release, and competing combo signals.")
    if cancel.get("active"):
        wk = cancel.get("wti_potential_week", 0)
        mc = cancel.get("model_cancel_prob")
        if mc is not None:
            parts.append(
                f"Combo C cancel watch: WTI leg week {wk}/4; "
                f"model P(cancel next 4wk)={float(mc) * 100:.0f}%."
            )
        else:
            parts.append(f"Combo C cancel watch: WTI leg week {wk}/4.")
    if pending_cpi:
        parts.append("CPI release pending this week — watch inflation leg.")
    return " — ".join(parts)


def _combo_c_cancelled_row(payload: dict[str, Any]) -> dict[str, Any] | None:
    cancel = payload.get("combo_c_cancel", {})
    cancel_date = cancel.get("cancel_date")
    if not cancel_date and not cancel.get("cancelled"):
        return None
    if cancel.get("active"):
        return None
    return {"cancel_date": cancel_date or cancel.get("last_check_date")}


def build_combo_status_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = load_config().get("briefing", {})
    labels = cfg.get("combo_labels", {})
    directions = cfg.get("combo_direction", {})
    max_weeks = cfg.get("combo_max_weeks", {})
    active = {c["combo"]: c for c in payload.get("active_combos", []) if c.get("combo")}
    watch = set(payload.get("watch_combos", []))
    db_stats = _all_time_combo_stats()
    c_cancel = _combo_c_cancelled_row(payload)
    rows: list[dict[str, Any]] = []
    for letter in _COMBO_ORDER:
        label = labels.get(letter, letter)
        match = active.get(letter)
        s = db_stats.get(letter, {})
        hr_disp = s.get("hit_rate_display", "—")
        avg_disp = s.get("avg_return_display", "—")
        if letter == "C" and c_cancel and letter not in active:
            rows.append(
                {
                    "combo": letter,
                    "name": label,
                    "status": "CANCELLED",
                    "duration": f"cancelled {c_cancel['cancel_date']}",
                    "direction": directions.get(letter, "—"),
                    "hit_rate_3m": hr_disp,
                    "avg_return_3m": avg_disp,
                }
            )
            continue
        if match:
            weeks = match.get("duration_weeks")
            bucket = match.get("duration_bucket") or "—"
            max_w = max_weeks.get(letter)
            ep = match.get("episode_start")
            if weeks and max_w:
                duration = f"Week {weeks} of {max_w} ({bucket})"
            elif weeks:
                duration = f"Week {weeks} ({bucket})"
            else:
                duration = bucket if bucket != "—" else "—"
            if ep:
                duration += f" · started {ep}"
            legs = match.get("confirmed_legs")
            if legs:
                duration += f" · legs {', '.join(legs)}"
            if match.get("show_hit_rate", True):
                hr_disp, avg_disp = format_hit_rate_display(match)
            rows.append(
                {
                    "combo": letter,
                    "name": label,
                    "status": match.get("status", "ACTIVE"),
                    "duration": duration,
                    "direction": directions.get(letter, "—"),
                    "hit_rate_3m": hr_disp,
                    "avg_return_3m": avg_disp,
                }
            )
        elif letter in watch:
            rows.append(
                {
                    "combo": letter,
                    "name": label,
                    "status": "WATCH",
                    "duration": "—",
                    "direction": directions.get(letter, "—"),
                    "hit_rate_3m": hr_disp,
                    "avg_return_3m": avg_disp,
                }
            )
        else:
            rows.append(
                {
                    "combo": letter,
                    "name": label,
                    "status": "INACTIVE",
                    "duration": "—",
                    "direction": directions.get(letter, "—"),
                    "hit_rate_3m": hr_disp,
                    "avg_return_3m": avg_disp,
                }
            )
    return rows


def build_regime_grid(payload: dict[str, Any]) -> list[tuple[str, str]]:
    regime = payload.get("regime", {})
    ssi = payload.get("ssi_multiplier")
    layer2 = payload.get("ssi_layer2_status")
    ssi_txt = f"{ssi:.2f}×" if ssi is not None else "—"
    if layer2:
        ssi_txt += f" ({layer2})"
    cape = regime.get("val_regime", "—")
    dash = payload.get("variables_dashboard", [])
    cape_row = next((d for d in dash if d.get("variable") == "CAPE"), None)
    if cape_row and cape_row.get("current") is not None:
        cape = f"{cape} CAPE {_fmt_num(cape_row.get('current'), decimals=2)}x"
    return [
        ("Fed Cycle",    str(regime.get("fed_cycle", "—"))),
        ("Yield Curve",  str(regime.get("curve_regime", "—"))),
        ("Geopolitical", str(regime.get("geo_overlay", "—"))),
        ("Valuation",    str(cape)),
        ("Liquidity",    str(regime.get("liquidity", "—"))),
        ("SSI",          ssi_txt),
    ]


def _derive_direction(var_id: str, raw: Any, pctile: float | None) -> str:
    """Derive UP/DOWN for variables where the engine returned None (NORMAL tier).

    Uses variable-specific sign semantics so the direction is meaningful:
    - For spread/stress variables (HY, VIX, VXTS, CFTC, CURVE): high pctile = stress = shown as UP
    - For level/rate-of-change variables (WTI, CNH, WALCL, GSR): sign of raw value
    - For conditions indices (NFCI): positive = tight = UP, negative = loose = DOWN
    - For inflation (CPI): positive surprise = UP
    - For valuation (CAPE): above median = UP
    """
    if pctile is None:
        return "—"
    # For all variables: percentile above 50 = reading is elevated (UP), below 50 = depressed (DOWN)
    return "UP" if pctile >= 50 else "DOWN"


def build_variable_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    links = _combo_links()
    rows: list[dict[str, Any]] = []
    for row in payload.get("variables_dashboard", []):
        vid = row.get("variable", "")
        tier = row.get("tier", "NORMAL")
        raw = row.get("current")
        pctile = row.get("pctile_3yr")
        direction = row.get("direction")
        if direction is None:
            direction = _derive_direction(vid, raw, pctile)
        combos_for_var = []
        for letter, vars_str in links.items():
            if vid in vars_str.split(","):
                combos_for_var.append(letter)
        entry = {
            "num": row.get("num"),
            "variable": vid,
            "current": _fmt_num(raw),
            "tier": tier,
            "pctile_3yr": _fmt_pct(pctile, decimals=0) if pctile is not None else "—",
            "direction": direction,
            "combos": ",".join(combos_for_var) if combos_for_var else "—",
        }
        if vid == "CFTC":
            entry["source_note"] = row.get("source_note") or (
                "CFTC.gov TFF · S&P 500 Consolidated · Lev Money net"
            )
        rows.append(entry)
    return rows


def build_briefing_sections(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config().get("briefing", {})
    labels = cfg.get("combo_labels", {})
    date = payload.get("date", datetime.now().strftime("%Y-%m-%d"))
    dominant = payload.get("dominant_signal") or "—"
    dom_label = labels.get(str(dominant), "")
    dom_combo = next(
        (r for r in build_combo_status_rows(payload) if r["combo"] == dominant),
        None,
    )
    duration_txt = dom_combo["duration"] if dom_combo else "—"
    return {
        "date": date,
        "title": "MACRO INTELLIGENCE AGENT — NIGHTLY BRIEFING",
        "subtitle": "Runic Agent v2.2",
        "dominant_signal": dominant,
        "dominant_label": dom_label,
        "dominant_duration": duration_txt,
        "dominant_reason": payload.get("dominant_reason", ""),
        "brave_fearful": posture_display(payload.get("brave_fearful_display") or payload.get("brave_fearful")),
        "combo_rows": build_combo_status_rows(payload),
        "regime_grid": build_regime_grid(payload),
        "narrative": payload.get("narrative", ""),
        "variable_rows": build_variable_rows(payload),
        "system_recommendation": build_system_recommendation(payload),
        "footer": "Runic Agent v2.2 | Macro Intelligence Agent | Internal use only",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  HTML renderer
# ─────────────────────────────────────────────────────────────────────────────

def _combo_row_style(status: str) -> str:
    if status in ("ACTIVE", "PARTIAL", "CONFIRMED", "CONFIRMED_3_OF_3"):
        return f"background:{_GREEN_BG};color:{_GREEN_TEXT};"
    if status == "WATCH":
        return f"background:{_AMBER_BG};color:{_AMBER_TEXT};"
    if status == "CANCELLED":
        return f"background:#4A3728;color:{_WHITE};"
    return f"background:{_INACTIVE_BG};color:{_BODY_TEXT};"


def _var_row_style(tier: str) -> str:
    if str(tier).upper() == "EXTREME":
        return f"background:{_AMBER_BG};color:{_AMBER_TEXT};"
    if str(tier).upper() == "HIGH":
        return f"background:{_HIGH_BG};color:{_HIGH_TEXT};"
    return ""


def render_html(payload: dict[str, Any]) -> str:
    s = build_briefing_sections(payload)

    combo_html = ""
    for r in s["combo_rows"]:
        row_style = _combo_row_style(r["status"])
        combo_html += (
            f'<tr style="{row_style}">'
            f"<td><b>{r['combo']}</b> — {r['name']}</td>"
            f"<td><b>{r['status']}</b></td>"
            f"<td>{r['duration']}</td>"
            f"<td>{r['direction']}</td>"
            f"<td>{r['hit_rate_3m']}</td>"
            f"<td>{r['avg_return_3m']}</td>"
            f"</tr>"
        )

    # 3-column regime grid
    grid_items = s["regime_grid"]
    regime_html = "<table style='border-collapse:collapse;width:100%;margin-top:8px'><tr>"
    for i, (lbl, val) in enumerate(grid_items):
        if i and i % 3 == 0:
            regime_html += "</tr><tr>"
        regime_html += (
            f"<td style='border:1px solid {_BORDER};padding:6px 10px;width:33%;vertical-align:top'>"
            f"<span style='font-size:9px;text-transform:uppercase;color:{_SUBTLE};font-weight:bold'>{lbl}</span>"
            f"<br><span style='font-size:12px;font-weight:bold;color:{_BODY_TEXT}'>{val}</span>"
            f"</td>"
        )
    regime_html += "</tr></table>"

    var_html = ""
    for r in s["variable_rows"]:
        row_style = _var_row_style(r["tier"])
        var_html += (
            f'<tr style="{row_style}">'
            f"<td>{r['num']}</td><td>{r['variable']}</td><td>{r['current']}</td>"
            f"<td>{r['tier']}</td><td>{r['pctile_3yr']}</td>"
            f"<td>{r['direction']}</td><td>{r['combos']}</td>"
            f"</tr>"
        )

    narrative_html = (s["narrative"] or "Narrative pending.").replace("\n\n", "</p><p>").replace("\n", "<br/>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Runic Briefing {s['date']}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;color:{_BODY_TEXT};font-size:12px;background:#F9FAFB}}
.page{{max-width:900px;margin:0 auto;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.12)}}
/* Header */
.hdr{{background:{_NAVY};color:{_WHITE};padding:20px 24px 16px}}
.hdr-title{{font-size:18px;font-weight:700;letter-spacing:.5px}}
.hdr-sub{{font-size:10px;opacity:.75;margin-top:4px;letter-spacing:.3px}}
/* Body */
.body{{padding:20px 24px}}
/* Dominant signal band */
.dominant{{background:{_NAVY};color:{_WHITE};padding:12px 16px;border-radius:4px;margin-bottom:14px;font-size:11px;line-height:1.6}}
.dominant .signal-label{{font-size:15px;font-weight:700;letter-spacing:.3px}}
/* Section headings */
.section-head{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:{_NAVY};border-bottom:2px solid {_NAVY};padding-bottom:4px;margin:16px 0 8px}}
/* Tables */
table{{border-collapse:collapse;width:100%;margin-bottom:12px}}
th{{background:{_NAVY_LIGHT};color:{_WHITE};padding:6px 8px;font-size:9px;text-align:left;text-transform:uppercase;letter-spacing:.4px}}
td{{border:1px solid {_BORDER};padding:5px 8px;font-size:10px;vertical-align:top}}
/* Narrative */
.narrative{{line-height:1.65;font-size:11px;text-align:justify;color:{_BODY_TEXT}}}
.narrative p{{margin-bottom:10px}}
/* Recommendation box */
.rec{{background:{_NAVY};color:{_WHITE};padding:14px 18px;border-radius:4px;font-size:11px;line-height:1.65;margin-top:14px}}
.rec-label{{font-size:10px;text-transform:uppercase;letter-spacing:.6px;opacity:.7;margin-bottom:4px}}
/* Footer */
.footer{{text-align:center;font-size:9px;color:{_SUBTLE};padding:14px 24px;border-top:1px solid {_BORDER};margin-top:8px}}
</style>
</head>
<body>
<div class="page">
  <!-- HEADER -->
  <div class="hdr">
    <div class="hdr-title">{s['title']}</div>
    <div class="hdr-sub">{s['date']} &nbsp;|&nbsp; {s['subtitle']} &nbsp;|&nbsp; Internal use only</div>
  </div>

  <div class="body">
    <!-- DOMINANT SIGNAL -->
    <div class="dominant">
      <div class="signal-label">COMBO {s['dominant_signal']} &mdash; {s['dominant_label']}</div>
      <div>{s['dominant_duration']}</div>
      <div style="margin-top:6px"><b>POSTURE:</b> {s['brave_fearful']}</div>
      <div style="margin-top:4px;opacity:.9">{s['dominant_reason']}</div>
    </div>

    <!-- COMBO STATUS -->
    <div class="section-head">Combo Status</div>
    <table>
      <tr>
        <th>Combo</th><th>Status</th><th>Duration</th><th>Direction</th><th>Hit Rate</th><th>Avg SPX Return</th>
      </tr>
      {combo_html}
    </table>

    <!-- REGIME GRID -->
    <div class="section-head">Current Regime State</div>
    {regime_html}

    <!-- NARRATIVE -->
    <div class="section-head">Macro Intelligence Briefing — {s['date']}</div>
    <div class="narrative"><p>{narrative_html}</p></div>

    <!-- VARIABLE DASHBOARD -->
    <div class="section-head">Live Variable Dashboard</div>
    <table>
      <tr>
        <th>#</th><th>Variable</th><th>Current</th><th>Tier</th><th>3yr Pctile</th><th>Signal</th><th>Combos</th>
      </tr>
      {var_html}
    </table>

    <!-- RECOMMENDATION -->
    <div class="rec">
      <div class="rec-label">System Recommendation</div>
      {s['system_recommendation']}
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">{s['footer']}</div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  PDF renderer
# ─────────────────────────────────────────────────────────────────────────────

def _rl_color(hex_str: str):
    from reportlab.lib.colors import HexColor
    return HexColor(hex_str)


def _pdf_escape(text: Any) -> str:
    return escape(str(text))


def _pdf_duration_html(duration: str) -> str:
    """Break long duration strings across lines in PDF cells."""
    if not duration or duration == "—":
        return "—"
    return _pdf_escape(duration).replace(" · ", "<br/>")


def _combo_table_col_widths(total_width: float) -> list[float]:
    """Column widths for combo status table — must sum to total_width."""
    fracs = (0.18, 0.12, 0.31, 0.10, 0.145, 0.145)
    return [total_width * f for f in fracs]


def _combo_row_on_color(status: str) -> bool:
    return status in (
        "ACTIVE",
        "PARTIAL",
        "CONFIRMED",
        "CONFIRMED_3_OF_3",
        "CANCELLED",
        "WATCH",
    )


def render_pdf(payload: dict[str, Any], pdf_path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    c_navy       = _rl_color(_NAVY)
    c_navy_light = _rl_color(_NAVY_LIGHT)
    c_white      = colors.white
    c_green      = _rl_color(_GREEN_BG)
    c_amber      = _rl_color(_AMBER_BG)
    c_high       = _rl_color(_HIGH_BG)
    c_inactive   = _rl_color(_INACTIVE_BG)
    c_border     = _rl_color(_BORDER)
    c_subtle     = _rl_color(_SUBTLE)

    s = build_briefing_sections(payload)
    styles = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    style_title = ps("PTitle", fontSize=15, textColor=c_white, fontName="Helvetica-Bold",
                     spaceAfter=2, leading=18)
    style_subtitle = ps("PSub", fontSize=8, textColor=c_white, spaceAfter=0, leading=10,
                        fontName="Helvetica")
    style_h2 = ps("PH2", fontSize=9, textColor=c_white, fontName="Helvetica-Bold",
                  spaceAfter=2, leading=11)
    style_body = ps("PBody", fontSize=9, textColor=_rl_color(_BODY_TEXT),
                    leading=13, spaceAfter=5)
    style_narrative = ps("PNarr", fontSize=9.5, textColor=_rl_color(_BODY_TEXT),
                         leading=14, spaceAfter=6, alignment=4)  # 4=JUSTIFY
    style_small = ps("PSmall", fontSize=7.5, textColor=c_subtle, leading=9, alignment=1)
    style_rec = ps("PRec", fontSize=9, textColor=c_white, fontName="Helvetica-Bold",
                   leading=13, spaceAfter=0)
    style_dom = ps("PDom", fontSize=9, textColor=c_white, leading=13, spaceAfter=0)
    style_combo_hdr = ps(
        "PComboHdr",
        fontSize=7.5,
        textColor=c_white,
        fontName="Helvetica-Bold",
        leading=9,
        spaceAfter=0,
    )
    style_combo_cell = ps(
        "PComboCell",
        fontSize=7,
        textColor=_rl_color(_BODY_TEXT),
        leading=10,
        spaceAfter=0,
        wordWrap="CJK",
    )
    style_combo_cell_w = ps(
        "PComboCellW",
        fontSize=7,
        textColor=c_white,
        leading=10,
        spaceAfter=0,
        wordWrap="CJK",
    )

    def combo_para(text: str, *, on_color: bool = False, bold: bool = False, nowrap: bool = False) -> Any:
        style = style_combo_cell_w if on_color else style_combo_cell
        body = _pdf_escape(text)
        if bold:
            body = f"<b>{body}</b>"
        if nowrap:
            body = f"<nobr>{body}</nobr>"
        return Paragraph(body, style)

    W = letter[0] - 1.1 * inch
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )

    story: list[Any] = []

    # ── Navy header band ──────────────────────────────────────────────────────
    header_data = [
        [Paragraph(s["title"], style_title)],
        [        Paragraph(
            f"{s['date']}  |  {s['subtitle']}  |  Internal use only",
            style_subtitle,
        )],
    ]
    header_tbl = Table(header_data, colWidths=[W])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_navy),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 6))

    # ── Dominant signal band ──────────────────────────────────────────────────
    dom_text = (
        f"<b>COMBO {s['dominant_signal']} — {s['dominant_label']}</b>  ·  "
        f"{s['dominant_duration']}<br/>"
        f"<b>POSTURE:</b> {s['brave_fearful']}<br/>"
        f"{s['dominant_reason']}"
    )
    dom_data = [[Paragraph(dom_text, style_dom)]]
    dom_tbl = Table(dom_data, colWidths=[W])
    dom_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), c_navy),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    story.append(dom_tbl)
    story.append(Spacer(1, 8))

    # ── Combo Status ──────────────────────────────────────────────────────────
    story.append(_section_header("COMBO STATUS", W, c_navy_light, style_h2))
    combo_header = ["Combo", "Status", "Duration", "Direction", "Hit Rate", "Avg Return"]
    combo_data = [[Paragraph(f"<b>{_pdf_escape(h)}</b>", style_combo_hdr) for h in combo_header]]
    combo_row_colors: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), c_navy_light),
    ]
    combo_col_widths = _combo_table_col_widths(W)
    for i, r in enumerate(s["combo_rows"], start=1):
        on_color = _combo_row_on_color(r["status"])
        combo_data.append(
            [
                combo_para(f"{r['combo']} — {r['name']}", on_color=on_color, bold=True),
                combo_para(r["status"], on_color=on_color, bold=True, nowrap=True),
                Paragraph(_pdf_duration_html(r["duration"]), style_combo_cell_w if on_color else style_combo_cell),
                combo_para(r["direction"], on_color=on_color, nowrap=True),
                combo_para(r["hit_rate_3m"], on_color=on_color, nowrap=True),
                combo_para(r["avg_return_3m"], on_color=on_color, nowrap=True),
            ]
        )
        if r["status"] in ("ACTIVE", "PARTIAL", "CONFIRMED", "CONFIRMED_3_OF_3"):
            combo_row_colors += [
                ("BACKGROUND", (0, i), (-1, i), c_green),
            ]
        elif r["status"] == "CANCELLED":
            combo_row_colors += [
                ("BACKGROUND", (0, i), (-1, i), _rl_color("#4A3728")),
            ]
        elif r["status"] == "WATCH":
            combo_row_colors += [
                ("BACKGROUND", (0, i), (-1, i), c_amber),
            ]
        else:
            combo_row_colors += [
                ("BACKGROUND", (0, i), (-1, i), c_inactive),
            ]

    combo_tbl = Table(
        combo_data,
        colWidths=combo_col_widths,
        repeatRows=1,
    )
    base_ts = [
        ("GRID",      (0, 0), (-1, -1), 0.4, c_border),
        ("VALIGN",    (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]
    combo_tbl.setStyle(TableStyle(combo_row_colors + base_ts))
    story.append(combo_tbl)
    story.append(Spacer(1, 8))

    # ── Regime Grid (3 columns) ───────────────────────────────────────────────
    story.append(_section_header("CURRENT REGIME STATE", W, c_navy_light, style_h2))
    grid_items = s["regime_grid"]
    regime_rows_data: list[list] = []
    cur_row: list = []
    cell_w = W / 3
    for i, (lbl, val) in enumerate(grid_items):
        cell_para = Paragraph(f"<font size='7'>{lbl.upper()}</font><br/><b><font size='10'>{val}</font></b>",
                              style_body)
        cur_row.append(cell_para)
        if len(cur_row) == 3:
            regime_rows_data.append(cur_row)
            cur_row = []
    if cur_row:
        while len(cur_row) < 3:
            cur_row.append(Paragraph("", style_body))
        regime_rows_data.append(cur_row)

    regime_tbl = Table(regime_rows_data, colWidths=[cell_w, cell_w, cell_w])
    regime_tbl.setStyle(TableStyle([
        ("GRID",          (0, 0), (-1, -1), 0.4, c_border),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("BACKGROUND",    (0, 0), (-1, -1), _rl_color(_INACTIVE_BG)),
    ]))
    story.append(regime_tbl)
    story.append(Spacer(1, 8))

    # ── Narrative ─────────────────────────────────────────────────────────────
    story.append(_section_header("MACRO INTELLIGENCE BRIEFING", W, c_navy_light, style_h2))
    narrative = s["narrative"] or "Narrative pending."
    for para in narrative.split("\n\n"):
        text = para.replace("\n", " ").strip()
        if text:
            story.append(Paragraph(text, style_narrative))
    story.append(Spacer(1, 6))

    # ── Page break → Variable Dashboard ──────────────────────────────────────
    story.append(PageBreak())
    story.append(_section_header("LIVE VARIABLE DASHBOARD", W, c_navy_light, style_h2))

    var_header = ["#", "Variable", "Current", "Tier", "3yr Pctile", "Signal", "Combos"]
    var_data = [var_header]
    var_row_colors: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), c_navy_light),
        ("TEXTCOLOR",  (0, 0), (-1, 0), c_white),
    ]
    for i, r in enumerate(s["variable_rows"], start=1):
        tier = str(r["tier"]).upper()
        var_data.append([
            str(r["num"]),
            r["variable"],
            r["current"],
            r["tier"],
            r["pctile_3yr"],
            str(r["direction"]),
            r["combos"],
        ])
        if tier == "EXTREME":
            var_row_colors += [
                ("BACKGROUND", (0, i), (-1, i), c_amber),
                ("TEXTCOLOR",  (0, i), (-1, i), c_white),
            ]
        elif tier == "HIGH":
            var_row_colors += [
                ("BACKGROUND", (0, i), (-1, i), c_high),
                ("TEXTCOLOR",  (0, i), (-1, i), _rl_color(_HIGH_TEXT)),
            ]

    var_tbl = Table(
        var_data,
        colWidths=[0.28*inch, 0.65*inch, 0.72*inch, 0.68*inch, 0.6*inch, 0.65*inch, 0.65*inch],
        repeatRows=1,
    )
    var_tbl.setStyle(TableStyle(var_row_colors + [
        ("FONTNAME",  (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",  (0, 0), (-1, -1), 7.5),
        ("GRID",      (0, 0), (-1, -1), 0.4, c_border),
        ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
    ]))
    story.append(var_tbl)
    story.append(Spacer(1, 12))

    # ── System Recommendation (navy box) ────────────────────────────────────
    rec_data = [
        [Paragraph("SYSTEM RECOMMENDATION", ps("PRecLbl", fontSize=7, textColor=c_white,
                                                fontName="Helvetica-Bold", leading=9, spaceAfter=0))],
        [Paragraph(s["system_recommendation"], style_rec)],
    ]
    rec_tbl = Table(rec_data, colWidths=[W])
    rec_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), c_navy),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    story.append(rec_tbl)
    story.append(Spacer(1, 18))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Paragraph(s["footer"], style_small))

    doc.build(story)


def _section_header(text: str, width: float, bg_color: Any, style: Any) -> Any:
    from reportlab.platypus import Paragraph, Table, TableStyle
    tbl = Table([[Paragraph(text, style)]], colWidths=[width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg_color),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    return tbl


def write_briefing(payload: dict[str, Any], out_dir: Path | None = None) -> dict[str, Path]:
    cfg = load_config().get("briefing", {})
    base = out_dir or Path(cfg.get("output_dir", "macro_intelligence/output"))
    base.mkdir(parents=True, exist_ok=True)
    date = payload.get("date", datetime.now().strftime("%Y-%m-%d"))
    paths: dict[str, Path] = {}

    html = render_html(payload)
    html_path = base / f"runic_briefing_{date}.html"
    html_path.write_text(html, encoding="utf-8")
    paths["html"] = html_path

    formats = cfg.get("formats", ["html"])
    if "pdf" in formats:
        try:
            pdf_path = base / f"runic_briefing_{date}.pdf"
            render_pdf(payload, pdf_path)
            paths["pdf"] = pdf_path
        except ImportError as exc:
            logger.error("reportlab required for PDF briefing but not installed: %s", exc)
            raise RuntimeError(
                "PDF briefing requested in CONFIG briefing.formats but reportlab is not installed. "
                "Run: .venv/bin/pip install reportlab"
            ) from exc

    return paths
