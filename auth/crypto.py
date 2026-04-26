"""
Symmetric encryption helper for sensitive per-user data
(MT5 password, API keys, etc.) using Fernet.

The master key is taken from the `APP_SECRET` env var. If absent, a key
is auto-generated and stored at `data/.app_secret` (chmod-protected on
Linux). Treat that file like a database — back it up; if lost, encrypted
fields cannot be recovered.
"""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from config.settings import DATA_DIR, env
from utils.logging import logger

_SECRET_FILE: Path = DATA_DIR / ".app_secret"


def _load_or_create_key() -> bytes:
    val = env("APP_SECRET")
    if val:
        # Derive a 32-byte key from the user-provided secret
        digest = hashlib.sha256(val.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_bytes()
    key = Fernet.generate_key()
    _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SECRET_FILE.write_bytes(key)
    try:
        os.chmod(_SECRET_FILE, 0o600)
    except Exception:                                      # noqa: BLE001
        pass
    logger.warning(
        f"Generated new encryption key at {_SECRET_FILE}. "
        f"Back this file up — losing it makes encrypted MT5 credentials unrecoverable."
    )
    return key


_FERNET = Fernet(_load_or_create_key())


def encrypt(plaintext: str | None) -> str | None:
    if plaintext is None or plaintext == "":
        return None
    return _FERNET.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _FERNET.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        logger.warning("decrypt: invalid token (wrong key or corrupted)")
        return None
