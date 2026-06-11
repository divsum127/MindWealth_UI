# GET /api/v1/health

## Summary

Returns API version and conviction store path/writability.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/health`
- **operationId:** `get_health`
- **Status:** implemented

## Maps to

`api.main.health` — checks `CONVICTION_STORE_DIR` from `src/config_paths.py`.

## Response

### 200 OK

```json
{
  "status": "ok",
  "version": "1.2.0",
  "conviction_store": "/path/to/conviction_store",
  "conviction_store_writable": true
}
```

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/health | jq
```

## Notes

- Use for load balancer health checks.
- `conviction_store_writable` performs a transient write/delete test file in the store directory.
