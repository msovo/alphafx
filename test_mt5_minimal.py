#!/usr/bin/env python3
"""
Minimal MT5 diagnostic — does NOT import config or dotenv.
Tests MT5 import, init, login using env vars directly.
"""
import os
import sys

print("=== MINIMAL MT5 DIAGNOSTIC ===")
print(f"Python: {sys.version}")
print(f"Platform: {sys.platform}")
print()

# Try to import MT5
try:
    import MetaTrader5 as mt5
    print("✓ MetaTrader5 imported successfully")
    print(f"  MT5 version: {mt5.__version__ if hasattr(mt5, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"✗ MetaTrader5 import failed: {e}")
    sys.exit(1)

# Check for MT5 environment variables
mt5_account = os.getenv("MT5_ACCOUNT")
mt5_password = os.getenv("MT5_PASSWORD")
mt5_server = os.getenv("MT5_SERVER")
mt5_path = os.getenv("MT5_PATH")

print()
print("Environment variables (from .env or OS):")
print(f"  MT5_ACCOUNT: {'***' if mt5_account else '(not set)'}")
print(f"  MT5_PASSWORD: {'***' if mt5_password else '(not set)'}")
print(f"  MT5_SERVER: {mt5_server or '(not set)'}")
print(f"  MT5_PATH: {mt5_path or '(not set)'}")

# Try MT5 initialize
print()
print("=== MT5 INITIALIZATION ===")
init_kwargs = {}
if mt5_path:
    init_kwargs["path"] = mt5_path
    print(f"  Using custom MT5 path: {mt5_path}")

if not mt5.initialize(**init_kwargs):
    print(f"✗ MT5.initialize() failed: {mt5.last_error()}")
    sys.exit(1)

print("✓ MT5.initialize() succeeded")

# Try login if creds present
if mt5_account and mt5_password and mt5_server:
    print(f"✓ Credentials found, attempting login to {mt5_server}...")
    ok = mt5.login(int(mt5_account), password=mt5_password, server=mt5_server)
    if not ok:
        print(f"✗ mt5.login() failed: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)
    print("✓ MT5 login succeeded")
else:
    print("⚠ No MT5 credentials in environment; skipping login")
    print("  (App will use mock broker with yfinance)")

# Get account info
print()
print("=== ACCOUNT INFO ===")
acc = mt5.account_info()
if acc:
    print(f"✓ Account retrieved:")
    print(f"  Login: {acc.login}")
    print(f"  Name: {acc.name}")
    print(f"  Server: {acc.server}")
    print(f"  Currency: {acc.currency}")
    print(f"  Balance: {acc.balance}")
    print(f"  Equity: {acc.equity}")
    print(f"  Margin: {acc.margin}")
    print(f"  Leverage: {acc.leverage}")
else:
    print("✗ Could not retrieve account info")

# Try EURUSD symbol
print()
print("=== EURUSD TICK INFO ===")
info = mt5.symbol_info("EURUSD")
if info is None:
    print("✗ EURUSD not found; trying to select...")
    ok = mt5.symbol_select("EURUSD", True)
    if ok:
        info = mt5.symbol_info("EURUSD")

if info:
    print(f"✓ EURUSD symbol info:")
    print(f"  Name: {info.name}")
    print(f"  Digits: {info.digits}")
    print(f"  Bid/Ask spread: {info.spread}")
    tick = mt5.symbol_info_tick("EURUSD")
    if tick:
        print(f"✓ Current tick:")
        print(f"  Bid: {tick.bid}")
        print(f"  Ask: {tick.ask}")
        print(f"  Time: {tick.time}")
    else:
        print(f"✗ Could not get tick info")
else:
    print("✗ Could not get EURUSD info even after symbol_select")

# Try OHLCV on M15
print()
print("=== EURUSD M15 OHLCV (last 5 candles) ===")
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M15, 0, 5)
if rates is not None and len(rates) > 0:
    print(f"✓ Got {len(rates)} candles:")
    for i, r in enumerate(rates):
        from datetime import datetime
        ts = datetime.fromtimestamp(r['time'])
        print(f"  [{i}] {ts.isoformat()} O={r['open']:.5f} H={r['high']:.5f} L={r['low']:.5f} C={r['close']:.5f} V={r['tick_volume']}")
else:
    print(f"✗ Could not fetch EURUSD M15 rates: {mt5.last_error()}")

mt5.shutdown()
print()
print("=== SHUTDOWN ===")
print("✓ MT5 session ended")
