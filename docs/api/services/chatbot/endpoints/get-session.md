# GET /api/v1/chatbot/sessions/{session_id}

## Summary

Session metadata and summary.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/sessions/{session_id}`
- **operationId:** `get_chat_session`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`SessionManager + ChatbotEngine.get_session_summary`

## Request

Path: session_id

## Response

Metadata object

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/chatbot/sessions/{session_id} | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
