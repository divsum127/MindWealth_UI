# SSI (Sentiment SuperIndex) — System Notes

## Purpose

SSI writes **`positioning.json`** for C++ at market open (~08:00 ET). Runic reads it for `ssi_multiplier` and Combo F + SSI `vix_bypass`.

## Jobs

```bash
python scripts/run_ssi_daily.py
python scripts/run_ssi_threshold_sweep.py
python scripts/run_ssi_threshold_sweep.py --write-config  # after Rohit review
```

## Inputs (no VXTS in Layer 2 combo overlap — VIX ratio used for SSI composite only)

| Input | Source |
|-------|--------|
| HYG/LQD | Yahoo |
| DBMF 21d beta vs SPY | Yahoo |
| CNN Fear & Greed | CNN API / cache |
| VIX3M/VIX | Yahoo (SSI level weight) |

## Layer 2 multipliers

| Status | Count | Multiplier |
|--------|-------|------------|
| CONFIRMED | ≥2 of 4 | 1.20 |
| PARTIAL | 1 of 4 | 1.00 |
| UNCONFIRMED | 0 of 4 | 0.80 |

## C++ contract (addendum)

```cpp
auto ssi = read_json("positioning.json");
float size_mult = ssi["signals"]["long"]["size_mult"];
```

When `runic_output.json` has `vix_bypass: true`, C++ ignores SSI size reduction.

## Paths

- Config: `macro_intelligence/SSI_CONFIG.yaml`
- Output: `macro_intelligence/output/positioning.json` (`SSI_POSITIONING_JSON`)
- DB: `macro_intelligence/data/ssi/ssi.db`
- Validation artifacts: `macro_intelligence/analysis/ssi_validation/`
- Validation docs: `docs/ssi_validation/` (run `scripts/run_ssi_validation_suite.py`)

## Validation suite

All 15 Divyanshu tests + Friday checklist:

```bash
.venv/bin/python scripts/run_ssi_validation_suite.py
```

Requires `MINDWEALTH_ROOT=/home/ubuntu/MindWealth` for tests 5 (TP/SL) and 15 (SBI breadth). See `docs/ssi_validation/README.md`.

## Ahil handoff

Provide sample `positioning.json` from `run_ssi_daily.py` for C++ field sign-off.
