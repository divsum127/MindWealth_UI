# GET /api/v1/macro/sentiment/positioning

## Summary

SSI (Sentiment Strength Index) positioning JSON.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/macro/sentiment/positioning`
- **operationId:** `get_ssi_positioning`
- **Status:** implemented
- **Typical status:** 200, 404

## Maps to

`macro_intelligence/output/positioning.json` via `reports_service.load_positioning()`

## Response

200: full positioning object (`ssi_level`, `ssi_percentile_5y`, `layer2_status`, `inputs`, etc.)

404: positioning file not found

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/macro/sentiment/positioning | jq '.ssi_level'
```

## Notes

Also surfaced in merged form via [get-sentiment-layers.md](../../analytics/endpoints/get-sentiment-layers.md).
