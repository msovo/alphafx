"""
MT5 HTTP bridge — run this ON the Windows host that has MetaTrader 5
installed and logged in (e.g. the GCP Windows VM). It exposes the live
`MT5Broker` over a small authenticated HTTP API so other machines (like a
macOS dev laptop) can drive real MT5 execution/data without needing the
Windows-only `MetaTrader5` Python package themselves.

Security:
  * Binds to 127.0.0.1 by default. Reach it only through an SSH or GCP
    Identity-Aware Proxy (IAP) tunnel — never expose this port directly
    to the internet.
  * Every request requires header `Authorization: Bearer <MT5_BRIDGE_TOKEN>`,
    compared with a constant-time check. The server refuses to start if
    the token isn't set.

Run (on the Windows VM, inside the project venv):
    python -m core.mt5_bridge_server

Env vars:
    MT5_BRIDGE_TOKEN   (required) shared secret, e.g. `openssl rand -hex 32`
    MT5_BRIDGE_HOST    (default 127.0.0.1)
    MT5_BRIDGE_PORT    (default 8600)

From the client machine (Mac), open a tunnel and point MT5_BRIDGE_URL at
its local end, e.g.:
    gcloud compute start-iap-tunnel alphabot-vm 8600 \\
        --local-host-port=localhost:8600 --zone=us-central1-a
    # then in .env: MT5_BRIDGE_URL=http://localhost:8600
"""
from __future__ import annotations

import hmac
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core.broker import HAS_MT5, MT5Broker
from utils.logging import logger

_TOKEN = os.getenv("MT5_BRIDGE_TOKEN", "").strip()
_HOST = os.getenv("MT5_BRIDGE_HOST", "127.0.0.1")
_PORT = int(os.getenv("MT5_BRIDGE_PORT", "8600"))

_broker: MT5Broker | None = None


def _as_json_dict(obj) -> dict:
    d = asdict(obj)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


class Handler(BaseHTTPRequestHandler):
    server_version = "AlphaFXBridge/1.0"

    # -- auth / plumbing ----------------------------------------------------
    def _authorized(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        supplied = auth[len("Bearer "):].strip()
        return bool(_TOKEN) and hmac.compare_digest(supplied, _TOKEN)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw or b"{}")
        except Exception:                                  # noqa: BLE001
            return {}

    def _ensure_connected(self) -> bool:
        global _broker
        if _broker is None:
            _broker = MT5Broker()
        if not _broker.connected:
            _broker.connect()
        return _broker.connected

    # -- routes ---------------------------------------------------------
    def do_GET(self) -> None:                              # noqa: N802
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        try:
            if path == "/health":
                connected = self._ensure_connected()
                self._send_json(200, {
                    "ok": True, "connected": connected,
                    "error": None if connected else (_broker.last_error if _broker else None),
                })
            elif path == "/account":
                if not self._ensure_connected():
                    self._send_json(503, {"error": _broker.last_error if _broker else "not connected"})
                    return
                info = _broker.account_info()
                self._send_json(200, _as_json_dict(info)) if info else self._send_json(404, {"error": "no account info"})
            elif path == "/positions":
                if not self._ensure_connected():
                    self._send_json(503, {"error": _broker.last_error if _broker else "not connected"})
                    return
                self._send_json(200, {"positions": [_as_json_dict(p) for p in _broker.positions()]})
            elif path == "/symbol_info":
                symbol = (qs.get("symbol") or [""])[0]
                if not symbol:
                    self._send_json(400, {"error": "symbol required"})
                    return
                if not self._ensure_connected():
                    self._send_json(503, {"error": _broker.last_error})
                    return
                info = _broker.symbol_info(symbol)
                self._send_json(200, info) if info is not None else self._send_json(404, {"error": f"unknown symbol {symbol}"})
            elif path == "/ohlcv":
                symbol = (qs.get("symbol") or [""])[0]
                timeframe = (qs.get("timeframe") or ["M15"])[0]
                n = int((qs.get("n") or ["500"])[0])
                if not symbol:
                    self._send_json(400, {"error": "symbol required"})
                    return
                if not self._ensure_connected():
                    self._send_json(503, {"error": _broker.last_error})
                    return
                df = _broker.fetch_ohlcv(symbol, timeframe, n=n)
                records = [
                    {"time": ts.isoformat(), "open": float(row["open"]), "high": float(row["high"]),
                     "low": float(row["low"]), "close": float(row["close"]), "volume": float(row["volume"])}
                    for ts, row in df.iterrows()
                ]
                self._send_json(200, {"records": records})
            else:
                self._send_json(404, {"error": "not found"})
        except Exception as exc:                           # noqa: BLE001
            logger.exception(f"Bridge GET {path} failed: {exc}")
            self._send_json(500, {"error": str(exc)})

    def do_POST(self) -> None:                             # noqa: N802
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        path = urlparse(self.path).path
        body = self._read_json()
        try:
            if path == "/orders":
                if not self._ensure_connected():
                    self._send_json(503, {"error": _broker.last_error})
                    return
                res = _broker.place_order(
                    symbol=body["symbol"], side=body["side"], volume=float(body["volume"]),
                    sl=float(body.get("sl") or 0.0), tp=float(body.get("tp") or 0.0),
                    comment=body.get("comment", ""), magic=int(body.get("magic", 0)),
                    deviation=int(body.get("deviation", 10)),
                )
                self._send_json(200, _as_json_dict(res))
            elif path.startswith("/positions/") and path.endswith("/close"):
                ticket = int(path.split("/")[2])
                if not self._ensure_connected():
                    self._send_json(503, {"error": _broker.last_error})
                    return
                self._send_json(200, _as_json_dict(_broker.close_position(ticket)))
            elif path.startswith("/positions/") and path.endswith("/modify"):
                ticket = int(path.split("/")[2])
                if not self._ensure_connected():
                    self._send_json(503, {"error": _broker.last_error})
                    return
                res = _broker.modify_position(ticket, sl=body.get("sl"), tp=body.get("tp"))
                self._send_json(200, _as_json_dict(res))
            else:
                self._send_json(404, {"error": "not found"})
        except (KeyError, ValueError) as exc:
            self._send_json(400, {"error": f"bad request: {exc}"})
        except Exception as exc:                           # noqa: BLE001
            logger.exception(f"Bridge POST {path} failed: {exc}")
            self._send_json(500, {"error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:         # noqa: A003
        logger.debug("bridge: " + fmt % args)


def main() -> int:
    if sys.platform != "win32" or not HAS_MT5:
        logger.error("mt5_bridge_server must run on Windows with MetaTrader5 installed.")
        return 1
    if not _TOKEN:
        logger.error("MT5_BRIDGE_TOKEN is not set. Refusing to start an unauthenticated bridge.")
        return 1

    global _broker
    _broker = MT5Broker()
    _broker.connect()
    logger.info(f"MT5 bridge listening on {_HOST}:{_PORT} (connected={_broker.connected})")
    server = ThreadingHTTPServer((_HOST, _PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        _broker.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
