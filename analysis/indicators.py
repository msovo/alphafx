"""
Technical-indicator wrappers built on `pandas-ta`.

`compute_indicators(df)` returns a copy of `df` with the standard
indicator columns appended. All other modules treat this as the
canonical feature set.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta                                 # type: ignore
    HAS_TA = True
except Exception:                                          # noqa: BLE001
    ta = None                                              # type: ignore
    HAS_TA = False


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / length, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / length, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.fillna(50)


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd = ema_fast - ema_slow
    sig = _ema(macd, signal)
    hist = macd - sig
    return macd, sig, hist


def _bbands(series: pd.Series, length: int = 20, mult: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = series.rolling(length).mean()
    std = series.rolling(length).std()
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower


def _stoch(df: pd.DataFrame, k: int = 14, d: int = 3, smooth: int = 3) -> tuple[pd.Series, pd.Series]:
    low_min = df["low"].rolling(k).min()
    high_max = df["high"].rolling(k).max()
    raw_k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    k_line = raw_k.rolling(smooth).mean()
    d_line = k_line.rolling(d).mean()
    return k_line, d_line


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    close = out["close"]

    out["ema20"] = _ema(close, 20)
    out["ema50"] = _ema(close, 50)
    out["ema200"] = _ema(close, 200)
    out["rsi"] = _rsi(close, 14)
    out["atr"] = _atr(out, 14)

    macd, sig, hist = _macd(close)
    out["macd"], out["macd_signal"], out["macd_hist"] = macd, sig, hist

    upper, mid, lower = _bbands(close, 20, 2.0)
    out["bb_upper"], out["bb_mid"], out["bb_lower"] = upper, mid, lower

    k_line, d_line = _stoch(out, 14, 3, 3)
    out["stoch_k"], out["stoch_d"] = k_line, d_line

    vol_avg = out["volume"].rolling(20).mean()
    out["rel_volume"] = out["volume"] / vol_avg.replace(0, np.nan)

    out["trend_short"] = np.where(out["ema20"] > out["ema50"], 1, -1)
    out["trend_long"] = np.where(out["ema50"] > out["ema200"], 1, -1)

    return out
