"""
Feature engineering for the ML filter.

Converts a signal dict (and optional context) into a flat numeric vector
that matches the columns the model was trained on.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from journal.db import query

FEATURES: list[str] = [
    "rsi", "atr_rel", "macd_hist", "stoch_k", "rel_volume",
    "ema_stack", "h4_trend", "h1_trend", "mtf_aligned",
    "session_id", "day_of_week", "hour_utc",
    "confluence_score", "rr", "sl_pips",
    "recent_winrate_5", "minutes_to_news",
]


_SESSION_ID = {"asia": 0, "london": 1, "new_york": 2, "overlap": 3, "off_hours": 4}


def signal_to_features(signal: dict[str, Any], minutes_to_news: int | None = None) -> pd.DataFrame:
    snap = signal.get("indicator_snapshot", {})
    mtf = signal.get("mtf", {})
    entry = float(signal.get("entry") or 0)
    atr_rel = (float(snap.get("rsi", 0)) and (signal.get("atr") or 0) / entry) if entry else 0
    ema_stack = 1 if (snap.get("ema20", 0) > snap.get("ema50", 0) > snap.get("ema200", 0)) else \
                -1 if (snap.get("ema20", 0) < snap.get("ema50", 0) < snap.get("ema200", 0)) else 0
    now = datetime.utcnow()
    feats = {
        "rsi": float(snap.get("rsi", 50)),
        "atr_rel": float(atr_rel or 0),
        "macd_hist": float(snap.get("macd_hist", 0)),
        "stoch_k": float(snap.get("stoch_k", 50)),
        "rel_volume": float(snap.get("rel_volume", 1.0) or 1.0),
        "ema_stack": ema_stack,
        "h4_trend": int(mtf.get("h4_trend", 0)),
        "h1_trend": int(mtf.get("h1_trend", 0)),
        "mtf_aligned": int(bool(mtf.get("aligned"))),
        "session_id": _SESSION_ID.get(signal.get("session", "off_hours"), 4),
        "day_of_week": now.weekday(),
        "hour_utc": now.hour,
        "confluence_score": float(signal.get("confluence_score", 0)),
        "rr": float(signal.get("rr", 0)),
        "sl_pips": float(signal.get("sl_pips", 0)),
        "recent_winrate_5": _recent_winrate(5),
        "minutes_to_news": float(minutes_to_news) if minutes_to_news is not None else 9999.0,
    }
    return pd.DataFrame([feats], columns=FEATURES)


def _recent_winrate(n: int) -> float:
    df = query(
        "SELECT pnl_usd FROM trades WHERE status='closed' ORDER BY close_time DESC LIMIT ?",
        [n],
    )
    if df.empty:
        return 0.5
    return float((df["pnl_usd"] > 0).mean())


def build_training_set() -> tuple[pd.DataFrame, pd.Series]:
    """Return (X, y) for training. Joins signals + trades on signal_id."""
    df = query(
        """
        SELECT s.*, t.pnl_usd, t.outcome
        FROM signals s
        JOIN trades  t ON t.signal_id = s.id
        WHERE t.status='closed' AND s.indicator_snapshot IS NOT NULL
        """
    )
    if df.empty:
        return pd.DataFrame(columns=FEATURES), pd.Series(dtype=int)

    rows = []
    for _, r in df.iterrows():
        try:
            snap = pd.json_normalize(eval(r["indicator_snapshot"]) if isinstance(r["indicator_snapshot"], str) else r["indicator_snapshot"]).iloc[0].to_dict()
        except Exception:                                  # noqa: BLE001
            continue
        meta = {}
        try:
            import json as _json
            meta = _json.loads(r.get("meta") or "{}")
        except Exception:                                  # noqa: BLE001
            meta = {}
        mtf = meta.get("mtf", {})
        entry = float(r.get("entry") or 0)
        ema_stack = 1 if (snap.get("ema20", 0) > snap.get("ema50", 0) > snap.get("ema200", 0)) else \
                    -1 if (snap.get("ema20", 0) < snap.get("ema50", 0) < snap.get("ema200", 0)) else 0
        rows.append({
            "rsi": snap.get("rsi", 50),
            "atr_rel": 0,
            "macd_hist": snap.get("macd_hist", 0),
            "stoch_k": snap.get("stoch_k", 50),
            "rel_volume": snap.get("rel_volume", 1.0) or 1.0,
            "ema_stack": ema_stack,
            "h4_trend": int(mtf.get("h4_trend", 0)),
            "h1_trend": int(mtf.get("h1_trend", 0)),
            "mtf_aligned": int(bool(mtf.get("aligned"))),
            "session_id": _SESSION_ID.get(r.get("session", "off_hours"), 4),
            "day_of_week": 0,
            "hour_utc": 0,
            "confluence_score": r.get("confluence_score", 0),
            "rr": r.get("rr", 0),
            "sl_pips": r.get("sl_pips", 0),
            "recent_winrate_5": 0.5,
            "minutes_to_news": 9999.0,
            "_y": 1 if (r.get("pnl_usd") or 0) > 0 else 0,
        })
    full = pd.DataFrame(rows)
    if full.empty:
        return pd.DataFrame(columns=FEATURES), pd.Series(dtype=int)
    return full[FEATURES].fillna(0), full["_y"].astype(int)
