"""
Trading session detection & gating.

Sessions (UTC):
- Asia        : 23:00 → 08:00
- London      : 07:00 → 16:00
- New York    : 12:00 → 21:00
- Overlap     : 12:00 → 16:00 (London/NY)
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Iterable

SESSIONS: dict[str, tuple[time, time]] = {
    "asia":     (time(23, 0), time(8, 0)),     # wraps midnight
    "london":   (time(7, 0),  time(16, 0)),
    "new_york": (time(12, 0), time(21, 0)),
    "overlap":  (time(12, 0), time(16, 0)),
}


def _in_window(now: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= now < end
    return now >= start or now < end                       # wraps midnight


def detect_session(now: datetime | None = None) -> str:
    now = (now or datetime.now(timezone.utc)).timetz()
    if _in_window(now.replace(tzinfo=None), *SESSIONS["overlap"]):
        return "overlap"
    for name in ("london", "new_york", "asia"):
        if _in_window(now.replace(tzinfo=None), *SESSIONS[name]):
            return name
    return "off_hours"


def is_session_active(current: str, allowed: Iterable[str]) -> bool:
    allowed_set = {a.lower() for a in allowed}
    return current.lower() in allowed_set or "all" in allowed_set
