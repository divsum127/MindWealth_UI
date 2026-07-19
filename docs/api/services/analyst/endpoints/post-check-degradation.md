# POST /api/v1/signals/check-degradation

## Summary

Raw Layer 1 degradation scan across forward-testing combos and virtual trading portfolio. Returns structured alerts (not panel-shaped). Prefer `GET /analytics/analyst/alerts` for the AI Analyst UI.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/signals/check-degradation`
- **operationId:** `check_signal_degradation`
- **Status:** implemented (updated v1.8.0)
- **Typical status:** 200

## Trigger rules (v1.8.0 — AI Analyst spec)

| Condition | Severity |
|-----------|----------|
| FWD win rate declining toward 60% while still ≥ 60% | `watch` |
| FWD win rate below 60% | `breach` |
| Booked loss on portfolio position | `breach` |
| Live MTM below -10% | `breach` |

## Maps to

`degradation_service.check_degradation()`

## Response

### 200 OK

```json
{
  "triggered": true,
  "alerts": [
    {
      "trigger_type": "fwd_degradation",
      "severity": "watch",
      "strategy": "DeltaDrift",
      "combo": { "asset": "AAPL", "function": "DeltaDrift", "interval": "Daily", "direction": "Short" },
      "bt_rate": 88.0,
      "fwd_rate": 62.5,
      "weekly_trend": [66.0, 64.5, 63.2, 62.5],
      "pattern": "Combo issue: AAPL/DeltaDrift — review model params",
      "recommendation": "Audit AAPL/DeltaDrift combo...",
      "message": "DeltaDrift / Short / Daily: FWD win rate 62.5% — approaching 60% floor...",
      "label": "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION WATCH",
      "border_color": "#ff4d6d"
    }
  ],
  "portfolio_alerts": [],
  "checked_combos": 142,
  "alert_count": 1,
  "floor_pct": 60.0,
  "label": "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION BREACH",
  "border_color": "#ff4d6d"
}
```

## Example

```bash
curl -s -X POST -H "X-API-Key: $KEY" \
  http://127.0.0.1:8507/api/v1/signals/check-degradation | jq '.alert_count'
```

## Notes

- Data source: `{MINDWEALTH_TRADE_STORE}/forward_testing/` and `virtual_trading_*.csv`.
- Rate-limited as `write_expensive` (POST).
