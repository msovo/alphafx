"""
Centralised loguru logger.

All modules import `from utils.logging import logger`.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger as _logger

from config.settings import LOG_DIR, get_settings

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return

    settings = get_settings()
    level = settings.log_level

    _logger.remove()

    _logger.add(
        sys.stdout,
        level=level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> | "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=settings.app_env != "production",
    )

    _logger.add(
        LOG_DIR / "alphabot_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    )

    _logger.add(
        LOG_DIR / "errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="00:00",
        retention="60 days",
        encoding="utf-8",
    )

    _configured = True


_configure()
logger = _logger

__all__ = ["logger"]
