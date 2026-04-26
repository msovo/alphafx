"""
Open-trade management — breakeven, partial close, trailing stop.
"""
from __future__ import annotations

from config.settings import get_settings
from core.broker import get_broker
from journal.db import log_event
from utils.logging import logger


def _r_distance(p, current_price: float) -> float:
    risk = abs(p.price_open - p.sl) if p.sl else 0.0
    if not risk:
        return 0.0
    progress = (current_price - p.price_open) if p.side == "BUY" else (p.price_open - current_price)
    return progress / risk


def manage_positions() -> None:
    s = get_settings()
    broker = get_broker()
    breakeven_at = float(s.get("risk.breakeven_at_r", 1.0))
    partial_at = float(s.get("risk.partial_close_at_r", 2.0))
    partial_pct = float(s.get("risk.partial_close_pct", 50))
    trail_after = float(s.get("risk.trail_after_r", 2.0))
    atr_mult = float(s.get("risk.atr_sl_multiplier", 1.5))

    for p in broker.positions():
        info = broker.symbol_info(p.symbol)
        if not info:
            continue
        cur = info["bid"] if p.side == "BUY" else info["ask"]
        r = _r_distance(p, cur)

        # Breakeven
        if r >= breakeven_at:
            new_sl = p.price_open
            if (p.side == "BUY" and p.sl < new_sl) or (p.side == "SELL" and p.sl > new_sl):
                res = broker.modify_position(p.ticket, sl=new_sl)
                if res.success:
                    logger.info(f"BE moved {p.symbol} #{p.ticket} → {new_sl}")
                    log_event("INFO", "trade_management", f"BE on #{p.ticket}", {"sl": new_sl})

        # Partial close
        if r >= partial_at and p.volume > 0.02:
            close_vol = round(p.volume * (partial_pct / 100.0), 2)
            if close_vol >= 0.01 and close_vol < p.volume:
                # Place opposite-side market order with same magic & smaller volume
                opposite = "SELL" if p.side == "BUY" else "BUY"
                res = broker.place_order(
                    symbol=p.symbol, side=opposite, volume=close_vol,
                    sl=0, tp=0, comment=f"partial#{p.ticket}",
                    magic=p.magic,
                )
                if res.success:
                    logger.info(f"Partial {partial_pct}% closed on {p.symbol} #{p.ticket}")
                    log_event("INFO", "trade_management", f"Partial #{p.ticket}", {"vol": close_vol})

        # Trailing stop (ATR-based step proxy: 1× SL distance behind price)
        if r >= trail_after:
            trail_dist = abs(p.price_open - p.sl) * 0.5
            if trail_dist > 0:
                new_sl = (cur - trail_dist) if p.side == "BUY" else (cur + trail_dist)
                if (p.side == "BUY" and new_sl > p.sl) or (p.side == "SELL" and new_sl < p.sl):
                    broker.modify_position(p.ticket, sl=new_sl)
                    logger.info(f"Trailed SL on {p.symbol} #{p.ticket} → {new_sl:.5f}")
