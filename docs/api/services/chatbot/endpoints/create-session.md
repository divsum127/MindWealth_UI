# POST /api/v1/chatbot/sessions

## Summary

Create a new chat session.

## HTTP

- **Method:** `POST`
- **Path:** `/api/v1/chatbot/sessions`
- **operationId:** `create_chat_session`
- **Status:** implemented
- **Typical status:** 201

## Maps to

`SessionManager.create_new_session`

## Request

Body: {"title"?}

## Response

{"session_id","title"}

## Example

```bash
curl -s -X POST http://51.20.53.218:8506/api/v1/chatbot/sessions -H "Content-Type: application/json" -d '{"title":"My chat"}'
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
