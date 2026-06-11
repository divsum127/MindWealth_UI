# GET /api/v1/signals/shortlist

## Summary

Claude shortlist report: markdown from `.txt` plus optional CSV records.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/signals/shortlist`
- **operationId:** `get_claude_shortlist`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`reports_service.get_shortlist_report()` — reads latest `*_claude_signals_report.txt` with CSV fallback.

## Request

None

## Response

200:

```json
{
  "report_date": "2026-05-20",
  "text_file": "/path/to/claude_signals_report.txt",
  "csv_file": "/path/to/claude_signals_report.csv",
  "markdown": "...",
  "row_count": 0,
  "records": []
}
```

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/signals/shortlist | jq '.markdown | length'
```

## Notes

When `claude_signals_report.csv` is empty, `markdown` is populated from the `.txt` file. Related: [overlay-signal-file.md](../../conviction/endpoints/overlay-signal-file.md).
