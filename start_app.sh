#!/bin/bash

APP_DIR="/home/ubuntu/uiv2/MindWealth_UI"
VENV_STREAMLIT="$APP_DIR/.venv/bin/streamlit"
PORT=8504

cd "$APP_DIR"
exec "$VENV_STREAMLIT" run app.py \
    --server.port "$PORT" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false
