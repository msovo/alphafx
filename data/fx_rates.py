"""FX rate helpers — currency conversions for localization."""
from __future__ import annotations

import time
from typing import Optional

from utils.logging import logger

_CACHE: dict[str, tuple[float, float]] = {}  # pair -> (rate, ts)
_TTL = 300  # seconds


def get_rate(pair: str = "USDZAR") -> Optional[float]:
    """Fetch latest FX rate via yfinance with a 5-minute cache. Returns None on failure."""
    pair = pair.upper()
    now = time.time()
    if pair in _CACHE:
        rate, ts = _CACHE[pair]
        if now - ts < _TTL:
            return rate
    try:
        import yfinance as yf
        ticker = f"{pair}=X"
        data = yf.Ticker(ticker).history(period="1d", interval="1h")
        if data.empty:
            return None
        rate = float(data["Close"].iloc[-1])
        _CACHE[pair] = (rate, now)
        return rate
    except Exception as exc:                               # noqa: BLE001
        logger.debug(f"FX rate fetch failed for {pair}: {exc}")
        return None


def usd_to_zar(amount_usd: float) -> Optional[float]:
    rate = get_rate("USDZAR")
    if rate is None:
        return None
    return amount_usd * rate


def fmt_zar(amount_usd: float) -> str:
    """Format USD amount as ZAR string, with USD fallback if rate unavailable."""
    zar = usd_to_zar(amount_usd)
    if zar is None:
        return "—"
    return f"R{zar:,.2f}"


def fmt_money(amount_usd: float, *, signed: bool = False) -> str:
    """Format an amount honouring `ui.display_currency` ('ZAR' default, else 'USD').

    Falls back gracefully to USD formatting if ZAR rate is unavailable.
    """
    try:
        from config.settings import get_settings
        cur = (get_settings().get("ui.display_currency", "ZAR") or "ZAR").upper()
    except Exception:                                      # noqa: BLE001
        cur = "ZAR"
    if cur == "ZAR":
        rate = get_rate("USDZAR")
        if rate is not None:
            val = amount_usd * rate
            sign = ("+" if val >= 0 else "") if signed else ""
            return f"{sign}R{val:,.2f}"
    sign = ("+" if amount_usd >= 0 else "") if signed else ""
    return f"{sign}${amount_usd:,.2f}"


def fmt_money_from_account(amount: float, account_currency: str | None, *, signed: bool = False) -> str:
    """Format amount using account currency -> selected UI currency conversion.

    Supported account currencies: USD, ZAR.
    If conversion rate is unavailable, falls back to raw account-currency formatting.
    """
    try:
        from config.settings import get_settings
        target = (get_settings().get("ui.display_currency", "ZAR") or "ZAR").upper()
    except Exception:                                      # noqa: BLE001
        target = "ZAR"
    src = (account_currency or "USD").upper()

    val = float(amount)
    if src != target:
        rate = get_rate("USDZAR")
        if rate is not None and rate > 0:
            if src == "USD" and target == "ZAR":
                val = val * rate
            elif src == "ZAR" and target == "USD":
                val = val / rate

    sign = ("+" if val >= 0 else "") if signed else ""
    symbol = "R" if target == "ZAR" else "$"
    return f"{sign}{symbol}{val:,.2f}"


def display_currency() -> str:
    try:
        from config.settings import get_settings
        return (get_settings().get("ui.display_currency", "ZAR") or "ZAR").upper()
    except Exception:                                      # noqa: BLE001
        return "ZAR"
