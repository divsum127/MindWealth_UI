# AI Analyst / Overwatch API

**Status:** implemented (v1.8.1)

**Routers:**
- `api/routers/analytics.py` — analyst alerts + brief
- `api/routers/overwatch.py` — SSE push stream
- `api/routers/system.py` — admin system health

**Services:**
- `api/services/analyst_service.py`
- `api/services/degradation_service.py`
- `api/services/system_health_service.py`
- `api/services/overwatch_event_bus.py`

**Spec:** `instruction_docs/ai_analyst/ai_analyst_spec_doc.md`

## Endpoints

| Method | Path | Doc |
|--------|------|-----|
| GET | `/analytics/analyst/alerts` | [get-analyst-alerts.md](endpoints/get-analyst-alerts.md) |
| GET | `/analytics/analyst/context` | [get-analyst-context.md](endpoints/get-analyst-context.md) |
| GET | `/analytics/analyst/brief` | [get-analyst-brief.md](endpoints/get-analyst-brief.md) |
| GET | `/overwatch/stream` | [get-overwatch-stream.md](endpoints/get-overwatch-stream.md) |
| GET | `/system/health` | [get-system-health.md](endpoints/get-system-health.md) |
| POST | `/signals/check-degradation` | [post-check-degradation.md](endpoints/post-check-degradation.md) |

All paths are prefixed with `/api/v1`.

## Frontend mapping (Alpha Terminal / Nuxt)

| UI area | Endpoint |
|---------|----------|
| Overwatch shell (cross-page) | `GET /analytics/analyst/context` |
| AI Analyst ALERTS / SIGNALS / MACRO tabs | `GET /analytics/analyst/alerts` |
| Tab filter only | `GET /analytics/analyst/alerts?channel=signals\|macro\|system` |
| Tab badge text | `meta.tabs` on alerts or context |
| Dashboard AI brief snippet | `GET /analytics/analyst/brief` |
| Overwatch auto-open (SSE) | `GET /overwatch/stream` |
| SYSTEM tab (admin only) | `GET /system/health` or `?include_system=true` on alerts |
| Raw degradation scan (BFF compat) | `POST /signals/check-degradation` |
| Panel chat (PULL mode) | `POST /chatbot/sessions/{id}/messages` with `page_context` |

## Auth

| Route | API key | JWT |
|-------|---------|-----|
| `/analytics/analyst/*` | When configured | Not required |
| `/overwatch/stream` | When configured | Recommended |
| `/system/health` | When configured | **Admin required** |

## Deployment notes

- SSE uses an **in-process** event bus — uvicorn must run with **1 worker**.
- Overwatch cron scripts: `scripts/overwatch/run_overwatch_*.py` (installed via `install_aws_cron_dual.sh`).
- Dedup state: `overwatch_store/alert_state.json` (runtime, gitignored).
