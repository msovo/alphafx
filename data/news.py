"""
Economic calendar fetcher.

Primary source : Forex Factory weekly JSON (free, no key).
Fallback       : empty list (gracefully disables news filter).

Cached for 1 h. High-impact = 'High' (red folder).
"""
from __future__ import annotations

import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from utils.logging import logger

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_CACHE: dict[str, Any] = {"ts": 0.0, "events": []}
_TTL = 3600


def _normalise(item: dict[str, Any]) -> dict[str, Any] | None:
    try:
        dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
    except Exception:                                      # noqa: BLE001
        return None
    return {
        "title": item.get("title", ""),
        "country": item.get("country", ""),
        "currency": item.get("country", ""),
        "impact": item.get("impact", "Low"),
        "datetime_utc": dt.astimezone(timezone.utc),
        "forecast": item.get("forecast", ""),
        "previous": item.get("previous", ""),
    }


def fetch_calendar(force: bool = False) -> list[dict[str, Any]]:
    now = _time.time()
    if not force and now - _CACHE["ts"] < _TTL and _CACHE["events"]:
        return _CACHE["events"]
    try:
        r = requests.get(FF_URL, timeout=10)
        r.raise_for_status()
        raw = r.json()
        events = [e for e in (_normalise(x) for x in raw) if e]
        _CACHE["ts"] = now
        _CACHE["events"] = events
        logger.info(f"Loaded {len(events)} calendar events")
        return events
    except Exception as exc:                               # noqa: BLE001
        logger.warning(f"Calendar fetch failed: {exc}")
        return _CACHE["events"]


def upcoming_high_impact(within_hours: int = 24, currencies: list[str] | None = None) -> list[dict[str, Any]]:
    events = fetch_calendar()
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=within_hours)
    out = []
    for e in events:
        if e["impact"] != "High":
            continue
        if currencies and e["currency"] not in currencies:
            continue
        if now <= e["datetime_utc"] <= horizon:
            out.append(e)
    return sorted(out, key=lambda x: x["datetime_utc"])


def is_news_blackout(symbol: str, before_min: int = 30, after_min: int = 15) -> tuple[bool, dict | None]:
    """Return (blocked, event) if the pair is within a news blackout window."""
    ccys = _symbol_currencies(symbol)
    events = fetch_calendar()
    now = datetime.now(timezone.utc)
    for e in events:
        if e["impact"] != "High" or e["currency"] not in ccys:
            continue
        delta = (e["datetime_utc"] - now).total_seconds() / 60.0
        if -after_min <= delta <= before_min:
            return True, e
    return False, None


def next_high_impact_event(symbol: str | None = None) -> dict[str, Any] | None:
    events = fetch_calendar()
    now = datetime.now(timezone.utc)
    ccys = _symbol_currencies(symbol) if symbol else None
    for e in sorted(events, key=lambda x: x["datetime_utc"]):
        if e["impact"] != "High" or e["datetime_utc"] < now:
            continue
        if ccys and e["currency"] not in ccys:
            continue
        return e
    return None


def _symbol_currencies(symbol: str) -> set[str]:
    s = symbol.upper()
    out: set[str] = set()
    for ccy in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"):
        if ccy in s:
            out.add(ccy)
    if s in {"XAUUSD", "US30", "NAS100", "SPX500"}:
        out.add("USD")
    return out or {"USD"}
