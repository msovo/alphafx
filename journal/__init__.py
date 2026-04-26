"""Journal package — DB, logger, analytics."""
from .db import init_db, connect, insert, update, query, fetch_one, snapshot_account, backup_database, log_event
from .logger import log_signal, log_trade, update_trade, log_ai
from .analytics import (
    closed_trades, equity_curve, overall_metrics, by_pair, by_session, generate_weekly_report,
)

__all__ = [
    "init_db", "connect", "insert", "update", "query", "fetch_one",
    "snapshot_account", "backup_database", "log_event",
    "log_signal", "log_trade", "update_trade", "log_ai",
    "closed_trades", "equity_curve", "overall_metrics", "by_pair", "by_session", "generate_weekly_report",
]
