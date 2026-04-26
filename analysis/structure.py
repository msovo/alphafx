"""
Market structure detection — swing high/lows, S&R levels, FVGs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def swing_points(df: pd.DataFrame, lookback: int = 3) -> pd.DataFrame:
    """Mark swing highs/lows where a bar is the local max/min over `lookback` on each side."""
    highs = df["high"].values
    lows = df["low"].values
    sw_high = np.zeros(len(df), dtype=bool)
    sw_low = np.zeros(len(df), dtype=bool)
    for i in range(lookback, len(df) - lookback):
        if highs[i] == max(highs[i - lookback:i + lookback + 1]):
            sw_high[i] = True
        if lows[i] == min(lows[i - lookback:i + lookback + 1]):
            sw_low[i] = True
    out = df.copy()
    out["swing_high"] = sw_high
    out["swing_low"] = sw_low
    return out


def support_resistance_levels(df: pd.DataFrame, n_levels: int = 5, lookback: int = 50) -> dict[str, list[float]]:
    """Return clustered support/resistance levels from recent swing points."""
    sub = swing_points(df.tail(lookback * 2), lookback=3)
    highs = sub.loc[sub["swing_high"], "high"].tolist()
    lows = sub.loc[sub["swing_low"], "low"].tolist()
    return {
        "resistance": _cluster(highs, n_levels),
        "support": _cluster(lows, n_levels),
    }


def _cluster(values: list[float], n: int) -> list[float]:
    if not values:
        return []
    s = sorted(values)
    if len(s) <= n:
        return s
    step = len(s) // n
    return [round(float(np.mean(s[i*step:(i+1)*step])), 5) for i in range(n)]


def pivot_points(df: pd.DataFrame) -> dict[str, float]:
    """Classic floor-trader pivots from the previous bar."""
    if len(df) < 2:
        return {}
    prev = df.iloc[-2]
    p = (prev["high"] + prev["low"] + prev["close"]) / 3
    r1 = 2 * p - prev["low"]
    s1 = 2 * p - prev["high"]
    r2 = p + (prev["high"] - prev["low"])
    s2 = p - (prev["high"] - prev["low"])
    return {"P": float(p), "R1": float(r1), "S1": float(s1), "R2": float(r2), "S2": float(s2)}


def detect_fvg(df: pd.DataFrame, lookback: int = 100) -> list[dict]:
    """Detect Fair Value Gaps in the last `lookback` bars."""
    sub = df.tail(lookback)
    fvgs: list[dict] = []
    rows = sub.reset_index()
    for i in range(2, len(rows)):
        a, b, c = rows.iloc[i - 2], rows.iloc[i - 1], rows.iloc[i]
        if a["high"] < c["low"]:
            fvgs.append({"type": "bullish", "low": float(a["high"]), "high": float(c["low"]), "index": i})
        elif a["low"] > c["high"]:
            fvgs.append({"type": "bearish", "low": float(c["high"]), "high": float(a["low"]), "index": i})
    return fvgs


def nearest_level(price: float, levels: list[float]) -> tuple[float | None, float]:
    """Return (level, distance) — distance is absolute price-units."""
    if not levels:
        return None, float("inf")
    nearest = min(levels, key=lambda x: abs(price - x))
    return nearest, abs(price - nearest)
