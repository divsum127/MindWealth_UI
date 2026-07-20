# GET /api/v1/analytics/analyst/context

## Summary

Cross-page Overwatch panel bundle for Nuxt layout: alerts + tab badges + regime snapshot + sentiment snapshot + chat integration paths. Call once on app shell mount and on route changes.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/analytics/analyst/context`
- **operationId:** `get_analyst_panel_context`
- **Status:** implemented (v1.8.1)

## Query parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `include_system` | boolean | `false` | Include SYSTEM-tab health alerts (admin workflows) |
| `channel` | string | — | Filter `panel_alerts` to `signals`, `macro`, or `system` |
| `floor_pct` | number | `60` | Degradation floor passed through to alert builder |

## Response

Same `panel_alerts` + `meta.tabs` as [get-analyst-alerts.md](get-analyst-alerts.md), plus:

| Block | Purpose |
|-------|---------|
| `regime` | 5-dim regime, dominant combo, `macro_override` (CAPE extreme + geo) |
| `sentiment` | Latest SSI level, posture, layer-2 status |
| `chat` | Chatbot paths for PULL-mode panel chat |

### Example

```json
{
  "meta": {
    "tabs": {
      "all": { "count": 5, "badge": "Overwatch · auto-triggered" },
      "signals": { "count": 1, "badge": "Overwatch · 1 watch active" },
      "macro": { "count": 4, "badge": "Overwatch · Combo C firing" },
      "system": { "count": 0, "badge": "System monitor · admin only" },
      "active_combo": "C"
    }
  },
  "count": 5,
  "panel_alerts": [],
  "regime": {
    "dominant_signal": "C",
    "macro_override": { "active": true, "reasons": ["Valuation extreme: CAPE 42.0×"] }
  },
  "sentiment": { "ssi_level": 0.9, "posture": "RISK_OFF", "short_signal_active": true },
  "chat": {
    "create_session_path": "/api/v1/chatbot/sessions",
    "messages_path_template": "/api/v1/chatbot/sessions/{session_id}/messages",
    "supports_page_context": true
  }
}
```

## Frontend usage

- Mount in Nuxt root layout — persists across page navigation.
- Use `meta.tabs` for header badge text per Overwatch tab.
- Use `regime.macro_override` for portfolio banner warnings.
- PULL chat: reuse one `session_id` in layout; pass `page_context` on each message (see chatbot API).
