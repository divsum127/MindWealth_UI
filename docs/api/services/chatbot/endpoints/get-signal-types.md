# GET /api/v1/chatbot/signal-types

## Summary

Allowed signal type catalog.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/signal-types`
- **operationId:** `get_signal_types`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`signal_type_selector`

## Request

None

## Response

allowed, default, descriptions

## Example

```bash
curl -s .../signal-types | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
