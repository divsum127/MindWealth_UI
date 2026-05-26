# API Services Catalog

Master index of all REST services in MindWealth_UI.

| Service | Status | Router prefix | Source module |
|---------|--------|---------------|---------------|
| [Health](health/) | Implemented | `/api/v1/health` | `api/main.py` |
| [Conviction Engine](conviction/) | Implemented | `/api/v1/conviction` | `src/conviction_engine/` |
| [Chatbot](chatbot/) | Implemented | `/api/v1/chatbot` | `chatbot/chatbot_engine.py` |
| [Signals / Reports](signals/) | Planned | `/api/v1/signals` | `trade_store/US`, `src/pages/analysis_page.py` |
| [Monitored Trades](monitored-trades/) | Planned | `/api/v1/monitored-trades` | `src/utils/monitored_trades.py` |
| [Virtual Trading](virtual-trading/) | Planned | `/api/v1/virtual-trading` | `trade_store/US/virtual_trading_*.csv` |
| [Analytics](analytics/) | Planned | `/api/v1/analytics` | `src/pages/breadth_page.py`, `performance_page.py` |

## Conviction endpoints (implemented)

See [conviction/README.md](conviction/README.md) and [conviction/endpoints/](conviction/endpoints/).
