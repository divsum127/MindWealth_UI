# GET /api/v1/overwatch/stream

## Summary

Server-Sent Events (SSE) stream for Overwatch auto-triggered alerts. Used by the AI Analyst panel to auto-open on SIGNALS or MACRO tabs when new alerts fire.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/overwatch/stream`
- **operationId:** `overwatch_stream`
- **Status:** implemented (v1.8.0)
- **Content-Type:** `text/event-stream`

## Auth

- `X-API-Key` when `API_KEY` env is set
- JWT recommended for user-scoped deployments

## Maps to

`overwatch_event_bus.event_bus` — in-process pub/sub. Cron scripts (`scripts/overwatch/`) call `publish_sync()` when new alerts are detected.

## Event format

Each message:

```
data: {"type":"degradation","id":"deg-...","label":"...","html":"...",...}

```

Payload matches `OverwatchPanelAlert` plus top-level `type` for client routing:

| `type` | Panel tab |
|--------|-----------|
| `degradation` | SIGNALS |
| `runic` | MACRO |
| `system` | SYSTEM (no auto-open) |

## Example

```bash
curl -N -H "X-API-Key: $KEY" http://127.0.0.1:8507/api/v1/overwatch/stream
```

## Notes

- Requires **single uvicorn worker** (in-process bus does not fan out across workers).
- Nuxt should proxy this route and connect via `EventSource` in `useOverwatch.ts`.
- Rate-limited under the `health` bucket (generous).
