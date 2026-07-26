# Live CONFIG formal re-check — 2026-07-17

Re-ran full production-viable sweep (`run_combo_de_followup.py`) and main factorial study (`run_combo_de_study.py`) against **live** `CONFIG.yaml` after promoting analysis case #4 (BEST PRODUCTION SCORE) for D and E.

## Verdict: PASS

Live CONFIG **is** BEST PRODUCTION SCORE for both combos. Hit rates match `de_threshold_test_analysis.md` case #4 within rounding.

| Combo | Live CONFIG gates | Analysis case #4 | Match |
| --- | --- | --- | --- |
| D | VXTS≥1.18 / CFTC≥95 / VIX≤13 / 2-of-3 | same | yes |
| E | CAPE≥32 / NFCI≤−0.15 / CFTC≥85 / 3-of-3 | same | yes |

### D — recheck vs analysis

| Metric | Analysis #4 | Live CONFIG recheck | Δ |
| --- | --- | --- | --- |
| Episodes | 46 | 46 | 0 |
| 1W bear | 56.5% | 56.52% | ~0 |
| 2W bear | 43.5% | 43.48% | ~0 |
| 3W bear | 43.5% | 43.48% | ~0 |
| 4W bear | 41.3% | 41.3% | 0 |
| Avg SPX 1W | −0.35% | −0.3499% | ~0 |

Followup also ranks this row **#1 production score** (`is_config_baseline: true`, score 54.62).

### E — recheck vs analysis

| Metric | Analysis #4 | Live CONFIG recheck | Δ |
| --- | --- | --- | --- |
| Episodes | 10 | 10 | 0 |
| 6M bear | 66.7% | 66.67% | ~0 |
| 9M bear | 66.7% | 66.67% | ~0 |
| 12M bear | 66.7% | 66.67% | ~0 |
| Avg SPX 12M | −6.54% | −6.5376% | ~0 |

Followup also ranks this row **#1 production score** (`is_config_baseline: true`, score 64.17).

## What ran

1. `testing/combo_de_thresholds/run_combo_de_followup.py` → `followup_meta.json` (2026-07-17T09:59:59Z)
   - D viable n≥10: 1131 rows; E viable: 382
2. `testing/combo_de_thresholds/run_combo_de_study.py` → `study_meta.json` (2026-07-17T09:59:51Z)
   - CONFIG baseline tagged correctly for new gates (D 2-of-3 + VIX 13 outside old univariate grid)

## Script fix applied for this recheck

D `is_config_baseline` / config baseline run previously hard-coded `legs == 3`. Updated to use `named_combos.D.min_of_three` so live 2-of-3 CONFIG is tagged and evaluated as baseline.

## Note on analysis.md section “1. CONFIG (current production)”

That section still documents **pre-promotion** gates (D 1.10/85/18 3-of-3; E 28/−0.30/80 2-of-3). Those are obsolete. Live production = case #4. This recheck file is the source of truth for post-promotion validation.

## Artifacts

- `output_files/followup_meta.json`
- `output_files/case1_production_viable_{d,e}.csv`
- `output_files/study_meta.json`
- `output_files/combo_de_recommended_thresholds.csv`
- Logs: `output_files/recheck_followup_2026-07-17.log`, `output_files/recheck_study_2026-07-17.log`
