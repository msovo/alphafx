"""Notification event names — used to gate whether to send."""
EVENTS = (
    "signal_detected",
    "ai_approved",
    "trade_opened",
    "trade_closed",
    "breakeven",
    "partial_close",
    "risk_warning",
    "kill_switch",
    "daily_summary",
    "weekly_report",
    "ml_retrain",
    "api_error",
)
