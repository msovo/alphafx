"""
Signal candidate builder.

Combines indicators + structure + patterns + MTF into a scored signal dict
that is the standard payload through the rest of the pipeline.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from analysis.patterns import detect_patterns, pattern_score
from analysis.structure import (
    detect_fvg, nearest_level, pivot_points, support_resistance_levels,
)
from config.settings import get_settings
from data.session import detect_session
from utils.helpers import price_to_pips, utcnow_iso


def _confluence_score(direction: str, last: pd.Series, mtf: dict, patterns_d: dict, sr: dict) -> float:
    score = 0.0
    weights = {
        "trend": 25, "rsi": 15, "macd": 15, "ema_stack": 15,
        "patterns": 10, "sr_proximity": 10, "bb": 5, "stoch": 5,
    }

    # MTF trend alignment
    if mtf.get("aligned") and mtf.get("direction") == direction:
        score += weights["trend"]

    # RSI bias (not overbought/oversold against direction)
    rsi = float(last.get("rsi", 50))
    if direction == "BUY":
        score += weights["rsi"] * max(0.0, min(1.0, (rsi - 30) / 40))
    else:
        score += weights["rsi"] * max(0.0, min(1.0, (70 - rsi) / 40))

    # MACD direction
    if direction == "BUY" and last.get("macd_hist", 0) > 0:
        score += weights["macd"]
    if direction == "SELL" and last.get("macd_hist", 0) < 0:
        score += weights["macd"]

    # EMA stack
    if direction == "BUY" and last.get("ema20", 0) > last.get("ema50", 0):
        score += weights["ema_stack"]
    if direction == "SELL" and last.get("ema20", 0) < last.get("ema50", 0):
        score += weights["ema_stack"]

    # Pattern confirmation
    psc = pattern_score(patterns_d, direction)
    score += max(0, psc) * (weights["patterns"] / 2)

    # S&R proximity (within ATR)
    atr = float(last.get("atr", 0)) or 1e-9
    levels = sr.get("support" if direction == "BUY" else "resistance", [])
    _, dist = nearest_level(float(last["close"]), levels)
    if dist < atr * 1.5:
        score += weights["sr_proximity"]

    # Bollinger reversion bias
    if direction == "BUY" and last["close"] <= last.get("bb_lower", last["close"]):
        score += weights["bb"]
    if direction == "SELL" and last["close"] >= last.get("bb_upper", last["close"]):
        score += weights["bb"]

    # Stochastic
    sk = float(last.get("stoch_k", 50))
    if direction == "BUY" and sk < 30:
        score += weights["stoch"]
    if direction == "SELL" and sk > 70:
        score += weights["stoch"]

    return round(min(score, 100.0), 2)


def _decide_direction(last: pd.Series, mtf: dict) -> str | None:
    if mtf.get("aligned"):
        return mtf["direction"]
    # Fallback bias from EMA stack
    if last["ema20"] > last["ema50"] > last["ema200"]:
        return "BUY"
    if last["ema20"] < last["ema50"] < last["ema200"]:
        return "SELL"
    return None


def build_signal(pair: str, timeframe: str, df: pd.DataFrame, mtf: dict) -> dict[str, Any] | None:
    if df is None or df.empty or len(df) < 50:
        return None

    last = df.iloc[-1]
    direction = _decide_direction(last, mtf)
    if direction is None:
        return None

    s = get_settings()
    atr = float(last.get("atr", 0))
    if atr <= 0:
        return None

    sl_mult = float(s.get("risk.atr_sl_multiplier", 1.5))
    tp_mult = float(s.get("risk.atr_tp_multiplier", 3.0))
    entry = float(last["close"])
    if direction == "BUY":
        sl = entry - atr * sl_mult
        tp = entry + atr * tp_mult
    else:
        sl = entry + atr * sl_mult
        tp = entry - atr * tp_mult

    rr = abs(tp - entry) / max(abs(entry - sl), 1e-9)
    if rr < float(s.get("strategy.min_rr", 1.5)):
        return None

    patterns = detect_patterns(df)
    sr = support_resistance_levels(df)
    pp = pivot_points(df)
    fvgs = detect_fvg(df)

    confluence = _confluence_score(direction, last, mtf, patterns, sr)

    digits = int(s.get(f"instruments.{pair}.digits", 5))
    sl_pips = price_to_pips(pair, digits, abs(entry - sl))

    return {
        "timestamp": utcnow_iso(),
        "pair": pair,
        "timeframe": timeframe,
        "direction": direction,
        "entry": round(entry, digits),
        "sl": round(sl, digits),
        "tp": round(tp, digits),
        "rr": round(rr, 2),
        "sl_pips": round(sl_pips, 1),
        "atr": atr,
        "confluence_score": confluence,
        "ml_probability": None,
        "ai_decision": None,
        "ai_confidence": None,
        "ai_reason": None,
        "ai_risk_flag": None,
        "executed": 0,
        "filter_stage": None,
        "session": detect_session(),
        "indicator_snapshot": {
            "rsi": float(last.get("rsi", 0)),
            "macd_hist": float(last.get("macd_hist", 0)),
            "ema20": float(last.get("ema20", 0)),
            "ema50": float(last.get("ema50", 0)),
            "ema200": float(last.get("ema200", 0)),
            "stoch_k": float(last.get("stoch_k", 0)),
            "bb_upper": float(last.get("bb_upper", 0)),
            "bb_lower": float(last.get("bb_lower", 0)),
            "rel_volume": float(last.get("rel_volume", 0)) if last.get("rel_volume") is not None else 0.0,
        },
        "structure": {"sr": sr, "pivots": pp, "fvgs": fvgs[-5:]},
        "patterns": patterns,
        "mtf": mtf,
    }
