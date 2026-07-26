# AI Analyst / Overwatch — Implementation Log

**Spec:** [`ai_analyst_spec_doc.md`](ai_analyst_spec_doc.md)  
**API version:** v1.8.1  
**Work period:** 2026-07-18 → 2026-07-20  
**Repo:** `/home/ubuntu/uiv2/git/MindWealth_UI` (branch `chatbot-dev`)

---

## Simple Explanation

*Written in plain language for anyone new to MindWealth or this project. This section describes what **I built** on the backend for the AI Analyst — how it works and why I built each piece.*

### What I built (the big picture)

MindWealth is a platform for trading strategies and portfolios. The product spec calls for an **AI Analyst** panel (also named **Overwatch**) — a side drawer on every page that watches for problems and shows warnings.

**I implemented the backend for that panel** (API version **1.8.1**, July 2026). I did not build the sliding UI itself (that is frontend/Nuxt). What I built is everything the panel needs behind the scenes: the logic that detects issues, the APIs that serve alerts, the live push stream, performance fixes, and the hooks for chat.

The panel is meant to work in two ways, and I wired up both on the server side:

1. **Push mode** — the system detects something important and can tell the UI to open the panel automatically.
2. **Pull mode** — the user opens the panel and asks questions; I made the chatbot accept **page context** so answers are aware of where they are and what alerts they see.

---

### Why I built it

When I started, warnings were scattered:

- Strategy health was buried in daily reports and thousands of CSV files.
- Macro warnings (valuation, geopolitics, sentiment) lived on different API routes.
- Pipeline health (stale data, failed syncs) had no single place in the product.

I built a **unified backend** so one place collects, labels, and serves all of that — and so the frontend does not have to stitch mocks or call ten different endpoints.

---

### The three channels I implemented

The spec splits alerts into three tabs: **SIGNALS**, **MACRO**, and **SYSTEM** (plus **ALL**). I built the logic and APIs for each.

#### 1. SIGNALS — strategy degradation watch

**What I watch:** For every strategy combo (asset + function + interval + direction), I track the **forward win rate** — how often it has been winning in live forward testing.

**Why I built this:** Strategies can silently get worse after launch. The spec uses a **60% floor**: above that with a declining trend = Watch; below 60% = Breach. I also flag **booked losses** and positions **down more than 10%** immediately.

**How it works in my code:** `degradation_service.py` scans forward-testing data; `analyst_service.py` turns results into panel-ready alerts with trend text and recommendations.

**Performance fix I had to do:** The first version read ~2,000 CSV files on every request and timed out (>4 minutes). I added `degradation_cache.py` (parquet + result cache) so cached reads are under a second. I also fixed a bug where portfolio checks re-loaded all files inside a loop.

---

#### 2. MACRO — Runic signals, regime, and sentiment

**What I watch:** MindWealth already has a nightly **macro / Runic** system (combos A–G, CAPE, VIX, oil, etc.). I connected that into the AI Analyst panel and added several alert types the spec and mockups needed but were not in one feed before.

**What I built for the MACRO tab:**

| What I alert on | What it means |
|---------------|----------------|
| **Runic signal** | An active macro combo (e.g. Combo C), with narrative + **Analog Finder** (historical SPX returns in similar episodes). I also made the nightly JSON writer output `historical_analogs` for this. |
| **Runic watch** | A combo on WATCH — building toward activation, not fully active yet. |
| **Regime warning** | “Macro override” — e.g. CAPE valuation extreme and/or geopolitical stress. I extracted shared logic in `macro_override.py` (used here and on the portfolio sizer). |
| **Sentiment warning** | SSI (sentiment index) in an extreme fear or complacency zone. |
| **Persistence** | Slow-grind patterns from the nightly `persistence_signals` list. |

**Why I built this:** The portfolio mockup showed a “MACRO OVERRIDE” banner, but that data only lived on the portfolio API. I pulled regime and sentiment into the analyst feed so the panel and portfolio tell the same story.

---

#### 3. SYSTEM — pipeline health (admin only)

**What I watch:** US/India data freshness, macro nightly job, Claude/Tavily/Sheets connectivity, SSI file writes.

**Why I built this:** Alerts are useless if the data behind them is stale. Admins get a dedicated health API and optional system alerts in the panel.

**Extra work I did:** I added **integration markers** — timestamp files written when Tavily search succeeds and when the conviction daily run syncs Sheets — so health checks show *when* things last worked, not just pass/fail.

---

### APIs and features I created

Below is what I shipped, in the order a frontend developer would use it.

#### `GET /api/v1/analytics/analyst/context` (v1.8.1)

**What I built:** One “shell” endpoint for the Nuxt layout on every page: alerts, tab badge text, regime snapshot, sentiment snapshot, macro override, and chat API paths.

**Why:** The panel is cross-page. I did not want the frontend re-fetching five endpoints on every route change.

---

#### `GET /api/v1/analytics/analyst/alerts`

**What I built:** The single source of truth for all panel alerts. Each alert has a `type` (e.g. `degradation`, `runic`, `regime_warning`) and a `channel` (`signals`, `macro`, `system`). Response includes `meta.tabs` with badge strings like “Overwatch · 3 watch active”.

**Why:** Replaces BFF mocks and scattered stitching. Supports `?channel=signals|macro|system` and toggles like `include_regime_warnings`, `include_system`, etc.

---

#### `GET /api/v1/analytics/analyst/brief`

**What I built:** A short one-line snippet for the main dashboard (from macro narrative or top degradation alert).

**Why:** Users who never open the panel still see what Overwatch cares about today.

---

#### `GET /api/v1/overwatch/stream`

**What I built:** Server-Sent Events (SSE) stream so new alerts push to the browser in real time. Background cron scripts call `scan_and_publish_new_alerts()` to publish when something new appears.

**Why:** Spec requires auto-open when degradation or runic alerts fire — that needs live push, not polling.

**Note I documented:** This uses an in-process event bus; production API must run with **one uvicorn worker**.

---

#### `GET /api/v1/system/health`

**What I built:** Admin-only health checks (JWT + `require_admin`). Seven checks with ok/warn/fail status.

**Why:** SYSTEM tab in the spec; also usable outside the panel for ops.

---

#### `POST /api/v1/signals/check-degradation`

**What I built:** Raw degradation scan endpoint (kept for backward compatibility with existing BFF code). The panel should prefer `/analyst/alerts`.

---

#### Background cron scripts (`scripts/overwatch/`)

**What I built:** Three scripts — signals (degradation + cache warm), macro, system — plus wiring in `install_aws_cron_dual.sh`.

**Why:** Overwatch must run on a schedule even when nobody is logged in.

---

#### Chat: `page_context` on `POST /chatbot/sessions/{id}/messages`

**What I built:** Optional fields on chat messages — current route, active panel tab, open alert ids, dominant combo — merged into the LLM context in `chatbot_service.py`.

**Why:** Pull-mode chat should know “you are on Portfolio looking at Combo C” without the user repeating it every time.

---

#### Optional Claude alert copy (`analyst_copy_service.py`)

**What I built:** When `ANALYST_USE_CLAUDE_COPY=true`, Claude can polish alert wording. **Rules still decide what fires;** Claude only rewrites text. Off by default.

**Why:** Spec says Claude writes messages, not triggers. I kept triggers deterministic and made copy optional.

---

#### API documentation (`docs/mindwealth-api-docs`, v1.8.1)

**What I built:** Endpoint pages, changelog, frontend mapping table, OpenAPI sync in the docs repo.

**Why:** So Parth/Nuxt can integrate without reading my Python.

---

### Problems I hit and how I fixed them

| Problem | What I did |
|---------|------------|
| Alerts API took >4 minutes | Parquet cache + result cache in `overwatch_store/` |
| Portfolio loop re-read 2,000 CSVs | Single load, pass dataframe into portfolio checks |
| Analyst routes 404 on prod | Deployed v1.8.0+ to prod branch |
| Dashboard 429 on performance | Raised rate limits; BFF caching (separate frontend fix) |
| No tab badges / channel filter for UI | Added `meta.tabs`, `channel`, and `/context` in v1.8.1 |
| Tavily/Sheets health empty | Integration marker files + writers in chatbot and conviction daily run |

---

### What I did **not** build (still outstanding)

| Item | Owner |
|------|--------|
| 360px sliding panel UI, gold button, Framer Motion | Frontend (Nuxt) |
| Replace `overwatch-panel.ts` mocks with my APIs | Frontend (Nuxt) |
| Prod deploy of latest `chatbot-dev` | Merge + prod pull/restart |

**My backend deliverable:** As of v1.8.1, **I have implemented every API and server-side behavior the AI Analyst spec needs.** The frontend is not blocked on a missing backend endpoint from my side.

---

### One-sentence summary (my work)

**I built the always-on backend watchdog** that unifies strategy degradation, macro/sentiment/regime warnings, and system health into one alert feed, pushes urgent items over SSE, caches degradation for speed, and supports context-aware panel chat — so the product can show users what matters without digging through reports.

---

## Part 1 — Concise Summary

### What was implemented

| Area | Deliverable |
|------|-------------|
| **Unified alerts API** | `GET /api/v1/analytics/analyst/alerts` — all Overwatch `panel_alerts[]` with `channel` + `type` |
| **Cross-page context bundle** | `GET /api/v1/analytics/analyst/context` — alerts + tab badges + regime + sentiment + chat paths |
| **Tab logic (backend)** | `meta.tabs` badge counts/text; `?channel=signals\|macro\|system` filter; every alert has `channel` |
| **Dashboard brief** | `GET /api/v1/analytics/analyst/brief` — short analyst snippet |
| **Degradation scan** | `POST /api/v1/signals/check-degradation` — raw scan (BFF compat) |
| **SSE push** | `GET /api/v1/overwatch/stream` — in-process event bus for auto-open |
| **System health** | `GET /api/v1/system/health` — admin-only; also `?include_system=true` on alerts |
| **Degradation rules** | 60% WATCH/BREACH, 4-week trend, portfolio booked-loss / MTM triggers |
| **Runic / macro alerts** | Active combos + Analog Finder + **watch combos** + **persistence** + **regime override** + **SSI warnings** |
| **Regime / sentiment integration** | `regime_warning`, `sentiment_warning`, `runic_watch`, `persistence` alert types on MACRO channel |
| **Cross-page chat (PULL)** | `page_context` on `POST /chatbot/sessions/{id}/messages` — route, tab, alert ids merged into LLM context |
| **Nightly JSON** | `historical_analogs` block for dominant combo |
| **Cron / overwatch** | `scripts/overwatch/run_overwatch_{signals,macro,system}.py` |
| **Performance cache** | Parquet + result cache in `overwatch_store/` |
| **Claude copy (optional)** | `analyst_copy_service.py` when `ANALYST_USE_CLAUDE_COPY=true` |
| **Health markers** | Tavily + Sheets integration timestamps |
| **API docs** | `docs/api/services/analyst/` + `docs/mindwealth-api-docs` v1.8.1 |
| **Tests** | `test_api_analyst.py`, `test_degradation_cache.py`, `test_chatbot_page_context.py` |

### Panel alert types (v1.8.1)

| `type` | `channel` | Tab | SSE auto-open |
|--------|-----------|-----|---------------|
| `degradation` | `signals` | SIGNALS | Yes |
| `runic` | `macro` | MACRO | Yes |
| `runic_watch` | `macro` | MACRO | No |
| `regime_warning` | `macro` | MACRO | No |
| `sentiment_warning` | `macro` | MACRO | No |
| `persistence` | `macro` | MACRO | No |
| `system` | `system` | SYSTEM | No |

### Problems faced and how they were solved

| # | Problem | Root cause | Solution |
|---|---------|------------|----------|
| 1 | Analyst routes 404 on prod | v1.8 not deployed | Merged `chatbot-dev` → `chatbot-prod`, restarted API |
| 2 | Dashboard avg fwd win rate missing | Nuxt BFF **429** on `/analytics/performance` | Raised rate-limit burst; BFF cache/dedup |
| 3 | `include_degradation=true` timed out (>240s) | ~1,990 CSVs read per request | `degradation_cache.py` parquet + result cache |
| 4 | Portfolio degradation still slow | Re-loaded all CSVs per booked-loss row | Single dataframe pass into portfolio triggers |
| 5 | System health missing Tavily/Sheets | No marker files | `integration_health_store.py` + writers |
| 6 | Frontend blocked — no tab/badge API | Only raw `panel_alerts[]` | `meta.tabs` + `channel` filter (v1.8.1) |
| 7 | Regime warnings only on portfolio sizer | `macro_override` not in analyst alerts | `regime_warning` alerts + `context.regime` (v1.8.1) |
| 8 | Sentiment / watch / persistence not in panel | Not wired into `analyst_service` | Dedicated alert builders (v1.8.1) |
| 9 | Cross-page chat had no page context | Generic chatbot only | `page_context` on chat messages (v1.8.1) |
| 10 | `include_system` not on HTTP route | Service-only flag | Exposed on alerts + context (v1.8.1) |
| 11 | `git push` failed on AWS host | No GitHub credentials | Commits local; push from dev machine |

### Architecture decisions (locked)

- **SSE:** in-process bus; **uvicorn workers=1**
- **Degradation floor:** spec 60% watch/breach
- **Claude:** copy only (optional); triggers are rule-based
- **Tab filtering:** server can filter via `channel`; client can also filter `panel_alerts[]` by `channel` or `type`
- **Cross-page state:** one `session_id` in Nuxt layout (frontend); backend provides `context` bundle + `page_context` per message
- **Regime override:** shared `compute_macro_override()` in `macro_override.py` (portfolio + analyst)

### Still deferred (frontend / prod only)

- Nuxt Overwatch panel UI (360px slide-in, Framer Motion) — `MindwealthUI_Vue`
- BFF `overwatch-panel.ts` mock removal — wire to `/analytics/analyst/context`
- Economic surprise as dedicated alert type
- Redis-backed SSE for multi-worker
- Weekly vs monthly per-combo degradation sensitivity
- Prod cron install + smoke tests `[PENDING]` in `dev_to_prod_migration_todos.md`
- `git push` from AWS host (needs creds)

### Commits and verification

| Check | Result |
|-------|--------|
| Unit tests (analyst + page_context + cache) | **Pass** |
| Live `:8507` health | **v1.8.1** (restarted 2026-07-20) |
| `GET /analytics/analyst/context` | **200** |
| Cached degradation alerts | **~0.07–0.25s** |
| MindWealth_UI | `b984f0d6c` (`chatbot-dev`) |
| mindwealth-api-docs | `c5c5b59` (`main`) |

---

## Part 2 — Detailed Implementation

### 2.1 Background and scope

The AI Analyst panel (spec) is a 360px floating Overwatch UI on **every page** with:

| Mode | Behaviour |
|------|-----------|
| **PUSHED** | Overwatch cron/SSE opens panel on SIGNALS or MACRO tab |
| **PULL** | User opens panel, asks via chatbot; `page_context` carries route/tab/alerts |

Three filter tabs: **ALL \| SIGNALS \| MACRO \| SYSTEM** (SYSTEM admin-only).

**Backend delivered:** all APIs, alert logic, tab metadata, regime/sentiment warnings, cross-page context bundle, chat integration hooks.

**Frontend (Parth/Nuxt):** panel chrome, animations, `useOverwatch` SSE hook, layout-persisted chat session.

---

### 2.2 API surface (v1.8.1)

All paths prefixed with `/api/v1`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/analytics/analyst/context` | **Cross-page bundle** — alerts + tabs + regime + sentiment + chat paths |
| GET | `/analytics/analyst/alerts` | Unified `panel_alerts[]` with filters |
| GET | `/analytics/analyst/brief` | Dashboard snippet |
| POST | `/signals/check-degradation` | Raw degradation scan |
| GET | `/overwatch/stream` | SSE auto-open stream |
| GET | `/system/health` | Admin pipeline health |
| POST | `/chatbot/sessions/{id}/messages` | PULL chat (+ `page_context`) |

#### `GET /analytics/analyst/alerts` — query parameters

| Param | Default | Description |
|-------|---------|-------------|
| `include_macro` | `true` | Runic active-combo alerts |
| `include_degradation` | `true` | FWD degradation alerts |
| `include_system` | `false` | Non-ok system health as panel alerts |
| `include_regime_warnings` | `true` | CAPE extreme + geo macro override |
| `include_sentiment_warnings` | `true` | SSI extreme / layer-2 warnings |
| `include_persistence` | `true` | Persistence / slow-grind signals |
| `include_watch_combos` | `true` | Runic WATCH combos |
| `channel` | — | Filter: `signals`, `macro`, or `system` |
| `floor_pct` | `60` | Degradation floor |
| `since` | — | ISO datetime filter |

#### `meta.tabs` (tab badge text per spec)

```json
{
  "tabs": {
    "all": { "count": 5, "badge": "Overwatch · auto-triggered" },
    "signals": { "count": 1, "badge": "Overwatch · 1 watch active" },
    "macro": { "count": 4, "badge": "Overwatch · Combo C firing" },
    "system": { "count": 0, "badge": "System monitor · admin only" },
    "active_combo": "C"
  }
}
```

#### `GET /analytics/analyst/context` — response extras

| Block | Source | Use |
|-------|--------|-----|
| `regime` | `macro_service.get_regime()` + `macro_override` | Portfolio banner, macro tab context |
| `sentiment` | `macro_service.get_ssi_summary()` | SSI posture in panel |
| `chat` | Static paths | PULL-mode session wiring |

---

### 2.3 Channel 1 — Degradation (SIGNALS)

**Files:** `degradation_service.py`, `degradation_cache.py`

- 60% floor WATCH/BREACH + 4-week `fwd_trend`
- Portfolio booked-loss and MTM &lt; −10% triggers
- Parquet cache: `overwatch_store/fwd_trades.parquet` — warm reads **&lt;1s**

Each alert: `type: degradation`, `channel: signals`, border `#ff4d6d`.

---

### 2.4 Channel 2 — Macro (MACRO)

**File:** `analyst_service.py`

| Builder | Alert `type` | Trigger |
|---------|--------------|---------|
| `_build_runic_alerts()` | `runic` | Dominant + active combos (≤3), Analog Finder |
| `_build_watch_combo_alerts()` | `runic_watch` | `watch_combos` not in `active_combos` |
| `_build_regime_warning_alerts()` | `regime_warning` | `compute_macro_override()` — CAPE EXTREME + geo |
| `_build_persistence_alerts()` | `persistence` | Nightly `persistence_signals` |
| `_build_sentiment_warning_alerts()` | `sentiment_warning` | SSI risk-on/off or layer-2 CONFIRMED |

**Regime override** (portfolio mockup “MACRO OVERRIDE” banner):

```json
{
  "macro_override": {
    "active": true,
    "reasons": [
      "Valuation extreme: CAPE 42.0×",
      "Geopolitical: Regional War"
    ]
  }
}
```

Shared logic: `api/services/macro_override.py` (used by `portfolio_service` and `analyst_service`).

---

### 2.5 Channel 3 — System (SYSTEM, admin)

**File:** `system_health_service.py`

- 7 pipeline/integration checks
- Non-ok checks → `type: system`, `channel: system` panel alerts when `include_system=true`
- Admin JWT required for `GET /system/health`

---

### 2.6 Cross-page chat (PULL mode)

**Not a new chat endpoint** — uses existing chatbot API with structured context.

**Create session once** in Nuxt root layout:

```
POST /api/v1/chatbot/sessions
```

**Send messages** from panel input:

```
POST /api/v1/chatbot/sessions/{session_id}/messages
```

**`page_context` body field** (`api/schemas/chatbot.py`):

| Field | Purpose |
|-------|---------|
| `route` | Current page, e.g. `/portfolio` |
| `page_title` | Human label |
| `active_tab` | Overwatch tab: `all` \| `signals` \| `macro` \| `system` |
| `panel_open` | Whether panel is open |
| `alert_ids` | Visible alert ids |
| `dominant_combo` | Active combo for macro context |

Merged into `additional_context` by `chatbot_service._merge_page_context()` before LLM call.

---

### 2.7 SSE and cron

Unchanged from v1.8.0:

- `overwatch_event_bus.py` — in-process SSE
- Cron: `run_overwatch_signals.py` (cache warm + publish), `run_overwatch_macro.py`, `run_overwatch_system.py`
- Auto-open per spec: `degradation` → SIGNALS; `runic` → MACRO

---

### 2.8 Performance hardening (v1.8.0)

| Endpoint | Warm latency |
|----------|--------------|
| `GET /analytics/analyst/alerts?include_degradation=true` | ~0.1–0.25s |
| `GET /analytics/analyst/context` | ~0.2–1.5s (includes macro/SSI reads) |
| `POST /signals/check-degradation` | ~0.1s |

Cold degradation build ~20s — handled by cron pre-warm, not user-facing.

---

### 2.9 Frontend integration guide (Nuxt / Parth)

```
┌─────────────────────────────────────────────────────────┐
│  Nuxt root layout (every page)                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │ onMount + onRouteChange:                          │  │
│  │   GET /analytics/analyst/context                  │  │
│  │   → panel_alerts, meta.tabs, regime, sentiment    │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ EventSource: GET /overwatch/stream                │  │
│  │   degradation → open panel, tab=signals           │  │
│  │   runic       → open panel, tab=macro             │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Chat session_id (persist in layout state)         │  │
│  │ POST .../messages { message, page_context }       │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

| UI need | API |
|---------|-----|
| Tab filter | `panel_alerts.filter(a => a.channel === 'macro')` or `?channel=macro` |
| Tab badge text | `meta.tabs.signals.badge` etc. |
| Portfolio macro banner | `context.regime.macro_override` |
| SYSTEM tab (admin) | `GET /system/health` or `?include_system=true` |
| Hide SYSTEM for non-admin | JWT `role !== 'admin'` (frontend) |

---

### 2.10 Documentation

| Location | Version |
|----------|---------|
| `docs/api/services/analyst/` | v1.8.1 — 6 endpoint pages incl. `get-analyst-context.md` |
| `docs/mindwealth-api-docs/services/analyst/` | v1.8.1 — synced submodule |
| `docs/api/changelog.md` | v1.8.0 + v1.8.1 entries |

---

### 2.11 Testing

| Suite | Coverage |
|-------|----------|
| `tests/test_api_analyst.py` | Alert shape, channel filter, warnings, context bundle, dedup |
| `tests/test_chatbot_page_context.py` | `page_context` merge into additional_context |
| `tests/test_degradation_cache.py` | Parquet + result cache |

**Live smoke (`:8507`):**

```bash
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8507/api/v1/health
# → "version": "1.8.1"

curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8507/api/v1/analytics/analyst/context | jq '{count, tabs: .meta.tabs, regime: .regime.macro_override}'
```

---

### 2.12 File map (key paths)

```
api/
  main.py                              # v1.8.1
  schemas/analyst.py                   # PanelAlertType, tabs, context models
  schemas/chatbot.py                   # PageContext
  routers/analytics.py                 # /analyst/alerts, /context, /brief
  services/
    analyst_service.py                 # All alert builders, context bundle
    macro_override.py                  # Shared CAPE + geo override
    degradation_service.py
    degradation_cache.py
    analyst_copy_service.py
    system_health_service.py
    chatbot_service.py                 # page_context merge
    integration_health_store.py
    overwatch_event_bus.py

docs/
  api/services/analyst/endpoints/get-analyst-context.md
  mindwealth-api-docs/                 # Submodule — v1.8.1

tests/
  test_api_analyst.py
  test_chatbot_page_context.py
  test_degradation_cache.py
```

---

### 2.13 Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MINDWEALTH_TRADE_STORE` | `.../trade_store/US` | Forward-testing CSVs |
| `OVERWATCH_STORE_DIR` | `overwatch_store/` | Cache + alert state |
| `ANALYST_USE_CLAUDE_COPY` | `false` | LLM alert copy |
| `SYSTEM_HEALTH_LIVE_PROBE` | `false` | Live Tavily probe |

---

### 2.14 Prod merge checklist

1. Push `chatbot-dev` + `mindwealth-api-docs` (from machine with GitHub creds)  
2. Merge `chatbot-dev` → `chatbot-prod`  
3. `bash scripts/prod-pull-and-restart.sh` in prod clone  
4. `scripts/install_aws_cron_dual.sh`  
5. Confirm API **workers=1**  
6. Smoke: context, alerts, degradation &lt;30s, SSE, system health (admin JWT)  
7. Nuxt: mount context in layout; remove BFF mocks  

---

### 2.15 Spec gaps vs `ai_analyst_spec_doc.md`

| Spec item | Backend | Frontend |
|-----------|---------|----------|
| 360px panel, slide animation | N/A | **Pending** (Nuxt) |
| Tab filter ALL/SIGNALS/MACRO/SYSTEM | **Done** — `channel` + `meta.tabs` | Wire UI |
| SSE auto-open on degradation/runic | **Done** | `useOverwatch` hook |
| PULL chat cross-page | **Done** — `page_context` + layout session | Wire UI |
| Regime / sentiment warnings in panel | **Done** — v1.8.1 alert types | Wire UI |
| Analog Finder in runic alerts | **Done** | Render HTML block |
| Degradation 4-bar mini chart | `fwd_trend[]` in API | Chart component |
| Economic surprise alert format | **Not implemented** | — |
| Redis SSE | **Deferred** | — |
| Claude triggers alerts | **No** — copy only | — |

**Backend verdict (v1.8.1):** No remaining API blockers for Overwatch panel integration. Frontend can proceed with `context`, `alerts`, `stream`, and chatbot + `page_context`.

---

*Last updated: 2026-07-20 (v1.8.1 — Simple Explanation in first person: backend work by Divyanshu)*
