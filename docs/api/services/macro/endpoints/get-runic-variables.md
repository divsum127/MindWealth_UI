# GET /api/v1/macro/runic/variables/current

## Summary

Current Runic regime and variables dashboard subset.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/macro/runic/variables/current`
- **operationId:** `get_runic_variables_current`
- **Status:** implemented
- **Typical status:** 200, 404

## Maps to

Subset of `load_runic_nightly()`: `date`, `regime`, `variables_dashboard`

## Response

200:

```json
{
  "date": "2026-05-26",
  "regime": {},
  "variables_dashboard": []
}
```

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/macro/runic/variables/current | jq '.regime'
```
