# Getting Started

## Prerequisites

- Python 3.11+ (see `runtime.txt`)
- Virtual environment with dependencies from `requirements.txt`

## Production: systemd (port 8506)

Install and start the background API service:

```bash
cd /path/to/MindWealth_UI
bash scripts/setup-mindwealth-api-systemd.sh
```

Manage the service:

```bash
sudo systemctl status mindwealth-api.service
sudo systemctl restart mindwealth-api.service
sudo journalctl -u mindwealth-api.service -f
```

The service listens on **http://0.0.0.0:8506** (all interfaces).

## Local development

```bash
cd /path/to/MindWealth_UI
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)"
uvicorn api.main:app --host 0.0.0.0 --port 8506 --reload
```

Or use the helper script (no reload):

```bash
bash scripts/start_api.sh
```

## Verify the server

Production (hosted):

```bash
curl -s http://51.20.53.218:8506/api/v1/health | jq
```

Local development:

```bash
curl -s http://localhost:8506/api/v1/health | jq
```

Expected:

```json
{
  "status": "ok",
  "version": "1.2.0",
  "conviction_store": "/path/to/conviction_store",
  "conviction_store_writable": true
}
```

## Example: signals and analytics (v1.2.0)

```bash
BASE=http://51.20.53.218:8506/api/v1

curl -s "$BASE/signals/reports" | jq
curl -s "$BASE/signals/shortlist" | jq '.row_count'
curl -s "$BASE/analytics/sigma" | jq '.row_count'
curl -s "$BASE/macro/runic/nightly" | jq '.date'
curl -s "$BASE/virtual-trading/portfolio" | jq
```

## Example: list overlay dates

```bash
curl -s http://51.20.53.218:8506/api/v1/conviction/overlays/dates | jq
```

## Example: evaluate a signal

```bash
curl -s -X POST http://51.20.53.218:8506/api/v1/conviction/signals/evaluate \
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
# Streamlit UI (separate service or manual)
streamlit run app.py

# API (systemd, already running on 8506)
curl -s http://localhost:8506/api/v1/health
```

No port conflict: Streamlit defaults to 8504/8509; API uses **8506**.
