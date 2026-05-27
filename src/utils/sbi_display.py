"""Display helpers for trade-arrival SBI percentile semantics.

Percentile-from-top (MindWealth compute.py):
  - LOW value (e.g. 10)  -> today is among the busiest days (top decile of signal counts)
  - HIGH value (e.g. 100) -> quiet day; 100 with 0 signals = no new signals (holiday/weekend)
"""


def sbi_activity_status(long_pct, short_pct, long_count=0, short_count=0):
    """
    Return (label, color, explanation) for SBI activity badge.

    Uses average of long/short percentile-from-top; lower = busier.
    """
    long_count = int(long_count or 0)
    short_count = int(short_count or 0)
    long_pct = float(long_pct or 0)
    short_pct = float(short_pct or 0)

    if long_count == 0 and short_count == 0:
        return (
            "⚪ No new signals",
            "gray",
            "No qualifying new long or short signals today (e.g. market holiday).",
        )

    avg_p = (long_pct + short_pct) / 2.0
    if avg_p <= 10:
        return (
            "🔴 Extreme activity",
            "crimson",
            "Top-decile signal day vs last 6 months (low percentile-from-top).",
        )
    if avg_p <= 25:
        return (
            "🟠 Elevated activity",
            "darkorange",
            "Above-average signal arrivals vs last 6 months.",
        )
    if avg_p >= 90:
        return (
            "🔵 Quiet day",
            "steelblue",
            "Few signals vs 6-month history (high percentile-from-top).",
        )
    return (
        "🟡 Normal",
        "goldenrod",
        "Typical signal activity vs last 6 months.",
    )


SBI_PERCENTILE_HELP = (
    "Percentile from the busiest day in the last 6 months. "
    "Lower = busier (e.g. 10 ≈ top 10% activity); higher = quieter."
)
