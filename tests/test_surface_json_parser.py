"""Tests for surface_json parser."""

import importlib.util
from pathlib import Path

_PARSER_PATH = Path(__file__).resolve().parents[1] / "src" / "utils" / "surface_json_parser.py"
_spec = importlib.util.spec_from_file_location("surface_json_parser", _PARSER_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
parse_surface_json = _mod.parse_surface_json
normalize_surface_row = _mod.normalize_surface_row


def test_parse_surface_json_legacy_quality_score():
    text = """
    Some report text
    <surface_json>
    {"surface_data": [{"symbol": "AAPL", "quality_score": 68, "timeliness_score": 90}]}
    </surface_json>
    """
    rows = parse_surface_json(text)
    assert len(rows) == 1
    assert rows[0]["composite_score"] == 68
    assert rows[0]["symbol"] == "AAPL"


def test_normalize_expected_return_alias():
    row = normalize_surface_row({"expected_return": 3.5, "quality_score": 40})
    assert row["er"] == 3.5
    assert row["composite_score"] == 40
