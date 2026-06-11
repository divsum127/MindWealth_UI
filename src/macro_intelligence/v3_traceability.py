"""v3 requirement registry for traceability matrix export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class V3Requirement:
    req_id: str
    category: str
    spec_ref: str
    implementation: str
    test_module: str
    live_check: str
    notes: str = ""


def all_requirements() -> list[V3Requirement]:
    """Static registry — status filled at export time by probes."""
    rows: list[V3Requirement] = []

    # --- 26 data variables (from DATA_SOURCES.yaml) ---
    macro_vars = [
        ("NFCI", "fred_pull.fetch_fred_series", "tests/test_macro_percentiles.py"),
        ("HY", "fred_pull.fetch_fred_series", "tests/test_macro_percentiles.py"),
        ("WALCL", "fred_pull + walcl_mom_pct", "tests/test_macro_percentiles.py"),
        ("CNH", "yahoo_pull + FRED DEXCHUS fallback", "tests/test_scraper_pipelines.py"),
        ("WTI", "yahoo_pull calendar_pct_change 28d", "tests/test_scraper_pipelines.py"),
        ("VIX", "yahoo_pull.fetch_yahoo_close", "tests/test_combo_b_oct_2022.py"),
        ("VXTS", "yahoo_pull.vix_term_structure", "tests/test_ssi_layer2.py"),
        ("CFTC", "cftc_pull S&P500 Consolidated", "tests/test_cftc_parser.py"),
        ("CURVE", "fred_pull.curve_features", "tests/test_macro_percentiles.py"),
        ("CPI", "bls_pull + investing_cpi_consensus", "tests/test_cpi_pull.py"),
        ("GSR", "yahoo_pull.gsr_ratio GC=F/SI=F", "—"),
        ("CAPE", "cape_scrape multpl", "tests/test_scraper_pipelines.py"),
    ]
    for vid, impl, test in macro_vars:
        rows.append(
            V3Requirement(
                f"var-macro-{vid}",
                "variable",
                f"DATA_SOURCES.yaml #{vid}",
                impl,
                test,
                "validate_production_data_sources.check_macro_series",
            )
        )

    ssi_vars = [
        ("AAII", "aaii_pull", "tests/test_scraper_pipelines.py"),
        ("NAAIM", "naaim_pull", "tests/test_scraper_pipelines.py"),
        ("CNN_FG", "cnn_fear_greed", "tests/test_scraper_pipelines.py"),
        ("PCT_ABOVE_200DMA", "pct_200dma_pull sp500", "tests/test_scraper_pipelines.py"),
        ("MCCLELLAN", "mcclellan_pull sp500", "tests/test_scraper_pipelines.py"),
        ("NH_NL_RATIO", "nh_nl_pull sp500", "tests/test_scraper_pipelines.py"),
        ("HYG_LQD", "yahoo_inputs.hyg_lqd_ratio", "tests/test_ssi_layer2.py"),
        ("SKEW", "skew_pull", "—"),
        ("CFTC_FM", "cftc_ssi layer3", "tests/test_cftc_parser.py"),
        ("CFTC_RM", "cftc_ssi rm_pctile dashboard", "tests/test_cftc_parser.py"),
        ("GROSS_NET_DIV", "cftc_ssi derived", "—"),
        ("DBMF", "yahoo_inputs.dbmf_beta", "tests/test_ssi_layer2.py"),
    ]
    for vid, impl, test in ssi_vars:
        rows.append(
            V3Requirement(
                f"var-ssi-{vid}",
                "variable",
                f"DATA_SOURCES.yaml {vid}",
                impl,
                test,
                "validate_production_data_sources.check_ssi_series",
            )
        )

    combos = [
        ("A", "combo_detector detect_named + direction vote", "tests/test_combo_a_vote.py", "v3 Combo A EASY_MONEY/FEARFUL"),
        ("B", "combo_detector Combo B ALL3", "tests/test_combo_b_oct_2022.py", "vix_bypass"),
        ("C", "combo_detector + combo_c_cancel", "tests/test_combo_c_cancel.py", "28d WTI calendar ROC"),
        ("D", "combo_detector VXTS+VIX+CFTC", "tests/test_combo_b_oct_2022.py", "RM pctile dashboard"),
        ("E", "combo_detector 2of3 CONFIRMED", "—", "CONFIRMED_3_OF_3 when 3 legs"),
        ("F", "combo_detector 50WMA + lifecycle", "tests/test_combo_f_jun_2020.py", "2020-06-08 validation date"),
        ("G", "combo_detector + hy_widen_4wk", "tests/test_combo_g.py", "hy_widen_4wk_bps"),
    ]
    for letter, impl, test, note in combos:
        rows.append(
            V3Requirement(
                f"combo-{letter}",
                "named_combo",
                f"CONFIG named_combos.{letter}",
                f"combo_detector.py {impl}",
                test,
                "detect_named_combos live",
                note,
            )
        )

    json_fields = [
        ("dominant_signal", "dominant.resolve_dominant PRIORITY", "tests/test_dominant_priority.py"),
        ("analog_details", "dominant.find_analog_details + backfill", "tests/test_backfill_hit_rates.py"),
        ("spx_3m_hit_rate", "hit_rates.raw_hit_rate", "tests/test_hit_rates.py"),
        ("combo_c_cancel", "combo_c_cancel.run_combo_c_cancel_check", "tests/test_combo_c_cancel.py"),
        ("cftc_status", "json_writer._cftc_status", "tests/test_runic_output_schema.py"),
        ("pending_cpi_release", "json_writer._pending_cpi_release", "tests/test_runic_output_schema.py"),
        ("ssi_multiplier", "json_writer.read_ssi_multiplier", "tests/test_ssi_positioning_json.py"),
        ("vix_bypass", "vix_bypass.compute_vix_bypass", "tests/test_ssi_vix_regime_oct_2022.py"),
        ("dual_percentiles", "percentiles unconditional+regime", "tests/test_macro_percentiles.py"),
        ("generic_prefilter", "prefilter.apply_prefilter + nightly generic_watch", "—"),
    ]
    for field, impl, test in json_fields:
        rows.append(
            V3Requirement(
                f"json-{field}",
                "json_output",
                "v3 nightly JSON contract",
                impl,
                test,
                "run_macro_nightly.py",
            )
        )

    ops = [
        ("backfill", "backfill_macro_history + forward_returns", "tests/test_backfill_hit_rates.py"),
        ("ssi_daily", "run_ssi_daily", "tests/test_ssi_positioning_json.py"),
        ("friday_pull", "run_macro_friday_pull detect_all", "tests/test_friday_pull_integration.py"),
        ("nightly", "run_macro_nightly", "tests/test_runic_output_schema.py"),
        ("no_prod_mock", "production paths no tests/fixtures", "scripts/audit_production_no_mocks.py"),
    ]
    for op_id, impl, test in ops:
        rows.append(
            V3Requirement(
                f"ops-{op_id}",
                "operations",
                "SYSTEM_DOCUMENTATION",
                impl,
                test,
                "run_full_v3_verification.py",
            )
        )

    return rows
