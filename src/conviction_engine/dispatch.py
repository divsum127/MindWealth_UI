"""Optional live-dispatch adapter for quant engine integrations."""

from __future__ import annotations

from .engine import modify_signal
from .signals import signal_timeframe_from_interval


def conviction_dispatch(
    symbol: str,
    signal_value: int | float | str,
    interval: str,
    function_name: str,
    strength: float = 0.75,
    near_stop: bool = False,
):
    if signal_value in (0, "0", None):
        return None
    if str(signal_value).strip().lower() in {"long", "buy", "1"} or signal_value == 1:
        direction = "BUY"
    else:
        direction = "SELL"

    timeframe = signal_timeframe_from_interval(interval)
    return modify_signal(
        ticker=symbol,
        technical_signal=direction,
        signal_timeframe=timeframe,
        signal_strength=strength,
        quant_model_name=f"{function_name}_{interval}",
        long_position_near_stop=near_stop,
    )
