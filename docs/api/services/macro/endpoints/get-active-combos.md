# GET /api/v1/macro/combo/active

## Summary

Dominant Runic signal plus active and watch combo lists.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/macro/combo/active`
- **operationId:** `get_active_combos`
- **Status:** implemented
- **Typical status:** 200, 404

## Maps to

Subset of `load_runic_nightly()`: `dominant_signal`, `active_combos`, `watch_combos`

## Response

200:

```json
{
  "date": "2026-05-26",
  "dominant_signal": "...",
  "active_combos": [],
  "watch_combos": []
}
```

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/macro/combo/active | jq '.active_combos | length'
```
