# POST /api/v1/chatbot/signal-types/preview

## Summary

Preview AI signal type selection.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/chatbot/signal-types/preview`
- **operationId:** `preview_signal_types`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`ChatbotEngine.determine_signal_types`

## Request

{"message","session_id"?}

## Response

signal_types, reasoning

## Example

```bash
curl -s -X POST .../signal-types/preview -d '{"message":"breadth today"}'
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
