# Macro / Runic API

**Status:** implemented (v1.5.0)

**Router:** `api/routers/macro.py`

**Source:** `macro_intelligence/output/runic_output.json`, `positioning.json`, SQLite `pending_releases`

**Domain docs:** [`docs/MACRO_INTELLIGENCE_MASTER.md`](../../../MACRO_INTELLIGENCE_MASTER.md)

**Frontend integration:** [`docs/api/frontend/macro-scheduled-events-integration.md`](../../frontend/macro-scheduled-events-integration.md)

## Endpoints

### Core / legacy

| Method | Path | Doc |
|--------|------|-----|
| GET | `/macro/runic/nightly` | [get-runic-nightly.md](endpoints/get-runic-nightly.md) |
| GET | `/macro/runic/variables/current` | [get-runic-variables.md](endpoints/get-runic-variables.md) |
| GET | `/macro/combo/active` | [get-active-combos.md](endpoints/get-active-combos.md) |
| GET | `/macro/sentiment/positioning` | [get-positioning.md](endpoints/get-positioning.md) |

### Dashboard tabs (v1.3.0+)

| Method | Path | operationId |
|--------|------|-------------|
| GET | `/macro/status` | `get_macro_status_bar` |
| GET | `/macro/overview/kpis` | `get_macro_overview_kpis` |
| GET | `/macro/regime` | `get_macro_regime` |
| GET | `/macro/variables/heatmap` | `get_variables_heatmap` |
| GET | `/macro/combos` | `list_named_combos` |
| GET | `/macro/combos/{combo_id}` | `get_named_combo_detail` |
| GET | `/macro/combo-c/cancel` | `get_combo_c_cancel_tracker` |
| GET | `/macro/combo-f/window` | `get_combo_f_window` |
| GET | `/macro/analogs/{combo_id}` | `get_combo_analog_table` |
| GET | `/macro/narrative` | `get_nightly_narrative` |
| GET | `/macro/persistence` | `get_persistence_signals` |
| GET | `/macro/data/freshness` | `get_data_freshness` |
| POST | `/macro/run-nightly` | `trigger_nightly_run` |

### Scheduled macro events (v1.5.0) — **new, no changes to existing responses**

| Method | Path | Doc |
|--------|------|-----|
| GET | `/macro/events/pre-catalyst` | [get-pre-catalyst.md](endpoints/get-pre-catalyst.md) |
| GET | `/macro/events/post-regime` | [get-post-event-regime.md](endpoints/get-post-event-regime.md) |
| GET | `/macro/events/calendar` | [get-scheduled-events-calendar.md](endpoints/get-scheduled-events-calendar.md) |

### SSI (v1.4.0)

| Method | Path |
|--------|------|
| GET | `/macro/ssi/summary` |
| GET | `/macro/ssi/history` |
| GET | `/macro/ssi/multiplier` |

All paths are prefixed with `/api/v1`.

## Backward compatibility

v1.5.0 adds **three new routes only**. Existing endpoints (`/macro/regime`, `/macro/status`, `/macro/combo-c/cancel`, etc.) keep the same response shape. Event intelligence is also present in the full nightly JSON (`pre_catalyst`, `post_event_regime` keys) for clients that already consume `/macro/runic/nightly`.

## Errors

| Status | Cause |
|--------|-------|
| 404 | Runic output file not found (pre-catalyst / post-regime endpoints) |

## Related

Merged SSI + sentiment view: [get-sentiment-layers.md](../analytics/endpoints/get-sentiment-layers.md)
