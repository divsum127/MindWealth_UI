"""AI Analyst panel alert orchestration."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from api.services import analyst_copy_service as copy_svc
from api.services import degradation_service as degrade_svc
from api.services import macro_service as macro_svc
from api.services import meta_service as meta_svc
from api.services import reports_service as reports_svc
from api.services import overwatch_schedule as schedule_svc
from api.services import system_health_service as health_svc
from api.services.macro_override import compute_macro_override
from api.services.meta_service import market_close_data_updated_at, resolve_report_date

PanelChannel = Literal["signals", "macro", "system"]
PanelTabId = Literal["all", "signals", "macro", "system"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


_SENTENCE_END = re.compile(r"(?<!\d)\.(?!\d)\s")


def _first_sentence(text: str, max_len: int = 220) -> str:
    """First sentence, without breaking inside a decimal.

    Splitting on a bare "." truncated "78.4% hit rate" to "78." — the number was
    read as the end of the sentence.
    """
    text = text.strip()
    if not text:
        return ""
    match = _SENTENCE_END.search(text)
    snippet = text[: match.start() + 1] if match else text
    if len(snippet) > max_len:
        snippet = snippet[:max_len].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"
    return snippet.strip()


def _channel_for_type(alert_type: str) -> PanelChannel:
    if alert_type in {"degradation", "position_risk"}:
        return "signals"
    if alert_type == "system":
        return "system"
    return "macro"


def _with_channel(alert: dict[str, Any]) -> dict[str, Any]:
    alert = dict(alert)
    alert["channel"] = _channel_for_type(str(alert.get("type", "runic")))
    return alert


def _build_historical_analogs(combo_id: str) -> dict[str, Any] | None:
    try:
        from api.services.macro_service import _load_runic, _safe

        nightly = _safe(_load_runic(), "historical_analogs")
        if nightly and str(nightly.get("combo", "")).upper() == combo_id.upper():
            return nightly
    except Exception:
        pass

    try:
        table = macro_svc.get_analog_table(combo_id)
    except Exception:
        return None

    details = table.get("analog_details") or []
    if not details:
        return None

    instances = []
    for row in details[:5]:
        date_raw = str(row.get("date", ""))
        date_fmt = date_raw[:7] if len(date_raw) >= 7 else date_raw
        regime = row.get("regime") or {}
        description = regime.get("label") or regime.get("geo_overlay") or f"Combo {combo_id} fire"
        instances.append({
            "date": date_fmt,
            "description": str(description),
            "spx_3m": row.get("spx_3m_pct"),
        })

    returns_3m = [r.get("spx_3m_pct") for r in details if r.get("spx_3m_pct") is not None]
    summary: dict[str, Any] = {}
    if returns_3m:
        sorted_r = sorted(returns_3m)
        summary = {
            "median_3m": round(sorted_r[len(sorted_r) // 2], 2),
            "worst": round(min(returns_3m), 2),
            "best": round(max(returns_3m), 2),
            "hit_rate": round(
                sum(1 for v in returns_3m if v < 0) / len(returns_3m), 2
            ),
        }
    hr = table.get("hit_rate_stats") or {}
    if hr.get("hit_rate_primary") is not None:
        summary["hit_rate"] = hr["hit_rate_primary"]

    return {"combo": combo_id, "instances": instances, "summary": summary}


def _degradation_to_panel_alert(raw: dict[str, Any], floor_pct: float) -> dict[str, Any]:
    """Forward win-rate drift only.

    Portfolio position triggers (booked loss / live MTM breach) are a different
    kind of event and go through ``_portfolio_to_panel_alert``. They used to be
    funnelled through here, which meant ``profit_pct`` — a mark-to-market
    percentage — was coalesced into ``fwd_rate`` and rendered as a win rate, so
    a position down 23.7% displayed as "FWD WR -23.7%, below the 60% floor".
    """
    combo = raw.get("combo") or {}
    function = combo.get("function") or raw.get("function") or raw.get("strategy", "")
    interval = combo.get("interval") or raw.get("interval", "")
    direction = combo.get("direction") or raw.get("direction", "Long")
    asset = combo.get("asset") or raw.get("symbol", "")
    fwd_rate = float(raw.get("fwd_rate") or 0)
    bt_rate = float(raw.get("bt_rate") or 0)
    gap = round(fwd_rate - bt_rate, 1) if bt_rate else 0.0
    fwd_trend = raw.get("weekly_trend") or raw.get("fwd_trend") or []

    alert_id = _slug(f"deg-{function}-{direction}-{interval}-{asset}")
    severity = raw.get("severity", "breach")
    label = raw.get("label") or (
        "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DRIFT ALERT WATCH"
        if severity == "watch"
        else "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DRIFT ALERT BREACH"
    )

    html = raw.get("message", "")
    if "<br>" not in html and "\n" in html:
        html = html.replace("\n", "<br>")

    html = copy_svc.generate_alert_copy(
        "degradation",
        {
            "function": function,
            "direction": direction,
            "interval": interval,
            "asset": asset,
            "fwd_rate": fwd_rate,
            "severity": severity,
            "pattern": raw.get("pattern"),
        },
        html,
    )

    return {
        "id": alert_id,
        "type": "degradation",
        "channel": "signals",
        "label": label,
        "html": html,
        "recommendation": raw.get("recommendation"),
        "fwd_trend": fwd_trend if fwd_trend else None,
        "created_at": _utc_now_iso(),
        "border_color": raw.get("border_color", "#ff4d6d"),
        "severity": severity,
        "signal": {
            "strategy": function,
            "interval": interval,
            "signal_type": direction,
            "fwd_wr": fwd_rate,
            "backtest_wr": bt_rate,
            "gap": gap,
            "pattern": raw.get("pattern", ""),
            "above_floor": fwd_rate >= floor_pct,
        },
    }


def _portfolio_to_panel_alert(raw: dict[str, Any]) -> dict[str, Any]:
    """Booked-loss / live-MTM alerts on open positions.

    These carry a P&L percentage, not a win rate, so they get their own type and
    their own payload. Nothing here may be written into ``signal``.
    """
    symbol = str(raw.get("symbol", ""))
    function = str(raw.get("function") or raw.get("strategy", ""))
    interval = str(raw.get("interval", ""))
    direction = str(raw.get("direction") or raw.get("side", "Long"))
    trigger_type = str(raw.get("trigger_type", "booked_loss"))
    profit_pct = float(raw.get("profit_pct") or 0)
    severity = str(raw.get("severity", "breach"))

    # degradation_service labels these "DRIFT ALERT BREACH" alongside the real
    # win-rate alerts. They are not drift, so the label is replaced here.
    kind = "BOOKED LOSS" if trigger_type == "booked_loss" else "LIVE MTM BREACH"
    label = f"AI ANALYST \u00b7 OVERWATCH AUTO-TRIGGERED \u00b7 {kind}"

    html = raw.get("message", "")
    if "<br>" not in html and "\n" in html:
        html = html.replace("\n", "<br>")

    # One combo can hold many open positions at once — SFTBY alone had 29 live
    # short breaches on the same function/interval. Without the trade's own
    # dates the ids collide, which breaks list keys and new-alert detection.
    entry_date = str(raw.get("entry_date", "") or "")
    exit_date = str(raw.get("exit_date", "") or "")
    trade_key = f"{entry_date}-{exit_date}" if (entry_date or exit_date) else f"{profit_pct}"

    return {
        "id": _slug(
            f"pos-{trigger_type}-{function}-{direction}-{interval}-{symbol}-{trade_key}"
        ),
        "type": "position_risk",
        "channel": "signals",
        "label": label,
        "html": html,
        "recommendation": raw.get("recommendation"),
        "fwd_trend": None,
        "created_at": _utc_now_iso(),
        "border_color": raw.get("border_color", "#ff4d6d"),
        "severity": severity,
        "position": {
            "symbol": symbol,
            "function": function,
            "interval": interval,
            "direction": direction,
            "side": str(raw.get("side", direction)).lower(),
            "trigger_type": trigger_type,
            "entry_date": entry_date or None,
            "exit_date": exit_date or None,
            "profit_pct": profit_pct,
            "floor_pct": (
                degrade_svc._MTM_LOSS_THRESHOLD if trigger_type == "live_mtm_breach" else None
            ),
        },
    }


def _build_runic_alerts() -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    try:
        status = macro_svc.get_status_bar()
        narrative = macro_svc.get_narrative()
    except Exception:
        return alerts

    dominant = status.get("dominant_signal")
    active_combos = status.get("active_combos") or []
    combo_ids = [dominant] if dominant else []
    for cid in active_combos:
        if cid and cid not in combo_ids:
            combo_ids.append(cid)

    brave = status.get("brave_fearful") or narrative.get("brave_fearful")
    narr_text = narrative.get("narrative") or narrative.get("dominant_reason") or ""

    for combo_id in combo_ids[:3]:
        if not combo_id:
            continue
        reason = narrative.get("dominant_reason", "") if combo_id == dominant else f"Combo {combo_id} active"
        historical = _build_historical_analogs(str(combo_id))
        analog_html = ""
        if historical and historical.get("instances"):
            inst_lines = [
                f"{i['date']}: SPX 3M {i.get('spx_3m', 'n/a')}%"
                for i in historical["instances"][:5]
            ]
            summ = historical.get("summary") or {}
            analog_html = (
                "<br><br><span class=\"analog-finder\">ANALOG FINDER · COMBO "
                f"{combo_id} HISTORICAL MATCHES</span><br>"
                + "<br>".join(inst_lines)
                + f"<br>Median 3M: {summ.get('median_3m', 'n/a')}% · "
                f"Worst: {summ.get('worst', 'n/a')}% · "
                f"Best: {summ.get('best', 'n/a')}% · "
                f"Hit rate: {summ.get('hit_rate', 'n/a')}"
            )

        html_body = narr_text[:400] if narr_text else reason
        if combo_id == dominant:
            html_body = (
                f"Dominant <span class=\"wa\">Combo {combo_id}</span>: {reason}"
            )

        full_html = html_body + analog_html
        full_html = copy_svc.generate_alert_copy(
            "runic",
            {
                "combo": combo_id,
                "reason": reason,
                "narrative": narr_text,
                "brave_fearful": brave,
                "historical_analogs": historical,
            },
            full_html,
        )

        alerts.append({
            "id": f"runic-{_slug(str(combo_id))}",
            "type": "runic",
            "channel": "macro",
            "label": f"AI ANALYST · OVERWATCH AUTO-TRIGGERED · RUNIC SIGNAL · COMBO {combo_id}",
            "html": full_html,
            "footer": "TAVILY ACTIVE · INTERNAL DATA PRIORITY · ONCE PER PAGE VISIT",
            "created_at": _utc_now_iso(),
            "border_color": "#C5A059",
            "macro": {
                "combo": str(combo_id),
                "reason": reason,
                "narrative": narr_text,
                "brave_fearful": brave,
                "variant": "dominant" if combo_id == dominant else "ssi",
                "historical_analogs": historical,
            },
        })

    return alerts


def _normalize_combo_id(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry.strip().upper() or None
    if isinstance(entry, dict):
        raw = entry.get("combo") or entry.get("id")
        return str(raw).strip().upper() if raw else None
    return None


def _build_watch_combo_alerts(
    *,
    status: dict[str, Any],
    narrative: dict[str, Any],
    active_ids: set[str],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    watch = status.get("watch_combos") or []
    for entry in watch:
        combo_id = _normalize_combo_id(entry)
        if not combo_id or combo_id in active_ids:
            continue
        reason = f"Combo {combo_id} on WATCH — legs building toward activation."
        html = (
            f"<span class=\"wa\">Combo {combo_id}</span> is on WATCH. "
            "Review Signals page for leg status."
        )
        alerts.append({
            "id": f"runic-watch-{_slug(combo_id)}",
            "type": "runic_watch",
            "channel": "macro",
            "label": f"AI ANALYST · OVERWATCH AUTO-TRIGGERED · RUNIC WATCH · COMBO {combo_id}",
            "html": html,
            "footer": "TAVILY ACTIVE · INTERNAL DATA PRIORITY · ONCE PER PAGE VISIT",
            "created_at": _utc_now_iso(),
            "border_color": "#C5A059",
            "macro": {
                "combo": combo_id,
                "reason": reason,
                "narrative": narrative.get("narrative"),
                "brave_fearful": status.get("brave_fearful") or narrative.get("brave_fearful"),
                "variant": "watch",
            },
        })
    return alerts


def _build_regime_warning_alerts(runic: dict[str, Any]) -> list[dict[str, Any]]:
    override = compute_macro_override(runic)
    if not override.get("active"):
        return []
    reasons = override.get("reasons") or []
    regime = runic.get("regime") or {}
    html_lines = [
        "The Overwatch agent flagged macro conditions not fully reflected in the VIX ceiling:",
        "",
        *[f"• {r}" for r in reasons],
        "",
        "These do not automatically reduce the equity ceiling — consider reviewing the Stress scenario.",
    ]
    return [{
        "id": "regime-macro-override",
        "type": "regime_warning",
        "channel": "macro",
        "label": "AI ANALYST · OVERWATCH · MACRO OVERRIDE",
        "html": "<br>".join(html_lines),
        "created_at": _utc_now_iso(),
        "border_color": "#C5A059",
        "macro": {
            "combo": runic.get("dominant_signal"),
            "reason": "; ".join(reasons),
            "narrative": runic.get("narrative"),
            "brave_fearful": runic.get("brave_fearful"),
            "variant": "regime_warning",
        },
        "warning": {"reasons": reasons, "regime": regime},
    }]


def _build_persistence_alerts(persistence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for item in persistence:
        if not isinstance(item, dict):
            continue
        name = item.get("signal_name") or item.get("name") or "Persistence"
        var_id = item.get("var_id") or item.get("variable") or ""
        weeks = item.get("weeks_count")
        trigger = item.get("trigger_value")
        html = (
            f"Persistence signal <b>{name}</b>"
            f"{f' ({var_id})' if var_id else ''}"
            f"{f' — {weeks} weeks' if weeks else ''}"
            f"{f', value {trigger}' if trigger is not None else ''}."
        )
        alerts.append({
            "id": f"persistence-{_slug(f'{name}-{var_id}')}",
            "type": "persistence",
            "channel": "macro",
            "label": "AI ANALYST · OVERWATCH · PERSISTENCE SIGNAL",
            "html": html,
            "created_at": _utc_now_iso(),
            "border_color": "#C5A059",
            "macro": {"combo": None, "reason": name, "variant": "persistence"},
            "warning": {"signal_name": str(name), "var_id": str(var_id) if var_id else None},
        })
    return alerts


def _build_coverage_alerts(ssi: dict[str, Any]) -> list[dict[str, Any]]:
    """Raise an Overwatch alert when an SSI layer is below its input-coverage minimum.

    A degraded feed used to be visible only in a log nobody reads. On 2026-08-18 four of Layer
    2's six inputs were missing for most of a day and the site showed a confident
    "UNCONFIRMED / 0.80x size" the whole time. Surfacing it here puts a data outage on the
    same page as the market alerts it would otherwise be mistaken for.
    """
    if ssi.get("coverage_ok", True):
        return []
    unreliable = ssi.get("coverage_unreliable_layers") or {}
    if not unreliable:
        return []
    detail = "<br>".join(
        f"<b>{layer.replace('layer', 'Layer ')}</b>: {reason}"
        for layer, reason in sorted(unreliable.items())
    )
    return [{
        "id": "sentiment-coverage-incomplete",
        "type": "sentiment_warning",
        "channel": "system",
        "label": "AI ANALYST · OVERWATCH · SSI COVERAGE INCOMPLETE",
        "html": (
            "SSI size multiplier held at 1.00× because inputs are missing, "
            "not because the market is neutral.<br>" + detail
        ),
        "created_at": _utc_now_iso(),
        "border_color": "#C5A059",
        "macro": {
            "combo": None,
            "reason": "SSI layer coverage below minimum",
            "variant": "sentiment",
        },
        "warning": {"reasons": sorted(unreliable), "coverage_ok": False},
    }]


def _build_sentiment_warning_alerts(ssi: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = _build_coverage_alerts(ssi)
    cftc = ssi.get("layer3_cftc") or {}
    pattern = cftc.get("positioning_pattern")
    if pattern:
        label = cftc.get("pattern_label") or str(pattern).replace("_", " ").title()
        plain = cftc.get("plain_english") or ""
        fm = cftc.get("fm_pctile")
        rm = cftc.get("rm_pctile")
        pct_note = ""
        if fm is not None and rm is not None:
            pct_note = f"FM {float(fm):.0f}th pct · RM {float(rm):.0f}th pct<br>"
        alerts.append({
            "id": "sentiment-cftc-pattern",
            "type": "sentiment_warning",
            "channel": "macro",
            "label": "AI ANALYST · OVERWATCH · CFTC POSITIONING",
            "html": f"{pct_note}CFTC pattern: {label}<br>{plain}" if plain else f"{pct_note}CFTC pattern: {label}",
            "created_at": _utc_now_iso(),
            "border_color": "#C5A059",
            "macro": {"variant": "sentiment", "reason": f"CFTC {label}"},
            "warning": {"cftc_pattern": pattern},
        })

    if cftc.get("gross_net_divergence_active"):
        gnd_label = cftc.get("gross_net_divergence_label") or "Gross/Net Divergence"
        gnd_plain = cftc.get("gross_net_divergence_plain_english") or "Gross elevated; RM net falling; credit widening"
        alerts.append({
            "id": "sentiment-gross-net-divergence",
            "type": "sentiment_warning",
            "channel": "macro",
            "label": "AI ANALYST · OVERWATCH · GROSS/NET DIVERGENCE",
            "html": f"{gnd_label}<br>{gnd_plain}",
            "created_at": _utc_now_iso(),
            "border_color": "#C5A059",
            "macro": {"variant": "sentiment", "reason": gnd_label},
            "warning": {"gross_net_divergence": True},
        })

    level = ssi.get("ssi_level")
    if level is None:
        return alerts
    posture = ssi.get("posture") or "NEUTRAL"
    long_active = bool(ssi.get("long_signal_active"))
    short_active = bool(ssi.get("short_signal_active"))
    if not long_active and not short_active:
        layer2 = (ssi.get("layer2_status") or "").upper()
        if layer2 not in {"CONFIRMED", "EXTREME"}:
            return alerts

    if short_active:
        headline = f"SSI {level:.2f} — Fear / risk-off zone ({posture})"
        note = "Elevated short-vol / defensive posture per SSI layer rules."
    elif long_active:
        headline = f"SSI {level:.2f} — Complacency / risk-on zone ({posture})"
        note = "Long-vol / complacency signal active per SSI layer rules."
    else:
        headline = f"SSI layer-2 status: {ssi.get('layer2_status')}"
        note = "Layer-2 sentiment confirmation active."

    alerts.append({
        "id": "sentiment-ssi-warning",
        "type": "sentiment_warning",
        "channel": "macro",
        "label": "AI ANALYST · OVERWATCH · SENTIMENT WARNING",
        "html": f"{headline}<br>{note}",
        "created_at": _utc_now_iso(),
        "border_color": "#C5A059",
        "macro": {"variant": "sentiment", "reason": headline},
        "warning": {"ssi_level": level, "ssi_posture": posture},
    })
    return alerts


def _load_runic_safe() -> dict[str, Any]:
    try:
        return reports_svc.load_runic_nightly()
    except Exception:
        return {}


def _signals_badge(drift_count: int, position_count: int) -> str:
    parts = []
    if drift_count:
        parts.append(f"{drift_count} drift watch")
    if position_count:
        parts.append(f"{position_count} position alert{'s' if position_count != 1 else ''}")
    if not parts:
        return "Overwatch · no signal watches"
    return "Overwatch · " + " · ".join(parts)


def _compute_tab_badges(panel_alerts: list[dict[str, Any]], dominant: str | None) -> dict[str, Any]:
    signal_count = sum(1 for a in panel_alerts if a.get("channel") == "signals")
    macro_count = sum(1 for a in panel_alerts if a.get("channel") == "macro")
    system_count = sum(1 for a in panel_alerts if a.get("channel") == "system")
    drift_count = sum(1 for a in panel_alerts if a.get("type") == "degradation")
    position_count = sum(1 for a in panel_alerts if a.get("type") == "position_risk")
    dom = dominant or next(
        (a.get("macro", {}).get("combo") for a in panel_alerts if a.get("type") == "runic"),
        None,
    )
    macro_badge = (
        f"Overwatch · Combo {dom} firing"
        if dom
        else f"Overwatch · {macro_count} macro alert{'s' if macro_count != 1 else ''}"
    )
    return {
        "all": {"count": len(panel_alerts), "badge": "Overwatch · auto-triggered"},
        "signals": {
            "count": signal_count,
            "drift_count": drift_count,
            "position_count": position_count,
            # Drift and position risk are different events. One combined count
            # read as "242 strategies are degrading" when only 5 were.
            "badge": _signals_badge(drift_count, position_count),
        },
        "macro": {"count": macro_count, "badge": macro_badge},
        "system": {"count": system_count, "badge": "System monitor · admin only"},
        "active_combo": dom,
    }


def _filter_by_channel(
    panel_alerts: list[dict[str, Any]],
    channel: PanelTabId | None,
) -> list[dict[str, Any]]:
    if not channel or channel == "all":
        return panel_alerts
    return [a for a in panel_alerts if a.get("channel") == channel]


def _meta_block(
    floor_pct: float,
    gap_threshold_pp: float,
    stale_reason: str | None = None,
    *,
    tabs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_date = resolve_report_date()
    data_updated_at = market_close_data_updated_at(report_date) if report_date else None
    return {
        "data_updated_at": data_updated_at,
        "floor_pct": floor_pct,
        "gap_threshold_pp": gap_threshold_pp,
        "next_signal_check": schedule_svc.next_signal_check(),
        "next_macro_scan": schedule_svc.next_macro_scan(),
        "stale_reason": stale_reason,
        "tabs": tabs,
    }


def get_panel_alerts(
    *,
    include_macro: bool = True,
    include_degradation: bool = True,
    include_system: bool = False,
    include_regime_warnings: bool = True,
    include_sentiment_warnings: bool = True,
    include_persistence: bool = True,
    include_watch_combos: bool = True,
    channel: PanelTabId | None = None,
    floor_pct: float = 60.0,
    gap_threshold_pp: float = 10.0,
    since: str | None = None,
) -> dict[str, Any]:
    panel_alerts: list[dict[str, Any]] = []
    stale_reason: str | None = None
    dominant: str | None = None
    runic = _load_runic_safe()

    if include_degradation:
        try:
            raw = degrade_svc.check_degradation(floor_pct=floor_pct)
            for item in raw.get("alerts", []):
                panel_alerts.append(_degradation_to_panel_alert(item, floor_pct))
            for item in raw.get("portfolio_alerts", []):
                panel_alerts.append(_portfolio_to_panel_alert(item))
        except Exception as exc:
            stale_reason = f"degradation_unavailable: {exc}"

    if include_macro:
        try:
            panel_alerts.extend(_build_runic_alerts())
            status = macro_svc.get_status_bar()
            narrative = macro_svc.get_narrative()
            dominant = status.get("dominant_signal")
            active_ids = {str(c).upper() for c in (status.get("active_combos") or []) if c}
            if include_watch_combos:
                panel_alerts.extend(
                    _build_watch_combo_alerts(
                        status=status,
                        narrative=narrative,
                        active_ids=active_ids,
                    )
                )
            if include_regime_warnings and runic:
                panel_alerts.extend(_build_regime_warning_alerts(runic))
            if include_persistence:
                persistence = runic.get("persistence_signals") or []
                if not persistence:
                    try:
                        persistence = macro_svc.get_persistence_signals().get("persistence_signals", [])
                    except Exception:
                        persistence = []
                panel_alerts.extend(_build_persistence_alerts(persistence))
        except Exception as exc:
            stale_reason = (stale_reason or "") + f"; macro_unavailable: {exc}"

    if include_sentiment_warnings:
        try:
            panel_alerts.extend(_build_sentiment_warning_alerts(macro_svc.get_ssi_summary()))
        except Exception as exc:
            stale_reason = (stale_reason or "") + f"; sentiment_unavailable: {exc}"

    if include_system:
        from api.main import API_VERSION  # noqa: PLC0415

        health = health_svc.run_system_health(API_VERSION)
        for alert in health_svc.system_checks_to_panel_alerts(health["checks"], health["checked_at"]):
            panel_alerts.append(_with_channel(alert))

    panel_alerts = [_with_channel(a) if "channel" not in a else a for a in panel_alerts]

    if since:
        panel_alerts = [a for a in panel_alerts if a.get("created_at", "") > since]

    panel_alerts.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    tabs = _compute_tab_badges(panel_alerts, dominant)
    filtered = _filter_by_channel(panel_alerts, channel)

    return {
        "meta": _meta_block(floor_pct, gap_threshold_pp, stale_reason, tabs=tabs),
        "count": len(filtered),
        "panel_alerts": filtered,
    }


def get_panel_context(
    *,
    include_system: bool = False,
    channel: PanelTabId | None = None,
    floor_pct: float = 60.0,
) -> dict[str, Any]:
    """Cross-page Overwatch bundle: alerts, tab badges, regime, sentiment, chat wiring."""
    alerts_payload = get_panel_alerts(
        include_system=include_system,
        channel=channel,
        floor_pct=floor_pct,
    )
    runic = _load_runic_safe()
    regime_block: dict[str, Any] = {}
    try:
        regime_block = macro_svc.get_regime()
    except Exception:
        if runic:
            regime_block = {
                "date": runic.get("date"),
                "regime": runic.get("regime", {}),
                "brave_fearful": runic.get("brave_fearful"),
                "brave_fearful_display": runic.get("brave_fearful_display"),
                "dominant_signal": runic.get("dominant_signal"),
                "dominant_reason": runic.get("dominant_reason"),
            }

    sentiment_block: dict[str, Any] = {}
    try:
        sentiment_block = macro_svc.get_ssi_summary()
    except Exception:
        pass

    override = compute_macro_override(runic) if runic else {"active": False, "reasons": []}

    return {
        **alerts_payload,
        "regime": {
            "date": regime_block.get("date"),
            "regime": regime_block.get("regime", {}),
            "brave_fearful": regime_block.get("brave_fearful"),
            "brave_fearful_display": regime_block.get("brave_fearful_display"),
            "dominant_signal": regime_block.get("dominant_signal"),
            "dominant_reason": regime_block.get("dominant_reason"),
            "macro_override": override,
        },
        "sentiment": {
            "ssi_level": sentiment_block.get("ssi_level"),
            "ssi_percentile_5y": sentiment_block.get("ssi_percentile_5y"),
            "ssi_multiplier": sentiment_block.get("ssi_multiplier"),
            "layer2_status": sentiment_block.get("layer2_status"),
            "posture": sentiment_block.get("posture"),
            "long_signal_active": sentiment_block.get("long_signal_active", False),
            "short_signal_active": sentiment_block.get("short_signal_active", False),
            "date": sentiment_block.get("date"),
        },
        "chat": {
            "create_session_path": "/api/v1/chatbot/sessions",
            "messages_path_template": "/api/v1/chatbot/sessions/{session_id}/messages",
            "history_path_template": "/api/v1/chatbot/sessions/{session_id}/history",
            "supports_page_context": True,
        },
    }


def get_analyst_brief() -> dict[str, Any]:
    try:
        narrative = macro_svc.get_narrative()
        text = (narrative.get("narrative") or narrative.get("dominant_reason") or "").strip()
        if text:
            return {
                "snippet": _first_sentence(text),
                "source": "narrative",
                "updated_at": narrative.get("date"),
            }
    except Exception:
        pass

    try:
        raw = degrade_svc.check_degradation()
        alerts = raw.get("alerts", [])
        if alerts:
            first = alerts[0]
            combo = first.get("combo", {})
            return {
                "snippet": (
                    f"{combo.get('asset', 'Signal')} on {combo.get('function', 'strategy')} "
                    f"— FWD {first.get('fwd_rate')}% ({first.get('severity', 'watch')} active)."
                ),
                "source": "template",
                "updated_at": _utc_now_iso(),
            }
    except Exception:
        pass

    return {"snippet": "No analyst brief available.", "source": "empty", "updated_at": None}


def scan_and_publish_new_alerts(
    state_path: str | None = None,
    floor_pct: float = 60.0,
) -> list[dict[str, Any]]:
    """Cron helper: return new alerts and optionally publish to SSE bus."""
    import json
    from pathlib import Path

    from api.services.overwatch_event_bus import event_bus

    payload = get_panel_alerts(include_macro=True, include_degradation=True, floor_pct=floor_pct)
    alerts = payload["panel_alerts"]

    store = Path(state_path or "overwatch_store/alert_state.json")
    store.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[str, str] = {}
    if store.exists():
        try:
            seen = json.loads(store.read_text(encoding="utf-8"))
        except Exception:
            seen = {}

    new_alerts: list[dict[str, Any]] = []
    for alert in alerts:
        aid = alert["id"]
        fingerprint = f"{alert.get('html', '')[:80]}|{alert.get('created_at', '')}"
        if seen.get(aid) == fingerprint:
            continue
        seen[aid] = fingerprint
        new_alerts.append(alert)
        event_bus.publish_sync(alert)

    store.write_text(json.dumps(seen, indent=2), encoding="utf-8")
    return new_alerts
