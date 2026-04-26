"""
Telegram notifications.

Uses the synchronous HTTP API directly so it can be called from any
thread (scheduler, dashboard, etc.) without an event-loop dance.

For inline-button approval in `manual_confirm` mode the bot's polling
listener can be added later (Phase 2).
"""
from __future__ import annotations

from typing import Any

import requests

from config.settings import get_settings
from utils.logging import logger

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _enabled() -> bool:
    s = get_settings()
    if not s.get("notifications.telegram_enabled", True):
        return False
    return bool(s.telegram_token and s.telegram_chat_id)


def _post(method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not _enabled():
        return None
    s = get_settings()
    url = API_BASE.format(token=s.telegram_token, method=method)
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            logger.warning(f"Telegram {method} {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as exc:                               # noqa: BLE001
        logger.warning(f"Telegram {method} failed: {exc}")
        return None


def send_alert(text: str, *, level: str = "info") -> None:
    s = get_settings()
    icon = {"info": "ℹ️", "warn": "⚠️", "warning": "⚠️", "critical": "🚨", "success": "✅"}.get(level, "•")
    _post("sendMessage", {
        "chat_id": s.telegram_chat_id,
        "text": f"{icon} {text}",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })


def send_signal(signal: dict, with_buttons: bool = False) -> None:
    s = get_settings()
    if not s.get("notifications.notify_signal_detected", False) and not with_buttons:
        return
    txt = (
        f"<b>📡 Signal — {signal['pair']} {signal['direction']}</b>\n"
        f"Entry: <code>{signal['entry']}</code>\n"
        f"SL:    <code>{signal['sl']}</code>\n"
        f"TP:    <code>{signal['tp']}</code>\n"
        f"R:R:   <b>{signal.get('rr')}</b>\n"
        f"Conflu:{signal.get('confluence_score')}/100  ML:{signal.get('ml_probability')}\n"
        f"AI:    {signal.get('ai_decision')} ({signal.get('ai_confidence')})\n"
        f"Why:   <i>{signal.get('ai_reason') or '—'}</i>"
    )
    payload: dict[str, Any] = {
        "chat_id": s.telegram_chat_id,
        "text": txt,
        "parse_mode": "HTML",
    }
    if with_buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "✅ Take Trade", "callback_data": f"take:{signal.get('signal_id', 0)}"},
                {"text": "🚫 Skip",        "callback_data": f"skip:{signal.get('signal_id', 0)}"},
            ]]
        }
    _post("sendMessage", payload)


def send_trade_opened(signal: dict, trade: dict) -> None:
    if not get_settings().get("notifications.notify_trade_opened", True):
        return
    send_alert(
        f"<b>🟢 Trade opened</b> {signal['pair']} {signal['direction']} "
        f"{trade.get('lots')} lots @ {trade.get('entry_price')}",
        level="success",
    )


def send_trade_closed(trade: dict) -> None:
    if not get_settings().get("notifications.notify_trade_closed", True):
        return
    pnl = trade.get("pnl_usd", 0.0)
    icon = "✅" if pnl > 0 else "❌"
    send_alert(
        f"<b>{icon} Trade closed</b> {trade.get('pair')} "
        f"{trade.get('direction')} P/L: {pnl:.2f} USD ({trade.get('exit_reason')})",
        level="info" if pnl > 0 else "warn",
    )


def send_daily_summary(metrics: dict) -> None:
    if not get_settings().get("notifications.notify_daily_summary", True):
        return
    send_alert(
        "<b>📊 Daily summary</b>\n" +
        "\n".join(f"• {k}: <b>{v}</b>" for k, v in metrics.items()),
        level="info",
    )
