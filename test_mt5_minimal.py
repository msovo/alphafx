#!/usr/bin/env python3
"""Minimal direct MT5 diagnostic for Windows; loads credentials from .env."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

__test__ = False  # This is an operator diagnostic, not a pytest module.


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")

    print("=== MINIMAL MT5 DIAGNOSTIC ===")
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")

    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        print(f"ERROR: MetaTrader5 import failed: {exc}")
        if sys.platform != "win32":
            print("The official MetaTrader5 Python package is Windows-only.")
        else:
            print("Run: python -m pip install --upgrade MetaTrader5")
        return 1

    print(f"MetaTrader5 version: {getattr(mt5, '__version__', 'unknown')}")
    account = os.getenv("MT5_ACCOUNT", "").strip()
    password = os.getenv("MT5_PASSWORD", "").strip()
    server = os.getenv("MT5_SERVER", "").strip()
    path = os.getenv("MT5_PATH", "").split("#", 1)[0].strip()

    print(f"MT5_ACCOUNT: {'set' if account else 'not set'}")
    print(f"MT5_PASSWORD: {'set' if password else 'not set'}")
    print(f"MT5_SERVER: {server or '(terminal active account)'}")
    print(f"MT5_PATH: {path or '(auto-detect)'}")

    kwargs = {"path": path} if path else {}
    if not mt5.initialize(**kwargs):
        print(f"ERROR: MT5 initialize failed: {mt5.last_error()}")
        return 1

    try:
        supplied = [bool(account), bool(password), bool(server)]
        if any(supplied) and not all(supplied):
            print("ERROR: MT5_ACCOUNT, MT5_PASSWORD, and MT5_SERVER must be set together")
            return 1
        if account and not account.isdigit():
            print("ERROR: MT5_ACCOUNT must contain digits only")
            return 1
        if all(supplied) and not mt5.login(int(account), password=password, server=server):
            print(f"ERROR: MT5 login failed: {mt5.last_error()}")
            return 1

        info = mt5.account_info()
        if info is None:
            print(f"ERROR: account_info failed: {mt5.last_error()}")
            return 1
        modes = {
            getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0): "demo",
            getattr(mt5, "ACCOUNT_TRADE_MODE_CONTEST", 1): "contest",
            getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", 2): "real",
        }
        mode = modes.get(getattr(info, "trade_mode", None), "unknown")
        print(f"Connected account: {info.login} @ {info.server}")
        print(f"Account type: {mode}")
        print(f"Balance/equity: {info.balance} / {info.equity} {info.currency}")
        if mode != "demo":
            print("ERROR: This verifier requires a demo account")
            return 1

        rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M15, 0, 5)
        if rates is None or len(rates) == 0:
            print(f"ERROR: EURUSD candle read failed: {mt5.last_error()}")
            return 1
        print(f"EURUSD M15 candles: {len(rates)}")
        print("PASS: Direct MT5 demo connection is working (no orders placed).")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
