# GET /api/v1/system/health

## Summary

Admin-only pipeline and integration health checks for the AI Analyst SYSTEM tab.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/system/health`
- **operationId:** `get_system_health`
- **Status:** implemented (v1.8.0)
- **Typical status:** 200 (admin JWT), 401 (missing/invalid JWT), 403 (non-admin)

## Auth

- `X-API-Key` when configured
- **JWT with `role: admin` required**

## Maps to

`system_health_service.run_system_health()`

## Checks performed

| Check | Source |
|-------|--------|
| US CSV pipeline | `trade_store/US/data_fetch_datetime.json` age |
| India CSV pipeline | India trade_store mtime |
| Claude API | Live `models.list()` probe |
| Tavily | Live search probe |
| Google Sheets sync | `conviction_store/.last_sheets_sync` marker |
| Macro agent | `runic_output.json` mtime |
| SSI JSON write | `positioning.json` mtime |

Status per check: `ok` / `warn` (>2× expected interval) / `fail`.

## Response

### 200 OK

```json
{
  "status": "warn",
  "version": "1.8.0",
  "checked_at": "2026-06-25T10:00:00Z",
  "checks": [
    {
      "name": "US CSV pipeline",
      "status": "ok",
      "detail": "42m ago",
      "last_success_at": "2026-06-25T09:18:00+05:30"
    },
    {
      "name": "Claude API",
      "status": "ok",
      "detail": "reachable · 240ms",
      "last_success_at": "2026-06-25T09:55:00Z"
    }
  ]
}
```

## Example

```bash
curl -s -H "X-API-Key: $KEY" -H "Authorization: Bearer $JWT" \
  http://127.0.0.1:8507/api/v1/system/health | jq '.checks[].status'
```

## Notes

- Distinct from `GET /api/v1/health` (conviction store only).
- Overwatch cron `run_overwatch_system.py` runs every 15 minutes and publishes warn/fail alerts to SSE.
