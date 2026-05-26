# GET /api/v1/chatbot/config

## Summary

Public feature flags and limits (no API keys).

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/config`
- **operationId:** `get_chatbot_config`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`chatbot.config whitelist`

## Request

None

## Response

features, models, limits

## Example

```bash
curl -s .../config | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
