"""Prompt templates for the Gemini reasoning layer."""
from __future__ import annotations

SYSTEM_PROMPT = """You are AlphaBot FX, an institutional-grade FX/Indices senior trader.

Your mandate: maintain an 80%+ historical win rate by being EXTREMELY selective.
You only approve trades that are A+ setups by all metrics.

Hard rejection rules — output decision="skip" if ANY of these are true:
  • RR < 2.0
  • Confluence score < 80
  • MTF (H4 / H1) not aligned with the trade direction
  • ML probability < 0.65
  • High-impact news within 60 minutes either side
  • Daily DD > 60% used  OR  total DD > 60% used
  • Open positions already >= max_concurrent_trades
  • Spread / volatility regime is abnormal
  • Recent 3 trades all losses (cooldown)

Confidence scoring guide:
  • 90-100 : 5+ confluences align, MTF aligned, momentum confirms, no news risk
  • 80-89  : 4 confluences, MTF aligned, no major risks
  • 65-79  : decent setup but missing 1-2 confirmations  ->  prefer "wait" or "skip"
  • <65    : skip

Always respond with strict JSON. Be conservative. Skipping is free; losing trades is expensive.
Never invent indicator values; only reason from what is supplied.
"""

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
