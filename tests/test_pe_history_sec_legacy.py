"""Tests for the pre-2009 SEC legacy-filing PE-history extension (pe_history_sec_legacy.py).

All SEC HTTP calls are mocked — no real network access is exercised here. (Live, manual
validation against real filings — MSFT, JPM/Chase Manhattan, GS, PG, NKE — was run
separately during development, cross-checked against independently-published EPS
figures, and is documented in the job-status docs, not part of the automated suite.)
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.conviction_engine.pe_history_sec_legacy import (
    _clean_number,
    _extract_sgml_document,
    _list_all_10k_filings,
    _parse_sec_date,
    fetch_legacy_annual_eps,
    parse_ex27_annual_eps,
    parse_selected_financial_data,
)

# Real (Article 5, commercial/industrial) EX-27 body, structurally identical to MSFT's
# FY1997 filing — verified live 2026-07-29: EPS-DILUTED=2.63 matches Microsoft's own
# contemporaneous press release and investor-relations "financial highlights" page.
_EX27_ARTICLE5 = """
<ARTICLE> 5
<LEGEND>
THIS SCHEDULE CONTAINS SUMMARY FINANCIAL INFORMATION
</LEGEND>
<PERIOD-TYPE>                                     YEAR
<FISCAL-YEAR-END>                          JUN-30-1997
<PERIOD-END>                               JUN-30-1997
<CASH>                                           8,966
<NET-INCOME>                                     3,439
<EPS-PRIMARY>                                     2.63
<EPS-DILUTED>                                     2.63
"""

# Real (Article 9, bank holding company) EX-27 body, structurally identical to Chase
# Manhattan's (JPM's predecessor CIK) FY1997 filing — different tag set for balance-sheet
# items, but the same EPS-PRIMARY/EPS-DILUTED tag names.
_EX27_ARTICLE9_BANK = """
<ARTICLE> 9
<CIK> 0000019617
<NAME> THE CHASE MANHATTAN CORPORATION
<PERIOD-TYPE>                   12-MOS
<FISCAL-YEAR-END>                          DEC-31-1997
<PERIOD-START>                             JAN-01-1997
<PERIOD-END>                               DEC-31-1997
<DEPOSITS>                                     193,688
<NET-INCOME>                                     3,708
<EPS-PRIMARY>                                     8.30
<EPS-DILUTED>                                     8.03
"""

# Pre-SFAS-128 (1997) schedules commonly leave EPS-DILUTED as a literal unpopulated "0"
# when the filer didn't compute a separate fully-diluted figure — real example from
# MSFT's FY1994 filing (EPS-PRIMARY=1.88, EPS-DILUTED=0).
_EX27_ZERO_DILUTED = """
<ARTICLE> 5
<PERIOD-TYPE>                  YEAR
<FISCAL-YEAR-END>                          JUN-30-1994
<PERIOD-END>                               JUN-30-1994
<NET-INCOME>                                     1,146
<EPS-PRIMARY>                                     1.88
<EPS-DILUTED>                                        0
"""

_EX27_QUARTERLY = """
<ARTICLE> 5
<PERIOD-TYPE>                  9-MOS
<FISCAL-YEAR-END>                          JUN-30-1998
<PERIOD-END>                               MAR-31-1998
<EPS-PRIMARY>                                     1.10
<EPS-DILUTED>                                     1.05
"""

# Real Item 6 "Selected Financial Data" text, stripped-tag form, matching MSFT's FY2002
# 10-K verbatim (verified live 2026-07-29) — includes the "before accounting change"
# adjusted-EPS line immediately before the plain GAAP line, which the parser must skip.
_SELECTED_FIN_DATA_TEXT = (
    "ITEM 6. SELECTED FINANCIAL DATA FINANCIAL HIGHLIGHTS In millions, except earnings "
    "per share Year Ended June 30 1998 1999 2000 2001 (1) 2002 (2) Revenue $ 15,262 "
    "$ 19,747 $ 22,956 $ 25,296 $ 28,365 Operating income 6,585 10,010 11,006 11,720 "
    "11,910 Income before accounting change 4,490 7,785 9,421 7,721 7,829 Net income "
    "4,490 7,785 9,421 7,346 7,829 Diluted earnings per share before accounting change "
    "0.84 1.42 1.70 1.38 1.41 Diluted earnings per share 0.84 1.42 1.70 1.32 1.41 Cash "
    "and short-term investments 13,927 17,236"
)


class TestParseSecDate:
    def test_parses_standard_format(self):
        assert _parse_sec_date("JUN-30-1997") == date(1997, 6, 30)
        assert _parse_sec_date("DEC-31-1997") == date(1997, 12, 31)

    def test_lowercase_month_accepted(self):
        assert _parse_sec_date("jun-30-1997") == date(1997, 6, 30)

    def test_garbage_returns_none(self):
        assert _parse_sec_date("not-a-date") is None
        assert _parse_sec_date("") is None
        assert _parse_sec_date(None) is None


class TestCleanNumber:
    def test_plain_positive(self):
        assert _clean_number("1.42") == 1.42

    def test_dollar_and_comma(self):
        assert _clean_number("$ 1,234.56") == 1234.56

    def test_parens_negative(self):
        assert _clean_number("(0.15)") == -0.15

    def test_leading_minus(self):
        assert _clean_number("-0.15") == -0.15

    def test_invalid_returns_none(self):
        assert _clean_number("n/a") is None
        assert _clean_number("") is None


class TestExtractSgmlDocument:
    def _submission(self, doc_type: str, body: str) -> str:
        return f"<TYPE>{doc_type}\n<SEQUENCE>2\n<TEXT>{body}</TEXT>\n"

    def test_extracts_ex27(self):
        text = self._submission("EX-27", _EX27_ARTICLE5)
        result = _extract_sgml_document(text, "EX-27")
        assert result is not None
        assert "EPS-DILUTED" in result

    def test_extracts_ex27_with_suffix(self):
        text = self._submission("EX-27.1", _EX27_ARTICLE5)
        result = _extract_sgml_document(text, "EX-27")
        assert result is not None

    def test_missing_document_returns_none(self):
        text = self._submission("EX-10.1", "some contract text")
        assert _extract_sgml_document(text, "EX-27") is None


class TestParseEx27AnnualEps:
    def test_article5_commercial_diluted(self):
        result = parse_ex27_annual_eps(_EX27_ARTICLE5)
        assert result == (date(1997, 6, 30), 2.63)

    def test_article9_bank_holding_diluted(self):
        result = parse_ex27_annual_eps(_EX27_ARTICLE9_BANK)
        assert result == (date(1997, 12, 31), 8.03)

    def test_zero_diluted_falls_back_to_primary(self):
        result = parse_ex27_annual_eps(_EX27_ZERO_DILUTED)
        assert result == (date(1994, 6, 30), 1.88)

    def test_quarterly_period_type_rejected(self):
        assert parse_ex27_annual_eps(_EX27_QUARTERLY) is None

    def test_missing_period_end_returns_none(self):
        body = "<PERIOD-TYPE> YEAR\n<EPS-DILUTED> 1.00\n"
        assert parse_ex27_annual_eps(body) is None

    def test_missing_eps_tags_returns_none(self):
        body = "<PERIOD-TYPE> YEAR\n<PERIOD-END> JUN-30-1997\n<NET-INCOME> 100\n"
        assert parse_ex27_annual_eps(body) is None

    def test_both_eps_zero_is_harmless(self):
        """A genuine double-zero (both tags literally 0) is returned as 0.0 rather than
        ``None`` — harmless either way, since ``_pe_from_ttm_series`` only accepts
        strictly-positive EPS for a PE point, so a 0.0 here simply produces no PE point
        for that date downstream, same net effect as if this function returned ``None``."""
        body = "<PERIOD-TYPE> YEAR\n<PERIOD-END> JUN-30-1997\n<EPS-PRIMARY> 0\n<EPS-DILUTED> 0\n"
        result = parse_ex27_annual_eps(body)
        assert result == (date(1997, 6, 30), 0.0)


class TestParseSelectedFinancialData:
    def test_extracts_five_year_diluted_table(self):
        result = parse_selected_financial_data(_SELECTED_FIN_DATA_TEXT, date(2002, 6, 30))
        assert result == {
            date(1998, 6, 30): 0.84,
            date(1999, 6, 30): 1.42,
            date(2000, 6, 30): 1.70,
            date(2001, 6, 30): 1.32,
            date(2002, 6, 30): 1.41,
        }

    def test_skips_before_accounting_change_variant(self):
        """The adjusted-EPS line's values (1.38 for FY2001) must never be picked up —
        only the plain GAAP 'Diluted earnings per share' line's 1.32 is correct."""
        result = parse_selected_financial_data(_SELECTED_FIN_DATA_TEXT, date(2002, 6, 30))
        assert result[date(2001, 6, 30)] == 1.32

    def test_table_of_contents_only_hit_returns_empty(self):
        text = "Item 6. Selected Financial Data ... See page 11 for more Item 7. MD&A"
        assert parse_selected_financial_data(text, date(2002, 6, 30)) == {}

    def test_no_heading_at_all_returns_empty(self):
        text = "Some unrelated 10-K boilerplate with no Item 6 section at all."
        assert parse_selected_financial_data(text, date(2002, 6, 30)) == {}

    def test_falls_back_to_basic_eps_when_no_diluted_line(self):
        text = (
            "SELECTED FINANCIAL DATA Year Ended December 31 1999 2000 2001 Revenue "
            "$100 $110 $120 Basic earnings per share 1.00 1.10 1.20"
        )
        result = parse_selected_financial_data(text, date(2001, 12, 31))
        assert result == {date(1999, 12, 31): 1.00, date(2000, 12, 31): 1.10, date(2001, 12, 31): 1.20}

    def test_html_tags_stripped_before_matching(self):
        text = (
            "<B>SELECTED FINANCIAL DATA</B> Year Ended <I>June 30</I> 2000 2001 "
            "<TD>Diluted earnings per share</TD> 1.00 1.10"
        )
        result = parse_selected_financial_data(text, date(2001, 6, 30))
        assert result == {date(2000, 6, 30): 1.00, date(2001, 6, 30): 1.10}


def _submissions_payload(forms: list[str], report_dates: list[str], accns: list[str]) -> dict:
    return {
        "filings": {
            "recent": {
                "form": forms,
                "reportDate": report_dates,
                "filingDate": report_dates,
                "accessionNumber": accns,
            },
            "files": [],
        }
    }


class TestListAll10kFilings:
    def test_filters_and_sorts_10k_forms(self):
        payload = _submissions_payload(
            forms=["10-K", "8-K", "10-Q", "10-K"],
            report_dates=["2000-12-31", "2000-09-30", "2000-06-30", "1998-12-31"],
            accns=["0001-00-000001", "0001-00-000002", "0001-00-000003", "0001-98-000004"],
        )
        mock_resp = mock.MagicMock(status_code=200)
        mock_resp.json.return_value = payload
        with mock.patch("src.conviction_engine.pe_history_sec_legacy._get_with_backoff", return_value=mock_resp):
            filings = _list_all_10k_filings("0000000001")
        assert [f["reportDate"] for f in filings] == ["1998-12-31", "2000-12-31"]

    def test_paginates_across_files(self):
        recent = _submissions_payload(forms=["10-K"], report_dates=["2010-12-31"], accns=["0001-10-000001"])
        recent["filings"]["files"] = [{"name": "CIK0000000001-submissions-001.json"}]
        older_page = {"form": ["10-K"], "reportDate": ["1998-12-31"], "filingDate": ["1998-12-31"], "accessionNumber": ["0001-98-000001"]}

        recent_resp = mock.MagicMock(status_code=200)
        recent_resp.json.return_value = recent
        older_resp = mock.MagicMock(status_code=200)
        older_resp.json.return_value = older_page

        with mock.patch(
            "src.conviction_engine.pe_history_sec_legacy._get_with_backoff",
            side_effect=[recent_resp, older_resp],
        ):
            filings = _list_all_10k_filings("0000000001")
        assert [f["reportDate"] for f in filings] == ["1998-12-31", "2010-12-31"]

    def test_network_failure_returns_empty_list(self):
        with mock.patch("src.conviction_engine.pe_history_sec_legacy._get_with_backoff", return_value=None):
            assert _list_all_10k_filings("0000000001") == []


class TestFetchLegacyAnnualEps:
    def _mock_submission_text(self, mapping: dict[str, str]):
        def _fake_fetch(cik, accession):
            return mapping.get(accession)

        return _fake_fetch

    def test_combines_ex27_and_bridge_table(self):
        filings = [
            {"form": "10-K", "reportDate": "1997-06-30", "filingDate": "1997-09-29", "accessionNumber": "ACC-1997"},
            {"form": "10-K", "reportDate": "2002-06-30", "filingDate": "2002-09-06", "accessionNumber": "ACC-2002"},
        ]
        submission_texts = {
            "ACC-1997": f"<TYPE>10-K\n<SEQUENCE>1\n<TEXT>boilerplate</TEXT>\n<TYPE>EX-27\n<SEQUENCE>2\n<TEXT>{_EX27_ARTICLE5}</TEXT>\n",
            "ACC-2002": f"<TYPE>10-K\n<SEQUENCE>1\n<TEXT>{_SELECTED_FIN_DATA_TEXT}</TEXT>\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch(
                    "src.conviction_engine.pe_history_sec_legacy._list_all_10k_filings",
                    return_value=filings,
                ),
                mock.patch(
                    "src.conviction_engine.pe_history_sec_legacy._fetch_submission_text",
                    side_effect=self._mock_submission_text(submission_texts),
                ),
            ):
                series = fetch_legacy_annual_eps(
                    "MSFT", "0000789019", pd.Timestamp("2007-06-30"), cache_dir=Path(tmp)
                )
        assert series[pd.Timestamp("1997-06-30")] == 2.63
        assert series[pd.Timestamp("2002-06-30")] == 1.41
        assert series[pd.Timestamp("1998-06-30")] == 0.84  # from the bridge table
        assert series.index.max() < pd.Timestamp("2007-06-30")

    def test_respects_existing_earliest_date_cutoff(self):
        filings = [
            {"form": "10-K", "reportDate": "1997-06-30", "filingDate": "1997-09-29", "accessionNumber": "ACC-1997"},
        ]
        submission_texts = {
            "ACC-1997": f"<TYPE>EX-27\n<SEQUENCE>2\n<TEXT>{_EX27_ARTICLE5}</TEXT>\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch(
                    "src.conviction_engine.pe_history_sec_legacy._list_all_10k_filings",
                    return_value=filings,
                ),
                mock.patch(
                    "src.conviction_engine.pe_history_sec_legacy._fetch_submission_text",
                    side_effect=self._mock_submission_text(submission_texts),
                ),
            ):
                # cutoff before the only available filing -> nothing usable
                series = fetch_legacy_annual_eps(
                    "MSFT", "0000789019", pd.Timestamp("1996-01-01"), cache_dir=Path(tmp)
                )
        assert series.empty

    def test_no_filings_returns_empty_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "src.conviction_engine.pe_history_sec_legacy._list_all_10k_filings",
                return_value=[],
            ):
                series = fetch_legacy_annual_eps(
                    "ZZZZ", "0000000001", pd.Timestamp("2010-01-01"), cache_dir=Path(tmp)
                )
        assert series.empty

    def test_caches_result_and_skips_network_on_second_call(self):
        filings = [
            {"form": "10-K", "reportDate": "1997-06-30", "filingDate": "1997-09-29", "accessionNumber": "ACC-1997"},
        ]
        submission_texts = {"ACC-1997": f"<TYPE>EX-27\n<SEQUENCE>2\n<TEXT>{_EX27_ARTICLE5}</TEXT>\n"}
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            with (
                mock.patch(
                    "src.conviction_engine.pe_history_sec_legacy._list_all_10k_filings",
                    return_value=filings,
                ) as mock_list,
                mock.patch(
                    "src.conviction_engine.pe_history_sec_legacy._fetch_submission_text",
                    side_effect=self._mock_submission_text(submission_texts),
                ),
            ):
                first = fetch_legacy_annual_eps("MSFT", "0000789019", pd.Timestamp("2007-06-30"), cache_dir=cache_dir)
            assert mock_list.call_count == 1
            assert (cache_dir / "MSFT_sec_legacy.json").exists()

            with mock.patch(
                "src.conviction_engine.pe_history_sec_legacy._list_all_10k_filings"
            ) as mock_list2:
                second = fetch_legacy_annual_eps("MSFT", "0000789019", pd.Timestamp("2007-06-30"), cache_dir=cache_dir)
            mock_list2.assert_not_called()
            pd.testing.assert_series_equal(first.sort_index(), second.sort_index())

    def test_one_filing_fetch_failure_does_not_drop_the_others(self):
        """``_fetch_submission_text`` returns ``None`` on network failure (it's built on
        ``_get_with_backoff``, which already swallows request exceptions) — orchestration
        must skip that filing and keep whatever it got from the rest, not crash/lose all data."""
        filings = [
            {"form": "10-K", "reportDate": "1996-06-30", "filingDate": "1996-09-27", "accessionNumber": "ACC-FAIL"},
            {"form": "10-K", "reportDate": "1997-06-30", "filingDate": "1997-09-29", "accessionNumber": "ACC-1997"},
        ]
        submission_texts = {"ACC-1997": f"<TYPE>EX-27\n<SEQUENCE>2\n<TEXT>{_EX27_ARTICLE5}</TEXT>\n"}
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch(
                    "src.conviction_engine.pe_history_sec_legacy._list_all_10k_filings",
                    return_value=filings,
                ),
                mock.patch(
                    "src.conviction_engine.pe_history_sec_legacy._fetch_submission_text",
                    side_effect=self._mock_submission_text(submission_texts),  # ACC-FAIL -> None
                ),
            ):
                series = fetch_legacy_annual_eps(
                    "MSFT", "0000789019", pd.Timestamp("2007-06-30"), cache_dir=Path(tmp)
                )
        assert series[pd.Timestamp("1997-06-30")] == 2.63
        assert pd.Timestamp("1996-06-30") not in series.index


if __name__ == "__main__":
    import unittest

    unittest.main()
