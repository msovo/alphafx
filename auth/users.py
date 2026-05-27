"""
User accounts — registration, authentication, per-user MT5 credentials,
per-user config and journal database isolation.

Storage: `data/auth.db` (SQLite, separate from the trading journal so it
isn't wiped when users clear their trade history).

Per-user storage layout:
  data/users/<user_id>/config.json     — settings (auto-copied from defaults)
  data/users/<user_id>/alphabot.db     — trade journal
  data/users/<user_id>/state.json      — runtime state
  data/users/<user_id>/logs/           — log files

MT5 credentials are stored in `auth.db.users.mt5_*` columns, encrypted at
rest using the symmetric key in `auth.crypto`.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from auth.crypto import decrypt, encrypt
from config.settings import DATA_DIR, ROOT_DIR
from utils.helpers import utcnow_iso
from utils.logging import logger

AUTH_DB: Path = DATA_DIR / "auth.db"
USERS_DIR: Path = DATA_DIR / "users"
DEFAULT_CONFIG_FILE: Path = ROOT_DIR / "config.json"

USERS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE,
        full_name TEXT,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        active INTEGER NOT NULL DEFAULT 1,
        mt5_account_enc TEXT,
        mt5_password_enc TEXT,
        mt5_server_enc TEXT,
        mt5_path_enc TEXT,
        created_at TEXT NOT NULL,
        last_login TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    """
    CREATE TABLE IF NOT EXISTS auth_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT UNIQUE NOT NULL,
        device_label TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        last_used_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tokens_hash ON auth_tokens(token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_tokens_user ON auth_tokens(user_id)",
]


@contextmanager
def _conn():
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_auth_db() -> None:
    AUTH_DB.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        for stmt in _SCHEMA:
            c.execute(stmt)
    logger.info(f"Auth DB initialised at {AUTH_DB}")


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------
_ITER = 200_000


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    pwd = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITER)
    return pwd.hex(), salt.hex()


def _verify_password(password: str, hex_hash: str, hex_salt: str) -> bool:
    salt = bytes.fromhex(hex_salt)
    expected, _ = _hash_password(password, salt)
    return secrets.compare_digest(expected, hex_hash)


# ---------------------------------------------------------------------------
# User dataclass
# ---------------------------------------------------------------------------
@dataclass
class User:
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    role: str
    active: bool
    created_at: str
    last_login: Optional[str]

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            id=int(row["id"]),
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            role=row["role"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            last_login=row["last_login"],
        )


# ---------------------------------------------------------------------------
# Per-user filesystem
# ---------------------------------------------------------------------------
def user_dir(user_id: int) -> Path:
    p = USERS_DIR / str(user_id)
    p.mkdir(parents=True, exist_ok=True)
    (p / "logs").mkdir(parents=True, exist_ok=True)
    return p


def user_config_path(user_id: int) -> Path:
    p = user_dir(user_id) / "config.json"
    if not p.exists() and DEFAULT_CONFIG_FILE.exists():
        shutil.copy(DEFAULT_CONFIG_FILE, p)
    return p


def user_db_path(user_id: int) -> Path:
    return user_dir(user_id) / "alphabot.db"


def user_state_path(user_id: int) -> Path:
    return user_dir(user_id) / "state.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def register(username: str, password: str, *, email: str | None = None,
             full_name: str | None = None, role: str = "user") -> User:
    init_auth_db()
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("username and password are required")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    pwd_hex, salt_hex = _hash_password(password)
    with _conn() as c:
        try:
            cur = c.execute(
                "INSERT INTO users (username, email, full_name, password_hash, "
                "password_salt, role, active, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (username, (email or None), (full_name or None),
                 pwd_hex, salt_hex, role, utcnow_iso()),
            )
            uid = int(cur.lastrowid)
        except sqlite3.IntegrityError as e:
            raise ValueError(f"username/email already exists: {e}") from e
    # Seed user files
    user_config_path(uid)
    logger.info(f"Registered user '{username}' (id={uid})")
    return get_user(uid)


def authenticate(username: str, password: str) -> Optional[User]:
    init_auth_db()
    username = username.strip().lower()
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
        ).fetchone()
        if not row:
            return None
        if not _verify_password(password, row["password_hash"], row["password_salt"]):
            return None
        c.execute("UPDATE users SET last_login = ? WHERE id = ?",
                  (utcnow_iso(), row["id"]))
    logger.info(f"Login: {username}")
    return User._from_row(row)


def get_user(user_id: int) -> User:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise LookupError(f"user {user_id} not found")
        return User._from_row(row)


def list_users() -> list[User]:
    init_auth_db()
    with _conn() as c:
        rows = c.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [User._from_row(r) for r in rows]


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    if len(new_password) < 8:
        raise ValueError("password must be at least 8 characters")
    with _conn() as c:
        row = c.execute("SELECT password_hash, password_salt FROM users WHERE id = ?",
                        (user_id,)).fetchone()
        if not row or not _verify_password(old_password, row["password_hash"],
                                           row["password_salt"]):
            return False
        pwd_hex, salt_hex = _hash_password(new_password)
        c.execute("UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
                  (pwd_hex, salt_hex, user_id))
    return True


# ---------------------------------------------------------------------------
# MT5 credentials
# ---------------------------------------------------------------------------
def set_mt5_credentials(user_id: int, *, account: str | None,
                        password: str | None, server: str | None,
                        path: str | None) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE users SET mt5_account_enc = ?, mt5_password_enc = ?, "
            "mt5_server_enc = ?, mt5_path_enc = ? WHERE id = ?",
            (encrypt(account), encrypt(password),
             encrypt(server), encrypt(path), user_id),
        )
    logger.info(f"MT5 credentials updated for user {user_id}")


def get_mt5_credentials(user_id: int) -> dict[str, str | None]:
    with _conn() as c:
        row = c.execute(
            "SELECT mt5_account_enc, mt5_password_enc, mt5_server_enc, mt5_path_enc "
            "FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not row:
        return {"account": None, "password": None, "server": None, "path": None}
    return {
        "account": decrypt(row["mt5_account_enc"]),
        "password": decrypt(row["mt5_password_enc"]),
        "server": decrypt(row["mt5_server_enc"]),
        "path": decrypt(row["mt5_path_enc"]),
    }


def has_any_users() -> bool:
    init_auth_db()
    with _conn() as c:
        n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return int(n) > 0


def set_active(user_id: int, active: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET active = ? WHERE id = ?",
                  (1 if active else 0, user_id))
    logger.info(f"User {user_id} active={active}")


def admin_reset_password(user_id: int, new_password: str) -> None:
    if len(new_password) < 8:
        raise ValueError("password must be at least 8 characters")
    pwd_hex, salt_hex = _hash_password(new_password)
    with _conn() as c:
        c.execute("UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
                  (pwd_hex, salt_hex, user_id))


def delete_user(user_id: int, *, wipe_data: bool = False) -> None:
    with _conn() as c:
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    if wipe_data:
        d = USERS_DIR / str(user_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    logger.info(f"User {user_id} deleted (wipe_data={wipe_data})")


# ---------------------------------------------------------------------------
# Persistent device sessions ("Remember me on this device")
# ---------------------------------------------------------------------------
import datetime as _dt

_TOKEN_TTL_DAYS = 30


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session_token(user_id: int, *, device_label: str | None = None,
                         ttl_days: int = _TOKEN_TTL_DAYS) -> str:
    """Create a persistent session token. Returns the *plain* token (only ever
    seen here). Only the SHA-256 hash is stored, so DB compromise can't
    recover the cookie."""
    init_auth_db()
    token = secrets.token_urlsafe(48)
    now = _dt.datetime.utcnow()
    exp = now + _dt.timedelta(days=ttl_days)
    with _conn() as c:
        c.execute(
            "INSERT INTO auth_tokens (user_id, token_hash, device_label, "
            "created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, _hash_token(token),
             (device_label or "")[:120],
             now.isoformat(timespec="seconds") + "Z",
             exp.isoformat(timespec="seconds") + "Z"),
        )
    logger.info(f"Persistent token issued for user {user_id} (ttl={ttl_days}d)")
    return token


def verify_session_token(token: str | None) -> Optional[User]:
    """Validate a token, refresh `last_used_at`, return the user (or None)."""
    if not token:
        return None
    init_auth_db()
    th = _hash_token(token)
    now = _dt.datetime.utcnow()
    with _conn() as c:
        row = c.execute(
            "SELECT t.user_id, t.expires_at FROM auth_tokens t "
            "JOIN users u ON u.id = t.user_id "
            "WHERE t.token_hash = ? AND u.active = 1", (th,)
        ).fetchone()
        if not row:
            return None
        try:
            exp = _dt.datetime.fromisoformat(row["expires_at"].rstrip("Z"))
        except Exception:                                   # noqa: BLE001
            return None
        if exp < now:
            c.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (th,))
            return None
        c.execute(
            "UPDATE auth_tokens SET last_used_at = ? WHERE token_hash = ?",
            (now.isoformat(timespec="seconds") + "Z", th),
        )
        urow = c.execute("SELECT * FROM users WHERE id = ?",
                         (row["user_id"],)).fetchone()
    return User._from_row(urow) if urow else None


def revoke_session_token(token: str | None) -> None:
    if not token:
        return
    with _conn() as c:
        c.execute("DELETE FROM auth_tokens WHERE token_hash = ?",
                  (_hash_token(token),))


def revoke_all_user_tokens(user_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))
    logger.info(f"All persistent tokens revoked for user {user_id}")


def list_user_tokens(user_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, device_label, created_at, expires_at, last_used_at "
            "FROM auth_tokens WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def purge_expired_tokens() -> int:
    now = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        cur = c.execute("DELETE FROM auth_tokens WHERE expires_at < ?", (now,))
    return cur.rowcount or 0
