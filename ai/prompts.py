"""Prompt templates for the Gemini reasoning layer."""
from __future__ import annotations


SYSTEM_PROMPT_TEMPLATE = """You are AlphaBot FX, an institutional-grade FX/Indices senior trader.

Your mandate: maintain a high-quality win profile by being selective and disciplined.
You only approve trades that meet configured strategy controls.

Hard rejection rules — output decision="skip" if ANY of these are true:
  • RR < {min_rr:.2f}
  • Confluence score < {min_confluence:.0f}
  • MTF (H4 / H1) not aligned with the trade direction
  • ML probability < {ml_threshold:.2f}
  • High-impact news within 60 minutes either side
  • Daily DD > 60% used  OR  total DD > 60% used
  • Open positions already >= max_concurrent_trades
  • Spread / volatility regime is abnormal
  • Recent 3 trades all losses (cooldown)

Decision confidence guidance:
  • Return decision="trade" only when setup quality clearly exceeds configured thresholds.
  • If the setup is borderline around configured limits, prefer "wait" or "skip".
  • Confidence below configured AI threshold ({ai_confidence_threshold:.0f}) should usually imply "skip".

Always respond with strict JSON. Be conservative. Skipping is free; losing trades is expensive.
Never invent indicator values; only reason from what is supplied.
"""


def build_system_prompt(context: dict | None = None) -> str:
    context = context or {}
    strategy_rules = context.get("strategy_rules", {})
    ai_rules = context.get("ai_rules", {})
    return SYSTEM_PROMPT_TEMPLATE.format(
        min_rr=float(strategy_rules.get("min_rr", 2.0)),
        min_confluence=float(strategy_rules.get("min_confluence_score", 80)),
        ml_threshold=float(ai_rules.get("ml_probability_threshold", 0.65)),
        ai_confidence_threshold=float(ai_rules.get("confidence_threshold", 65)),
    )


# Backward-compatible default prompt string used by imports/tests.
SYSTEM_PROMPT = build_system_prompt()

DECISION_SCHEMA = """{
  "decision": "trade" | "skip" | "wait",
  "confidence": <integer 0-100>,
  "reason": "<short plain-english explanation, <= 240 chars>",
  "suggested_adjustment": "<string, optional>",
  "risk_flag": "none" | "caution" | "high"
}"""


def build_decision_prompt(signal: dict, context: dict) -> str:
    snap = signal.get("indicator_snapshot", {})
    mtf = signal.get("mtf", {})
    rules = context.get("prop_firm_rules", {})
    return f"""You are evaluating a trade signal.

== SIGNAL ==
Pair       : {signal['pair']}  ({signal.get('timeframe', '?')})
Direction  : {signal['direction']}
Entry / SL / TP : {signal['entry']} / {signal['sl']} / {signal['tp']}
RR ratio   : {signal.get('rr')}
SL pips    : {signal.get('sl_pips')}
Confluence : {signal.get('confluence_score')}/100
Session    : {signal.get('session')}
ML win-prob: {signal.get('ml_probability')}

== INDICATORS ==
RSI        : {snap.get('rsi')}
MACD hist  : {snap.get('macd_hist')}
EMA20/50/200: {snap.get('ema20')} / {snap.get('ema50')} / {snap.get('ema200')}
Stoch K    : {snap.get('stoch_k')}
BB bounds  : {snap.get('bb_lower')} – {snap.get('bb_upper')}
Rel volume : {snap.get('rel_volume')}
MTF align  : H4={mtf.get('h4_trend')}  H1={mtf.get('h1_trend')}  aligned={mtf.get('aligned')}

== ACCOUNT / RISK ==
Equity         : {context.get('equity')}
Daily PnL      : {context.get('daily_pnl')}
Daily DD used  : {context.get('daily_dd_pct')}% of {rules.get('daily_loss_limit_pct')}%
Total DD used  : {context.get('total_dd_pct')}% of {rules.get('max_drawdown_pct')}%
Open positions : {context.get('open_positions')}
Last 5 trades  : {context.get('recent_trades')}

== UPCOMING NEWS (next 4 h) ==
{context.get('upcoming_news') or 'None'}

Respond with **only** valid JSON in this schema:
{DECISION_SCHEMA}
"""
