# Getting Started

## Prerequisites

- Python 3.11+ (see `runtime.txt`)
- Virtual environment with dependencies from `requirements.txt`

## Install and run

```bash
cd /path/to/MindWealth_UI
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the helper script:

```bash
bash scripts/start_api.sh
```

## Verify the server

```bash
curl -s http://localhost:8000/api/v1/health | jq
```

Expected:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "conviction_store": "/path/to/conviction_store",
  "conviction_store_writable": true
}
```

## Example: list overlay dates

```bash
curl -s http://localhost:8000/api/v1/conviction/overlays/dates | jq
```

## Example: evaluate a signal

```bash
curl -s -X POST http://localhost:8000/api/v1/conviction/signals/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "technical_signal": "BUY",
    "signal_timeframe": "long"
  }' | jq
```

Requires an existing conviction record for the ticker (run daily pipeline or `POST .../recalculate` first).

## Export OpenAPI snapshot

After changing routes:

```bash
python scripts/export_openapi.py
```

Updates `docs/api/openapi/mindwealth-v1.json`.

## Run alongside Streamlit

```bash
# Terminal 1
streamlit run app.py

# Terminal 2
bash scripts/start_api.sh
```

No port conflict: Streamlit defaults to 8504/8509; API uses 8000.
