"""CE-33: any-ticker conviction look-up route."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services import conviction_service
from src.conviction_engine.engine import full_recalculation
from tests.api_test_helpers import disable_rate_limits


@pytest.fixture()
def client():
    disable_rate_limits()
    with patch.dict("os.environ", {"API_KEY": ""}, clear=False), patch("api.dependencies.API_KEY", ""):
        yield TestClient(app)


def _scored(tmp_path: Path, ticker: str) -> dict:
    return full_recalculation(
        ticker,
        info={"quoteType": "EQUITY", "sector": "Technology", "industry": "Software - Application"},
        fundamentals={"price": 100.0, "market_cap": 10_000_000_000, "eps_ttm": 2.0},
        overrides={"bq_raw": 6},
        store_dir=tmp_path,
    )


def test_stored_ticker_is_read_not_recomputed(client, tmp_path):
    record = _scored(tmp_path, "AAA")
    with patch.object(conviction_service, "load_record", lambda t, d=None: record if t == "AAA" else None), patch(
        "src.conviction_engine.fundamentals.update_ticker_fundamentals"
    ) as fetch:
        body = client.get("/api/v1/conviction/lookup/AAA").json()
    fetch.assert_not_called()
    assert body["source"] == "store"
    assert body["applicable"] is True
    assert "components" in body["valuation_tax_breakdown"]
    assert "components" in body["fs_score_breakdown"]
    assert body["if_buy_signal"]["verdict"]
    assert body["report_only"] is True


def test_unknown_ticker_is_scored_in_a_throwaway_store(client, tmp_path):
    stored = {}

    def fake_update(ticker, mode="full", store_dir=None, **_):
        stored["dir"] = store_dir
        _scored(store_dir, ticker)
        return {}

    real_load = conviction_service.load_record

    def load(ticker, store_dir=None):
        return real_load(ticker, store_dir) if store_dir is not None else None

    with patch.object(conviction_service, "load_record", load), patch(
        "src.conviction_engine.fundamentals.update_ticker_fundamentals", fake_update
    ):
        body = client.get("/api/v1/conviction/lookup/BBB").json()
    assert body["source"] == "on_demand"
    assert body["ticker"] == "BBB"
    assert not Path(stored["dir"]).exists()  # throwaway directory removed
