"""Order placement with retry & instrumentation."""
from __future__ import annotations

import time
from typing import Any

from config.settings import get_settings
from core.broker import OrderResult, get_broker
from core.state import get_state
from journal.db import log_event
from journal.logger import log_trade
from risk.calculator import calc_lot_for_signal
from risk.guardian import increment_daily_trades
from utils.helpers import utcnow_iso
from utils.logging import logger


def execute_signal(signal: dict[str, Any]) -> OrderResult:
    s = get_settings()
    broker = get_broker()
    info = broker.account_info()
    if info is None:
        return OrderResult(False, None, -1, "Broker offline")

    lots = calc_lot_for_signal(signal, info.balance)
    magic = int(s.get("execution.magic_number", 730501))
    comment = f"{s.get('execution.comment_prefix', 'AlphaBot')}#{signal.get('signal_id', 0)}"

    retries = int(s.get("execution.max_retries", 3))
    delay = float(s.get("execution.retry_delay_sec", 2.0))
    last: OrderResult | None = None

    for attempt in range(1, retries + 1):
        result = broker.place_order(
            symbol=signal["pair"], side=signal["direction"], volume=lots,
            sl=signal["sl"], tp=signal["tp"], comment=comment, magic=magic,
            deviation=int(s.get("execution.max_slippage_pips", 3)),
        )
        last = result
        if result.success:
            break
        logger.warning(f"order_send retry {attempt}/{retries}: {result.retcode} {result.comment}")
        time.sleep(delay)

    assert last is not None
    if not last.success:
        log_event("ERROR", "execution", f"Order failed {last.retcode} {last.comment}",
                  {"signal_id": signal.get("signal_id")})
        return last

    state = get_state().state
    trade_row = {
        "signal_id": signal.get("signal_id"),
        "broker_ticket": last.ticket,
        "pair": signal["pair"],
        "direction": signal["direction"],
        "entry_price": last.price or signal["entry"],
        "sl_price": signal["sl"],
        "tp_price": signal["tp"],
        "lots": last.volume or lots,
        "open_time": utcnow_iso(),
        "session": signal.get("session"),
        "day_of_week": __import__("datetime").datetime.utcnow().weekday(),
        "confluence_score": signal.get("confluence_score"),
        "ml_probability": signal.get("ml_probability"),
        "ai_decision": signal.get("ai_decision"),
        "ai_confidence": signal.get("ai_confidence"),
        "ai_reason": signal.get("ai_reason"),
        "balance_at_open": info.balance,
        "daily_dd_at_open": state.daily_dd_pct,
        "total_dd_at_open": state.total_dd_pct,
        "status": "open",
    }
    trade_id = log_trade(trade_row)
    signal["executed"] = 1
    signal["trade_id"] = trade_id
    increment_daily_trades()
    log_event("INFO", "execution", f"Trade opened #{last.ticket} {signal['pair']} {signal['direction']}",
              {"trade_id": trade_id})
    try:
        from notifications.telegram import send_trade_opened
        send_trade_opened(signal, trade_row)
    except Exception:                                      # noqa: BLE001
        pass
    return last
