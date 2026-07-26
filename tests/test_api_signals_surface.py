"""Tests for Signals Page API endpoints."""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
BASE = "/api/v1"
def test_outstanding_signals_enriched():
    r = client.get(f"{BASE}/signals/reports/outstanding-signals/latest")
    assert r.status_code == 200
    d = r.json()
    assert d["row_count"] > 0
    rec = d["records"][0]
    assert "composite_score" in rec
    assert "window_remaining_pct" in rec
    assert "tier" in rec
    assert "exit_fired" in rec
    assert "er_annualized" in rec
    assert "signal_alpha_annualized" in rec
    assert "mtm_pct" in rec
    assert "days_elapsed" in rec
    assert "avg_hold_days" in rec
    assert "direction" in rec
    assert rec["tier"] in ("tA", "best", "tierc", "exit", "watch", "ok")
    if rec.get("rr_dynamic") is not None:
        assert isinstance(rec["rr_dynamic"], (int, float))


def test_outstanding_not_enriched():
    r = client.get(f"{BASE}/signals/reports/outstanding-signals/latest?enrich=false")
    assert r.status_code == 200
    d = r.json()
    rec = d["records"][0]
    # Pipeline may persist MasterSpec columns in CSV; enrich=false skips runtime overlay fields.
    assert "conviction_score" not in rec
    assert "mtm_pct" not in rec


def test_portfolio_risk_cross_function_conflicts_key():
    r = client.get(f"{BASE}/signals/reports/portfolio-risk/latest", params={"book_id": "model"})
    if r.status_code == 404:
        pytest.skip("portfolio-risk report not available")
    assert r.status_code == 200
    d = r.json()
    assert d["book_id"] == "model"
    assert "cross_function_conflicts" in d
    assert isinstance(d["cross_function_conflicts"], list)
    assert "cross_function_conflict_count" in d
    if d["cross_function_conflicts"]:
        c = d["cross_function_conflicts"][0]
        assert "symbol" in c
        if c.get("open_positions"):
            assert "implied_natural_exit_date" in c["open_positions"][0]


def test_parse_signal_meta_reads_plain_interval_column():
    """Regression (2026-07-27): portfolio-risk (outstanding) report rows carry a plain
    "Interval" column, not the "Interval, Confirmation Status" compound used by
    new-signals/target-signals. Before this fix, interval always resolved to "" for that
    report, silently breaking _lookup_hold_days()/implied_natural_exit_date matching."""
    from api.services.portfolio_pipeline_service import _parse_signal_meta

    row = {
        "Symbol, Signal, Signal Date/Price[$]": "3690.HK, Long, 2026-07-08 @ 80.9",
        "Function": "TRENDPULSE",
        "Interval": "Daily",
    }
    meta = _parse_signal_meta(row)
    assert meta["interval"] == "Daily"
    assert meta["symbol"] == "3690.HK"
    assert meta["function"] == "TRENDPULSE"

    # Compound column still takes priority when both are present.
    row2 = {**row, "Interval, Confirmation Status": "Weekly, Confirmed"}
    assert _parse_signal_meta(row2)["interval"] == "Weekly"


def test_signal_entries_endpoint():
    r = client.get(f"{BASE}/signals/entries", params={"book_id": "model"})
    assert r.status_code == 200
    d = r.json()
    assert d["book_id"] == "model"
    assert "entries" in d
    if d["entries"]:
        e = d["entries"][0]
        assert "ticker" in e and "rank" in e


def test_signal_exits_endpoint():
    r = client.get(f"{BASE}/signals/exits", params={"book_id": "model"})
    assert r.status_code == 200
    d = r.json()
    assert d["book_id"] == "model"
    assert "exits" in d
    if d["exits"]:
        assert d["exits"][0]["exit_type"] in ("signal", "rr", "eviction")


def test_new_signals_enriched():
    r = client.get(f"{BASE}/signals/reports/new-signals/latest")
    assert r.status_code == 200
    d = r.json()
    assert d["row_count"] > 0
    rec = d["records"][0]
    assert "tier" in rec
    assert "composite_score" in rec


def test_surface_endpoint_outstanding():
    r = client.get(f"{BASE}/signals/surface?report=outstanding-signals")
    assert r.status_code == 200
    d = r.json()
    assert d["row_count"] > 0
    rec = d["records"][0]
    assert rec.get("composite_score") is not None
    assert rec.get("window_remaining_pct") is not None
    assert rec.get("tier") in ("tA", "best", "tierc", "exit")


def test_surface_endpoint_new():
    r = client.get(f"{BASE}/signals/surface?report=new-signals")
    assert r.status_code == 200
    d = r.json()
    assert d["row_count"] > 0


def test_summary_outstanding():
    r = client.get(f"{BASE}/signals/summary?report=outstanding-signals")
    assert r.status_code == 200
    d = r.json()
    assert "total" in d
    assert "long" in d
    assert "short" in d
    assert "tier_counts" in d
    assert "function_counts" in d
    assert d["total"] == d["long"] + d["short"]
    assert d["total"] > 0


def test_counts_endpoint():
    r = client.get(f"{BASE}/signals/counts")
    assert r.status_code == 200
    d = r.json()
    assert "outstanding" in d
    assert "new" in d
    assert "shortlist" in d
    assert d["outstanding"]["total"] > 0
    assert "tier_counts" in d["outstanding"]


def test_shortlist_structured_records():
    r = client.get(f"{BASE}/signals/shortlist")
    assert r.status_code == 200
    d = r.json()
    assert d["row_count"] > 0
    assert len(d["records"]) > 0
    rec = d["records"][0]
    assert "symbol" in rec
    assert "function" in rec
    assert "direction" in rec


def test_strategy_health():
    r = client.get(f"{BASE}/signals/strategy-health")
    assert r.status_code == 200
    d = r.json()
    assert "strategy_health" in d
    assert len(d["strategy_health"]) > 0
    sh = d["strategy_health"][0]
    assert "strategy" in sh
    assert "fwd_wr" in sh
    assert "gate_a2b" in sh


def test_gate_a2b_gating():
    r = client.get(f"{BASE}/signals/gate-a2b")
    assert r.status_code == 200
    d = r.json()
    assert d["floor_pct"] == 60.0
    assert "gates" in d
    assert len(d["gates"]) > 0
    assert d["row_count"] == len(d["gates"])
    assert d["approved_count"] + d["disapproved_count"] == d["row_count"]
    gate = d["gates"][0]
    assert "function" in gate
    assert "interval" in gate
    assert "direction" in gate
    assert gate["verdict"] in ("approve", "disapprove")
    assert gate["approved"] == (gate["verdict"] == "approve")
    if gate["fwd_wr"] is not None:
        if gate["fwd_wr"] >= 60.0:
            assert gate["verdict"] == "approve"
        else:
            assert gate["verdict"] == "disapprove"


def test_horizontal_new_high():
    r = client.get(f"{BASE}/signals/reports/horizontal-new-high/latest")
    assert r.status_code in (200, 404)


def test_combined_performance():
    r = client.get(f"{BASE}/signals/reports/combined-performance/latest")
    assert r.status_code in (200, 404)


def test_breadth_report():
    r = client.get(f"{BASE}/signals/reports/breadth/latest")
    assert r.status_code == 200
    d = r.json()
    assert d["row_count"] > 0


def test_surface_404():
    r = client.get(f"{BASE}/signals/surface?report=nonexistent-report")
    assert r.status_code == 404


def test_er_annualized_math():
    """er_annualized = er * 252 / avg_hold_days — verify math is consistent."""
    r = client.get(f"{BASE}/signals/surface?report=outstanding-signals")
    d = r.json()
    for rec in d["records"][:10]:
        er = rec.get("er")
        hold = rec.get("avg_hold_days")
        er_ann = rec.get("er_annualized")
        if er is not None and hold and er_ann is not None:
            expected = round(er * 252 / hold, 4)
            assert abs(er_ann - expected) < 0.01, f"er_annualized mismatch: {er_ann} vs {expected} (er={er}, hold={hold})"


def test_all_signal_composite_scores_with_enrich():
    """all_signal CSV lacks MasterSpec columns — enrich must compute composite_score."""
    r = client.get(f"{BASE}/signals/reports/all-signal/latest?enrich=true&limit=20")
    assert r.status_code == 200
    d = r.json()
    recs = d.get("records", [])
    assert len(recs) > 0
    with_score = [x for x in recs if x.get("composite_score") is not None]
    assert len(with_score) > 0, "expected composite_score computed from raw backtest fields"
    assert all(isinstance(x.get("composite_score"), (int, float)) for x in with_score)


def test_all_signal_no_enrich_by_default():
    """all-signal defaults enrich=false to avoid per-request latency on large datasets."""
    r = client.get(f"{BASE}/signals/reports/all-signal/latest")
    assert r.status_code == 200
    d = r.json()
    assert d["row_count"] >= 0
    if d["records"]:
        rec = d["records"][0]
        assert "conviction_score" not in rec
        assert "mtm_pct" not in rec


def test_all_signal_enrich_true_explicit():
    """Caller can opt-in to enrichment for all-signal via ?enrich=true."""
    r = client.get(f"{BASE}/signals/reports/all-signal/latest?enrich=true")
    assert r.status_code == 200
    d = r.json()
    if d["records"]:
        rec = d["records"][0]
        assert "tier" in rec
        assert "window_remaining_pct" in rec


def test_report_limit_param():
    """?limit=5 returns at most 5 records and adds returned_count field."""
    r = client.get(f"{BASE}/signals/reports/outstanding-signals/latest?limit=5")
    assert r.status_code == 200
    d = r.json()
    assert len(d["records"]) <= 5
    assert "returned_count" in d
    assert d["returned_count"] == len(d["records"])

