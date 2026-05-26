# POST /api/v1/chatbot/sessions/{session_id}/flag

## Summary

Export flagged user/assistant pair for debugging.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/chatbot/sessions/{session_id}/flag`
- **operationId:** `flag_chat_exchange`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`save_flagged_pair`

## Request

{"message_index","notes"?}

## Response

{"path","session_id"}

## Example

```bash
curl -s -X POST .../flag -d '{"message_index":0}'
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
