# MindWealth Signals MasterSpec — Implementation Status v3

**Date:** 2026-06-22  
**Reference:** `additional_details.md`, `doubts.md`, `MindWealth_Signals_MasterSpec.pdf` (external)  
**Core implementation repo:** `/home/ubuntu/MindWealth`  
**UI repo:** `/home/ubuntu/uiv2/git/MindWealth_UI`

---

## Summary

| Area | Status |
|------|--------|
| Divyanshu tasks (A1, B1–B2, C, D, E1, F2, G1–G3) | **DONE** in MindWealth core |
| Streamlit bubble chart (New / Outstanding / Claude) | **DONE** in MindWealth_UI (2026-06-22) |
| Conviction fields in Claude JSON payload (F1 / Gate A2c) | **DONE** — overlay merge in `send_email.py` |
| Ahil A2 (OscillatorDelta entry timing) | **NOT STARTED** |
| Ahil A3 (IBKR B&H CAGR window) | **NOT STARTED** |
| R_ref table revision | **BLOCKED** — see `doubts.md` #1 |

---

## Completed (MindWealth core)

See `status_v2.md` for file-level detail. Key modules:

- `helper_functions/claude_lateness_metrics.py` — asset class, E[R], signal_alpha, R:R, composite_score, reward_remaining_pct
- `constant.py` — GOOD_SIGNAL_QUERY gates A2a/A2e, composite formula, surface_json schema
- `send_email.py` — BT_WR_FOOTNOTE, regime context, conviction overlay merge, email columns
- `virtual_trading.py` — ASSET_CLASS_MAP universe warning
- `tests/test_signals_masterspec_g3.py` — 6 smoke tests (all pass)

---

## Completed (MindWealth_UI — 2026-06-22)

### Bubble chart — Signal Quality Composite vs Lifecycle

| File | Purpose |
|------|---------|
| `src/utils/surface_json_parser.py` | Parse `<surface_json>` from Claude txt (legacy `quality_score` alias) |
| `src/utils/signal_quality.py` | Compute fields via MindWealth `enrich_signal_dict` |
| `src/components/quality_bubble_chart.py` | Plotly bubble chart (Y=composite, X=timeliness/days) |
| `src/pages/analysis_page.py` | Chart on New Signals, Outstanding Signals, All Signal Report |
| `src/pages/text_file_page.py` | Chart on Claude page (surface_json → CSV fallback) |

---

## Residual gaps

| Gap | Owner | Notes |
|-----|-------|-------|
| R_ref / ER_GATE_MIN revision | Spec owner | `additional_details.md` says table too aggressive; values TBD |
| Ahil A2 / A3 | Ahil | Independent track |
| Python-authored surface_json | TBD | Claude may still emit old `quality_score` — see doubts #5 |
| Conviction cron ordering | Ops | Overlay must exist before email run — see doubts #6 |
| MasterSpec PDF in repo | Docs | PDF not checked into `instruction_docs/` |

---

## Verification

```bash
cd /home/ubuntu/MindWealth
python3 -m pytest tests/test_signals_masterspec_g3.py -v
```

---

*Supersedes `status.md` (2026-06-19 snapshot). Use this file + `doubts.md` for current state.*
