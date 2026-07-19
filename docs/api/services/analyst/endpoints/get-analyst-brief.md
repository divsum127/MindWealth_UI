# GET /api/v1/analytics/analyst/brief

## Summary

Short dashboard analyst snippet derived from macro narrative or top degradation signal.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/analytics/analyst/brief`
- **operationId:** `get_analyst_brief`
- **Status:** implemented (v1.8.0)
- **Typical status:** 200

## Maps to

`analyst_service.get_analyst_brief()` — prefers `macro_service.get_narrative()`, falls back to degradation template.

## Response

### 200 OK

```json
{
  "snippet": "Tactical tight money with strategic easy money backdrop.",
  "source": "narrative",
  "updated_at": "2026-06-18"
}
```

| `source` | Meaning |
|----------|---------|
| `narrative` | First sentence from macro nightly narrative |
| `template` | Built from top degradation alert |
| `empty` | No data available |

## Example

```bash
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8507/api/v1/analytics/analyst/brief | jq
```
