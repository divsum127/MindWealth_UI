"""CE-24: CEO start dates from the DEF 14A Pay-versus-Performance table."""

from __future__ import annotations

from src.conviction_engine.ceo_tenure import derive_ceo_start, parse_peo_history


def _ctx(cid, start, end, member=None):
    seg = (
        f'<xbrli:segment><xbrldi:explicitMember dimension="ecd:IndividualAxis">{member}</xbrldi:explicitMember></xbrli:segment>'
        if member else ""
    )
    return (f'<xbrli:context id="{cid}"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier>{seg}</xbrli:entity>'
            f'<xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context>')


def _doc(body):
    return ('<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
            'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:ecd="http://xbrl.sec.gov/ecd/2024">' + body + "</xbrli:xbrl>").encode()


YEARS = [("2021-10-01", "2022-09-30"), ("2022-10-01", "2023-09-30"), ("2023-10-01", "2024-09-29"), ("2024-09-30", "2025-09-28")]


def test_disney_style_named_years_with_handover():
    names = ["Mr. Old", "Mr. Old", "Mr. New", "Mr. New"]
    body = "".join(_ctx(f"y{i}", *y) for i, y in enumerate(YEARS))
    body += "".join(_ctx(f"m{i}", *YEARS[2], member=m) for i, m in enumerate(["co:MrOldMember", "co:MrNewMember"]))
    body += "".join(f'<ecd:PeoName contextRef="y{i}">{n}</ecd:PeoName>' for i, n in enumerate(names))
    body += '<ecd:PeoTotalCompAmt contextRef="m0">5</ecd:PeoTotalCompAmt><ecd:PeoTotalCompAmt contextRef="m1">5</ecd:PeoTotalCompAmt>'
    history = parse_peo_history(_doc(body))
    assert history[2]["peos"] == ["Mr. New", "Mr. Old"]  # members matched to names, no duplicates
    assert derive_ceo_start(history) == {"ceo_name": "Mr. New", "precision": "handover_year_end", "ceo_start_date": "2024-09-29"}


def test_clean_change_between_years_uses_year_start():
    history = [{"start": a, "end": b, "peos": [p]} for (a, b), p in zip(YEARS, ["A", "A", "B", "B"])]
    assert derive_ceo_start(history) == {"ceo_name": "B", "precision": "fiscal_year", "ceo_start_date": "2023-10-01"}


def test_same_ceo_across_window_is_only_a_lower_bound():
    history = [{"start": a, "end": b, "peos": ["A"]} for a, b in YEARS]
    out = derive_ceo_start(history)
    assert out["precision"] == "lower_bound" and "ceo_start_date" not in out
    unnamed = [{"start": a, "end": b, "peos": []} for a, b in YEARS]
    assert derive_ceo_start(unnamed) == {"ceo_name": None, "precision": "lower_bound", "at_least_since": "2021-10-01"}


def test_unnamed_earlier_years_are_not_a_ceo_change():
    # AMD-style: only the latest year carries a name; earlier years are unnamed PEO pay.
    history = [{"start": a, "end": b, "peos": p} for (a, b), p in zip(YEARS, [[], [], [], ["Lisa Su"]])]
    assert derive_ceo_start(history)["precision"] == "lower_bound"


def test_name_variants_are_the_same_person():
    history = [{"start": a, "end": b, "peos": [p]} for (a, b), p in zip(YEARS, ["Dr. Su", "Dr. Su", "Lisa Su", "Lisa Su"])]
    assert derive_ceo_start(history)["precision"] == "lower_bound"
