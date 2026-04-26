"""
Risk math: lot sizing, pip values, R:R helpers.
"""
from __future__ import annotations

from config.settings import get_settings
from utils.helpers import pip_size


def lot_size(account_balance: float, risk_pct: float, sl_pips: float,
             pip_value_usd: float, min_lot: float = 0.01, max_lot: float = 100.0,
             step: float = 0.01) -> float:
    if sl_pips <= 0 or pip_value_usd <= 0:
        return min_lot
    risk_dollars = account_balance * (risk_pct / 100.0)
    raw = risk_dollars / (sl_pips * pip_value_usd)
    raw = max(min_lot, min(max_lot, raw))
    rounded = round(raw / step) * step
    return round(rounded, 2)


def calc_lot_for_signal(signal: dict, account_balance: float) -> float:
    s = get_settings()
    risk_pct = float(s.get("risk.risk_pct_per_trade", 1.0))
    pair = signal["pair"]
    inst = s.get(f"instruments.{pair}", {}) or {}
    pip_value = float(inst.get("pip_value_usd", 10.0))
    max_lot = float(inst.get("max_lot", 5.0))
    return lot_size(
        account_balance=account_balance,
        risk_pct=risk_pct,
        sl_pips=float(signal.get("sl_pips", 20)),
        pip_value_usd=pip_value,
        max_lot=max_lot,
    )


def rr_ratio(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    return reward / risk if risk else 0.0


def price_for_r(entry: float, sl: float, direction: str, r: float) -> float:
    risk = abs(entry - sl)
    return entry + risk * r if direction.upper() == "BUY" else entry - risk * r
