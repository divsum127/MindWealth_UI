# Signals / Reports API

**Status:** implemented (v1.2.0)

**Router:** `api/routers/signals.py`

**Source:** `trade_store/US/`, `api/services/reports_service.py`

**UI reference:** Streamlit analysis pages reading trade-store CSVs

## Endpoints

| Method | Path | Doc |
|--------|------|-----|
| GET | `/signals/reports` | [list-reports.md](endpoints/list-reports.md) |
| GET | `/signals/reports/{report_name}/latest` | [get-latest-report.md](endpoints/get-latest-report.md) |
| GET | `/signals/reports/{report_name}/{report_date}` | [get-dated-report.md](endpoints/get-dated-report.md) |
| GET | `/signals/shortlist` | [get-shortlist.md](endpoints/get-shortlist.md) |

All paths are prefixed with `/api/v1`.

## Report name slugs

Use slug or base filename in `{report_name}`:

| Slug | CSV file |
|------|----------|
| `new-signals` | `new_signal.csv` |
| `outstanding-signals` | `outstanding_signal.csv` |
| `target-signals` | `target_signal.csv` |
| `all-signal` | `all_signal.csv` |
| `breadth` / `sbi` | `breadth.csv` |
| `sigma` | `sigma.csv` |
| `sentiment` | `sentiment.csv` |
| `combined-performance` | `combined_performance_report.csv` |
| `claude-shortlist` | `claude_signals_report.csv` |
| `f-stack` | `F-Stack-Analyzer.csv` |

## Notes

- Empty or 1-byte CSV files are handled gracefully (no 500 errors).
- Claude overlay via conviction: [overlay-signal-file.md](../conviction/endpoints/overlay-signal-file.md).
