# GET /api/v1/macro/events/calendar

## Summary

Upcoming scheduled macro release dates — CPI, FOMC, and NFP — from `pending_releases`.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/macro/events/calendar`
- **operationId:** `get_macro_scheduled_events_calendar`
- **Query:** `days` (optional, default 21, max 90) — forward horizon
- **Status:** implemented (v1.5.0)
- **Typical status:** 200

## Data sources

| Event | Primary source |
|-------|----------------|
| CPI | Trading Economics + BLS actuals; FRED release_id=10 for dates |
| FOMC | FRED release_id=19 (FOMC Press Release) |
| NFP | FRED release_id=50 (Employment Situation) |

Requires `FRED_API_KEY` for FOMC/NFP date sync. See `scripts/sync_macro_calendar.py`.

## Response

```json
{
  "as_of": "2026-06-18",
  "days_forward": 21,
  "event_types": ["CPI", "FOMC", "NFP"],
  "events": [
    {
      "release_type": "FOMC",
      "release_date": "2026-06-25",
      "consensus": null,
      "actual": null,
      "source": "fred_release_calendar"
    }
  ]
}
```

## Example

```bash
curl -s "http://51.20.53.218:8506/api/v1/macro/events/calendar?days=30" | jq '.events | length'
```

## Notes

- Reads SQLite `pending_releases`; does not require `runic_output.json`.
- `GET /macro/combo-c/cancel` `upcoming_releases` remains CPI/PPI only (unchanged).
