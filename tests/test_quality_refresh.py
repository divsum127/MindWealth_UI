"""Quality columns must move with the price they are derived from.

The consolidated chatbot CSVs kept several rows per signal, one per day written,
and a daily job refreshed Today/MTM on every one of them while leaving R:R,
timeliness and reward remaining frozen. The fetcher then served the oldest row,
so a June ratio was printed beside an August price.
"""

import pandas as pd
import pytest

from src.utils.quality_refresh import QUALITY_AS_OF_COLUMN, refresh_quality_columns

SYMBOL_COL = "Symbol, Signal, Signal Date/Price[$]"
TODAY_COL = "Today Trading Date/Price[$], Today Price vs Signal"
STOP_COL = (
    "Stop Loss (Recent Extrema/Horizontal/F-Stack 1/F-Stack 2/"
    "F-Track 1/F-Track 2/EMA 200) [$]"
)


def _mcy_frame(rr_static=1.48, rr_dynamic=1.90, timeliness=100.0, reward_remaining="100.0%"):
    """The stale MCY.NZ row as chatbot/data/entry.csv actually held it."""
    return pd.DataFrame(
        [
            {
                "Function": "OSCILLATOR DELTA",
                SYMBOL_COL: "MCY.NZ, Long, 2026-06-22 (Price: 6.89)",
                "Signal Open Price": 6.94,
                TODAY_COL: "2026-08-25 (Price: 6.9500), 0.87% above",
                "Trading Days between Signal and Today Date": "65 days",
                "Interval, Confirmation Status": "Daily, is Confirmed on 2026-06-22",
                "Backtested Returns(Win Trades) [%] (Max/Min/Avg)": "9.68%/0.31%/2.64%",
                STOP_COL: (
                    "No Recent Minima/5.13/No F-Stack Support/No F-Stack Support/"
                    "6.7672/6.5259/6.56"
                ),
                "Cancellation Level/Date": "Already confirmed",
                "R:R Static": rr_static,
                "R:R Dynamic": rr_dynamic,
                "Timeliness Score": timeliness,
                "Reward Remaining [%]": reward_remaining,
            }
        ]
    )


def test_refresh_replaces_the_signal_date_ratio_with_todays():
    out = refresh_quality_columns(_mcy_frame())
    assert out.loc[0, "R:R Dynamic"] < 1.0
    assert out.loc[0, "R:R Dynamic"] != 1.90
    assert out.loc[0, "R:R Static"] != 1.48


def test_refresh_corrects_timeliness_and_reward_remaining():
    out = refresh_quality_columns(_mcy_frame())
    assert out.loc[0, "Timeliness Score"] == 0
    assert out.loc[0, "Reward Remaining [%]"] != "100.0%"
    assert float(str(out.loc[0, "Reward Remaining [%]"]).rstrip("%")) < 100.0


def test_refresh_stamps_the_vintage_from_the_price_date():
    out = refresh_quality_columns(_mcy_frame())
    assert out.loc[0, QUALITY_AS_OF_COLUMN] == "2026-08-25"


def test_explicit_as_of_wins_over_the_price_date():
    out = refresh_quality_columns(_mcy_frame(), as_of="2026-08-27")
    assert out.loc[0, QUALITY_AS_OF_COLUMN] == "2026-08-27"


def test_refresh_is_idempotent():
    once = refresh_quality_columns(_mcy_frame())
    twice = refresh_quality_columns(once)
    for column in ("R:R Static", "R:R Dynamic", "Timeliness Score", "Reward Remaining [%]"):
        assert str(once.loc[0, column]) == str(twice.loc[0, column]), column


def test_refresh_does_not_invent_columns_the_report_never_had():
    frame = _mcy_frame().drop(columns=["R:R Static"])
    out = refresh_quality_columns(frame)
    assert "R:R Static" not in out.columns


def test_empty_frame_passes_through():
    empty = pd.DataFrame()
    assert refresh_quality_columns(empty).empty


def test_unenrichable_row_keeps_its_previous_values():
    """A row the enricher cannot read must not be silently zeroed."""
    frame = pd.DataFrame(
        [{SYMBOL_COL: "", "Function": "", "R:R Dynamic": 2.5, TODAY_COL: ""}]
    )
    out = refresh_quality_columns(frame)
    assert out.loc[0, "R:R Dynamic"] in (2.5, None) or pd.isna(out.loc[0, "R:R Dynamic"])


def test_stale_and_fresh_rows_converge_after_refresh():
    """Two vintages of the same signal must agree once both are recomputed."""
    stale = _mcy_frame(rr_static=1.48, rr_dynamic=1.90, timeliness=100.0)
    fresh = _mcy_frame(rr_static=0.55, rr_dynamic=0.71, timeliness=20.0)
    a = refresh_quality_columns(stale)
    b = refresh_quality_columns(fresh)
    assert a.loc[0, "R:R Dynamic"] == pytest.approx(b.loc[0, "R:R Dynamic"])


def test_answering_prompt_carries_the_risk_reward_rules():
    """The rules must live in the prompt that writes answers, not only the one
    that picks columns — the first draft put them in chatbot_system.txt, which is
    only read by the column selector."""
    from chatbot.config import SYSTEM_PROMPT

    assert "RISK / REWARD REPORTING" in SYSTEM_PROMPT
    for required in (
        "nearest_support_stop",
        "stop_distance_pct",
        "rr_null_reason",
        "quality_as_of",
        "Never present current MTM as a reason to enter",
        # A wide stop is an honest large risk leg, not a noise artefact. The first
        # draft said only "below 1.5 means noise" and a model duly described a
        # 12.43% stop as "inside normal volatility".
        "never as noise",
        # A replay had the model print stored R:R Static 0.4 and its own 0.55
        # beside it, and guess that Reward Remaining referred to the pivot target.
        "It is NOT the reward-to-risk of the original entry",
        "It never refers to the pivot",
    ):
        assert required in SYSTEM_PROMPT, required


def test_audit_columns_are_created_even_when_absent_from_the_report():
    frame = _mcy_frame()
    out = refresh_quality_columns(frame)
    for column in (
        "nearest_support_stop",
        "nearest_support_stop_type",
        "risk_to_nearest_stop",
        "proposed_reward",
        "bt_avg_exit_price",
        "stop_distance_pct",
    ):
        assert column in out.columns, column
    assert out.loc[0, "nearest_support_stop_type"] == "F-Track 1"


def test_quoted_ratio_reproduces_from_its_own_audit_legs():
    out = refresh_quality_columns(_mcy_frame())
    ratio = out.loc[0, "proposed_reward"] / out.loc[0, "risk_to_nearest_stop"]
    assert out.loc[0, "R:R Dynamic"] == pytest.approx(ratio, abs=0.01)


def test_nan_cells_from_a_dataframe_row_do_not_abort_enrichment():
    """Pandas hands back NaN for an empty cell where csv.DictReader gives "".

    Every parser was written for the latter, so recomputing over DataFrame rows
    raised AttributeError mid-enrichment and the row silently kept its stale
    values — the exact failure this work exists to remove.
    """
    frame = _mcy_frame()
    frame.loc[
        0,
        "Targets (Historic Rise or Fall to Pivot/Avg % Gain of Historic Winning trades/"
        "Function Specific Target/Horizontal/F-Stack 1/F-Stack 2/EMA 200) [$]",
    ] = float("nan")
    out = refresh_quality_columns(frame)
    assert out.loc[0, "nearest_support_stop"] == 6.7672
    assert out.loc[0, QUALITY_AS_OF_COLUMN] == "2026-08-25"


def test_a_row_with_no_valid_stop_reports_why_instead_of_a_ratio():
    stop_col = (
        "Stop Loss (Recent Extrema/Horizontal/F-Stack 1/F-Stack 2/"
        "F-Track 1/F-Track 2/EMA 200) [$]"
    )
    frame = _mcy_frame()
    frame.loc[0, stop_col] = (
        "No Recent Minima/No Horizontal/No F-Stack Support/No F-Stack Support/"
        "No F-Track Level/No F-Track Level/No EMA 200 Stop Loss"
    )
    out = refresh_quality_columns(frame)
    assert out.loc[0, "rr_null_reason"]
    assert pd.isna(out.loc[0, "R:R Dynamic"]) or out.loc[0, "R:R Dynamic"] is None


def test_importing_the_enricher_does_not_shadow_this_repo_config():
    """MINDWEALTH_ROOT must not precede this repo on sys.path.

    The core repo ships its own top-level ``config`` module. Inserting its root at
    position 0 made the chatbot's ``from config import CHATBOT_ENTRY_DIR`` resolve
    to the core file and fail at import time, on the serving path.
    """
    import sys

    from src.config_paths import MINDWEALTH_ROOT
    from src.utils.quality_refresh import _enrich_signal_dict

    _enrich_signal_dict()
    # The root is borrowed for the import and handed back, so it must not linger.
    assert str(MINDWEALTH_ROOT) not in sys.path

    # Importing the fetcher after the enricher must still resolve the chatbot's
    # own config, which is the import that broke.
    from chatbot.column_metadata_extractor import CHATBOT_ENTRY_DIR

    assert "MindWealth_UI" in str(CHATBOT_ENTRY_DIR)
