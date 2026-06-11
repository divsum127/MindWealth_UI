# GET /api/v1/chatbot/jobs/{job_id}

## Summary

Poll job status and result.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/jobs/{job_id}`
- **operationId:** `get_chat_job`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`JobStore.get`

## Request

Path: job_id

## Response

Job object with flow_steps, result, error

## Example

```bash
curl -s http://51.20.53.218:8506/api/v1/chatbot/jobs/{job_id} | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
