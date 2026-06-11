# GET /api/v1/chatbot/sessions

## Summary

List sessions with metadata.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/sessions`
- **operationId:** `list_chat_sessions`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`SessionManager.list_all_sessions`

## Request

Query: sort_by, search, limit

## Response

Array of session summaries

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/chatbot/sessions | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
