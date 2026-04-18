#!/usr/bin/env bash
# Install mindwealth-streamlit.service, reload systemd, enable and start the service, show status.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="mindwealth-streamlit.service"
SERVICE_SRC="${SCRIPT_DIR}/${SERVICE_NAME}"
VENV_BIN="${REPO_ROOT}/.venv/bin/streamlit"

if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "Missing ${SERVICE_SRC}" >&2
  exit 1
fi

if [[ ! -x "${VENV_BIN}" ]]; then
  echo "Streamlit not found at ${VENV_BIN}. Create the venv and run: pip install -r requirements.txt" >&2
  exit 1
fi

sudo cp "${SERVICE_SRC}" "/etc/systemd/system/${SERVICE_NAME}"
sudo systemctl daemon-reload
sudo systemctl enable --now mindwealth-streamlit.service
sudo systemctl status mindwealth-streamlit.service
