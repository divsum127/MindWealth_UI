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
No hedging language. No disclaimers. Cite specific numbers at every opportunity.
Do NOT use subjective adjectives (e.g. commanding, dismal, spectacular). State hit rates as neutral facts.
Use numeric horizon labels: 3m, 6m, 12m, 5d — never spell out "three-month".

VARIABLE SIGNIFICANCE GUIDE — use these definitions when interpreting variable levels:
- NFCI: Chicago Fed weekly financial conditions index. Negative = easy/loose (bullish). Positive = tight/stressed. -0.3 to +0.3 is normal. Below -0.5 = meaningfully accommodative. Above +0.8 = crisis territory.
- HY: High-yield credit spread (OAS in %). Below 3.0% (300bps) = credit benign/tight. 4.0%+ = stress building. 5.0%+ = major credit event. Tightening = risk-on; widening = risk-off.
- WALCL: Fed balance sheet MoM % change. Positive = QE/expanding (bullish). Negative = QT/shrinking (bearish). Near-zero = neutral.
- CNH: USD/CNH 4wk % change. Positive = yuan weakening / China stress. Negative = yuan strengthening / risk-on EM.
- WTI: Oil 4wk % change. Spike above +10% = Combo C stagflation risk. Below -10% = disinflationary, potential Fed-easing tailwind.
- VIX: Fear gauge. Below 15 = suppressed/complacent. 20-25 = normal concern. 25+ = Combo B territory. 35+ = capitulation/buy-zone.
- VXTS: VIX term structure ratio (VIX3M/VIX). Above 1.10 = complacency/contango (Combo D watch). Below 1.0 = backwardation/near-term stress (Combo G territory). Normal = 1.05-1.15.
- CFTC: Hedge fund (Fast Money) net position 3yr rolling percentile. Below 15th = extreme short / contrarian buy territory. Above 85th = crowded long / fragile. Current level feeds Combos B, D, E, F directly.
- CURVE: 10Y-2Y yield spread in bps. Positive = normal. Negative = inverted (recession signal). Rapid steepening from inversion = recovery signal.
- CPI: Surprise vs consensus in pp. Above +0.2pp = hot surprise (Combo C fire leg). Near zero = neutral. Below -0.2pp = miss (disinflationary).
- GSR: Gold/Silver ratio 4wk % change. Rising = risk-off hedging / fear. Falling = risk-on / industrial demand.
- CAPE: Shiller P/E. Below 20 = cheap. 25-28 = fair/elevated. Above 28 = expensive (Combo E leg). Above 35 = historically extreme. Above 40 = near all-time-high territory.

COMBO SIGNIFICANCE GUIDE:
- Combo A (Liquidity): 2+ of NFCI/HY/WALCL/CNH at RARE+. Multi-variable macro stress or ease.
- Combo B (Capitulation): VIX≥25 + HY≥400bps + CFTC≤15th ALL three. Rare blood-in-streets buy signal. VIX bypass active when confirmed.
- Combo C (Stagflation/Energy Shock): WTI≥+10% + hot CPI + flat WALCL. Fed hands tied by inflation. CANCELLED means 4-Friday oil+CPI clear met.
- Combo D (FOMO Top): VXTS≥1.10 + CFTC≥85th + VIX<18. Complacency extreme — crowded longs in calm market. Tactical bearish.
- Combo E (Valuation Extreme): 2 of 3 — CAPE≥28 + NFCI easy + CFTC≥80th. Structural slow-burn bear. 12m horizon, not 3m.
- Combo F (Recovery): SPX ≥3% above 50WMA + CFTC≤50th. Momentum with positioning room. 6m primary, 26-week lifecycle.
- Combo G (Hidden Stress): VXTS<1.0 + HY 4wk widening≥30bps + VIX≤20. Credit leading equity fear. Timing warning — no return hit rate. Testable from 2007 only.

Mandatory structure — five sections, in this order:

SECTION 1 — DOMINANT SIGNAL
Name the dominant combo (letter + full name), its current duration and bucket (SHORT/MEDIUM/LONG), the episode start date, how many weeks remain in the active window, and the current SPX vs 50WMA level (for Combo F) or the key driving variable. State its validated hit rate at its primary horizon. In two sentences explain why this combo outweighs ALL competing signals this week — cite specific variable values and the priority rank.

SECTION 2 — ALL COMBOS FULL STATUS
Cover ALL 7 named combos (A through G) — active, watch, cancelled, and inactive. For each: its status, which legs are met and which are not (with exact variable values vs thresholds), the directional implication, and the validated hit rate at its proper horizon. For WATCH combos state how many legs are met and what is needed to fire. For CANCELLED combos state the cancel date and the reason. For INACTIVE combos state the key missing leg. Do NOT skip any combo. Combo G: state current VXTS/HY/VIX levels vs thresholds, confirm INACTIVE, note it is a timing warning with no return hit rate. Minimum 2 sentences per combo.

SECTION 3 — WHAT THE VARIABLES ARE TELLING US
Walk through the most significant variables in the dashboard — specifically those at EXTREME or RARE tier — and explain what each signal means in the current macro context. Connect each EXTREME variable explicitly to the combos it affects and to real-world conditions (Fed policy, energy, credit, positioning). Then give three numbered reasons (1) (2) (3) why the dominant signal wins over competing signals, using specific variable levels, regime labels, and historical precedent.

SECTION 4 — HISTORICAL ANALOGS
Provide 2–3 historical analogs with exact dates, the macro conditions at that date that matched today, and the realized SPX forward returns at 3m, 6m, and 12m. If analog forward returns are 0.0% or unavailable, use broader macro database knowledge to provide real historical comparisons — do not report zero returns. State which analog is closest and why.

SECTION 5 — POSTURE AND WHAT WOULD CHANGE IT
State the system posture. Give explicit numbered conditions that would flip the posture — for each: name the variable, the threshold, the duration requirement, and which combo it would affect. Also state what would STRENGTHEN the current posture (confirm a second bullish combo or additional variable moves in the right direction).

Total length: 600–750 words. Use plain paragraphs. No bullet points. No markdown headers. No em dashes."""


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
    all_combo_rows = payload.get("combo_status_rows") or []

    # Build a rich per-combo block covering ALL 7 (A–G)
    combo_descriptions = []
    for row in all_combo_rows:
        letter = row.get("combo", "?")
        label = combo_labels.get(letter, letter)
        status = row.get("status", "INACTIVE")
        duration = row.get("duration", "—")
        direction = row.get("direction", "—")
        hit = row.get("hit_rate_3m", "—")
        avg = row.get("avg_return_3m", "—")
        entry: dict = {
            "combo": f"{letter} — {label}",
            "status": status,
            "duration": duration,
            "direction": direction,
            "hit_rate": hit,
            "avg_return": avg,
        }
        # Merge in richer stats for active combos
        for c in active_combos:
            if c.get("combo") == letter:
                entry["duration_weeks"] = c.get("duration_weeks")
                entry["duration_bucket"] = c.get("duration_bucket")
                entry["episode_start"] = c.get("episode_start")
                entry["confirmed_legs"] = c.get("confirmed_legs")
                if c.get("hit_rate_primary") is not None:
                    entry["primary_hit_rate"] = (
                        f"{c['hit_rate_primary'] * 100:.1f}% ({c.get('primary_label', '')})"
                    )
                if c.get("avg_return_primary") is not None:
                    entry["primary_avg_return"] = (
                        f"{c['avg_return_primary']:+.2f}% ({c.get('primary_label', '')})"
                    )
                if c.get("n_obs_primary") is not None:
                    entry["n_obs"] = c["n_obs_primary"]
                break
        combo_descriptions.append(entry)

    # Build variable summary with significance flags
    var_summary = []
    extreme_vars = []
    rare_vars = []
    for v in vars_block:
        tier = v.get("tier", "NORMAL")
        entry = {
            "variable": v.get("variable"),
            "current": v.get("current"),
            "tier": tier,
            "pctile_3yr": v.get("pctile_3yr"),
            "direction": v.get("direction"),
        }
        if v.get("source_date"):
            entry["source_date"] = v["source_date"]
            entry["lag_days"] = v.get("lag_days")
        var_summary.append(entry)
        if tier == "EXTREME":
            extreme_vars.append(v.get("variable"))
        elif tier == "RARE":
            rare_vars.append(v.get("variable"))

    # CFTC RM percentile context if present
    cftc_row = next((v for v in vars_block if v.get("variable") == "CFTC"), {})
    cftc_rm = cftc_row.get("cftc_rm_pctile")
    cftc_note = ""
    if cftc_rm is not None:
        cftc_note = (
            f"CFTC FM (Lev Money) net at {cftc_row.get('current', '?'):,.0f} contracts, "
            f"FM pctile {cftc_row.get('pctile_3yr', '?'):.1f}th, "
            f"Asset Manager (RM) pctile {cftc_rm:.1f}th (divergence: FM extreme short, RM may differ)."
        )

    _hr_val = payload.get("spx_3m_hit_rate")
    _ret_val = payload.get("spx_3m_forward_avg")
    _hr_str = f"{_hr_val * 100:.1f}%" if _hr_val is not None else "n/a"
    _ret_str = f"{_ret_val:+.2f}%" if _ret_val is not None else "n/a"

    user = (
        f"Report date: {payload.get('date')}.\n"
        f"System posture: {payload.get('brave_fearful_display') or payload.get('brave_fearful')}.\n"
        f"Dominant signal: Combo {dominant} ({dom_label}). "
        f"Dominant reason: {payload.get('dominant_reason')}\n"
        f"Dominant combo — primary hit rate: {_hr_str}, avg SPX return: {_ret_str}.\n\n"
        f"VARIABLES CURRENTLY AT EXTREME TIER: {', '.join(extreme_vars) if extreme_vars else 'none'}.\n"
        f"VARIABLES CURRENTLY AT RARE TIER: {', '.join(rare_vars) if rare_vars else 'none'}.\n"
        f"{cftc_note}\n\n"
        f"ALL 7 NAMED COMBOS (A–G) — FULL STATUS:\n{json.dumps(combo_descriptions, indent=2)}\n\n"
        f"REGIME (5 dimensions):\n{json.dumps(payload.get('regime', {}), indent=2)}\n\n"
        f"12-VARIABLE DASHBOARD (with percentiles and tiers):\n{json.dumps(var_summary, indent=2)}\n\n"
        f"COMBO C CANCEL DETAIL: {json.dumps(payload.get('combo_c_cancel', {}))}\n"
        f"PENDING CPI RELEASE THIS WEEK: {payload.get('pending_cpi_release', False)}\n"
        f"PRE-CATALYST FRAGILITY: {json.dumps(payload.get('pre_catalyst', {}))}\n"
        f"POST-EVENT REGIME: {json.dumps(payload.get('post_event_regime', {}))}\n"
        f"SSI LAYER2 STATUS: {payload.get('ssi_layer2_status')} | SSI MULTIPLIER: {payload.get('ssi_multiplier')}\n"
        f"VIX BYPASS ACTIVE: {payload.get('vix_bypass', False)}\n\n"
        f"HISTORICAL ANALOGS (date + realized SPX forward returns):\n"
        f"{json.dumps(payload.get('analog_details', payload.get('analog_dates', [])), indent=2)}\n\n"
        f"CURRENT MACRO NEWS (Tavily — use where relevant to explain variable moves):\n"
        f"{macro_headlines or 'No headlines available.'}\n\n"
        "Write the nightly briefing now following the five-section structure."
    )

    try:
        return call_claude(SYSTEM, user, max_tokens=max_tokens)
    except Exception:
        return _template_briefing(payload)


def _template_briefing(payload: dict[str, Any]) -> str:
    """Fallback when Claude is unavailable — analytical narrative prose (~200 words)."""
    cfg = load_config().get("briefing", {})
    combo_labels = cfg.get("combo_labels", {})
    dom = payload.get("dominant_signal", "N/A")
    dom_label = combo_labels.get(str(dom), "")
    brave = (payload.get("brave_fearful_display") or payload.get("brave_fearful") or "NEUTRAL").replace("_", " ")

    active_combos = payload.get("active_combos", [])
    all_combo_rows = payload.get("combo_status_rows") or []
    vars_block = payload.get("variables_dashboard") or []
    regime = payload.get("regime", {})

    dom_combo = next((c for c in active_combos if c.get("combo") == dom), {})
    wk = dom_combo.get("duration_weeks") or 0
    ep = dom_combo.get("episode_start") or ""
    hr_primary = dom_combo.get("hit_rate_primary")
    avg_primary = dom_combo.get("avg_return_primary")
    primary_label = dom_combo.get("primary_label", "6M")
    hr_txt = f"{hr_primary * 100:.0f}% {primary_label}" if hr_primary is not None else "—"
    avg_txt = f"{avg_primary:+.1f}% avg" if avg_primary is not None else ""
    remaining = 26 - wk if wk else None
    ep_txt = f" (started {ep})" if ep else ""

    # Variable lookup helpers
    def _var(vid: str) -> dict:
        return next((v for v in vars_block if v.get("variable") == vid), {})

    def _val(vid: str) -> float | None:
        return _var(vid).get("current")

    def _pct(vid: str) -> float | None:
        return _var(vid).get("pctile_3yr")

    def _tier(vid: str) -> str:
        return (_var(vid).get("tier") or "NORMAL").upper()

    # --- Paragraph 1: Dominant signal analysis ---
    rem_txt = f", {remaining} weeks remaining in active window" if remaining else ""
    p1 = (
        f"Combo {dom} ({dom_label}) is the dominant signal, active for week {wk} of 26{ep_txt}{rem_txt}. "
        f"Its validated {primary_label} hit rate is {hr_txt} ({avg_txt}), making it the highest-confidence "
        f"signal in the current stack. "
    )

    # Combo F specific: explain CFTC fuel
    cftc_pct = _pct("CFTC")
    cftc_val = _val("CFTC")
    if dom == "F" and cftc_pct is not None:
        if cftc_pct <= 20:
            p1 += (
                f"Hedge fund positioning (CFTC Fast Money net {cftc_val:,.0f} contracts, {cftc_pct:.0f}th percentile) "
                f"remains extremely short, providing structural fuel for the recovery — the covering rally has not yet run "
                f"its full course. "
            )
        elif cftc_pct <= 50:
            p1 += (
                f"Hedge fund positioning at the {cftc_pct:.0f}th percentile means Fast Money has not yet fully rotated "
                f"long, sustaining the buying capacity that underpins Combo F momentum. "
            )

    # Regime tailwind or headwind
    fed = regime.get("fed_cycle", "")
    curve = regime.get("curve_regime", "")
    if "CUT" in fed.upper() or "EASY" in str(regime.get("liquidity", "")).upper():
        p1 += f"The macro backdrop — {fed} Fed cycle with {curve.lower()} yield curve and {regime.get('liquidity', '?')} global liquidity — is broadly supportive of the dominant bullish signal. "
    elif "PAUSE" in fed.upper():
        p1 += f"The Fed is paused and the yield curve is {curve.lower()}, a neutral regime that neither amplifies nor undermines the recovery signal. "

    # --- Paragraph 2: Key variable signals ---
    wti_val = _val("WTI")
    wti_pct = _pct("WTI")
    cape_val = _val("CAPE")
    cape_pct = _pct("CAPE")
    vxts_val = _val("VXTS")
    vix_val = _val("VIX")
    hy_val = _val("HY")
    hy_pct = _pct("HY")

    var_lines = []

    if wti_val is not None and _tier("WTI") in ("EXTREME", "RARE"):
        if wti_val < -10:
            var_lines.append(
                f"WTI crude has collapsed {wti_val:.1f}% in 4 weeks ({wti_pct:.0f}th percentile) — "
                f"the sharpest oil drop in years — removing the stagflation pressure that previously activated Combo C. "
                f"This disinflationary impulse reduces the CPI risk leg and gives the Fed room to ease further."
            )
        elif wti_val > 10:
            var_lines.append(
                f"WTI has spiked {wti_val:+.1f}% in 4 weeks ({wti_pct:.0f}th percentile), "
                f"keeping the Combo C inflation risk leg active and constraining the Fed's ability to cut rates."
            )

    if cape_val is not None and _tier("CAPE") in ("EXTREME", "RARE"):
        e_row = next((r for r in all_combo_rows if r.get("combo") == "E"), {})
        e_status = e_row.get("status", "INACTIVE")
        e_hr = e_row.get("hit_rate_3m", "")
        # Extract confirmed legs from duration string like "— · legs CAPE, NFCI"
        e_dur = e_row.get("duration", "")
        e_legs = ""
        if "legs" in e_dur:
            e_legs = e_dur.split("legs")[-1].strip().strip("·").strip()
        legs_txt = f" (legs: {e_legs})" if e_legs else ""
        var_lines.append(
            f"CAPE at {cape_val:.1f}x ({cape_pct:.0f}th percentile) has confirmed Combo E "
            f"(Valuation Extreme, {e_status}{legs_txt}, {e_hr}). "
            f"However, Combo E operates on a 12m horizon — a slow structural headwind, not a near-term catalyst. "
            f"It does not override Combo F's momentum at week {wk}."
        )

    if vxts_val is not None and _tier("VXTS") == "RARE":
        var_lines.append(
            f"VXTS (VIX term structure) at {vxts_val:.2f} flags mild complacency — near-term options are unusually "
            f"cheap relative to the 3-month outlook. This keeps Combo D (FOMO Top) partially elevated but CFTC "
            f"positioning at {cftc_pct:.0f}th percentile is far too short to confirm the crowding leg, so Combo D remains on WATCH only."
        )

    if hy_val is not None and _tier("HY") in ("EXTREME", "RARE"):
        if hy_val > 4.5:
            var_lines.append(
                f"HY credit spreads at {hy_val:.2f}% ({hy_pct:.0f}th percentile) are at stress levels — "
                f"a potential precursor for Combo G (Hidden Stress) if VXTS drops into backwardation."
            )
        elif hy_val < 3.0:
            var_lines.append(
                f"HY spreads at {hy_val:.2f}% remain tight, confirming credit is not stressed and removing any imminent Combo G or Combo A risk."
            )

    p2 = " ".join(var_lines) if var_lines else ""

    # --- Paragraph 3: Competing combos summary ---
    non_dom_active = [r for r in all_combo_rows if r.get("status") not in ("INACTIVE",) and r.get("combo") != dom]
    comp_lines = []
    for row in non_dom_active:
        letter = row.get("combo", "?")
        lbl = combo_labels.get(letter, letter)
        status = row.get("status", "")
        hr = row.get("hit_rate_3m", "")
        dur = row.get("duration", "")
        direction = row.get("direction", "").lower()
        if status == "WATCH":
            comp_lines.append(f"Combo {letter} ({lbl}) is on WATCH ({direction}); not yet firing.")
        elif status in ("CONFIRMED", "CONFIRMED_3_OF_3"):
            comp_lines.append(f"Combo {letter} ({lbl}) is CONFIRMED ({direction}, {hr}).")
        elif status == "CANCELLED":
            comp_lines.append(f"Combo {letter} ({lbl}) has been CANCELLED.")
        elif status in ("ACTIVE", "PARTIAL"):
            comp_lines.append(f"Combo {letter} ({lbl}) is {status} — {dur} — {direction}, {hr}.")
    p3 = "Competing signals: " + " ".join(comp_lines) if comp_lines else ""

    # --- Paragraph 4: Posture and conditions to watch ---
    cpi_flag = "A CPI release is pending this week — a hot surprise above +0.2pp would re-activate the Combo C inflation leg and shift posture. " if payload.get("pending_cpi_release") else ""
    ssi_txt = ""
    ssi = payload.get("ssi_layer2_status")
    if ssi == "CONFIRMED":
        ssi_txt = "SSI Layer 2 is CONFIRMED, applying a 1.20x multiplier to position sizing. "
    elif ssi:
        ssi_txt = f"SSI Layer 2 status: {ssi}. "

    f_expiry = ""
    if dom == "F" and remaining is not None and remaining <= 8:
        f_expiry = f"Combo F expires at week 26 — only {remaining} weeks remain; re-evaluate posture as the window closes. "

    p4 = f"System posture: {brave}. {cpi_flag}{ssi_txt}{f_expiry}".strip()

    parts = [p for p in [p1, p2, p3, p4] if p]
    return "\n\n".join(parts)
