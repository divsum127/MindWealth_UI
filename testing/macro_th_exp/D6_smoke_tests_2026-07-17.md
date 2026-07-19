# D6 — Smoke Tests

**Date:** 2026-07-17
**Result:** 8/8 passed — **ALL PASS**

| Test | Pass | Detail |
|------|------|--------|
| combo_c_insufficient_episodes_flag | ✅ | n_primary=3, min=5, insufficient=True |
| combo_c_briefing_display_string | ✅ | hit_rate_cell='insufficient episodes', avg_cell='—' |
| briefing_all_time_combo_c_row | ✅ | hit_rate_display='insufficient episodes' |
| briefing_combo_status_row_c | ✅ | C row hit_rate_3m='insufficient episodes' |
| api_get_combo_detail_c | ✅ | insufficient=True, n=3 |
| api_list_named_combos_c | ✅ | hit_rate_primary=None |
| fm_fed_slice_no_pivoting_bucket | ✅ | buckets=['EASING', 'EASY', 'TIGHTENING'], EASING n=20 |
| fm_liquidity_analytics_max_4_buckets | ✅ | buckets=['EASY_IMPROVING', 'EASY_TIGHTENING'] (n=2) |

## Scope

- Combo C `insufficient episodes` (DB n&lt;5 at 6M primary horizon)
- Briefing renderer all-time + status rows
- API `macro_service.get_combo_detail('C')` and `get_all_combos()`
- FM `fed_cycle_v2` slice has no PIVOTING bucket; liquidity ≤4 analytics buckets

Run: `.venv/bin/python testing/macro_th_exp/run_d6_smoke_tests.py`
