# MindWealth API

FastAPI backend for MindWealth services (Conviction Engine + Chatbot). Canonical documentation: **[docs/mindwealth-api-docs/README.md](../docs/mindwealth-api-docs/README.md)**.

Chatbot uses **async jobs** — see [docs/mindwealth-api-docs/services/chatbot/async-jobs.md](../docs/mindwealth-api-docs/services/chatbot/async-jobs.md).

## Production (systemd)

The API runs as a background service on **port 8506**:

```bash
bash scripts/setup-mindwealth-api-systemd.sh   # install + enable + start
sudo systemctl status mindwealth-api.service
sudo systemctl restart mindwealth-api.service
```

- Base URL: http://51.20.53.218:8506/api/v1
- Swagger UI: http://51.20.53.218:8506/docs
- ReDoc: http://51.20.53.218:8506/redoc
- Health: http://51.20.53.218:8506/api/v1/health

Service unit: [`scripts/mindwealth-api.service`](mindwealth-api.service)

## Local development

Use `http://localhost:8506` when running the API on your machine:

```bash
cd /path/to/MindWealth_UI
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
uvicorn api.main:app --host 0.0.0.0 --port 8506 --reload
```

Or: `bash scripts/start_api.sh`

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | `8506` | Listen port (`start_api.sh` and systemd unit) |
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_KEY` | (unset) | When set, requires `X-API-Key` header |
| `CORS_ORIGINS` | Streamlit localhost ports | Comma-separated origins |
| `CHATBOT_JOB_WORKERS` | `2` | Parallel chatbot background jobs |

Streamlit UI is unchanged; run it separately with `streamlit run app.py`.
