#!/usr/bin/env python3
"""
Quick MT5 local connection test.
Checks: HAS_MT5, broker mode, account info, symbol ticks, OHLCV.
"""
from core.broker import get_broker, reset_broker, HAS_MT5
from data.feed import get_ohlcv, clear_cache

print('=== MT5 CONNECTION TEST ===')
print('HAS_MT5 import:', HAS_MT5)
reset_broker()
clear_cache()
b = get_broker(force=True)
print('Broker name:', b.name)
print('Broker connected:', getattr(b, 'connected', None))

ai = b.account_info()
print('Account info present:', ai is not None)
if ai:
    print('  Login:', ai.login)
    print('  Server:', ai.server)
    print('  Balance:', ai.balance)
    print('  Equity:', ai.equity)
    print('  Currency:', ai.currency)
else:
    print('  (No account info)')

print()
print('=== SYMBOL & TICK TEST ===')
sym = 'EURUSD'
info = b.symbol_info(sym)
print('Symbol info present:', info is not None)
if info:
    print('  Symbol:', info.get('symbol'))
    print('  Bid:', info.get('bid'))
    print('  Ask:', info.get('ask'))
    print('  Spread:', info.get('spread'))
    print('  Digits:', info.get('digits'))
else:
    print('  (No symbol info)')

print()
print('=== OHLCV TEST ===')
for tf in ['M5','M15','H1']:
    df = get_ohlcv(sym, tf, n=5, refresh=True)
    print(f'{tf}: rows={len(df)}')
    if not df.empty:
        row = df.iloc[-1]
        print(f'  Last candle UTC: {str(df.index[-1])}')
        print(f'  Open={row["open"]:.5f}, High={row["high"]:.5f}, Low={row["low"]:.5f}, Close={row["close"]:.5f}, Vol={row["volume"]:.0f}')
    else:
        print(f'  (Empty)')
