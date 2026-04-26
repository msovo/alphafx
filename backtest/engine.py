"""
Vectorised backtester.

Replays a pair's OHLCV through `compute_indicators + build_signal`, simulates
trades with ATR-based SL/TP and the same R:R rules used live.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from analysis.indicators import compute_indicators
from analysis.mtf import compute_mtf_alignment
from analysis.signal import build_signal
from data.feed import get_ohlcv


@dataclass
class BacktestTrade:
    open_time: pd.Timestamp
    close_time: pd.Timestamp
    pair: str
    direction: str
    entry: float
    sl: float
    tp: float
    exit_price: float
    pnl_pips: float
    rr_achieved: float
    outcome: str


def run_backtest(pair: str, timeframe: str = "M15", n: int = 1000) -> dict:
    df = get_ohlcv(pair, timeframe, n=n)
    if df is None or df.empty:
        return {"trades": [], "metrics": {}, "equity": []}

    df_ind = compute_indicators(df)
    mtf = compute_mtf_alignment(pair)

    trades: list[BacktestTrade] = []
    open_trade: dict | None = None
    for i in range(50, len(df_ind) - 1):
        bar = df_ind.iloc[i]
        ts = df_ind.index[i]

        if open_trade:
            high = bar["high"]; low = bar["low"]
            hit_tp = (open_trade["direction"] == "BUY" and high >= open_trade["tp"]) or \
                     (open_trade["direction"] == "SELL" and low <= open_trade["tp"])
            hit_sl = (open_trade["direction"] == "BUY" and low <= open_trade["sl"]) or \
                     (open_trade["direction"] == "SELL" and high >= open_trade["sl"])
            if hit_sl or hit_tp:
                exit_price = open_trade["tp"] if hit_tp else open_trade["sl"]
                outcome = "win" if hit_tp else "loss"
                pnl_price = (exit_price - open_trade["entry"]) if open_trade["direction"] == "BUY" \
                    else (open_trade["entry"] - exit_price)
                trades.append(BacktestTrade(
                    open_time=open_trade["time"], close_time=ts, pair=pair,
                    direction=open_trade["direction"], entry=open_trade["entry"],
                    sl=open_trade["sl"], tp=open_trade["tp"], exit_price=exit_price,
                    pnl_pips=pnl_price, rr_achieved=open_trade["rr"] if hit_tp else -1.0,
                    outcome=outcome,
                ))
                open_trade = None

        if open_trade is None:
            sig = build_signal(pair, timeframe, df_ind.iloc[: i + 1], mtf)
            if sig:
                open_trade = {
                    "time": ts, "direction": sig["direction"], "entry": sig["entry"],
                    "sl": sig["sl"], "tp": sig["tp"], "rr": sig["rr"],
                }

    eq, run = [], 0.0
    for t in trades:
        run += t.pnl_pips
        eq.append({"time": str(t.close_time), "equity": run})

    wins = [t for t in trades if t.outcome == "win"]
    metrics = {
        "trades": len(trades),
        "win_rate": round(len(wins) / max(1, len(trades)) * 100, 2),
        "total_return_pips": round(sum(t.pnl_pips for t in trades), 4),
    }
    return {
        "trades": [asdict(t) for t in trades],
        "metrics": metrics,
        "equity": eq,
    }
