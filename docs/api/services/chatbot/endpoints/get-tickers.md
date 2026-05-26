# GET /api/v1/chatbot/tickers

## Summary

Available tickers from signal data.

## HTTP

- **Method:** `GET`
- **Path:** `/api/v1/chatbot/tickers`
- **operationId:** `get_chatbot_tickers`
- **Status:** implemented
- **Typical status:** 200

## Maps to

`ChatbotEngine.get_available_tickers`

## Request

None

## Response

string array

## Example

```bash
curl -s .../tickers | jq
```

## Notes

Async message and preset routes return **202** — poll the job URL. See [async-jobs.md](../async-jobs.md).
