"""
MetaTrader 5 broker adapter.

Provides a stable, broker-agnostic interface so that the rest of the
platform never imports `MetaTrader5` directly. When the MT5 package is
not available (e.g. on Linux dev machines) the adapter falls back to a
synthetic `MockBroker` driven by `yfinance` so the UI remains usable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import time
from typing import Any

import pandas as pd

from config.settings import get_settings
from utils.logging import logger

# ---------------------------------------------------------------------------
# Optional import of MetaTrader5
# ---------------------------------------------------------------------------
try:
    import MetaTrader5 as mt5                              # type: ignore
    HAS_MT5 = True
except Exception:                                          # noqa: BLE001
    mt5 = None                                             # type: ignore
    HAS_MT5 = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class AccountInfo:
    login: int
    name: str
    server: str
    currency: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: int
    company: str = ""


@dataclass
class Position:
    ticket: int
    symbol: str
    side: str           # BUY / SELL
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    swap: float
    open_time: datetime
    magic: int
    comment: str


@dataclass
class OrderResult:
    success: bool
    ticket: int | None
    retcode: int
    comment: str
    price: float | None = None
    volume: float | None = None


# ---------------------------------------------------------------------------
# Timeframes
# ---------------------------------------------------------------------------
TIMEFRAME_MAP: dict[str, int] = {}
if HAS_MT5:
    TIMEFRAME_MAP = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
    }


# ---------------------------------------------------------------------------
# Broker interface
# ---------------------------------------------------------------------------
class BrokerBase:
    """Abstract broker. Concrete impls: MT5Broker, MockBroker."""
    name: str = "base"
    connected: bool = False
    last_error: str | None = None

    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def account_info(self) -> AccountInfo | None: ...
    def positions(self) -> list[Position]: ...
    def fetch_ohlcv(self, symbol: str, timeframe: str, n: int = 500) -> pd.DataFrame: ...
    def symbol_info(self, symbol: str) -> dict[str, Any] | None: ...
    def place_order(self, *, symbol: str, side: str, volume: float, sl: float, tp: float,
                    comment: str = "", magic: int = 0, deviation: int = 10) -> OrderResult: ...
    def close_position(self, ticket: int) -> OrderResult: ...
    def modify_position(self, ticket: int, sl: float | None = None, tp: float | None = None) -> OrderResult: ...


# ---------------------------------------------------------------------------
# MT5 implementation
# ---------------------------------------------------------------------------
class MT5Broker(BrokerBase):
    name = "mt5"

    @staticmethod
    def _detect_terminal_path() -> str | None:
        """Best-effort discovery of terminal64.exe on Windows hosts."""
        candidates = [
            Path(r"C:\Program Files\MetaTrader 5\terminal64.exe"),
            Path(r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"),
        ]
        for base in (Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")):
            if not base.exists():
                continue
            for pat in ("MetaTrader*\\terminal64.exe", "*MetaTrader*\\terminal64.exe"):
                try:
                    candidates.extend(base.glob(pat))
                except Exception:                          # noqa: BLE001
                    pass
        for p in candidates:
            try:
                if p and p.exists():
                    return str(p)
            except Exception:                              # noqa: BLE001
                continue
        return None

    def connect(self) -> bool:
        if not HAS_MT5:
            self.last_error = "MetaTrader5 package not available"
            logger.warning(self.last_error)
            return False
        s = get_settings()
        kwargs: dict[str, Any] = {}
        explicit_path = (s.mt5_path or "").strip() if s.mt5_path else ""
        detected_path = self._detect_terminal_path() if not explicit_path else None
        if explicit_path:
            kwargs["path"] = explicit_path
        elif detected_path:
            kwargs["path"] = detected_path

        if not mt5.initialize(**kwargs):                   # type: ignore[attr-defined]
            path_note = kwargs.get("path") or "<auto>"
            self.last_error = f"MT5 init failed ({path_note}): {mt5.last_error()}"
            logger.error(self.last_error)
            return False
        if s.mt5_account and s.mt5_password and s.mt5_server:
            ok = mt5.login(s.mt5_account, password=s.mt5_password, server=s.mt5_server)
            if not ok:
                self.last_error = f"MT5 login failed: {mt5.last_error()}"
                logger.error(self.last_error)
                self.disconnect()
                return False
        elif s.mt5_account or s.mt5_server:
            self.last_error = "MT5 credentials incomplete (account/password/server required)"
            logger.error(self.last_error)
            self.disconnect()
            return False
        self.connected = True
        self.last_error = None
        info = mt5.account_info()
        if info:
            logger.success(f"MT5 connected — {info.login} @ {info.server} (balance={info.balance})")
        return True

    def disconnect(self) -> None:
        if HAS_MT5:
            mt5.shutdown()
        self.connected = False

    # -- queries ----------------------------------------------------------

    def account_info(self) -> AccountInfo | None:
        if not self.connected:
            return None
        a = mt5.account_info()
        if not a:
            return None
        return AccountInfo(
            login=a.login, name=a.name, server=a.server, currency=a.currency,
            balance=a.balance, equity=a.equity, margin=a.margin,
            free_margin=a.margin_free, leverage=a.leverage, company=a.company,
        )

    def positions(self) -> list[Position]:
        if not self.connected:
            return []
        out: list[Position] = []
        for p in mt5.positions_get() or []:
            out.append(Position(
                ticket=p.ticket, symbol=p.symbol,
                side="BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                volume=p.volume, price_open=p.price_open, sl=p.sl, tp=p.tp,
                profit=p.profit, swap=p.swap,
                open_time=datetime.fromtimestamp(p.time),
                magic=p.magic, comment=p.comment,
            ))
        return out

    def fetch_ohlcv(self, symbol: str, timeframe: str, n: int = 500) -> pd.DataFrame:
        if not self.connected or timeframe not in TIMEFRAME_MAP:
            return pd.DataFrame()
        tf = TIMEFRAME_MAP[timeframe]
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.set_index("time", inplace=True)
        df.rename(columns={"tick_volume": "volume"}, inplace=True)
        return df[["open", "high", "low", "close", "volume"]]

    def symbol_info(self, symbol: str) -> dict[str, Any] | None:
        if not self.connected:
            return None
        info = mt5.symbol_info(symbol)
        if not info:
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
        if not info:
            return None
        tick = mt5.symbol_info_tick(symbol)
        return {
            "symbol": info.name,
            "digits": info.digits,
            "point": info.point,
            "spread": info.spread,
            "trade_contract_size": info.trade_contract_size,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "bid": tick.bid if tick else 0.0,
            "ask": tick.ask if tick else 0.0,
        }

    # -- trading ----------------------------------------------------------

    def place_order(self, *, symbol: str, side: str, volume: float, sl: float, tp: float,
                    comment: str = "", magic: int = 0, deviation: int = 10) -> OrderResult:
        if not self.connected:
            return OrderResult(False, None, -1, "Not connected")
        info = mt5.symbol_info(symbol)
        if info is None:
            return OrderResult(False, None, -1, f"Unknown symbol {symbol}")
        if not info.visible:
            mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if side.upper() == "BUY" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if side.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "deviation": int(deviation),
            "magic": int(magic),
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        res = mt5.order_send(request)
        if res is None:
            return OrderResult(False, None, -1, f"order_send returned None: {mt5.last_error()}")
        ok = res.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(ok, res.order if ok else None, res.retcode, res.comment, res.price, res.volume)

    def close_position(self, ticket: int) -> OrderResult:
        if not self.connected:
            return OrderResult(False, None, -1, "Not connected")
        positions = [p for p in mt5.positions_get(ticket=ticket) or []]
        if not positions:
            return OrderResult(False, None, -1, "Position not found")
        p = positions[0]
        tick = mt5.symbol_info_tick(p.symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": p.ticket,
            "price": tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "deviation": 10,
            "magic": p.magic,
            "comment": f"close#{p.ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        res = mt5.order_send(request)
        if res is None:
            return OrderResult(False, None, -1, f"order_send returned None: {mt5.last_error()}")
        ok = res.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(ok, res.order if ok else None, res.retcode, res.comment, res.price, res.volume)

    def modify_position(self, ticket: int, sl: float | None = None, tp: float | None = None) -> OrderResult:
        if not self.connected:
            return OrderResult(False, None, -1, "Not connected")
        positions = [p for p in mt5.positions_get(ticket=ticket) or []]
        if not positions:
            return OrderResult(False, None, -1, "Position not found")
        p = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": p.symbol,
            "position": p.ticket,
            "sl": float(sl) if sl is not None else p.sl,
            "tp": float(tp) if tp is not None else p.tp,
        }
        res = mt5.order_send(request)
        if res is None:
            return OrderResult(False, None, -1, f"order_send returned None: {mt5.last_error()}")
        ok = res.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(ok, p.ticket, res.retcode, res.comment)


# ---------------------------------------------------------------------------
# Mock implementation (fallback when MT5 not available)
# ---------------------------------------------------------------------------
class MockBroker(BrokerBase):
    """Synthetic broker for development on non-Windows machines.

    Uses yfinance for OHLCV; orders are simulated in-memory.
    """
    name = "mock"

    _SYMBOL_MAP = {
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
        "AUDUSD": "AUDUSD=X", "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X",
        "XAUUSD": "GC=F",     "US30":   "^DJI",     "NAS100": "^NDX",
        "SPX500": "^GSPC",
    }
    _INTERVAL = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
                 "H1": "60m", "H4": "60m", "D1": "1d"}

    def __init__(self) -> None:
        self._positions: list[Position] = []
        self._next_ticket = 1000000
        self._balance = 10_000.0
        self._equity = 10_000.0
        self.last_error = None

    def connect(self) -> bool:
        self.connected = True
        logger.warning("Using MockBroker — MT5 not available. Trading disabled, charts read from yfinance.")
        return True

    def disconnect(self) -> None:
        self.connected = False

    def account_info(self) -> AccountInfo:
        floating = sum(p.profit for p in self._positions)
        return AccountInfo(
            login=0, name="MockAccount", server="MockServer", currency="USD",
            balance=self._balance, equity=self._balance + floating,
            margin=0.0, free_margin=self._balance + floating,
            leverage=100, company="AlphaBot Mock",
        )

    def positions(self) -> list[Position]:
        return list(self._positions)

    def fetch_ohlcv(self, symbol: str, timeframe: str, n: int = 500) -> pd.DataFrame:
        try:
            import yfinance as yf
        except Exception:                                  # noqa: BLE001
            return pd.DataFrame()
        yf_sym = self._SYMBOL_MAP.get(symbol.upper(), symbol)
        interval = self._INTERVAL.get(timeframe, "15m")
        period = "60d" if interval.endswith("m") else "2y"
        df = yf.download(yf_sym, interval=interval, period=period, progress=False, auto_adjust=False)
        if df.empty:
            return df
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)
        if "volume" not in df.columns:
            df["volume"] = 0
        df = df[["open", "high", "low", "close", "volume"]].tail(n)
        df.index = pd.to_datetime(df.index, utc=True)
        return df

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        df = self.fetch_ohlcv(symbol, "M15", 1)
        last = float(df["close"].iloc[-1]) if not df.empty else 1.0
        digits = 2 if symbol.upper() in {"USDJPY", "XAUUSD"} else 5
        return {
            "symbol": symbol, "digits": digits, "point": 10 ** -digits,
            "spread": 1, "trade_contract_size": 100000,
            "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
            "bid": last, "ask": last + 10 ** -digits,
        }

    def place_order(self, *, symbol: str, side: str, volume: float, sl: float, tp: float,
                    comment: str = "", magic: int = 0, deviation: int = 10) -> OrderResult:
        info = self.symbol_info(symbol)
        price = info["ask"] if side.upper() == "BUY" else info["bid"]
        ticket = self._next_ticket
        self._next_ticket += 1
        self._positions.append(Position(
            ticket=ticket, symbol=symbol, side=side.upper(), volume=volume,
            price_open=price, sl=sl, tp=tp, profit=0.0, swap=0.0,
            open_time=datetime.utcnow(), magic=magic, comment=comment,
        ))
        return OrderResult(True, ticket, 0, "ok (mock)", price, volume)

    def close_position(self, ticket: int) -> OrderResult:
        for i, p in enumerate(self._positions):
            if p.ticket == ticket:
                self._balance += p.profit
                self._positions.pop(i)
                return OrderResult(True, ticket, 0, "ok (mock)")
        return OrderResult(False, None, -1, "Position not found")

    def modify_position(self, ticket: int, sl: float | None = None, tp: float | None = None) -> OrderResult:
        for p in self._positions:
            if p.ticket == ticket:
                if sl is not None:
                    p.sl = sl
                if tp is not None:
                    p.tp = tp
                return OrderResult(True, ticket, 0, "ok (mock)")
        return OrderResult(False, None, -1, "Position not found")


# ---------------------------------------------------------------------------
# Factory / singleton
# ---------------------------------------------------------------------------
_broker: BrokerBase | None = None
_last_mt5_retry_ts: float = 0.0


def get_broker(force: bool = False) -> BrokerBase:
    global _broker
    global _last_mt5_retry_ts

    # If currently mocked, periodically retry MT5 attach automatically.
    if _broker is not None and not force:
        if isinstance(_broker, MockBroker) and HAS_MT5:
            now = time.time()
            if now - _last_mt5_retry_ts >= 30:
                _last_mt5_retry_ts = now
                b_try: BrokerBase = MT5Broker()
                if b_try.connect():
                    _broker = b_try
                    return _broker
                _broker.last_error = getattr(b_try, "last_error", None)
        return _broker
    if HAS_MT5:
        b: BrokerBase = MT5Broker()
        if b.connect():
            _broker = b
            return _broker
        logger.warning("Falling back to MockBroker after MT5 failure.")
    _broker = MockBroker()
    if HAS_MT5:
        _broker.last_error = getattr(locals().get("b", None), "last_error", "MT5 connection failed")
    else:
        _broker.last_error = "MetaTrader5 package unavailable in current environment"
    _broker.connect()
    return _broker


def reset_broker() -> None:
    """Drop cached broker so the next get_broker() rebuilds it
    (e.g. after switching active user / changing MT5 credentials)."""
    global _broker
    try:
        if _broker is not None and hasattr(_broker, "disconnect"):
            _broker.disconnect()
    except Exception:                                      # noqa: BLE001
        pass
    _broker = None
