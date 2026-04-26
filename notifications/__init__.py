"""Notifications package."""
from .telegram import send_alert, send_signal, send_trade_opened, send_trade_closed, send_daily_summary

__all__ = ["send_alert", "send_signal", "send_trade_opened", "send_trade_closed", "send_daily_summary"]
