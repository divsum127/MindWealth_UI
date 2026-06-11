#!/usr/bin/env bash
# Install mindwealth-api.service, reload systemd, enable and start the service, show status.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="mindwealth-api.service"
SERVICE_SRC="${SCRIPT_DIR}/${SERVICE_NAME}"
VENV_UVICORN="${REPO_ROOT}/.venv/bin/uvicorn"

if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "Missing ${SERVICE_SRC}" >&2
  exit 1
fi

if [[ ! -x "${VENV_UVICORN}" ]]; then
  echo "uvicorn not found at ${VENV_UVICORN}. Create the venv and run: pip install -r requirements.txt" >&2
  exit 1
fi

sudo cp "${SERVICE_SRC}" "/etc/systemd/system/${SERVICE_NAME}"
sudo systemctl daemon-reload
sudo systemctl enable --now mindwealth-api.service
sudo systemctl status mindwealth-api.service
