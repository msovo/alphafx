#!/usr/bin/env python3
"""Read-only verification of AlphaFX's configured MetaTrader 5 connection."""
from __future__ import annotations

import sys

from config.settings import get_settings
from core.broker import HAS_MT5, MT5Broker, RemoteBroker

__test__ = False  # This is an operator diagnostic, not a pytest module.


def _fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    settings = get_settings()

    print("=== ALPHAFX MT5 DEMO VERIFICATION (READ ONLY) ===")
    print(f"Platform: {sys.platform}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"MetaTrader5 package importable: {HAS_MT5}")
    print(f"MT5 account configured: {settings.mt5_account is not None}")
    print(f"MT5 server: {settings.mt5_server or '(terminal active account)'}")
    print(f"Demo-only safety enabled: {settings.mt5_require_demo}")

    if settings.mt5_bridge_url:
        broker = RemoteBroker()
        print(f"Connection mode: bridge ({settings.mt5_bridge_url})")
    elif HAS_MT5:
        broker = MT5Broker()
        print("Connection mode: local Windows MT5 terminal")
    else:
        return _fail(
            "No live MT5 connection is available. The official MetaTrader5 Python "
            "package requires Windows. Run AlphaFX beside MT5 on Windows, or set "
            "MT5_BRIDGE_URL and MT5_BRIDGE_TOKEN for a Windows bridge."
        )

    if not broker.connect():
        return _fail(broker.last_error or "MT5 connection failed")

    try:
        account = broker.account_info()
        if account is None:
            return _fail("Connected, but account_info() returned no account")

        print("\nAccount")
        print(f"  Login: {account.login}")
        print(f"  Server: {account.server}")
        print(f"  Company: {account.company}")
        print(f"  Type: {account.trade_mode}")
        print(f"  Currency: {account.currency}")
        print(f"  Balance: {account.balance}")
        print(f"  Expert trading allowed: {account.trade_expert}")

        if account.trade_mode != "demo":
            return _fail(
                f"Account type is {account.trade_mode!r}, not 'demo'. "
                "Do not enable automated execution on this account."
            )

        symbol = "EURUSD"
        info = broker.symbol_info(symbol)
        if info is None:
            return _fail(f"{symbol} is unavailable (your broker may use a symbol suffix)")
        print(f"\n{symbol}: bid={info.get('bid')} ask={info.get('ask')} spread={info.get('spread')}")

        candles = broker.fetch_ohlcv(symbol, "M15", n=5)
        if candles.empty:
            return _fail(f"No {symbol} M15 candles returned")
        print(f"M15 candles: {len(candles)} (latest {candles.index[-1]})")
        print("\nPASS: AlphaFX can read the configured MT5 demo account.")
        print("No order was placed or modified by this verification.")
        return 0
    finally:
        broker.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
