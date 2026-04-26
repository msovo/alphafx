"""
Centralised configuration loader.

Loads in order:
  1. `.env`              — secrets (never commit)
  2. `config.json`       — user-tunable runtime settings
  3. `defaults`          — hard-coded fallbacks

The `Settings` object is a singleton accessible everywhere via `get_settings()`.
Mutating runtime config from the dashboard rewrites `config.json` and
broadcasts a reload to all subscribers.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from loguru import logger

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parents[1]
ENV_FILE: Path = ROOT_DIR / ".env"
CONFIG_FILE: Path = ROOT_DIR / "config.json"
DATA_DIR: Path = ROOT_DIR / "data"
LOG_DIR: Path = ROOT_DIR / "logs"
ML_MODEL_DIR: Path = ROOT_DIR / "ml" / "models"
BACKUP_DIR: Path = ROOT_DIR / "backups"
REPORT_DIR: Path = ROOT_DIR / "reports"

for _d in (DATA_DIR, LOG_DIR, ML_MODEL_DIR, BACKUP_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# .env
# ---------------------------------------------------------------------------
load_dotenv(ENV_FILE)


def env(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key, default)
    if val is None:
        return default
    # Strip inline "# comment" tail and whitespace (defensive for hand-edited .env)
    if "#" in val:
        val = val.split("#", 1)[0]
    val = val.strip().strip('"').strip("'")
    return val if val else default


# ---------------------------------------------------------------------------
# Settings singleton
# ---------------------------------------------------------------------------
class Settings:
    """Thread-safe live-reload settings store.

    Supports per-user override: when `set_active_user(user_id)` is called,
    the singleton swaps to that user's `data/users/<id>/config.json`
    (lazy-imports auth.users to avoid circular dependency).
    """

    _instance: "Settings | None" = None
    _lock = threading.RLock()

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._user_id: int | None = None
        self._config_file: Path = CONFIG_FILE
        self._user_db_path: Path | None = None
        self.reload()

    # -- per-user switching ------------------------------------------------
    def set_active_user(self, user_id: int | None) -> None:
        with self._lock:
            self._user_id = user_id
            if user_id is None:
                self._config_file = CONFIG_FILE
                self._user_db_path = None
            else:
                try:
                    from auth.users import user_config_path, user_db_path
                    self._config_file = user_config_path(user_id)
                    self._user_db_path = user_db_path(user_id)
                except Exception as exc:                   # noqa: BLE001
                    logger.warning(f"set_active_user fallback: {exc}")
                    self._config_file = CONFIG_FILE
                    self._user_db_path = None
        self.reload()

    @property
    def active_user_id(self) -> int | None:
        return self._user_id

    # -- public API --------------------------------------------------------

    def reload(self) -> None:
        with self._lock:
            target = getattr(self, "_config_file", CONFIG_FILE)
            if target.exists():
                self._data = json.loads(target.read_text(encoding="utf-8"))
            else:
                self._data = {}
                logger.warning(f"{target} not found — using empty config")
        for cb in self._subscribers:
            try:
                cb(self._data)
            except Exception as exc:                        # noqa: BLE001
                logger.exception(f"Settings subscriber raised: {exc}")

    def save(self, new_data: dict[str, Any] | None = None) -> None:
        with self._lock:
            if new_data is not None:
                self._data = new_data
            target = getattr(self, "_config_file", CONFIG_FILE)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        self.reload()

    def get(self, dotted_key: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted_key: str, value: Any) -> None:
        with self._lock:
            node = self._data
            parts = dotted_key.split(".")
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = value
            self.save()

    def subscribe(self, cb: Callable[[dict[str, Any]], None]) -> None:
        self._subscribers.append(cb)

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    # -- env shortcuts -----------------------------------------------------

    @property
    def mt5_account(self) -> int | None:
        if self._user_id is not None:
            try:
                from auth.users import get_mt5_credentials
                v = get_mt5_credentials(self._user_id).get("account")
                if v and str(v).isdigit():
                    return int(v)
            except Exception:                              # noqa: BLE001
                pass
        v = env("MT5_ACCOUNT")
        return int(v) if v and v.isdigit() else None

    @property
    def mt5_password(self) -> str | None:
        if self._user_id is not None:
            try:
                from auth.users import get_mt5_credentials
                v = get_mt5_credentials(self._user_id).get("password")
                if v:
                    return v
            except Exception:                              # noqa: BLE001
                pass
        return env("MT5_PASSWORD")

    @property
    def mt5_server(self) -> str | None:
        if self._user_id is not None:
            try:
                from auth.users import get_mt5_credentials
                v = get_mt5_credentials(self._user_id).get("server")
                if v:
                    return v
            except Exception:                              # noqa: BLE001
                pass
        return env("MT5_SERVER")

    @property
    def mt5_path(self) -> str | None:
        if self._user_id is not None:
            try:
                from auth.users import get_mt5_credentials
                v = get_mt5_credentials(self._user_id).get("path")
                if v:
                    return v
            except Exception:                              # noqa: BLE001
                pass
        return env("MT5_PATH")

    @property
    def gemini_api_key(self) -> str | None:
        return env("GEMINI_API_KEY")

    @property
    def gemini_model(self) -> str:
        return env("GEMINI_MODEL", self.get("ai.model", "gemini-2.5-pro")) or "gemini-2.5-pro"

    @property
    def ai_backend(self) -> str:
        """'studio' or 'vertex'."""
        return (env("AI_BACKEND", self.get("ai.backend", "studio")) or "studio").lower()

    @property
    def vertex_project(self) -> str | None:
        return env("VERTEX_PROJECT", self.get("ai.vertex_project"))

    @property
    def vertex_location(self) -> str:
        return env("VERTEX_LOCATION", self.get("ai.vertex_location", "us-central1")) or "us-central1"

    @property
    def telegram_token(self) -> str | None:
        return env("TELEGRAM_BOT_TOKEN")

    @property
    def telegram_chat_id(self) -> str | None:
        return env("TELEGRAM_CHAT_ID")

    @property
    def telegram_owner_chat_id(self) -> str | None:
        return env("TELEGRAM_OWNER_CHAT_ID") or env("TELEGRAM_CHAT_ID")

    @property
    def db_path(self) -> Path:
        # Per-user DB if a user is logged in
        user_db = getattr(self, "_user_db_path", None)
        if user_db is not None:
            return user_db
        return Path(env("DB_PATH", str(DATA_DIR / "alphabot.db")) or str(DATA_DIR / "alphabot.db"))

    @property
    def log_level(self) -> str:
        return env("LOG_LEVEL", "INFO") or "INFO"

    @property
    def app_env(self) -> str:
        return env("APP_ENV", "development") or "development"


def get_settings() -> Settings:
    if Settings._instance is None:
        with Settings._lock:
            if Settings._instance is None:
                Settings._instance = Settings()
    return Settings._instance
