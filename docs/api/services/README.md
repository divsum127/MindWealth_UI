# API Services Catalog

Master index of all REST services in MindWealth_UI. **API version 1.8.0**.

| Service | Status | Router prefix | Endpoints | Documentation |
|---------|--------|---------------|-----------|---------------|
| [Health](health/) | Implemented | `/api/v1/health` | 1 | [get-health.md](health/get-health.md) |
| [Conviction Engine](conviction/) | Implemented | `/api/v1/conviction` | 15 | [README](conviction/README.md) + [endpoints/](conviction/endpoints/) |
| [Chatbot](chatbot/) | Implemented | `/api/v1/chatbot` | 22 | [README](chatbot/README.md) + [endpoints/](chatbot/endpoints/) |
| [Signals / Reports](signals/) | Implemented | `/api/v1/signals` | 5+ | [README](signals/README.md) + [endpoints/](signals/endpoints/) |
| [Monitored Trades](monitored-trades/) | Implemented | `/api/v1/monitored-trades` | 3 | [README](monitored-trades/README.md) + [endpoints/](monitored-trades/endpoints/) |
| [Virtual Trading](virtual-trading/) | Implemented | `/api/v1/virtual-trading` | 3 | [README](virtual-trading/README.md) + [endpoints/](virtual-trading/endpoints/) |
| [Analytics](analytics/) | Implemented | `/api/v1/analytics` | 7 | [README](analytics/README.md) + [endpoints/](analytics/endpoints/) |
| [Macro / Runic](macro/) | Implemented | `/api/v1/macro` | 20+ | [README](macro/README.md) + [endpoints/](macro/endpoints/) |
| [AI Analyst / Overwatch](analyst/) | Implemented | `/analytics/analyst`, `/overwatch`, `/system` | 5 | [README](analyst/README.md) + [endpoints/](analyst/endpoints/) |

## Quick reference by UI area

| Streamlit / Alpha Terminal page | Primary API routes |
|---------------------------------|-------------------|
| Analysis / signal reports | `/signals/reports`, `/signals/shortlist` |
| Virtual portfolio | `/virtual-trading/long`, `/short`, `/portfolio` |
| Monitored trades | `/monitored-trades` |
| Dashboard sigma | `/analytics/sigma` |
| Sentiment / SSI | `/analytics/sentiment/layers`, `/macro/sentiment/positioning` |
| Performance | `/analytics/performance` |
| Overwatch YTD | `/analytics/portfolio-ytd` |
| AI Analyst panel | `/analytics/analyst/alerts`, `/overwatch/stream` |
| Runic macro | `/macro/runic/nightly`, `/combo/active`, `/macro/events/pre-catalyst`, `/macro/events/post-regime` |
| Conviction overlay | `/conviction/overlays/{date}/score-sheet` |
| Chatbot | `/chatbot/sessions`, `/chatbot/jobs` |

## Conviction & chatbot

See [conviction/README.md](conviction/README.md) and [chatbot/README.md](chatbot/README.md) for full endpoint tables.
