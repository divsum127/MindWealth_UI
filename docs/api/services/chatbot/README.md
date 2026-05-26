# Chatbot API

**Status:** implemented (v1.1.0)

AI trading analysis chatbot with async job-based messaging for long-running queries (deep research, hybrid RAG, signal data fetches).

**Source module:** [`chatbot/chatbot_engine.py`](../../../chatbot/chatbot_engine.py)  
**UI reference:** [`src/pages/chatbot_page.py`](../../../src/pages/chatbot_page.py)  
**Sidebar buttons:** [`docs/documentation/CHATBOT_UI_BUTTONS.md`](../../documentation/CHATBOT_UI_BUTTONS.md)

## Async jobs

Long responses use **202 Accepted** + job polling (not token streaming).

1. `POST /api/v1/chatbot/sessions/{id}/messages` → `{ job_id, poll_url }`
2. `GET /api/v1/chatbot/jobs/{job_id}` until `status` is `completed` or `failed`
3. Read `result.content` and `result.metadata` when completed

See [async-jobs.md](async-jobs.md) for client examples.

## Presets (sidebar buttons)

| Preset | Endpoint | Signal types |
|--------|----------|--------------|
| Analyze Asset | `POST /analyze-asset` | entry, exit |
| Signal Insights | `POST /signal-insights` | entry |
| Breadth Analysis | `POST /breadth-analysis` | breadth |
| Freeform chat | `POST /sessions/{id}/messages` | AI-selected (empty list) |

Preset convenience routes create a **new session** (matches Streamlit button behavior).

## Endpoints

### Sessions

| Method | Path | Doc |
|--------|------|-----|
| POST | `/sessions` | [create-session.md](endpoints/create-session.md) |
| GET | `/sessions` | [list-sessions.md](endpoints/list-sessions.md) |
| GET | `/sessions/{session_id}` | [get-session.md](endpoints/get-session.md) |
| PATCH | `/sessions/{session_id}` | [update-session.md](endpoints/update-session.md) |
| DELETE | `/sessions/{session_id}` | [delete-session.md](endpoints/delete-session.md) |
| POST | `/sessions/{session_id}/finalize` | [finalize-session.md](endpoints/finalize-session.md) |
| GET | `/sessions/{session_id}/history` | [get-history.md](endpoints/get-history.md) |

### Messages and jobs

| Method | Path | Doc |
|--------|------|-----|
| POST | `/sessions/{session_id}/messages` | [enqueue-message.md](endpoints/enqueue-message.md) |
| GET | `/jobs/{job_id}` | [get-job.md](endpoints/get-job.md) |
| GET | `/jobs` | [list-jobs.md](endpoints/list-jobs.md) |

### Preset launches

| Method | Path | Doc |
|--------|------|-----|
| POST | `/analyze-asset` | [launch-analyze-asset.md](endpoints/launch-analyze-asset.md) |
| POST | `/signal-insights` | [launch-signal-insights.md](endpoints/launch-signal-insights.md) |
| POST | `/breadth-analysis` | [launch-breadth-analysis.md](endpoints/launch-breadth-analysis.md) |

### Discovery

| Method | Path | Doc |
|--------|------|-----|
| GET | `/config` | [get-config.md](endpoints/get-config.md) |
| GET | `/signal-types` | [get-signal-types.md](endpoints/get-signal-types.md) |
| POST | `/signal-types/preview` | [preview-signal-types.md](endpoints/preview-signal-types.md) |
| GET | `/tickers` | [get-tickers.md](endpoints/get-tickers.md) |
| GET | `/functions` | [get-functions.md](endpoints/get-functions.md) |
| GET | `/memory/stats` | [get-memory-stats.md](endpoints/get-memory-stats.md) |

### Debug

| Method | Path | Doc |
|--------|------|-----|
| POST | `/sessions/{session_id}/flag` | [flag-exchange.md](endpoints/flag-exchange.md) |

All paths are prefixed with `/api/v1/chatbot`.
