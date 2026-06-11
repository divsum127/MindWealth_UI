# GET /api/v1/conviction/overlays/{report_date}/summary

## Summary

Aggregate metrics: cancel buy, max conviction, yield traps.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/conviction/overlays/{report_date}/summary`
- **operationId:** `get_overlay_summary`
- **Status:** implemented

## Maps to

`formatting.summarize_overlay()`

## Request

Path: report_date

## Response

200: {total_signals, applicable, cancel_buy, max_conviction, yield_traps, tactical_plus}

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/conviction/overlays/2026-05-20/summary | jq
```

## Notes

See [Conviction Engine overview](../README.md) and [fundamentals doc](../../../../documentation/conviction_engine_fundamentals.md).
