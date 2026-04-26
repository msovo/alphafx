"""
Pure-pandas candlestick pattern detection.
Returns a dict[name -> bool] for the **last** bar of `df`.
"""
from __future__ import annotations

import pandas as pd


def _body(c: pd.Series) -> float:
    return abs(c["close"] - c["open"])


def _range(c: pd.Series) -> float:
    return max(c["high"] - c["low"], 1e-10)


def _is_bullish(c: pd.Series) -> bool:
    return c["close"] > c["open"]


def detect_patterns(df: pd.DataFrame) -> dict[str, bool]:
    if df is None or len(df) < 3:
        return {}
    p1, p2, p3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    out: dict[str, bool] = {}

    # Engulfing
    out["bullish_engulfing"] = bool(
        not _is_bullish(p2) and _is_bullish(p3)
        and p3["close"] > p2["open"] and p3["open"] < p2["close"]
    )
    out["bearish_engulfing"] = bool(
        _is_bullish(p2) and not _is_bullish(p3)
        and p3["close"] < p2["open"] and p3["open"] > p2["close"]
    )

    # Pin bar / hammer / shooting star
    body = _body(p3)
    rng = _range(p3)
    upper_wick = p3["high"] - max(p3["open"], p3["close"])
    lower_wick = min(p3["open"], p3["close"]) - p3["low"]
    small_body = body < 0.35 * rng
    out["hammer"] = bool(small_body and lower_wick > 2 * body and upper_wick < body)
    out["shooting_star"] = bool(small_body and upper_wick > 2 * body and lower_wick < body)
    out["pin_bar_bullish"] = out["hammer"]
    out["pin_bar_bearish"] = out["shooting_star"]

    # Inside bar
    out["inside_bar"] = bool(p3["high"] < p2["high"] and p3["low"] > p2["low"])

    # Morning / Evening star
    out["morning_star"] = bool(
        not _is_bullish(p1) and _body(p2) < 0.3 * _range(p2)
        and _is_bullish(p3) and p3["close"] > (p1["open"] + p1["close"]) / 2
    )
    out["evening_star"] = bool(
        _is_bullish(p1) and _body(p2) < 0.3 * _range(p2)
        and not _is_bullish(p3) and p3["close"] < (p1["open"] + p1["close"]) / 2
    )

    return out


def pattern_score(patterns: dict[str, bool], direction: str) -> int:
    """Convert pattern dict → directional score (-2..+2)."""
    score = 0
    if direction.upper() == "BUY":
        score += 1 if patterns.get("bullish_engulfing") else 0
        score += 1 if patterns.get("hammer") else 0
        score += 1 if patterns.get("morning_star") else 0
        score -= 1 if patterns.get("bearish_engulfing") else 0
        score -= 1 if patterns.get("shooting_star") else 0
    else:
        score += 1 if patterns.get("bearish_engulfing") else 0
        score += 1 if patterns.get("shooting_star") else 0
        score += 1 if patterns.get("evening_star") else 0
        score -= 1 if patterns.get("bullish_engulfing") else 0
        score -= 1 if patterns.get("hammer") else 0
    return score
