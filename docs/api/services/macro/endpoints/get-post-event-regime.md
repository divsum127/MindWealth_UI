# GET /api/v1/macro/events/post-regime

## Summary

Post-event regime reclassification within 48 hours of a CPI, FOMC, or NFP release.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/macro/events/post-regime`
- **operationId:** `get_macro_post_event_regime`
- **Status:** implemented (v1.5.0)
- **Typical status:** 200, 404

## Maps to

`post_event_regime` block from `macro_intelligence/output/runic_output.json` (computed nightly by `detect_post_event_transition()`).

## Response fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Nightly as-of date |
| `active` | boolean | True when inside 48h post-event window |
| `regime_transition` | boolean | True when ≥ 2 variables crossed RARE thresholds |
| `transition_type` | string \| null | One of: `LIQUIDITY_SHOCK`, `FISCAL_DOMINANCE_FEAR`, `CREDIBILITY_RESTORED`, `BEAR_FLATTEN`, `BULL_STEEPEN` |
| `event` | object \| null | `{ type, date }` — triggering release |
| `hours_since_event` | float \| null | Hours from scheduled release time to nightly run |
| `pre_date` | string | Last trading day before event (when active) |
| `post_date` | string | Latest trading day in window (when active) |
| `variables_crossed` | string[] | Variable IDs that crossed thresholds |
| `combos_changed` | boolean | Named combo set changed pre vs post |
| `combo_diff` | string[] | Combo letters added or removed (e.g. `["D"]`) |
| `metrics` | object | Event-window deltas: `hy_bps`, `usd_pct`, `dgs2_bps`, `dgs10_bps`, `vix_pts`, `curve_bps`, etc. |

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/macro/events/post-regime | jq .
```

```json
{
  "date": "2026-06-18",
  "active": true,
  "regime_transition": true,
  "transition_type": "CREDIBILITY_RESTORED",
  "event": {"type": "FOMC", "date": "2026-06-17"},
  "hours_since_event": 28.0,
  "variables_crossed": ["HY", "CNH", "CURVE"],
  "metrics": {
    "hy_bps": -8.0,
    "usd_pct": 0.4,
    "dgs2_bps": 6.0,
    "dgs10_bps": 1.0,
    "curve_bps": -5.0
  }
}
```

## Notes

- Does **not** modify `GET /macro/regime` — use this endpoint for post-event UI.
- Transition types are mutually exclusive (priority-ordered classifier).
