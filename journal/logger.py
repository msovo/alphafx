"""Trade & signal logging helpers."""
from __future__ import annotations

import json
from typing import Any

from journal.db import insert, update
from utils.logging import logger


def log_signal(signal: dict[str, Any]) -> int:
    row = {
        "timestamp": signal.get("timestamp"),
        "pair": signal.get("pair"),
        "timeframe": signal.get("timeframe"),
        "direction": signal.get("direction"),
        "entry": signal.get("entry"),
        "sl": signal.get("sl"),
        "tp": signal.get("tp"),
        "rr": signal.get("rr"),
        "sl_pips": signal.get("sl_pips"),
        "confluence_score": signal.get("confluence_score"),
        "ml_probability": signal.get("ml_probability"),
        "ml_filtered": int(signal.get("filter_stage") == "ml"),
        "ai_decision": signal.get("ai_decision"),
        "ai_confidence": signal.get("ai_confidence"),
        "ai_reason": signal.get("ai_reason"),
        "ai_risk_flag": signal.get("ai_risk_flag"),
        "executed": int(signal.get("executed", 0)),
        "filter_stage": signal.get("filter_stage"),
        "session": signal.get("session"),
        "indicator_snapshot": json.dumps(signal.get("indicator_snapshot") or {}, default=str),
        "meta": json.dumps({
            "structure": signal.get("structure"),
            "patterns": signal.get("patterns"),
            "mtf": signal.get("mtf"),
        }, default=str),
    }
    sid = insert("signals", row)
    signal["signal_id"] = sid
    logger.debug(f"Signal logged id={sid} pair={row['pair']} stage={row['filter_stage']}")
    return sid


def log_trade(trade: dict[str, Any]) -> int:
    tid = insert("trades", trade)
    logger.info(f"Trade logged id={tid} pair={trade.get('pair')} ticket={trade.get('broker_ticket')}")
    return tid


def update_trade(trade_id: int, fields: dict[str, Any]) -> None:
    update("trades", trade_id, fields)


def log_ai(prompt: str, response: str, *, signal_id: int | None = None,
           model: str = "", latency_ms: int = 0, error: str | None = None) -> int:
    from utils.helpers import utcnow_iso
    return insert("ai_log", {
        "signal_id": signal_id, "timestamp": utcnow_iso(),
        "prompt": prompt, "response": response,
        "model": model, "latency_ms": latency_ms, "error": error,
    })
