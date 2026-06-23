# <METHOD> /api/v1/<service>/<path>

## Summary

One sentence: what this endpoint returns and why a client would call it.

## HTTP

- **Method:** `<GET|POST|PUT|DELETE>`
- **Path:** `/api/v1/<service>/<path>`
- **operationId:** `<uniqueCamelCaseId>`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`<module>.<function>()` in `<MindWealth|MindWealth_UI>` — brief note on data source (CSV, JSON, DB, live compute).

## Request

### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `ticker` | string | Uppercase symbol; `/` as `_` |

### Query parameters

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `report_date` | string | latest | `YYYY-MM-DD` |

### Body (POST/PUT only)

```json
{
  "field": "value"
}
```

## Response

200:

```json
{
  "records": [],
  "row_count": 0
}
```

### Error responses

| Code | When |
|------|------|
| 400 | Invalid date or parameter |
| 404 | Ticker / report / file not found |
| 502 | Upstream fetch failure |

## Example

```bash
curl -s http://localhost:8606/api/v1/<service>/<path> | jq
```

With API key:

```bash
curl -s http://localhost:8606/api/v1/<service>/<path> \
  -H "X-API-Key: $API_KEY" | jq
```

## Notes

- Link related endpoints or Streamlit pages.
- Document latency expectations if > 1s.
- Document required env vars or preconditions (e.g. conviction record must exist).
