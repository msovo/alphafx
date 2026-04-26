"""
SQLite layer.

Schema versioning + idempotent CRUD helpers used by every other module.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from config.settings import BACKUP_DIR, get_settings
from utils.helpers import utcnow_iso
from utils.logging import logger

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id INTEGER,
        broker_ticket INTEGER,
        pair TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry_price REAL,
        sl_price REAL,
        tp_price REAL,
        lots REAL,
        open_time TEXT,
        close_time TEXT,
        close_price REAL,
        pnl_usd REAL,
        pnl_pips REAL,
        rr_achieved REAL,
        session TEXT,
        day_of_week INTEGER,
        confluence_score REAL,
        ml_probability REAL,
        ai_decision TEXT,
        ai_confidence INTEGER,
        ai_reason TEXT,
        outcome TEXT,
        exit_reason TEXT,
        balance_at_open REAL,
        daily_dd_at_open REAL,
        total_dd_at_open REAL,
        status TEXT DEFAULT 'open'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pair TEXT NOT NULL,
        timeframe TEXT,
        direction TEXT,
        entry REAL,
        sl REAL,
        tp REAL,
        rr REAL,
        sl_pips REAL,
        confluence_score REAL,
        ml_probability REAL,
        ml_filtered INTEGER DEFAULT 0,
        ai_decision TEXT,
        ai_confidence INTEGER,
        ai_reason TEXT,
        ai_risk_flag TEXT,
        executed INTEGER DEFAULT 0,
        filter_stage TEXT,
        session TEXT,
        indicator_snapshot TEXT,
        meta TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id INTEGER,
        timestamp TEXT,
        prompt TEXT,
        response TEXT,
        model TEXT,
        latency_ms INTEGER,
        error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS account_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        balance REAL,
        equity REAL,
        margin REAL,
        free_margin REAL,
        daily_pnl REAL,
        daily_dd REAL,
        total_dd REAL,
        peak_equity REAL,
        open_positions INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ml_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trained_at TEXT,
        model_file TEXT,
        n_samples INTEGER,
        accuracy REAL,
        precision REAL,
        recall REAL,
        f1 REAL,
        feature_importance TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        level TEXT,
        category TEXT,
        message TEXT,
        meta TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        actor TEXT,
        action TEXT NOT NULL,
        target TEXT,
        before TEXT,
        after TEXT,
        meta TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ml_drift (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        feature TEXT NOT NULL,
        baseline_mean REAL,
        baseline_std REAL,
        recent_mean REAL,
        recent_std REAL,
        psi REAL,
        drift_flag INTEGER DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_trades_open ON trades(open_time)",
    "CREATE INDEX IF NOT EXISTS idx_trades_pair ON trades(pair)",
    "CREATE INDEX IF NOT EXISTS idx_account_ts ON account_snapshots(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp)",
]


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------
def _db_path() -> Path:
    p = get_settings().db_path
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connect():
    conn = sqlite3.connect(_db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        for stmt in SCHEMA:
            c.execute(stmt)
    logger.info(f"Database initialised at {_db_path()}")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def insert(table: str, row: dict[str, Any]) -> int:
    cols = ", ".join(row.keys())
    placeholders = ", ".join(["?"] * len(row))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    with connect() as c:
        cur = c.execute(sql, tuple(_serialise(v) for v in row.values()))
        return int(cur.lastrowid or 0)


def update(table: str, row_id: int, fields: dict[str, Any]) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    sql = f"UPDATE {table} SET {sets} WHERE id = ?"
    with connect() as c:
        c.execute(sql, (*[_serialise(v) for v in fields.values()], row_id))


def query(sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
    with connect() as c:
        return pd.read_sql_query(sql, c, params=tuple(params))


def fetch_one(sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    with connect() as c:
        cur = c.execute(sql, tuple(params))
        row = cur.fetchone()
        return dict(row) if row else None


def _serialise(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    return v


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------
def snapshot_account() -> None:
    """Persist a current account snapshot. Called by the scheduler."""
    from core.broker import get_broker
    from core.state import get_state

    broker = get_broker()
    info = broker.account_info()
    if not info:
        return
    state = get_state().state
    insert("account_snapshots", {
        "timestamp": utcnow_iso(),
        "balance": info.balance,
        "equity": info.equity,
        "margin": info.margin,
        "free_margin": info.free_margin,
        "daily_pnl": state.daily_pnl,
        "daily_dd": state.daily_dd_pct,
        "total_dd": state.total_dd_pct,
        "peak_equity": state.peak_equity or info.equity,
        "open_positions": state.open_positions,
    })


def backup_database() -> str | None:
    src = _db_path()
    if not src.exists():
        return None
    dst = BACKUP_DIR / f"alphabot_{utcnow_iso().replace(' ', '_').replace(':', '-')}.db"
    shutil.copy2(src, dst)
    logger.info(f"Database backed up → {dst}")
    return str(dst)


def log_event(level: str, category: str, message: str, meta: dict | None = None) -> None:
    insert("events", {
        "timestamp": utcnow_iso(),
        "level": level,
        "category": category,
        "message": message,
        "meta": meta or {},
    })


def log_audit(action: str, *, actor: str | None = None, target: str | None = None,
              before: Any = None, after: Any = None, meta: dict | None = None) -> None:
    """Append an immutable audit-log row (settings change, manual close, login, etc.)."""
    insert("audit_log", {
        "timestamp": utcnow_iso(),
        "actor": actor or "system",
        "action": action,
        "target": target,
        "before": before,
        "after": after,
        "meta": meta or {},
    })
