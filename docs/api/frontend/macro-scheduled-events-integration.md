# Frontend integration — scheduled macro event intelligence

Guidelines for wiring **pre-catalyst fragility** and **post-event regime transition** into the Macro UI (Streamlit `runic_page.py`, HTML dashboard, or any API client).

**Rule:** Use the **new v1.5.0 endpoints** — do not expect these fields on `GET /macro/regime` or other existing routes.

---

## What to show users

### 1. Pre-catalyst card (before CPI / FOMC / NFP)

**API:** `GET /api/v1/macro/events/pre-catalyst`

**When `active: true`:**

- Show upcoming event: `{type} on {date}` (e.g. "FOMC on 2026-06-25")
- Show `days_to_event`
- If `fragility_score` is non-null → prominent warning badge:
  - **HIGH — REGIME SENSITIVE TO CATALYST**
- List `near_threshold_vars` with count (`near_threshold_count` / 12)

**When `active: false`:** Hide card or show "No major macro release in the next 7 days."

### 2. Post-event card (within 48h after release)

**API:** `GET /api/v1/macro/events/post-regime`

**When `active: true`:**

- Event line: `{type} · {date} · {hours_since_event}h ago`
- If `regime_transition: true`:
  - Headline: `transition_type` (humanize underscores → "Credibility Restored")
  - List `variables_crossed`
  - Optional metrics row: HY Δ, USD %, 2Y/10Y bps, VIX, curve bps from `metrics`
- If `regime_transition: false` but `active: true`: "Event window open — no threshold crossing yet."

**When `active: false`:** Hide card or show "Outside post-event window."

### 3. Event calendar strip (optional)

**API:** `GET /api/v1/macro/events/calendar?days=21`

- Timeline or table of `events[]` filtered to CPI / FOMC / NFP
- Highlight the next event; link pre-catalyst card to same date

---

## Suggested layout (Macro page)

```
┌─────────────────────────────────────────────────────────┐
│ Status bar (existing — GET /macro/status)               │
├─────────────────────────────────────────────────────────┤
│ [NEW] Scheduled events row                              │
│   Pre-catalyst warning  |  Post-event transition        │
│   (or calendar mini-list)                               │
├─────────────────────────────────────────────────────────┤
│ Regime metrics (existing)                               │
│ Combo status / variables (existing)                     │
│ Briefing narrative (existing — may mention events)      │
└─────────────────────────────────────────────────────────┘
```

Place the new row **above** "Current Regime" so fragility is visible before regime dimensions.

---

## API call pattern

```javascript
// Parallel fetch on macro page load
const [preCatalyst, postRegime, calendar] = await Promise.all([
  fetch('/api/v1/macro/events/pre-catalyst').then(r => r.json()),
  fetch('/api/v1/macro/events/post-regime').then(r => r.json()),
  fetch('/api/v1/macro/events/calendar?days=21').then(r => r.json()),
]);
```

**Streamlit example:**

```python
import requests

base = os.environ.get("MACRO_API_BASE", "http://localhost:8506/api/v1")
pre = requests.get(f"{base}/macro/events/pre-catalyst", timeout=10).json()
post = requests.get(f"{base}/macro/events/post-regime", timeout=10).json()

if pre.get("active") and pre.get("fragility_score"):
    st.warning(f"{pre['fragility_score']} — {pre['upcoming_event']['type']} in {pre['days_to_event']}d")
```

Alternatively read from local JSON (Streamlit today):

```python
pre = data.get("pre_catalyst", {})
post = data.get("post_event_regime", {})
```

Use API when the UI is decoupled from `runic_output.json` on disk.

---

## Transition type display labels

| API value | UI label | Short meaning |
|-----------|----------|----------------|
| `LIQUIDITY_SHOCK` | Liquidity shock | VIX spike + credit stress + USD rally |
| `FISCAL_DOMINANCE_FEAR` | Fiscal dominance fear | Widening HY, weaker USD, long yields lead |
| `CREDIBILITY_RESTORED` | Credibility restored | Tighter credit, stronger USD, short rates lead |
| `BEAR_FLATTEN` | Bear flatten | Curve flattens without credit stress |
| `BULL_STEEPEN` | Bull steepen | Curve steepens (growth/fiscal optimism) |

Use color coding: red for `LIQUIDITY_SHOCK` / `FISCAL_DOMINANCE_FEAR`, amber for fragility-only, green/neutral for `CREDIBILITY_RESTORED` when appropriate for your design system.

---

## What NOT to change

| Endpoint | Reason |
|----------|--------|
| `GET /macro/regime` | Stable contract — no `pre_catalyst` / `post_event_regime` keys |
| `GET /macro/status` | Header strip unchanged |
| `GET /macro/overview/kpis` | KPI cards unchanged |
| `GET /macro/combo-c/cancel` | `upcoming_releases` stays CPI/PPI only |

Bulk consumers may continue using `GET /macro/runic/nightly` which includes both blocks in the full JSON.

---

## Refresh cadence

- Data updates after **nightly macro run** (`scripts/run_macro_nightly.py`, ~18:00 ET weekdays)
- Calendar DB sync runs on each data pull; optional manual: `python scripts/sync_macro_calendar.py`
- Post-event card is only meaningful for **48 hours** after a release — hide stale UI if `active: false`

---

## Testing checklist

- [ ] Pre-catalyst card hidden when `active: false`
- [ ] Fragility badge only when `fragility_score` is non-null (≥ 4 near-threshold vars)
- [ ] Post-event card shows `transition_type` only when `regime_transition: true`
- [ ] Calendar lists FOMC/NFP after `FRED_API_KEY` sync
- [ ] Existing regime/combo panels unchanged
- [ ] 404 handled if nightly JSON missing (show "Run nightly macro job")

---

## Reference

- API docs: [get-pre-catalyst.md](../services/macro/endpoints/get-pre-catalyst.md), [get-post-event-regime.md](../services/macro/endpoints/get-post-event-regime.md), [get-scheduled-events-calendar.md](../services/macro/endpoints/get-scheduled-events-calendar.md)
- Config thresholds: `macro_intelligence/CONFIG.yaml` → `scheduled_events`
