"""Common helpers used across the platform."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


# South African Standard Time (no DST, UTC+2)
SAST = timezone(timedelta(hours=2), name="SAST")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().strftime("%Y-%m-%d %H:%M:%S")


def to_sast(dt: datetime) -> datetime:
    """Convert a UTC (or naive-assumed-UTC) datetime to SAST."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAST)


def fmt_sast(dt: datetime, fmt: str = "%H:%M") -> str:
    """Format a UTC datetime in SAST."""
    return to_sast(dt).strftime(fmt)


def now_sast_iso() -> str:
    return datetime.now(SAST).strftime("%Y-%m-%d %H:%M:%S %Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def pct(part: float, whole: float) -> float:
    return (part / whole) * 100.0 if whole else 0.0


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def pip_size(symbol: str, digits: int) -> float:
    """Return the value of one pip in price units."""
    s = symbol.upper()
    if s.endswith("JPY") or "JPY" in s:
        return 0.01
    if s in {"XAUUSD", "GOLD"}:
        return 0.10
    if s in {"US30", "NAS100", "SPX500", "GER40"}:
        return 1.0
    return 0.0001 if digits >= 4 else 0.01


def price_to_pips(symbol: str, digits: int, price_diff: float) -> float:
    p = pip_size(symbol, digits)
    return price_diff / p if p else 0.0
