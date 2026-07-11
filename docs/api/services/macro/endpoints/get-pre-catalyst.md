# GET /api/v1/macro/events/pre-catalyst

## Summary

Pre-catalyst fragility intelligence — counts macro variables in near-threshold percentile bands before an upcoming CPI, FOMC, or NFP release.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/macro/events/pre-catalyst`
- **operationId:** `get_macro_pre_catalyst`
- **Status:** implemented (v1.5.0)
- **Typical status:** 200, 404

## Maps to

`pre_catalyst` block from `macro_intelligence/output/runic_output.json` (computed nightly by `compute_pre_catalyst_fragility()`).

## Response fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Nightly as-of date (YYYY-MM-DD) |
| `active` | boolean | True when a CPI/FOMC/NFP event is within 7 calendar days |
| `upcoming_event` | object \| null | `{ type, date }` — next scheduled event |
| `days_to_event` | int \| null | Calendar days until event |
| `near_threshold_count` | int | Variables in 60th–79th or 21st–40th percentile |
| `near_threshold_vars` | string[] | Variable IDs (e.g. `NFCI`, `HY`, `VIX`) |
| `fragility_score` | string \| null | `"HIGH — REGIME SENSITIVE TO CATALYST"` when count ≥ 4 |

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/macro/events/pre-catalyst | jq .
```

```json
{
  "date": "2026-06-18",
  "active": true,
  "upcoming_event": {"type": "FOMC", "date": "2026-06-25"},
  "days_to_event": 7,
  "near_threshold_count": 5,
  "near_threshold_vars": ["NFCI", "HY", "VIX", "CURVE", "CFTC"],
  "fragility_score": "HIGH — REGIME SENSITIVE TO CATALYST"
}
```

## Notes

- Does **not** modify `GET /macro/regime` — use this endpoint for fragility UI.
- Full nightly JSON also includes `pre_catalyst` via `GET /macro/runic/nightly`.
