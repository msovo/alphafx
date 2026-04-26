"""
Multi-timeframe (MTF) confluence helper.

Looks at H4 (trend) + H1 (structure) + entry-TF and reports:
- direction agreement
- trend strength
- key MA alignment
"""
from __future__ import annotations

from typing import Any

from analysis.indicators import compute_indicators
from data.feed import get_ohlcv


def _trend_from_df(df) -> int:
    if df is None or df.empty:
        return 0
    last = df.iloc[-1]
    if last["close"] > last["ema50"] > last["ema200"]:
        return 1
    if last["close"] < last["ema50"] < last["ema200"]:
        return -1
    return 0


def compute_mtf_alignment(symbol: str) -> dict[str, Any]:
    h4 = compute_indicators(get_ohlcv(symbol, "H4", n=300))
    h1 = compute_indicators(get_ohlcv(symbol, "H1", n=300))
    h4_trend = _trend_from_df(h4)
    h1_trend = _trend_from_df(h1)

    aligned = h4_trend != 0 and h4_trend == h1_trend
    direction = "BUY" if h4_trend == 1 else "SELL" if h4_trend == -1 else "NONE"

    return {
        "h4_trend": h4_trend,
        "h1_trend": h1_trend,
        "aligned": aligned,
        "direction": direction,
        "strength": int(aligned) * (abs(h4_trend) + abs(h1_trend)),
    }
