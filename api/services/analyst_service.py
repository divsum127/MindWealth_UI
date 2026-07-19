"""AI Analyst panel alert orchestration."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from api.services import degradation_service as degrade_svc
from api.services import macro_service as macro_svc
from api.services import system_health_service as health_svc
from src.config_paths import DATA_FETCH_DATETIME_JSON
from src.utils.helpers import get_data_fetch_datetime


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


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
    combo = raw.get("combo") or {}
    function = combo.get("function") or raw.get("function") or raw.get("strategy", "")
    interval = combo.get("interval") or raw.get("interval", "")
    direction = combo.get("direction") or raw.get("direction", "Long")
    asset = combo.get("asset") or raw.get("symbol", "")
    fwd_rate = float(raw.get("fwd_rate") or raw.get("profit_pct") or 0)
    bt_rate = float(raw.get("bt_rate") or 0)
    gap = round(fwd_rate - bt_rate, 1) if bt_rate else 0.0
    fwd_trend = raw.get("weekly_trend") or raw.get("fwd_trend") or []

    alert_id = _slug(f"deg-{function}-{direction}-{interval}-{asset}")
    severity = raw.get("severity", "breach")
    label = raw.get("label") or (
        "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION WATCH"
        if severity == "watch"
        else "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION BREACH"
    )

    html = raw.get("message", "")
    if "<br>" not in html and "\n" in html:
        html = html.replace("\n", "<br>")

    return {
        "id": alert_id,
        "type": "degradation",
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

        alerts.append({
            "id": f"runic-{_slug(str(combo_id))}",
            "type": "runic",
            "label": f"AI ANALYST · OVERWATCH AUTO-TRIGGERED · RUNIC SIGNAL · COMBO {combo_id}",
            "html": html_body + analog_html,
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


def _meta_block(floor_pct: float, gap_threshold_pp: float, stale_reason: str | None = None) -> dict[str, Any]:
    fetch_info = get_data_fetch_datetime(DATA_FETCH_DATETIME_JSON)
    data_updated_at = None
    if fetch_info:
        data_updated_at = {
            "datetime": fetch_info.get("datetime"),
            "timezone": fetch_info.get("timezone", "IST"),
        }
    return {
        "data_updated_at": data_updated_at,
        "floor_pct": floor_pct,
        "gap_threshold_pp": gap_threshold_pp,
        "next_signal_check": None,
        "next_macro_scan": None,
        "stale_reason": stale_reason,
    }


def get_panel_alerts(
    *,
    include_macro: bool = True,
    include_degradation: bool = True,
    include_system: bool = False,
    floor_pct: float = 60.0,
    gap_threshold_pp: float = 10.0,
    since: str | None = None,
) -> dict[str, Any]:
    panel_alerts: list[dict[str, Any]] = []
    stale_reason: str | None = None

    if include_degradation:
        try:
            raw = degrade_svc.check_degradation(floor_pct=floor_pct)
            for item in raw.get("alerts", []) + raw.get("portfolio_alerts", []):
                panel_alerts.append(_degradation_to_panel_alert(item, floor_pct))
        except Exception as exc:
            stale_reason = f"degradation_unavailable: {exc}"

    if include_macro:
        try:
            panel_alerts.extend(_build_runic_alerts())
        except Exception as exc:
            stale_reason = (stale_reason or "") + f"; macro_unavailable: {exc}"

    if include_system:
        from api.main import API_VERSION  # noqa: PLC0415 — lazy to avoid import cycle at module load

        health = health_svc.run_system_health(API_VERSION)
        panel_alerts.extend(
            health_svc.system_checks_to_panel_alerts(health["checks"], health["checked_at"])
        )

    if since:
        panel_alerts = [a for a in panel_alerts if a.get("created_at", "") > since]

    panel_alerts.sort(key=lambda a: a.get("created_at", ""), reverse=True)

    return {
        "meta": _meta_block(floor_pct, gap_threshold_pp, stale_reason),
        "count": len(panel_alerts),
        "panel_alerts": panel_alerts,
    }


def get_analyst_brief() -> dict[str, Any]:
    try:
        narrative = macro_svc.get_narrative()
        text = (narrative.get("narrative") or narrative.get("dominant_reason") or "").strip()
        if text:
            snippet = text.split(".")[0].strip() + "."
            return {"snippet": snippet, "source": "narrative", "updated_at": narrative.get("date")}
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
