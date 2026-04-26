"""
End-to-end signal pipeline.

`run_signal_scan()` is the heart of the bot:
   data → indicators → MTF → confluence → ML filter → AI reasoning →
   risk gate → execution mode handler → journal → notify.
"""
from __future__ import annotations

import json

from config.settings import get_settings
from core.broker import get_broker
from core.state import get_state
from data.session import detect_session, is_session_active
from utils.helpers import utcnow_iso
from utils.logging import logger


def run_signal_scan() -> list[dict]:
    """Single iteration of the signal scan loop across all enabled pairs.

    Returns a list of summary dicts (one per evaluated pair) so the dashboard
    can show what happened.
    """
    s = get_settings()
    state = get_state()
    results: list[dict] = []

    if state.is_killed:
        logger.warning("Kill-switch active — skipping signal scan")
        return results

    session = detect_session()
    state.update(active_session=session, last_scan=utcnow_iso())

    if not is_session_active(session, s.get("bot.active_sessions", [])):
        logger.debug(f"Session '{session}' not active — skipping scan")
        return results

    # Lazy imports to avoid circular references
    from analysis.signal import build_signal
    from analysis.indicators import compute_indicators
    from analysis.mtf import compute_mtf_alignment
    from ml.model import score_signal
    from ai.gemini import evaluate_signal as ai_evaluate
    from risk.guardian import pre_trade_checks
    from execution.modes import handle_signal
    from journal.logger import log_signal
    from data.feed import get_ohlcv

    broker = get_broker()
    pairs: list[str] = list(s.get("bot.pairs", []))
    primary_tf: str = s.get("bot.primary_timeframe", "M15")
    instruments: dict = s.get("instruments", {})

    for pair in pairs:
        if not instruments.get(pair, {}).get("enabled", True):
            continue
        try:
            df = get_ohlcv(pair, primary_tf, n=300)
            if df is None or df.empty or len(df) < 60:
                logger.debug(f"{pair}: insufficient data")
                results.append({"pair": pair, "stage": "no_data"})
                continue

            df_ind = compute_indicators(df)
            mtf = compute_mtf_alignment(pair)
            signal = build_signal(pair, primary_tf, df_ind, mtf)
            if signal is None:
                results.append({"pair": pair, "stage": "no_setup"})
                continue

            min_conf = float(s.get("strategy.min_confluence_score", 60))
            if signal["confluence_score"] < min_conf:
                signal["filter_stage"] = "confluence"
                log_signal(signal)
                continue

            # ML filter
            ml_threshold = float(s.get("ai.ml_probability_threshold", 0.55))
            ml_prob = score_signal(signal)
            signal["ml_probability"] = ml_prob
            if ml_prob is not None and ml_prob < ml_threshold:
                signal["filter_stage"] = "ml"
                log_signal(signal)
                continue

            # AI reasoning
            ai_resp = ai_evaluate(signal)
            signal.update({
                "ai_decision": ai_resp.get("decision"),
                "ai_confidence": ai_resp.get("confidence"),
                "ai_reason": ai_resp.get("reason"),
                "ai_risk_flag": ai_resp.get("risk_flag"),
            })
            ai_threshold = int(s.get("ai.confidence_threshold", 65))
            if ai_resp.get("decision") != "trade" or int(ai_resp.get("confidence", 0)) < ai_threshold:
                signal["filter_stage"] = "ai"
                log_signal(signal)
                continue

            # External validators (news + web sentiment)
            try:
                from ai.validators import validate_signal
                vok, vreport = validate_signal(signal)
                signal["validators"] = vreport
                if not vok:
                    failed = next((k for k, v in vreport.items()
                                   if isinstance(v, dict) and not v.get("ok")), "validator")
                    signal["filter_stage"] = f"validator:{failed}"
                    log_signal(signal)
                    results.append({"pair": pair, "stage": f"blocked_{failed}",
                                    "report": vreport})
                    continue
            except Exception as exc:                       # noqa: BLE001
                logger.warning(f"validator error on {pair}: {exc}")

            # Risk gate
            risk_ok, risk_reason = pre_trade_checks(signal)
            if not risk_ok:
                signal["filter_stage"] = f"risk:{risk_reason}"
                log_signal(signal)
                continue

            # Execute (mode-aware)
            handle_signal(signal)
            log_signal(signal)
            results.append({"pair": pair, "stage": "executed", "signal": signal})

        except Exception as exc:                           # noqa: BLE001
            logger.exception(f"Pipeline error on {pair}: {exc}")
            results.append({"pair": pair, "stage": "error", "error": str(exc)})

    return results


def manage_open_positions() -> None:
    """Apply breakeven / partial close / trailing rules to open positions."""
    from risk.manager import manage_positions
    try:
        manage_positions()
    except Exception as exc:                               # noqa: BLE001
        logger.exception(f"manage_open_positions failed: {exc}")
