"""CE-06: operating-segment mix from a 10-K XBRL instance and the dominant-segment tie-break."""

from __future__ import annotations

from src.conviction_engine.segments import (
    mix_from_revenue,
    parse_segment_revenue,
    resolve_segment_mix,
    segment_tiebreak_type,
)

INSTANCE = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:us-gaap="http://fasb.org/us-gaap/2025">
  <xbrli:context id="a"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier>
    <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">co:ServicesMember</xbrldi:explicitMember></xbrli:segment>
  </xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:context id="b"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier>
    <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">co:CloudMember</xbrldi:explicitMember></xbrli:segment>
  </xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:context id="q"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier>
    <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">co:CloudMember</xbrldi:explicitMember></xbrli:segment>
  </xbrli:entity><xbrli:period><xbrli:startDate>2025-10-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:context id="g"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier>
    <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">co:CloudMember</xbrldi:explicitMember>
    <xbrldi:explicitMember dimension="srt:StatementGeographicalAxis">co:UsMember</xbrldi:explicitMember></xbrli:segment>
  </xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
  <us-gaap:Revenues contextRef="a">300</us-gaap:Revenues>
  <us-gaap:Revenues contextRef="b">100</us-gaap:Revenues>
  <us-gaap:Revenues contextRef="q">30</us-gaap:Revenues>
  <us-gaap:Revenues contextRef="g">90</us-gaap:Revenues>
</xbrli:xbrl>"""


def test_parses_annual_segment_revenue_only():
    mix = parse_segment_revenue(INSTANCE)
    assert mix["dominant_segment"] == "co:ServicesMember"
    assert mix["dominant_share"] == 0.75  # quarter and two-axis facts ignored
    assert mix["multi_segment"] is False
    assert mix["source"] == "sec_10k_xbrl"


def test_mixed_business_and_tiebreak_from_documented_override():
    override = {
        "segments": {"telco": 45, "data_centres": 35, "renewables": 20},
        "segments_source": "FY26 annual report",
        "segment_types": {"telco": "telco", "data_centres": "compounder", "renewables": "income"},
    }
    mix = resolve_segment_mix("IFT.NZ", override, us_filer=False)
    assert mix["multi_segment"] is True
    assert mix["dominant_segment"] == "telco"
    assert mix["source"] == "override: FY26 annual report"
    assert segment_tiebreak_type(mix, override) == "telco"


def test_no_mapping_means_no_tiebreak():
    mix = mix_from_revenue({"a": 50, "b": 50}, source="x")
    assert segment_tiebreak_type(mix, None) is None
    assert segment_tiebreak_type(mix, {"segments": {}}) is None


def test_non_us_without_override_has_no_mix():
    assert resolve_segment_mix("SPK.NZ", None, us_filer=False) is None
