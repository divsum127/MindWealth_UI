# GET /api/v1/macro/runic/nightly

## Summary

Full Runic Macro Intelligence nightly output JSON.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/macro/runic/nightly`
- **operationId:** `get_runic_nightly`
- **Status:** implemented
- **Typical status:** 200, 404

## Maps to

`macro_intelligence/output/runic_output.json` via `reports_service.load_runic_nightly()`

## Response

200: full nightly JSON (regime, combos, variables dashboard, dominant signal, etc.)

404: runic output file not found on disk

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/macro/runic/nightly | jq '.date'
```

## Notes

See [Macro overview](../README.md) and `docs/MACRO_INTELLIGENCE_MASTER.md`.
