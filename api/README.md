# MindWealth API

FastAPI backend for MindWealth services (Conviction Engine + Chatbot). Canonical documentation: **[docs/api/README.md](../docs/api/README.md)**.

Chatbot uses **async jobs** — see [docs/api/services/chatbot/async-jobs.md](../docs/api/services/chatbot/async-jobs.md).

## Quick start

```bash
cd /path/to/MindWealth_UI
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Or: `bash scripts/start_api.sh`

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/api/v1/health

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | `8000` | Listen port (`start_api.sh`) |
| `API_KEY` | (unset) | When set, requires `X-API-Key` header |
| `CORS_ORIGINS` | Streamlit localhost ports | Comma-separated origins |

Streamlit UI is unchanged; run it separately with `streamlit run app.py`.
