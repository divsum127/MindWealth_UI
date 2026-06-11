# SSI validation (Divyanshu test list)

Source spec: `macro_intelligence_docs/SSI_OpenQuestions_DivyanshuTestList (1).docx` (Part 9 — 15 tests + Part 10 Friday pulls).

## Run

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
set -a && source .env && set +a

# Full suite (live data; 30–90 min)
.venv/bin/python scripts/run_ssi_validation_suite.py

# Skip MindWealth-dependent tests 5 and 15
.venv/bin/python scripts/run_ssi_validation_suite.py --skip-mindwealth

# Single threshold sweep
.venv/bin/python scripts/run_ssi_threshold_sweep.py
```

## Environment

| Variable | Purpose |
|----------|---------|
| `MINDWEALTH_ROOT` | `/home/ubuntu/MindWealth` — TP/SL and SBI adapters |
| `MINDWEALTH_TRADE_STORE` | Optional; full `trade_store/US` history |

## Outputs

| Path | Contents |
|------|----------|
| `macro_intelligence/analysis/ssi_validation/*.json` | Machine-readable results |
| `docs/ssi_validation/*.md` | Human reports (merged from `_generated/`) |
| `docs/ssi_validation/SIGNOFF.md` | Rohit threshold decisions |

## Reports

- **[../MACRO_INTELLIGENCE_MASTER.md](../MACRO_INTELLIGENCE_MASTER.md)** — Complete build reference: idea, variables, combos, implementation, SSI, thresholds, 40-hour breakdown
- **[SSI_THRESHOLD_JUSTIFICATION.md](SSI_THRESHOLD_JUSTIFICATION.md)** — Single doc: justification for every production threshold (SSI + Layer 2)
- [SSI_OPEN_QUESTIONS_SUMMARY.md](SSI_OPEN_QUESTIONS_SUMMARY.md) — Plain-language summary of experiments and conclusions
- [00_methodology.md](00_methodology.md)
- Tests 01–16 numbered markdown files
- [SIGNOFF.md](SIGNOFF.md)
