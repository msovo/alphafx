"""
Market data feed with simple in-memory cache.

`get_ohlcv()` is the single read-path for indicator calculations.
Cache TTL = 1× timeframe. Uses the active broker (MT5 or Mock).
"""
from __future__ import annotations

import time as _time
from threading import RLock

import pandas as pd

from core.broker import get_broker
from utils.logging import logger

_TF_TTL_SEC: dict[str, int] = {
    "M1": 30, "M5": 60, "M15": 120, "M30": 300,
    "H1": 600, "H4": 1800, "D1": 3600,
}

_cache: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}
_lock = RLock()


def get_ohlcv(symbol: str, timeframe: str, n: int = 500, refresh: bool = False) -> pd.DataFrame:
    key = (symbol.upper(), timeframe.upper())
    ttl = _TF_TTL_SEC.get(timeframe.upper(), 300)
    now = _time.time()
    with _lock:
        if not refresh and key in _cache:
            ts, df = _cache[key]
            if now - ts < ttl and len(df) >= n:
                return df.tail(n).copy()
    try:
        broker = get_broker()
        df = broker.fetch_ohlcv(symbol, timeframe, n=max(n, 500))
    except Exception as exc:                               # noqa: BLE001
        logger.exception(f"OHLCV fetch failed {symbol}/{timeframe}: {exc}")
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    with _lock:
        _cache[key] = (now, df)
    return df.tail(n).copy()


def clear_cache() -> None:
    with _lock:
        _cache.clear()
