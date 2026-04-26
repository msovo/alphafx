"""
Performance analytics on the trade journal.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import REPORT_DIR
from journal.db import query
from utils.helpers import utcnow_iso
from utils.logging import logger


def closed_trades(limit: int | None = None) -> pd.DataFrame:
    sql = "SELECT * FROM trades WHERE status='closed' ORDER BY close_time DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return query(sql)


def equity_curve() -> pd.DataFrame:
    df = closed_trades()
    if df.empty:
        return pd.DataFrame(columns=["close_time", "equity"])
    df = df.sort_values("close_time")
    df["equity"] = df["pnl_usd"].fillna(0).cumsum()
    return df[["close_time", "equity", "pair", "pnl_usd"]]


def overall_metrics() -> dict:
    df = closed_trades()
    if df.empty:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "avg_rr": 0,
                "total_pnl": 0, "max_consec_loss": 0}
    wins = df[df["pnl_usd"] > 0]
    losses = df[df["pnl_usd"] <= 0]
    wr = len(wins) / len(df) * 100
    pf = (wins["pnl_usd"].sum() / abs(losses["pnl_usd"].sum())) if not losses.empty and losses["pnl_usd"].sum() != 0 else float("inf")
    return {
        "trades": int(len(df)),
        "win_rate": round(wr, 2),
        "profit_factor": round(float(pf), 2) if pf != float("inf") else None,
        "avg_rr": round(float(df["rr_achieved"].mean() or 0), 2),
        "total_pnl": round(float(df["pnl_usd"].sum() or 0), 2),
        "best_pair": _best_group(df, "pair"),
        "worst_pair": _worst_group(df, "pair"),
        "best_session": _best_group(df, "session"),
        "max_consec_loss": _max_consec_loss(df),
        "sharpe_30": _sharpe(df.tail(30)["pnl_usd"]),
    }


def _best_group(df: pd.DataFrame, col: str) -> str | None:
    if col not in df.columns or df.empty:
        return None
    g = df.groupby(col)["pnl_usd"].sum().sort_values(ascending=False)
    return None if g.empty else str(g.index[0])


def _worst_group(df: pd.DataFrame, col: str) -> str | None:
    if col not in df.columns or df.empty:
        return None
    g = df.groupby(col)["pnl_usd"].sum().sort_values()
    return None if g.empty else str(g.index[0])


def _max_consec_loss(df: pd.DataFrame) -> int:
    streak = best = 0
    for v in df["pnl_usd"].fillna(0):
        if v <= 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def _sharpe(returns: pd.Series) -> float:
    if returns is None or returns.empty or returns.std(ddof=0) == 0:
        return 0.0
    return round(float(returns.mean() / returns.std(ddof=0) * np.sqrt(252)), 2)


def by_pair() -> pd.DataFrame:
    df = closed_trades()
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("pair").agg(
        trades=("id", "count"),
        win_rate=("pnl_usd", lambda s: (s > 0).mean() * 100),
        pnl=("pnl_usd", "sum"),
        avg_rr=("rr_achieved", "mean"),
    ).reset_index()
    return g


def by_session() -> pd.DataFrame:
    df = closed_trades()
    if df.empty or "session" not in df.columns:
        return pd.DataFrame()
    g = df.groupby("session").agg(
        trades=("id", "count"),
        win_rate=("pnl_usd", lambda s: (s > 0).mean() * 100),
        pnl=("pnl_usd", "sum"),
    ).reset_index()
    return g


def generate_weekly_report() -> str | None:
    df = closed_trades()
    if df.empty:
        logger.info("No closed trades — skipping weekly report")
        return None
    metrics = overall_metrics()
    fname = REPORT_DIR / f"weekly_report_{utcnow_iso().replace(' ', '_').replace(':', '-')}.csv"
    df.to_csv(fname, index=False)
    summary = REPORT_DIR / fname.name.replace(".csv", "_summary.txt")
    summary.write_text("\n".join(f"{k}: {v}" for k, v in metrics.items()), encoding="utf-8")
    logger.success(f"Weekly report → {fname}")
    return str(fname)
