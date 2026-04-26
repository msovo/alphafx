"""
Risk Guardian — pre-trade gates, kill-switch, daily counters.
"""
from __future__ import annotations

from datetime import date

from config.settings import get_settings
from core.broker import get_broker
from core.state import get_state
from data.news import is_news_blackout
from journal.db import log_event, query
from utils.helpers import pct, utcnow_iso
from utils.logging import logger


_today: date | None = None
_daily_start_balance: float | None = None
_daily_trades: int = 0


def _today_starts_new() -> bool:
    global _today
    today = date.today()
    if _today != today:
        _today = today
        return True
    return False


def reset_daily_counters() -> None:
    global _daily_start_balance, _daily_trades
    info = get_broker().account_info()
    _daily_start_balance = info.balance if info else None
    _daily_trades = 0
    get_state().update(daily_pnl=0.0, daily_dd_pct=0.0, daily_trades=0)
    logger.info(f"Daily counters reset (start_balance={_daily_start_balance})")


def _ensure_daily_baseline() -> float:
    global _daily_start_balance
    if _daily_start_balance is None or _today_starts_new():
        info = get_broker().account_info()
        _daily_start_balance = info.balance if info else 0.0
    return _daily_start_balance or 0.0


def update_drawdowns() -> tuple[float, float]:
    """Recompute daily/total drawdown % and persist on state."""
    state_store = get_state()
    info = get_broker().account_info()
    if not info:
        return 0.0, 0.0
    base = _ensure_daily_baseline()
    daily_pnl = info.equity - base if base else 0.0
    daily_dd = max(0.0, -daily_pnl / base * 100) if base else 0.0
    peak = max(state_store.state.peak_equity or 0.0, info.equity)
    total_dd = pct(peak - info.equity, peak) if peak else 0.0
    state_store.update(
        peak_equity=peak, daily_pnl=daily_pnl,
        daily_dd_pct=round(daily_dd, 2), total_dd_pct=round(total_dd, 2),
    )
    return daily_dd, total_dd


def _trip_kill_switch(reason: str) -> None:
    state = get_state()
    if state.is_killed:
        return
    state.trigger_kill_switch(reason)
    logger.critical(f"KILL-SWITCH: {reason}")
    log_event("CRITICAL", "kill_switch", reason)
    # Close all positions
    broker = get_broker()
    for p in broker.positions():
        try:
            broker.close_position(p.ticket)
        except Exception as exc:                           # noqa: BLE001
            logger.exception(f"close_position failed for {p.ticket}: {exc}")
    # Notify
    try:
        from notifications.telegram import send_alert
        send_alert(f"🚨 KILL SWITCH: {reason}", level="critical")
    except Exception:                                      # noqa: BLE001
        pass


def evaluate_kill_switches() -> None:
    """Periodic check: trip if DD limits breached."""
    s = get_settings()
    daily_limit = float(s.get("risk.daily_loss_limit_pct", 5.0))
    max_dd = float(s.get("risk.max_drawdown_pct", 10.0))
    warn = float(s.get("risk.kill_switch_warning_pct", 80)) / 100.0

    daily_dd, total_dd = update_drawdowns()

    if daily_dd >= daily_limit:
        _trip_kill_switch(f"Daily loss {daily_dd:.2f}% ≥ limit {daily_limit:.2f}%")
        return
    if total_dd >= max_dd:
        _trip_kill_switch(f"Total DD {total_dd:.2f}% ≥ max {max_dd:.2f}%")
        return
    if daily_dd >= daily_limit * warn:
        logger.warning(f"⚠️ Daily DD at {daily_dd:.2f}% (warn {daily_limit*warn:.2f}%)")
    if total_dd >= max_dd * warn:
        logger.warning(f"⚠️ Total DD at {total_dd:.2f}% (warn {max_dd*warn:.2f}%)")


def pre_trade_checks(signal: dict) -> tuple[bool, str]:
    """Run all hard pre-trade gates. Returns (ok, reason_if_blocked)."""
    s = get_settings()
    state = get_state()

    if state.is_killed:
        return False, "kill_switch"
    if not state.is_running and state.state.mode != "manual_confirm":
        return False, "bot_not_running"

    # Concurrent positions
    open_count = len(get_broker().positions())
    state.update(open_positions=open_count)
    if open_count >= int(s.get("risk.max_concurrent_trades", 3)):
        return False, "max_concurrent_trades"

    # Daily trade count
    today_count = _today_trade_count()
    if today_count >= int(s.get("risk.max_daily_trades", 5)):
        return False, "max_daily_trades"

    # News blackout
    if s.get("prop_firm.news_block_before_min", 30) > 0:
        blocked, ev = is_news_blackout(
            signal["pair"],
            before_min=int(s.get("prop_firm.news_block_before_min", 30)),
            after_min=int(s.get("prop_firm.news_block_after_min", 15)),
        )
        if blocked:
            return False, f"news_blackout:{ev['title'] if ev else ''}"

    # Spread guard
    info = get_broker().symbol_info(signal["pair"])
    if info:
        spread_pips = max(0.0, (info["ask"] - info["bid"]) / max(info["point"], 1e-9) / 10)
        if spread_pips > float(s.get("risk.max_spread_pips", 3.0)):
            return False, f"spread_too_wide:{spread_pips:.1f}"

    # Drawdown gates
    daily_dd, total_dd = update_drawdowns()
    if daily_dd >= float(s.get("risk.daily_loss_limit_pct", 5.0)):
        _trip_kill_switch("Daily DD limit breached at signal time")
        return False, "daily_dd_limit"
    if total_dd >= float(s.get("risk.max_drawdown_pct", 10.0)):
        _trip_kill_switch("Max DD limit breached at signal time")
        return False, "total_dd_limit"

    return True, "ok"


def _today_trade_count() -> int:
    df = query(
        "SELECT COUNT(*) as n FROM trades WHERE substr(open_time,1,10) = ?",
        [utcnow_iso()[:10]],
    )
    return int(df["n"].iloc[0]) if not df.empty else 0


def increment_daily_trades() -> int:
    global _daily_trades
    _daily_trades += 1
    get_state().update(daily_trades=_daily_trades)
    return _daily_trades
