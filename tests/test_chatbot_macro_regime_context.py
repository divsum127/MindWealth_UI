from chatbot.macro_context import MacroContextBuilder


class _Client:
    def get(self, path, params=None):
        if path == "/macro/runic/nightly":
            return {
                "date": "2026-09-25",
                "dominant_signal": "F",
                "dominant_reason": "Combo F active",
                "regime": {
                    "fed_cycle": "HIKING_LATE",
                    "val_regime": "EXTREME",
                    "val_regime_source": "CAPE",
                },
                "variables_dashboard": [
                    {
                        "variable": "VIX",
                        "current": 15.0,
                        "tier": "NORMAL",
                        "pctile_3yr": 29.23,
                        "source_date": "2026-09-25",
                    },
                    {
                        "variable": "CAPE",
                        "current": 40.94,
                        "tier": "EXTREME",
                        "pctile_3yr": 99.1,
                        "source_date": "2026-09-01",
                    },
                ],
                "brave_fearful_display": "TACTICAL EASY MONEY",
                "system_recommendation": "Normal risk ceiling",
                "ssi_multiplier": 1.0,
                "ssi_layer2_status": "PARTIAL",
                "vix_bypass": False,
            }
        if path == "/macro/ssi/summary":
            return {"date": "2026-09-25", "ssi_level": 0.1}
        if path == "/portfolio/risk":
            return {"date": "2026-09-25", "cluster_weights": {}, "breaches": []}
        raise AssertionError(path)


def test_regime_context_exposes_vix_and_cape_as_distinct_internal_dimensions():
    block = MacroContextBuilder(client=_Client()).build(
        "Using current internal data only, give the VIX and CAPE regimes with fields and as-of dates."
    )

    assert block is not None
    assert "VIX level: 15" in block
    assert "VIX volatility regime/tier: NORMAL" in block
    assert "VIX 3y percentile: 29.23" in block
    assert "VIX source_as_of: 2026-09-25" in block
    assert "CAPE level: 40.94" in block
    assert "CAPE valuation regime/tier: EXTREME" in block
    assert "CAPE source_as_of: 2026-09-01" in block
    assert "VIX is a volatility input; CAPE is a valuation input" in block


def test_regime_context_uses_snapshot_date_without_inventing_variable_source_date():
    client = _Client()
    nightly = client.get("/macro/runic/nightly")
    nightly["variables_dashboard"][0]["source_date"] = None

    class MissingDateClient(_Client):
        def get(self, path, params=None):
            if path == "/macro/runic/nightly":
                return nightly
            return super().get(path, params)

    block = MacroContextBuilder(client=MissingDateClient()).build("current internal VIX regime")

    assert block is not None
    assert "VIX source_as_of: unavailable; Runic snapshot_as_of: 2026-09-25" in block
