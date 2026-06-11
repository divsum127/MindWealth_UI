# DELETE /api/v1/monitored-trades/{trade_id}

## Summary

Remove a monitored trade by ID.

## HTTP

- **Method:** `DELETE`
- **Path:** `/api/v1/monitored-trades/{trade_id}`
- **operationId:** `delete_monitored_trade`
- **Status:** implemented
- **Typical status:** 204, 404

## Maps to

`src/utils/monitored_trades.remove_trade_from_monitored()`

## Request

Path: `trade_id`

## Response

204: no body on success

404: trade not found

## Example

```bash
curl -s -X DELETE http://51.20.53.218:8506/api/v1/monitored-trades/TEST-1 -w "\nHTTP %{http_code}\n"
```
