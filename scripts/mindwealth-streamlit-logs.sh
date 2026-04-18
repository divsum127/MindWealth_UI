#!/usr/bin/env bash
# Follow MindWealth Streamlit service logs (Ctrl+C to exit).
set -euo pipefail
exec journalctl -u mindwealth-streamlit.service -f
