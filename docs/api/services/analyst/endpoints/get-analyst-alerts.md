# GET /api/v1/analytics/analyst/alerts

## Summary

Single source of truth for AI Analyst Overwatch panel alerts. Returns display-ready `panel_alerts[]` for degradation (signals) and runic (macro) channels.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/analytics/analyst/alerts`
- **operationId:** `get_analyst_alerts`
- **Status:** implemented (v1.8.0)
- **Typical status:** 200

## Query parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `include_macro` | boolean | `true` | Include runic / macro alerts |
| `include_degradation` | boolean | `true` | Include FWD degradation alerts |
| `floor_pct` | number | `60` | Absolute FWD win-rate floor (%) |
| `gap_threshold_pp` | number | `10` | Reserved for BFF compat (BT vs FWD gap) |
| `since` | ISO datetime | — | Only alerts with `created_at` after this time |

## Maps to

`analyst_service.get_panel_alerts()` — merges:
- `degradation_service.check_degradation()` (60% watch/breach, 4-week `fwd_trend`)
- `macro_service.get_status_bar()` + `get_narrative()` + `get_analog_table()` (Analog Finder)

## Response

### 200 OK

```json
{
  "meta": {
    "data_updated_at": { "datetime": "2026-06-25T09:21:00+05:30", "timezone": "IST" },
    "floor_pct": 60,
    "gap_threshold_pp": 10,
    "next_signal_check": null,
    "next_macro_scan": null,
    "stale_reason": null
  },
  "count": 2,
  "panel_alerts": [
    {
      "id": "deg-deltadrift-short-daily-aapl",
      "type": "degradation",
      "label": "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION WATCH",
      "html": "DeltaDrift / Short / Daily: FWD win rate 62.5% — approaching 60% floor.<br>...",
      "recommendation": "pause new entries on this combo",
      "fwd_trend": [66.0, 64.5, 63.2, 62.5],
      "created_at": "2026-06-25T09:00:00Z",
      "border_color": "#ff4d6d",
      "severity": "watch",
      "signal": {
        "strategy": "DeltaDrift",
        "interval": "Daily",
        "signal_type": "Short",
        "fwd_wr": 62.5,
        "backtest_wr": 88.0,
        "gap": -25.5,
        "pattern": "Combo issue: AAPL/DeltaDrift — review model params",
        "above_floor": true
      }
    },
    {
      "id": "runic-c",
      "type": "runic",
      "label": "AI ANALYST · OVERWATCH AUTO-TRIGGERED · RUNIC SIGNAL · COMBO C",
      "html": "Dominant <span class=\"wa\">Combo C</span>: Combo C active...",
      "footer": "TAVILY ACTIVE · INTERNAL DATA PRIORITY · ONCE PER PAGE VISIT",
      "created_at": "2026-06-25T06:00:00Z",
      "border_color": "#C5A059",
      "macro": {
        "combo": "C",
        "reason": "Combo C active (week 11, MEDIUM).",
        "narrative": "Tactical tight money backdrop.",
        "brave_fearful": "TACTICAL_TIGHT_MONEY",
        "variant": "dominant",
        "historical_analogs": {
          "combo": "C",
          "instances": [{ "date": "2022-06", "description": "...", "spx_3m": -16.0 }],
          "summary": { "median_3m": -8.4, "worst": -19.0, "best": 18.0, "hit_rate": 0.8 }
        }
      }
    }
  ]
}
```

## Example

```bash
curl -s -H "X-API-Key: $KEY" \
  "http://127.0.0.1:8507/api/v1/analytics/analyst/alerts?include_macro=true&floor_pct=60" \
  | jq '{count, types: [.panel_alerts[].type]}'
```

## Notes

- Matches Nuxt `OverwatchPanelAlert` in `MindwealthUI_Vue/types/api.ts`.
- No mock data when sources are missing — returns empty `panel_alerts` with optional `meta.stale_reason`.
- Replaces BFF logic in `server/utils/overwatch-panel.ts`.
