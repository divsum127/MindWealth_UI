"""Tests for event_date_extractor."""

from chatbot.tools.event_date_extractor import (
    best_event_date,
    extract_event_dates,
    known_fallback_date,
)


def test_prose_dmy_to_iso():
    text = "Infratil Limited 1 October 2015 agreed to sell its 20% stake in Z Energy"
    assert extract_event_dates(text) == ["2015-10-01"]
    assert best_event_date(
        text, precedent_name="Z Energy / Infratil 2015", sold_ticker="ZEL.NZ"
    ) == "2015-10-01"


def test_url_date():
    text = "https://www.asx.com.au/asxpdf/20151001/pdf/431ryddm2lkcgp.pdf"
    dates = extract_event_dates(text)
    assert "2015-10-01" in dates


def test_penalize_2026_cen_in_z_energy_blob():
    blob = """
    Infratil reduces Contact stake May 2026 expected to complete on 25 May 2026 NZ$495 million.
    Infratil Limited 1 October 2015 agreed to sell 20% Z Energy block trade.
    """
    assert best_event_date(
        blob, precedent_name="Z Energy", sold_ticker="ZEL.NZ"
    ) == "2015-10-01"


def test_known_fallback_z_energy():
    assert known_fallback_date("Z Energy / Infratil 2015", "ZEL.NZ") == "2015-10-01"


def test_known_fallback_origin():
    assert known_fallback_date("Origin / Contact 2015", "CEN.NZ") == "2015-08-10"
