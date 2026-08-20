#!/usr/bin/env python3
"""Run full SSI Open Questions validation suite and refresh docs."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOCS = ROOT / "docs" / "ssi_validation"
GENERATED = DOCS / "_generated"

DOC_MAP = {
    "01_02_threshold_sweep": "01_long_threshold_sweep.md",
    "03_04_cftc_grid": "03_squeeze_grid.md",
    "05_tp_sl": "05_tp_sl_optimization.md",
    "06_cnn_fear_greed": "06_cnn_fear_greed.md",
    "07_dbmf_beta": "07_dbmf_beta.md",
    "08_hyg_lqd": "08_hyg_lqd_widening.md",
    "09_zscore_vs_percentile": "09_zscore_vs_percentile.md",
    "10_layer2_sweep": "10_layer2_confirmation.md",
    "11_vix_regime_ab": "11_vix_regime_multiplier.md",
    "12_bollinger_ssi": "12_bollinger_ssi.md",
    "13_stoch_mcclellan": "13_stochastic_mcclellan.md",
    "14_gross_net": "14_gross_net_divergence.md",
    "15_sbi_short": "15_sbi_short_signal.md",
    "16_friday_pull": "16_friday_pull_checklist.md",
    "17_trendpulse": "17_trendpulse_deterioration.md",
    "18_cot_fm_long_gate": "18_cot_fm_long_gate.md",
    "19_vix_fm_washout": "19_vix_fm_washout.md",
    "20_layer2_zscore_sweep": "20_layer2_zscore_sweep.md",
    "21_staleness_decay": "21_staleness_decay.md",
    "22_layer2_gate_grid": "22_layer2_gate_grid.md",
}


def _merge_docs() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    for gen in sorted(GENERATED.glob("*.md")):
        for key, dest in DOC_MAP.items():
            if key in gen.stem:
                target = DOCS / dest
                body = gen.read_text(encoding="utf-8")
                target.write_text(f"<!-- generated from {gen.name} -->\n\n{body}", encoding="utf-8")
                break


def main() -> int:
    parser = argparse.ArgumentParser(description="SSI validation suite")
    parser.add_argument("--skip-mindwealth", action="store_true", help="Skip tests 5 and 15")
    parser.add_argument("--start", default="2010-01-01")
    args = parser.parse_args()
    errors: list[str] = []
    runners = [
        ("01_02", "src.sentiment_superindex.analysis.threshold_sweep", True),
        ("03_04", "src.sentiment_superindex.analysis.cftc_grid", True),
        ("05", "src.sentiment_superindex.analysis.tp_sl_sweep", False),
        ("06", "src.sentiment_superindex.analysis.cnn_forward_returns", True),
        ("07", "src.sentiment_superindex.analysis.dbmf_beta_study", True),
        ("08", "src.sentiment_superindex.analysis.hyg_lqd_study", True),
        ("09", "src.sentiment_superindex.analysis.zscore_vs_percentile", True),
        ("10", "src.sentiment_superindex.analysis.layer2_threshold_sweep", True),
        ("11", "src.sentiment_superindex.analysis.vix_regime_ab", False),
        ("12", "src.sentiment_superindex.analysis.bb_ssi_combo", True),
        ("13", "src.sentiment_superindex.analysis.stoch_mcclellan", True),
        ("14", "src.sentiment_superindex.analysis.gross_net_divergence", True),
        ("15", "src.sentiment_superindex.analysis.sbi_short_validation", True),
        ("16", "src.sentiment_superindex.analysis.friday_pull_checklist", False),
        ("17", "src.sentiment_superindex.analysis.trendpulse_deterioration", True),
        ("18", "src.sentiment_superindex.analysis.cot_fm_long_gate", True),
        ("19", "src.sentiment_superindex.analysis.vix_fm_washout", True),
        ("20", "src.sentiment_superindex.analysis.layer2_zscore_sweep", True),
        ("21", "src.sentiment_superindex.analysis.staleness_decay_study", True),
        ("22", "src.sentiment_superindex.analysis.layer2_gate_grid_sweep", True),
    ]
    for tid, module, use_start in runners:
        if args.skip_mindwealth and tid in ("05", "15"):  # MindWealth-dependent tests
            print(f"SKIP {tid}")
            continue
        print(f"RUN {tid} ...", flush=True)
        try:
            mod = importlib.import_module(module)
            if use_start:
                mod.run_and_report(start=args.start)
            else:
                mod.run_and_report()
        except Exception as e:
            errors.append(f"{tid}: {e}")
            print(f"FAIL {tid}: {e}", flush=True)
    _merge_docs()
    signoff = DOCS / "SIGNOFF.md"
    if not signoff.exists():
        signoff.write_text(
            "# SSI validation sign-off\n\nRun `scripts/run_ssi_validation_suite.py` then review numbered reports.\n"
            "Do not switch production to percentile SSI until Rohit approves Test 9.\n",
            encoding="utf-8",
        )
    print(f"Artifacts: {ROOT / 'macro_intelligence' / 'analysis' / 'ssi_validation'}")
    print(f"Docs: {DOCS}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
