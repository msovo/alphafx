"""Seed the journal DB with demo closed trades for dashboard previews.

Run:  python scripts/seed_demo_trades.py [--count 60]

Generates ~60 days of realistic-looking trades across 6 pairs with mixed
outcomes, sessions, and AI metadata. All times stored as UTC ISO strings.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make repo root importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal.db import init_db, insert, query, connect  # noqa: E402

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US30", "NAS100"]
SESSIONS = ["asia", "london", "new_york", "overlap"]
AI_REASONS_OK = [
    "Strong MTF alignment, EMA stack supports continuation, RSI not extreme.",
    "Pullback to EMA20 in established uptrend, MACD crossover confirms.",
    "Bollinger squeeze breakout with rising volume; structure intact.",
    "Liquidity sweep + reclaim of key support; risk-reward favourable.",
]
AI_REASONS_LOSS = [
    "Trade taken at retest but news caused volatility spike.",
    "Range-bound conditions invalidated breakout assumption.",
    "Stop hunt below pivot before reversal continued.",
]


def _random_trade(d: datetime, idx: int) -> dict:
    pair = random.choice(PAIRS)
    direction = random.choice(["BUY", "SELL"])
    win = random.random() < 0.58  # 58% win rate
    rr = round(random.uniform(1.4, 2.6), 2)

    # Realistic-ish prices per pair
    if pair == "EURUSD":      base, sl_pips = 1.085, random.randint(15, 35)
    elif pair == "GBPUSD":    base, sl_pips = 1.265, random.randint(20, 45)
    elif pair == "USDJPY":    base, sl_pips = 152.0, random.randint(20, 50)
    elif pair == "XAUUSD":    base, sl_pips = 2350.0, random.randint(40, 120)
    elif pair == "US30":      base, sl_pips = 39000.0, random.randint(60, 200)
    else:                     base, sl_pips = 17500.0, random.randint(50, 180)

    entry = round(base + random.uniform(-base * 0.005, base * 0.005), 5)
    if direction == "BUY":
        sl = entry - sl_pips * 0.0001 * (1 if pair not in ("USDJPY",) else 100)
        tp = entry + sl_pips * 0.0001 * rr * (1 if pair not in ("USDJPY",) else 100)
        close_price = tp if win else sl
    else:
        sl = entry + sl_pips * 0.0001 * (1 if pair not in ("USDJPY",) else 100)
        tp = entry - sl_pips * 0.0001 * rr * (1 if pair not in ("USDJPY",) else 100)
        close_price = tp if win else sl

    risk_usd = random.choice([50, 75, 100, 150])  # per trade risk
    pnl = round(risk_usd * (rr if win else -1.0), 2)
    pnl_pips = round(sl_pips * (rr if win else -1.0), 1)

    open_t = d.replace(hour=random.randint(7, 18), minute=random.choice([0, 15, 30, 45]),
                       second=0, microsecond=0)
    close_t = open_t + timedelta(minutes=random.randint(20, 220))
    session = random.choice(SESSIONS)

    return {
        "signal_id": idx + 1,
        "broker_ticket": 1_000_000 + idx,
        "pair": pair,
        "direction": direction,
        "entry_price": entry,
        "sl_price": round(sl, 5),
        "tp_price": round(tp, 5),
        "lots": round(random.uniform(0.05, 0.5), 2),
        "open_time": open_t.strftime("%Y-%m-%d %H:%M:%S"),
        "close_time": close_t.strftime("%Y-%m-%d %H:%M:%S"),
        "close_price": round(close_price, 5),
        "pnl_usd": pnl,
        "pnl_pips": pnl_pips,
        "rr_achieved": rr if win else -1.0,
        "session": session,
        "day_of_week": open_t.weekday(),
        "confluence_score": round(random.uniform(60, 92), 1),
        "ml_probability": round(random.uniform(0.55, 0.92), 3),
        "ai_decision": "trade",
        "ai_confidence": random.randint(65, 92),
        "ai_reason": random.choice(AI_REASONS_OK if win else AI_REASONS_LOSS),
        "outcome": "win" if win else "loss",
        "exit_reason": "tp_hit" if win else "sl_hit",
        "balance_at_open": 10000.0,
        "daily_dd_at_open": round(random.uniform(0, 2.0), 2),
        "total_dd_at_open": round(random.uniform(0, 4.0), 2),
        "status": "closed",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=60,
                        help="Number of trades to generate (default 60)")
    parser.add_argument("--days", type=int, default=45,
                        help="Spread trades across the last N days (default 45)")
    parser.add_argument("--clear", action="store_true",
                        help="Delete existing trades before seeding")
    args = parser.parse_args()

    init_db()
    if args.clear:
        with connect() as c:
            c.execute("DELETE FROM trades")
        print("Cleared existing trades.")

    today = datetime.now(timezone.utc)
    rows: list[dict] = []
    for i in range(args.count):
        days_back = random.randint(0, args.days - 1)
        # Skip weekends
        d = today - timedelta(days=days_back)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        rows.append(_random_trade(d, i))

    cols = list(rows[0].keys())
    for r in rows:
        insert("trades", r)

    total = query("SELECT COUNT(*) AS n, COALESCE(SUM(pnl_usd),0) AS pnl FROM trades WHERE status='closed'")
    n = int(total.iloc[0]["n"])
    pnl = float(total.iloc[0]["pnl"])
    print(f"Inserted {len(rows)} demo trades. Total closed in DB: {n} (cum P/L ${pnl:,.2f})")


if __name__ == "__main__":
    main()
