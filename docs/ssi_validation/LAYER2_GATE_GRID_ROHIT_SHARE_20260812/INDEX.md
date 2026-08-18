# Layer 2 gate 2-D grid — Rohit share pack

**Test 22** — joint sweep of `gate_z_min` × `min_confirmed` on production **6-gate** Layer 2 logic.

| Field | Value |
|-------|-------|
| Window | 2015-01-01 → 2026-08 (3,872 trading days) |
| z thresholds | 0, 0.25, 0.5, 0.75, 1.0 |
| min_confirmed | 1, 2, 3, 4 of 6 |
| Long gate | SSI 5y pctile ≤ 20 |
| Production today | `gate_z_min=0.5`, `min_confirmed=2` |

## Files

| What | Path |
|------|------|
| **Report (markdown)** | [22_layer2_gate_grid_report.md](22_layer2_gate_grid_report.md) |
| **Report (PDF)** | [pdf/22_layer2_gate_grid_report_20260812.pdf](pdf/22_layer2_gate_grid_report_20260812.pdf) |
| **Summary grid CSV** (20 cells, hit rate / freq / FP) | [csv/22_layer2_gate_grid_summary.csv](csv/22_layer2_gate_grid_summary.csv) |
| **Forward returns CSV** (all horizons, long+gate vs FP) | [csv/22_layer2_gate_grid_forward_returns.csv](csv/22_layer2_gate_grid_forward_returns.csv) |
| Full JSON artifact | [data/22_layer2_gate_grid_20260811.json](data/22_layer2_gate_grid_20260811.json) |
| How to share | [SHARE.md](SHARE.md) |

## Production cell headline (z≥0.5, min=2)

- Long gate + confirmed: **n=160**
- 3m hit rate: **41.25%**
- 3m avg return (long+gate): **−1.20%**
- Signal frequency: **50.2%** of days
- False positives: **n=1,785** (77.5% 3m win)

## Decision needed

Keep defaults, tighten (z↑ or min↑), or treat Layer 2 as display/sizing overlay only?
