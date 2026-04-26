"""
Operating-mode dispatcher.

- signal_only   : log + notify, never trade
- manual_confirm: notify with inline buttons (Telegram), wait for tap
- full_auto     : execute immediately
"""
from __future__ import annotations

from typing import Any

from core.state import get_state
from execution.executor import execute_signal
from utils.logging import logger


def handle_signal(signal: dict[str, Any]) -> None:
    mode = get_state().state.mode
    pair = signal.get("pair")
    direction = signal.get("direction")
    logger.info(f"[{mode}] handling signal {pair} {direction} conf={signal.get('confluence_score')}")

    if mode == "signal_only":
        try:
            from notifications.telegram import send_signal
            send_signal(signal, with_buttons=False)
        except Exception:                                  # noqa: BLE001
            pass
        return

    if mode == "manual_confirm":
        try:
            from notifications.telegram import send_signal
            send_signal(signal, with_buttons=True)
        except Exception:                                  # noqa: BLE001
            pass
        return

    if mode == "full_auto":
        execute_signal(signal)
        return

    logger.warning(f"Unknown bot mode: {mode}")
