#!/usr/bin/env bash
# Pull-only deploy for prod clone (chatbot-prod). Never commit from prod.
set -euo pipefail
ROOT="/home/ubuntu/uiv2/prod/MindWealth_UI"
cd "$ROOT"
git fetch upstream
git checkout chatbot-prod
git pull upstream chatbot-prod
"$ROOT/.venv/bin/pip" install -r requirements.txt
sudo cp "$ROOT/scripts/mindwealth-api.service" /etc/systemd/system/mindwealth-api.service
sudo systemctl daemon-reload
sudo systemctl restart mindwealth-api.service
curl -s http://127.0.0.1:8506/api/v1/health | python3 -m json.tool
